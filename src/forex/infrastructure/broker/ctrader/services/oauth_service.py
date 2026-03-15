"""
OAuth 帳戶認證服務
"""
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAAccountLogoutReq,
)

from forex.config.constants import ConnectionStatus, MessageType
from forex.config.paths import TOKEN_FILE
from forex.config.runtime import load_config, retry_policy_from_config
from forex.config.settings import OAuthTokens
from forex.infrastructure.broker.base import BaseCallbacks, build_callbacks
from forex.infrastructure.broker.ctrader.auth.events import (
    ACCOUNT_DISCONNECT_EVENT,
    ACCOUNTS_TOKEN_INVALIDATED_EVENT,
)
from forex.infrastructure.broker.ctrader.auth.policy import is_invalid_token_error
from forex.infrastructure.broker.ctrader.auth.refresh import refresh_tokens
from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from forex.infrastructure.broker.ctrader.services.base import CTraderServiceBase
from forex.infrastructure.broker.ctrader.services.message_helpers import (
    dispatch_payload,
    format_error,
    format_success,
)
from forex.infrastructure.broker.ctrader.services.timeout_tracker import TimeoutTracker
from forex.infrastructure.broker.errors import ErrorCode, error_message
from forex.utils.metrics import metrics


class OAuthMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str


@dataclass
class OAuthServiceCallbacks(BaseCallbacks):
    """OAuthService 的回調函式"""
    on_oauth_success: Callable[[OAuthTokens], None] | None = None
    on_status_changed: Callable[[ConnectionStatus], None] | None = None


