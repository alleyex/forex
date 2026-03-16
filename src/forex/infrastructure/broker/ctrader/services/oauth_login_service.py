"""OAuth login service (browser flow)."""
import threading
from collections.abc import Callable
from dataclasses import dataclass

from forex.config.paths import TOKEN_FILE
from forex.config.runtime import load_config
from forex.config.settings import AppCredentials, OAuthTokens
from forex.infrastructure.broker.base import (
    BaseCallbacks,
    LogHistoryMixin,
    OperationStateMixin,
    build_callbacks,
)
from forex.infrastructure.broker.ctrader.services.message_helpers import format_success
from forex.infrastructure.broker.errors import ErrorCode, error_message
from forex.infrastructure.broker.oauth.callback_server import CallbackServer
from forex.infrastructure.broker.oauth.tokens import TokenExchanger


@dataclass
class OAuthLoginServiceCallbacks(BaseCallbacks):
    """Callbacks for OAuthLoginService."""
    on_oauth_login_success: Callable[[OAuthTokens], None] | None = None


class OAuthLoginService(LogHistoryMixin[OAuthLoginServiceCallbacks], OperationStateMixin):
    """
    Handle the browser-based OAuth authorization-code flow.

    Usage:
        service = OAuthLoginService.create(TOKEN_FILE, "http://127.0.0.1:8765/callback")
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
        self._log_history = []

    @classmethod
    def create(
        cls,
        token_file: str = TOKEN_FILE,
        redirect_uri: str = "http://127.0.0.1:8765/callback",
    ) -> "OAuthLoginService":
        """Factory method that builds a service instance from configuration."""
        credentials = AppCredentials.from_file(token_file)
        return cls(credentials=credentials, redirect_uri=redirect_uri, token_file=token_file)

    def set_callbacks(
        self,
        on_oauth_login_success: Callable[[OAuthTokens], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        """Set callbacks."""
        self._callbacks = build_callbacks(
            OAuthLoginServiceCallbacks,
            on_oauth_login_success=on_oauth_login_success,
            on_error=on_error,
            on_log=on_log,
        )
        self._replay_log_history()

    def connect(self) -> None:
        """Start the OAuth flow on a background thread."""
        if not self._start_operation():
            self._log("⚠️ An OAuth flow is already in progress")
            return
        thread = threading.Thread(target=self._run_flow, daemon=True)
        thread.start()

    def exchange_code(self, code: str) -> OAuthTokens:
        """Exchange an authorization code for tokens and save them."""
        existing_account_id = self._get_existing_account_id()
        tokens = self._token_exchanger.exchange_code(code, existing_account_id)
        tokens.save(self._token_file)
        return tokens

    def _run_flow(self) -> None:
        """Run the complete OAuth flow."""
        try:
            auth_url = self._token_exchanger.build_authorize_url()
            runtime = load_config()
            code = self._callback_server.wait_for_code(
                auth_url,
                timeout_seconds=runtime.oauth_login_timeout,
                on_log=self._log,
            )

            if not code:
                self._log("ℹ️ You can fall back to the manual authorization-code flow")
                self._emit_error(error_message(ErrorCode.TIMEOUT, "OAuth authorization timed out"))
                return

            tokens = self.exchange_code(code)
            self._log(format_success("OAuth token saved"))

            if self._callbacks.on_oauth_login_success:
                self._callbacks.on_oauth_login_success(tokens)
        except Exception as e:
            self._emit_error(error_message(ErrorCode.PROVIDER, "OAuth flow failed", str(e)))
        finally:
            self._end_operation()

    def _get_existing_account_id(self) -> int | None:
        """Try to read the existing account id from the token file."""
        try:
            existing = OAuthTokens.from_file(self._token_file)
            return existing.account_id
        except Exception:
            return None
