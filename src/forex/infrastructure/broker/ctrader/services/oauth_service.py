"""OAuth account authentication service."""
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
    """Callbacks for OAuthService."""
    on_oauth_success: Callable[[OAuthTokens], None] | None = None
    on_status_changed: Callable[[ConnectionStatus], None] | None = None


class OAuthService(CTraderServiceBase[OAuthServiceCallbacks]):
    """
    Handle the OAuth account authentication flow.

    Usage:
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
        """Factory method that builds a service instance from configuration."""
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
        """Return the current token set."""
        return self._tokens

    @property
    def last_authenticated_account_id(self) -> int | None:
        return self._last_authenticated_account_id

    def update_tokens(self, tokens: OAuthTokens) -> None:
        """Update tokens, for example after switching accounts."""
        self._tokens = tokens

    def set_callbacks(
        self,
        on_oauth_success: Callable[[OAuthTokens], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        on_status_changed: Callable[[ConnectionStatus], None] | None = None,
    ) -> None:
        """Set callbacks."""
        self._callbacks = build_callbacks(
            OAuthServiceCallbacks,
            on_oauth_success=on_oauth_success,
            on_error=on_error,
            on_log=on_log,
            on_status_changed=on_status_changed,
        )
        self._replay_log_history()

    def connect(self, timeout_seconds: int | None = None) -> None:
        """Send the account authentication request."""
        if self._status == ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log("ℹ️ Account already authorized; skipping duplicate authentication")
            return
        self._set_status(ConnectionStatus.CONNECTING)
        self._log("🔐 Sending account authentication...")
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
        """Interrupt the account authentication flow."""
        if self._in_progress:
            self._end_operation()
        self._timeout_tracker.cancel()
        self._unbind_handler(self._handle_message)
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._log("🔌 Account connection interrupted")

    def logout(self) -> None:
        """Send an account logout request to the server."""
        account_id = self._tokens.account_id
        if not account_id:
            self._log("⚠️ Missing account ID; skipping account logout")
            return
        try:
            client = self._app_auth_service.get_client()
        except Exception as exc:
            self._log(f"⚠️ Unable to log out the account: {exc}")
            return
        self._logout_requested = True
        request = ProtoOAAccountLogoutReq()
        request.ctidTraderAccountId = int(account_id)
        self._log(f"🚪 Account logout request account_id={int(account_id)}")
        client.send(request)

    def _validate_tokens(self) -> str | None:
        """Validate tokens and return an error message if they are invalid."""
        if not self._tokens.access_token:
            return error_message(ErrorCode.AUTH, "Missing access token")
        if not self._tokens.account_id:
            return error_message(ErrorCode.AUTH, "Missing account ID")
        if self._tokens.is_expired():
            if not self._tokens.refresh_token:
                metrics.inc("ctrader.oauth.refresh.missing")
                return error_message(
                    ErrorCode.AUTH,
                    "Token expired and no refresh token is available",
                )
            try:
                refreshed = refresh_tokens(
                    token_file=self._token_file,
                    refresh_token=self._tokens.refresh_token,
                    existing_account_id=self._tokens.account_id,
                )
                refreshed.save(self._token_file)
                self._tokens = refreshed
                self._log("🔁 OAuth token refreshed automatically")
                metrics.inc("ctrader.oauth.refresh.success")
            except Exception as exc:
                metrics.inc("ctrader.oauth.refresh.failure")
                return error_message(ErrorCode.AUTH, "Token refresh failed", str(exc))
        return None

    def _send_auth_request(self) -> None:
        """Send the authentication request."""
        request = ProtoOAAccountAuthReq()
        request.accessToken = self._tokens.access_token
        request.ctidTraderAccountId = int(self._tokens.account_id)
        self._log(f"🔐 Account auth request account_id={request.ctidTraderAccountId}")
        self._client.send(request)

    def _handle_message(self, client: Client, msg: OAuthMessage) -> bool:
        """Handle the account authentication response."""
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
        """Handle authentication success."""
        self._end_operation()
        self._timeout_tracker.cancel()
        self._set_status(ConnectionStatus.ACCOUNT_AUTHENTICATED)
        try:
            self._last_authenticated_account_id = int(self._tokens.account_id)
        except Exception:
            self._last_authenticated_account_id = None
        self._log(format_success("Account authorized!"))
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
        """Handle authentication errors."""
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
                self._log(
                    "🔁 Token became invalid; "
                    "refreshed automatically and retried authentication"
                )
                metrics.inc("ctrader.oauth.refresh.success")
                self._send_auth_request()
                return
            except Exception as exc:
                metrics.inc("ctrader.oauth.refresh.failure")
                self._log(f"⚠️ Token refresh failed: {exc}")

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
        self._emit_error(error_message(ErrorCode.TIMEOUT, "Account authentication timed out"))
        self._set_status(ConnectionStatus.DISCONNECTED)

    def _retry_auth_request(self, attempt: int) -> None:
        if not self._in_progress:
            return
        self._log(f"⚠️ Account authentication timed out, retry attempt {attempt}")
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
        self._log("⚠️ The account was disconnected by the server; reauthorization is required")
        metrics.inc("ctrader.oauth.disconnect.event")
        if self._logout_requested:
            self._log("✅ Account logout completed")
        self._set_disconnected_with_error("Account connection was interrupted")

    def _on_accounts_token_invalidated(self, msg: OAuthMessage) -> None:
        account_ids = getattr(msg, "ctidTraderAccountIds", None)
        current_id = self._tokens.account_id
        if current_id is None:
            return
        if account_ids and int(current_id) not in {int(a) for a in account_ids}:
            return
        reason = getattr(msg, "reason", "") or "Token became invalid or was revoked"
        self._log(f"⚠️ Account token invalidated: {reason}")
        metrics.inc("ctrader.oauth.token_invalidated.event")
        self._set_disconnected_with_error("Account token is no longer valid", reason)