class OAuthService(CTraderServiceBase[OAuthServiceCallbacks]):
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
        super().__init__(app_auth_service=app_auth_service, callbacks=OAuthServiceCallbacks())
        self._client = client
        self._tokens = tokens
        self._token_file = token_file
        self._timeout_tracker = TimeoutTracker(self._on_timeout)
        self._last_authenticated_account_id: int | None = None
        self._metrics_started_at: float | None = None
        self._refresh_attempted: bool = False
        self._logout_requested: bool = False

    @classmethod
    def create(
        cls,
        app_auth_service: AppAuthService,
        token_file: str = TOKEN_FILE,
    ) -> "OAuthService":
        """工廠方法：從設定檔建立服務實例"""
        tokens = OAuthTokens.from_file(token_file)
        client = app_auth_service.get_client()
        return cls(
            app_auth_service=app_auth_service,
            client=client,
            tokens=tokens,
            token_file=token_file,
        )

    @property
    def tokens(self) -> OAuthTokens:
        """取得目前的 Token"""
        return self._tokens

    @property
    def last_authenticated_account_id(self) -> int | None:
        return self._last_authenticated_account_id

    def update_tokens(self, tokens: OAuthTokens) -> None:
        """更新 Token（例如切換帳戶後）"""
        self._tokens = tokens

    def set_callbacks(
        self,
        on_oauth_success: Callable[[OAuthTokens], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        on_status_changed: Callable[[ConnectionStatus], None] | None = None,
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

    def connect(self, timeout_seconds: int | None = None) -> None:
        """發送帳戶認證請求"""
        if self._status == ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log("ℹ️ 帳戶已授權，略過重複認證")
            return
        self._set_status(ConnectionStatus.CONNECTING)
        self._log("🔐 正在發送帳戶認證...")
        self._metrics_started_at = time.monotonic()
        self._refresh_attempted = False

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
        self._bind_handler(self._handle_message)
        self._timeout_tracker.start(timeout_seconds or runtime.oauth_timeout)
        self._send_auth_request()

    def disconnect(self) -> None:
        """中斷帳戶認證流程"""
        if self._in_progress:
            self._end_operation()
        self._timeout_tracker.cancel()
        self._unbind_handler(self._handle_message)
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._log("🔌 已中斷帳戶連線")

    def logout(self) -> None:
        """向伺服器送出帳戶登出請求"""
        account_id = self._tokens.account_id
        if not account_id:
            self._log("⚠️ 無帳戶 ID，略過帳戶登出")
            return
        try:
            client = self._app_auth_service.get_client()
        except Exception as exc:
            self._log(f"⚠️ 無法登出帳戶: {exc}")
            return
        self._logout_requested = True
        request = ProtoOAAccountLogoutReq()
        request.ctidTraderAccountId = int(account_id)
        self._log(f"🚪 帳戶登出請求 account_id={int(account_id)}")
        client.send(request)

    def _validate_tokens(self) -> str | None:
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
                refreshed = refresh_tokens(
                    token_file=self._token_file,
                    refresh_token=self._tokens.refresh_token,
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
        if self._in_progress:
            return dispatch_payload(
                msg,
                {
                    MessageType.ACCOUNT_AUTH_RESPONSE: lambda _msg: self._on_auth_success(),
                    MessageType.ERROR_RESPONSE: self._on_auth_error,
                    ACCOUNT_DISCONNECT_EVENT: self._on_account_disconnect,
                    ACCOUNTS_TOKEN_INVALIDATED_EVENT: self._on_accounts_token_invalidated,
                },
            )
        if self._status >= ConnectionStatus.ACCOUNT_AUTHENTICATED:
            return dispatch_payload(
                msg,
                {
                    ACCOUNT_DISCONNECT_EVENT: self._on_account_disconnect,
                    ACCOUNTS_TOKEN_INVALIDATED_EVENT: self._on_accounts_token_invalidated,
                },
            )
        return False

    def _on_auth_success(self) -> None:
        """認證成功處理"""
        self._end_operation()
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

    def _set_disconnected_with_error(self, message: str, detail: str | None = None) -> None:
        self._unbind_handler(self._handle_message)
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._emit_error(error_message(ErrorCode.AUTH, message, detail))

    def _on_auth_error(self, msg: OAuthMessage) -> None:
        """認證錯誤處理"""
        if (
            not self._refresh_attempted
            and is_invalid_token_error(getattr(msg, "errorCode", -1))
            and self._tokens.refresh_token
        ):
            self._refresh_attempted = True
            try:
                refreshed = refresh_tokens(
                    token_file=self._token_file,
                    refresh_token=self._tokens.refresh_token,
                    existing_account_id=self._tokens.account_id,
                )
                refreshed.save(self._token_file)
                self._tokens = refreshed
                self._log("🔁 Token 失效，已自動刷新並重試認證")
                metrics.inc("ctrader.oauth.refresh.success")
                self._send_auth_request()
                return
            except Exception as exc:
                metrics.inc("ctrader.oauth.refresh.failure")
                self._log(f"⚠️ Token 刷新失敗: {exc}")

        self._end_operation()
        self._unbind_handler(self._handle_message)
        self._timeout_tracker.cancel()
        metrics.inc("ctrader.oauth.error")
        self._emit_error(format_error(msg.errorCode, msg.description))
        self._set_status(ConnectionStatus.DISCONNECTED)

    def _on_timeout(self) -> None:
        if not self._in_progress:
            return
        self._end_operation()
        self._unbind_handler(self._handle_message)
        metrics.inc("ctrader.oauth.timeout")
        self._emit_error(error_message(ErrorCode.TIMEOUT, "帳戶認證逾時"))
        self._set_status(ConnectionStatus.DISCONNECTED)

    def _retry_auth_request(self, attempt: int) -> None:
        if not self._in_progress:
            return
        self._log(f"⚠️ 帳戶認證逾時，重試第 {attempt} 次")
        metrics.inc("ctrader.oauth.retry")
        self._send_auth_request()

    def _on_account_disconnect(self, msg: OAuthMessage) -> None:
        account_id = getattr(msg, "ctidTraderAccountId", None)
        if (
            account_id
            and self._tokens.account_id
            and int(account_id) != int(self._tokens.account_id)
        ):
            return
        self._log("⚠️ 帳戶已在伺服器端中斷，請重新授權")
        metrics.inc("ctrader.oauth.disconnect.event")
        if self._logout_requested:
            self._log("✅ 帳戶登出完成")
        self._set_disconnected_with_error("帳戶連線已中斷")

    def _on_accounts_token_invalidated(self, msg: OAuthMessage) -> None:
        account_ids = getattr(msg, "ctidTraderAccountIds", None)
        current_id = self._tokens.account_id
        if current_id is None:
            return
        if account_ids and int(current_id) not in {int(a) for a in account_ids}:
            return
        reason = getattr(msg, "reason", "") or "Token 已失效或被撤銷"
        self._log(f"⚠️ 帳戶 Token 失效: {reason}")
        metrics.inc("ctrader.oauth.token_invalidated.event")
        self._set_disconnected_with_error("帳戶 Token 已失效", reason)
