"""
OAuth 帳戶認證服務
"""
from dataclasses import dataclass
import threading
from typing import Callable, Optional, Protocol, List

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAAccountAuthReq

from broker.base import BaseCallbacks, BaseService, build_callbacks
from broker.services.app_auth_service import AppAuthService
from config.constants import ConnectionStatus, MessageType
from config.settings import OAuthTokens


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
        super().__init__(callbacks=OAuthServiceCallbacks())
        self._app_auth_service = app_auth_service
        self._client = client
        self._tokens = tokens
        self._timeout_timer: Optional[threading.Timer] = None
        self._log_history: List[str] = []

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
        self._callbacks = build_callbacks(
            OAuthServiceCallbacks,
            on_oauth_success=on_oauth_success,
            on_error=on_error,
            on_log=on_log,
            on_status_changed=on_status_changed,
        )
        if self._callbacks.on_log:
            for message in self._log_history:
                self._callbacks.on_log(message)

    def get_log_history(self) -> list[str]:
        return list(self._log_history)

    def _log(self, message: str) -> None:
        self._log_history.append(message)
        super()._log(message)

    def connect(self, timeout_seconds: Optional[int] = None) -> None:
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
        self._start_timeout_timer(timeout_seconds)
        self._send_auth_request()

    def disconnect(self) -> None:
        """中斷帳戶認證流程"""
        if self._in_progress:
            self._end_operation()
        self._cancel_timeout_timer()
        self._app_auth_service.remove_message_handler(self._handle_message)
        if self._status == ConnectionStatus.ACCOUNT_AUTHENTICATED:
            # 帳戶已授權時無法透過此流程解除伺服器端的授權
            self._log("🔌 已停止監聽，但帳戶仍為已授權狀態")
            return
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._log("🔌 已中斷帳戶連線")

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

    def _handle_message(self, client: Client, msg: OAuthMessage) -> bool:
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
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._cancel_timeout_timer()
        self._set_status(ConnectionStatus.ACCOUNT_AUTHENTICATED)
        self._log("✅ 帳戶已授權！")
        if self._callbacks.on_oauth_success:
            self._callbacks.on_oauth_success(self._tokens)

    def _on_auth_error(self, msg: OAuthMessage) -> None:
        """認證錯誤處理"""
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._cancel_timeout_timer()
        self._emit_error(f"錯誤 {msg.errorCode}: {msg.description}")
        self._set_status(ConnectionStatus.DISCONNECTED)

    def _start_timeout_timer(self, timeout_seconds: Optional[int]) -> None:
        if not timeout_seconds:
            return
        self._cancel_timeout_timer()
        self._timeout_timer = threading.Timer(timeout_seconds, self._on_timeout)
        self._timeout_timer.daemon = True
        self._timeout_timer.start()

    def _cancel_timeout_timer(self) -> None:
        if self._timeout_timer:
            self._timeout_timer.cancel()
            self._timeout_timer = None

    def _on_timeout(self) -> None:
        if not self._in_progress:
            return
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._emit_error("帳戶認證逾時")
        self._set_status(ConnectionStatus.DISCONNECTED)
