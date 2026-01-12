"""
OAuth 相關服務
"""
from typing import Callable, Optional
from dataclasses import dataclass
import threading

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAGetAccountListByAccessTokenReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType

from broker.base import BaseService, BaseCallbacks, OperationStateMixin, LoggingMixin
from broker.app_auth import AppAuthService
from broker.oauth.tokens import TokenExchanger
from broker.oauth.callback_server import CallbackServer
from config.constants import ConnectionStatus, MessageType
from config.settings import OAuthTokens, AppCredentials


# ─────────────────────────────────────────────────────────────
# OAuth 帳戶認證服務
# ─────────────────────────────────────────────────────────────

@dataclass
class OAuthServiceCallbacks(BaseCallbacks):
    """OAuthService 的回調函式"""
    on_oauth_success: Optional[Callable[[OAuthTokens], None]] = None
    on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None


class OAuthService(BaseService):
    """
    處理 OAuth 帳戶認證流程
    
    使用方式：
        service = OAuthService.create(app_auth_service, "token.json")
        service.set_callbacks(on_oauth_success=..., on_error=...)
        service.connect()
    """

    def __init__(
        self,
        app_auth_service: AppAuthService,
        client: Client,
        tokens: OAuthTokens,
    ):
        super().__init__()
        self._app_auth_service = app_auth_service
        self._client = client
        self._tokens = tokens
        self._callbacks = OAuthServiceCallbacks()

    @classmethod
    def create(cls, app_auth_service: AppAuthService, token_file: str) -> "OAuthService":
        """工廠方法：從設定檔建立服務實例"""
        tokens = OAuthTokens.from_file(token_file)
        client = app_auth_service.get_client()
        return cls(app_auth_service=app_auth_service, client=client, tokens=tokens)

    @property
    def tokens(self) -> OAuthTokens:
        """取得目前的 Token"""
        return self._tokens

    def set_callbacks(
        self,
        on_oauth_success: Optional[Callable[[OAuthTokens], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None,
    ) -> None:
        """設定回調函式"""
        self._callbacks = OAuthServiceCallbacks(
            on_oauth_success=on_oauth_success,
            on_error=on_error,
            on_log=on_log,
            on_status_changed=on_status_changed,
        )

    def connect(self) -> None:
        """發送帳戶認證請求"""
        self._set_status(ConnectionStatus.CONNECTING)
        self._log("🔐 正在發送帳戶認證...")

        if error := self._validate_tokens():
            self._emit_error(error)
            self._set_status(ConnectionStatus.DISCONNECTED)
            return

        if not self._start_operation():
            return
            
        self._app_auth_service.add_message_handler(self._handle_message)
        self._send_auth_request()

    def _validate_tokens(self) -> Optional[str]:
        """驗證 Token，若無效則回傳錯誤訊息"""
        if not self._tokens.access_token:
            return "缺少存取權杖"
        if not self._tokens.account_id:
            return "缺少帳戶 ID"
        return None

    def _send_auth_request(self) -> None:
        """發送認證請求"""
        request = ProtoOAAccountAuthReq()
        request.accessToken = self._tokens.access_token
        request.ctidTraderAccountId = int(self._tokens.account_id)
        self._client.send(request)

    def _handle_message(self, client: Client, msg) -> bool:
        """處理帳戶認證回應"""
        if not self._in_progress:
            return False

        msg_type = msg.payloadType
        
        if msg_type == MessageType.ACCOUNT_AUTH_RESPONSE:
            self._on_auth_success()
            return True

        if msg_type == MessageType.ERROR_RESPONSE:
            self._on_auth_error(msg)
            return True

        return False

    def _on_auth_success(self) -> None:
        """認證成功處理"""
        self._end_operation()
        self._set_status(ConnectionStatus.ACCOUNT_AUTHENTICATED)
        self._log("✅ 帳戶已授權！")
        if self._callbacks.on_oauth_success:
            self._callbacks.on_oauth_success(self._tokens)

    def _on_auth_error(self, msg) -> None:
        """認證錯誤處理"""
        self._end_operation()
        self._emit_error(f"錯誤 {msg.errorCode}: {msg.description}")
        self._set_status(ConnectionStatus.DISCONNECTED)


# ─────────────────────────────────────────────────────────────
# OAuth 登入服務（瀏覽器流程）
# ─────────────────────────────────────────────────────────────

@dataclass
class OAuthLoginServiceCallbacks(BaseCallbacks):
    """OAuthLoginService 的回調函式"""
    on_oauth_login_success: Optional[Callable[[OAuthTokens], None]] = None


class OAuthLoginService(LoggingMixin, OperationStateMixin):
    """
    處理瀏覽器式 OAuth 授權碼流程
    
    使用方式：
        service = OAuthLoginService.create("token.json", "http://127.0.0.1:8765/callback")
        service.set_callbacks(on_oauth_login_success=..., on_error=...)
        service.connect()
    """

    def __init__(
        self,
        credentials: AppCredentials,
        redirect_uri: str,
        token_file: str,
    ):
        self._token_file = token_file
        self._token_exchanger = TokenExchanger(credentials, redirect_uri)
        self._callback_server = CallbackServer(redirect_uri)
        self._callbacks = OAuthLoginServiceCallbacks()
        self._in_progress = False

    @classmethod
    def create(cls, token_file: str, redirect_uri: str) -> "OAuthLoginService":
        """工廠方法：從設定檔建立服務實例"""
        credentials = AppCredentials.from_file(token_file)
        return cls(credentials=credentials, redirect_uri=redirect_uri, token_file=token_file)

    def set_callbacks(
        self,
        on_oauth_login_success: Optional[Callable[[OAuthTokens], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        """設定回調函式"""
        self._callbacks = OAuthLoginServiceCallbacks(
            on_oauth_login_success=on_oauth_login_success,
            on_error=on_error,
            on_log=on_log,
        )

    def connect(self) -> None:
        """在背景執行緒中啟動 OAuth 流程"""
        thread = threading.Thread(target=self._run_flow, daemon=True)
        thread.start()

    def exchange_code(self, code: str) -> OAuthTokens:
        """將授權碼交換為 Token 並儲存"""
        existing_account_id = self._get_existing_account_id()
        tokens = self._token_exchanger.exchange_code(code, existing_account_id)
        tokens.save(self._token_file)
        return tokens

    def _run_flow(self) -> None:
        """執行完整的 OAuth 流程"""
        try:
            auth_url = self._token_exchanger.build_authorize_url()
            code = self._callback_server.wait_for_code(
                auth_url, 
                timeout_seconds=300,
                on_log=self._log
            )
            
            if not code:
                self._emit_error("OAuth 授權逾時")
                return

            tokens = self.exchange_code(code)
            self._log("✅ OAuth Token 已儲存")

            if self._callbacks.on_oauth_login_success:
                self._callbacks.on_oauth_login_success(tokens)
        except Exception as e:
            self._emit_error(str(e))

    def _get_existing_account_id(self) -> Optional[int]:
        """嘗試從 Token 檔案取得現有帳戶 ID"""
        try:
            existing = OAuthTokens.from_file(self._token_file)
            return existing.account_id
        except Exception:
            return None


# ─────────────────────────────────────────────────────────────
# 帳戶列表服務
# ─────────────────────────────────────────────────────────────

@dataclass
class AccountListServiceCallbacks(BaseCallbacks):
    """AccountListService 的回調函式"""
    on_accounts_received: Optional[Callable[[list], None]] = None


class AccountListService(LoggingMixin, OperationStateMixin):
    """
    透過存取權杖取得帳戶列表
    
    使用方式：
        service = AccountListService(app_auth_service, access_token)
        service.set_callbacks(on_accounts_received=..., on_error=...)
        service.fetch()
    """

    def __init__(self, app_auth_service: AppAuthService, access_token: str):
        self._app_auth_service = app_auth_service
        self._access_token = access_token
        self._callbacks = AccountListServiceCallbacks()
        self._in_progress = False

    def set_callbacks(
        self,
        on_accounts_received: Optional[Callable[[list], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        """設定回調函式"""
        self._callbacks = AccountListServiceCallbacks(
            on_accounts_received=on_accounts_received,
            on_error=on_error,
            on_log=on_log,
        )

    def fetch(self) -> None:
        """取得帳戶列表"""
        if not self._access_token:
            self._emit_error("缺少存取權杖")
            return

        if not self._start_operation():
            return
            
        self._app_auth_service.add_message_handler(self._handle_message)
        self._send_request()

    def _send_request(self) -> None:
        """發送帳戶列表請求"""
        request = ProtoOAGetAccountListByAccessTokenReq()
        request.accessToken = self._access_token
        self._log("📥 正在取得帳戶列表...")
        self._app_auth_service.get_client().send(request)

    def _handle_message(self, client: Client, msg) -> bool:
        """處理帳戶列表回應"""
        if not self._in_progress:
            return False

        if msg.payloadType == ProtoOAPayloadType.PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES:
            self._on_accounts_received(msg)
            return True

        if msg.payloadType == ProtoOAPayloadType.PROTO_OA_ERROR_RES:
            self._on_error(msg)
            return True

        return False

    def _on_accounts_received(self, msg) -> None:
        """帳戶列表接收成功"""
        self._end_operation()
        accounts = self._parse_accounts(msg.ctidTraderAccount)
        self._log(f"✅ 已接收帳戶: {len(accounts)} 個")
        if self._callbacks.on_accounts_received:
            self._callbacks.on_accounts_received(accounts)

    def _on_error(self, msg) -> None:
        """帳戶列表接收失敗"""
        self._end_operation()
        self._emit_error(f"錯誤 {msg.errorCode}: {msg.description}")

    @staticmethod
    def _parse_accounts(raw_accounts) -> list:
        """解析原始帳戶資料"""
        return [
            {
                "account_id": int(account.ctidTraderAccountId),
                "is_live": bool(account.isLive),
                "trader_login": int(account.traderLogin) if account.traderLogin else None,
            }
            for account in raw_accounts
        ]