"""
OAuth 帳戶認證服務
"""
from dataclasses import dataclass
import time
from typing import Callable, Optional, Protocol

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAAccountAuthReq

from infrastructure.broker.base import BaseCallbacks, BaseService, build_callbacks
from infrastructure.broker.errors import ErrorCode, error_message
from infrastructure.broker.oauth.tokens import TokenExchanger
from infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from infrastructure.broker.ctrader.services.message_helpers import (
    dispatch_payload,
    format_error,
    format_success,
)
from infrastructure.broker.ctrader.services.timeout_tracker import TimeoutTracker
from config.constants import ConnectionStatus, MessageType
from config.paths import TOKEN_FILE
from config.runtime import load_config, retry_policy_from_config
from config.settings import OAuthTokens
from utils.metrics import metrics


class OAuthMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str


@dataclass
class OAuthServiceCallbacks(BaseCallbacks):
    """OAuthService 的回調函式"""
    on_oauth_success: Optional[Callable[[OAuthTokens], None]] = None
    on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None


class OAuthService(BaseService[OAuthServiceCallbacks]):
    """
    處理 OAuth 帳戶認證流程

    使用方式：
        service = OAuthService.create(app_auth_service, TOKEN_FILE)
        service.set_callbacks(on_oauth_success=..., on_error=...)
        service.connect()
    """

    def __init__(
        self,
        app_auth_service: AppAuthService,
        client: Client,
        tokens: OAuthTokens,
        token_file: str,
    ):
        super().__init__(callbacks=OAuthServiceCallbacks())
        self._app_auth_service = app_auth_service
        self._client = client
        self._tokens = tokens
        self._token_file = token_file
        self._timeout_tracker = TimeoutTracker(self._on_timeout)
        self._last_authenticated_account_id: Optional[int] = None
        self._metrics_started_at: Optional[float] = None

    @classmethod
    def create(cls, app_auth_service: AppAuthService, token_file: str = TOKEN_FILE) -> "OAuthService":
        """工廠方法：從設定檔建立服務實例"""
        tokens = OAuthTokens.from_file(token_file)
        client = app_auth_service.get_client()
        return cls(app_auth_service=app_auth_service, client=client, tokens=tokens, token_file=token_file)

    @property
    def tokens(self) -> OAuthTokens:
        """取得目前的 Token"""
        return self._tokens

    @property
    def last_authenticated_account_id(self) -> Optional[int]:
        return self._last_authenticated_account_id

    def update_tokens(self, tokens: OAuthTokens) -> None:
        """更新 Token（例如切換帳戶後）"""
        self._tokens = tokens

    def set_callbacks(
        self,
        on_oauth_success: Optional[Callable[[OAuthTokens], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None,
    ) -> None:
        """設定回調函式"""
        self._callbacks = build_callbacks(
            OAuthServiceCallbacks,
            on_oauth_success=on_oauth_success,
            on_error=on_error,
            on_log=on_log,
            on_status_changed=on_status_changed,
        )
        self._replay_log_history()

    def connect(self, timeout_seconds: Optional[int] = None) -> None:
        """發送帳戶認證請求"""
        if self._status == ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log("ℹ️ 帳戶已授權，略過重複認證")
            return
        self._set_status(ConnectionStatus.CONNECTING)
        self._log("🔐 正在發送帳戶認證...")
        self._metrics_started_at = time.monotonic()

        if error := self._validate_tokens():
            self._emit_error(error)
            self._set_status(ConnectionStatus.DISCONNECTED)
            return

        if not self._start_operation():
            return

        try:
            self._client = self._app_auth_service.get_client()
        except Exception as exc:
            self._emit_error(str(exc))
            self._set_status(ConnectionStatus.DISCONNECTED)
            self._end_operation()
            return

        runtime = load_config()
        self._timeout_tracker.configure_retry(
            retry_policy_from_config(runtime),
            self._retry_auth_request,
        )
        self._app_auth_service.add_message_handler(self._handle_message)
        self._timeout_tracker.start(timeout_seconds or runtime.oauth_timeout)
        self._send_auth_request()

    def disconnect(self) -> None:
        """中斷帳戶認證流程"""
        if self._in_progress:
            self._end_operation()
        self._timeout_tracker.cancel()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._log("🔌 已中斷帳戶連線")

    def _validate_tokens(self) -> Optional[str]:
        """驗證 Token，若無效則回傳錯誤訊息"""
        if not self._tokens.access_token:
            return error_message(ErrorCode.AUTH, "缺少存取權杖")
        if not self._tokens.account_id:
            return error_message(ErrorCode.AUTH, "缺少帳戶 ID")
        if self._tokens.is_expired():
            if not self._tokens.refresh_token:
                metrics.inc("ctrader.oauth.refresh.missing")
                return error_message(ErrorCode.AUTH, "Token 已過期，且缺少 refresh token")
            try:
                exchanger = TokenExchanger(self._app_auth_service.get_credentials())
                refreshed = exchanger.refresh_tokens(
                    self._tokens.refresh_token,
                    existing_account_id=self._tokens.account_id,
                )
                refreshed.save(self._token_file)
                self._tokens = refreshed
                self._log("🔁 已自動刷新 OAuth Token")
                metrics.inc("ctrader.oauth.refresh.success")
            except Exception as exc:
                metrics.inc("ctrader.oauth.refresh.failure")
                return error_message(ErrorCode.AUTH, "Token 刷新失敗", str(exc))
        return None

    def _send_auth_request(self) -> None:
        """發送認證請求"""
        request = ProtoOAAccountAuthReq()
        request.accessToken = self._tokens.access_token
        request.ctidTraderAccountId = int(self._tokens.account_id)
        self._log(f"🔐 Account auth request account_id={request.ctidTraderAccountId}")
        self._client.send(request)

    def _handle_message(self, client: Client, msg: OAuthMessage) -> bool:
        """處理帳戶認證回應"""
        if not self._in_progress:
            return False
        return dispatch_payload(
            msg,
            {
                MessageType.ACCOUNT_AUTH_RESPONSE: lambda _msg: self._on_auth_success(),
                MessageType.ERROR_RESPONSE: self._on_auth_error,
            },
        )

    def _on_auth_success(self) -> None:
        """認證成功處理"""
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._timeout_tracker.cancel()
        self._set_status(ConnectionStatus.ACCOUNT_AUTHENTICATED)
        try:
            self._last_authenticated_account_id = int(self._tokens.account_id)
        except Exception:
            self._last_authenticated_account_id = None
        self._log(format_success("帳戶已授權！"))
        metrics.inc("ctrader.oauth.success")
        if self._metrics_started_at is not None:
            metrics.observe("ctrader.oauth.latency_s", time.monotonic() - self._metrics_started_at)
        if self._callbacks.on_oauth_success:
            self._callbacks.on_oauth_success(self._tokens)

    def _on_auth_error(self, msg: OAuthMessage) -> None:
        """認證錯誤處理"""
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._timeout_tracker.cancel()
        metrics.inc("ctrader.oauth.error")
        self._emit_error(format_error(msg.errorCode, msg.description))
        self._set_status(ConnectionStatus.DISCONNECTED)

    def _on_timeout(self) -> None:
        if not self._in_progress:
            return
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        metrics.inc("ctrader.oauth.timeout")
        self._emit_error(error_message(ErrorCode.TIMEOUT, "帳戶認證逾時"))
        self._set_status(ConnectionStatus.DISCONNECTED)

    def _retry_auth_request(self, attempt: int) -> None:
        if not self._in_progress:
            return
        self._log(f"⚠️ 帳戶認證逾時，重試第 {attempt} 次")
        metrics.inc("ctrader.oauth.retry")
        self._send_auth_request()
