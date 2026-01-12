from typing import Callable, Optional, Protocol, Tuple
from dataclasses import dataclass
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAGetAccountListByAccessTokenReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType

from broker.app_auth import AppAuthService
from config.constants import ConnectionStatus, MessageType
from config.settings import OAuthTokens, AppCredentials


class OAuthCallbacks(Protocol):
    """Protocol defining expected callbacks"""
    def on_oauth_success(self, tokens: OAuthTokens) -> None: ...
    def on_error(self, error: str) -> None: ...
    def on_log(self, message: str) -> None: ...
    def on_status_changed(self, status: ConnectionStatus) -> None: ...


@dataclass
class OAuthServiceCallbacks:
    """Callback container with defaults"""
    on_oauth_success: Optional[Callable[[OAuthTokens], None]] = None
    on_error: Optional[Callable[[str], None]] = None
    on_log: Optional[Callable[[str], None]] = None
    on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None


class OAuthService:
    """
    Handles OAuth account authentication workflow.

    Usage:
        service = OAuthService.create(app_auth_service, "token.json")
        service.set_callbacks(callbacks)
        service.connect()
    """

    def __init__(
        self,
        app_auth_service: AppAuthService,
        client: Client,
        tokens: OAuthTokens,
    ):
        self._app_auth_service = app_auth_service
        self._tokens = tokens
        self._status = ConnectionStatus.DISCONNECTED
        self._callbacks = OAuthServiceCallbacks()
        self._client = client
        self._auth_in_progress = False

    @classmethod
    def create(cls, app_auth_service: AppAuthService, token_file: str) -> "OAuthService":
        """Factory method to create service with configuration"""
        tokens = OAuthTokens.from_file(token_file)
        client = app_auth_service.get_client()
        return cls(
            app_auth_service=app_auth_service,
            client=client,
            tokens=tokens,
        )

    @property
    def status(self) -> ConnectionStatus:
        return self._status

    @property
    def tokens(self) -> OAuthTokens:
        return self._tokens

    def set_callbacks(
        self,
        on_oauth_success: Optional[Callable[[OAuthTokens], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None,
    ) -> None:
        """Set callback functions for various events"""
        self._callbacks = OAuthServiceCallbacks(
            on_oauth_success=on_oauth_success,
            on_error=on_error,
            on_log=on_log,
            on_status_changed=on_status_changed,
        )

    def connect(self) -> None:
        """Send account authentication request"""
        self._set_status(ConnectionStatus.CONNECTING)
        self._log("🔐 Sending Account Auth...")

        if not self._tokens.access_token:
            self._emit_error("Missing access token.")
            self._set_status(ConnectionStatus.DISCONNECTED)
            return
        if not self._tokens.account_id:
            self._emit_error("Missing account_id.")
            self._set_status(ConnectionStatus.DISCONNECTED)
            return

        self._auth_in_progress = True
        self._app_auth_service.add_message_handler(self._handle_message)

        request = ProtoOAAccountAuthReq()
        request.accessToken = self._tokens.access_token
        request.ctidTraderAccountId = int(self._tokens.account_id)
        self._client.send(request)

    # ─────────────────────────────────────────────────────────────
    # Private Methods
    # ─────────────────────────────────────────────────────────────

    def _set_status(self, status: ConnectionStatus) -> None:
        """Update status and notify callback"""
        self._status = status
        if self._callbacks.on_status_changed:
            self._callbacks.on_status_changed(status)

    def _log(self, message: str) -> None:
        """Log message through callback or print"""
        if self._callbacks.on_log:
            self._callbacks.on_log(message)
        else:
            print(message)

    def _emit_error(self, error: str) -> None:
        """Emit error through callback"""
        self._log(f"❌ {error}")
        if self._callbacks.on_error:
            self._callbacks.on_error(error)

    def _handle_message(self, client: Client, msg) -> bool:
        """Handle account auth responses and errors"""
        if not self._auth_in_progress:
            return False

        msg_type = msg.payloadType
        if msg_type == MessageType.ACCOUNT_AUTH_RESPONSE:
            self._auth_in_progress = False
            self._set_status(ConnectionStatus.ACCOUNT_AUTHENTICATED)
            self._log("✅ Account Authorized!")
            if self._callbacks.on_oauth_success:
                self._callbacks.on_oauth_success(self._tokens)
            return True

        if msg_type == MessageType.ERROR_RESPONSE:
            self._auth_in_progress = False
            error_msg = f"Error {msg.errorCode}: {msg.description}"
            self._emit_error(error_msg)
            self._set_status(ConnectionStatus.DISCONNECTED)
            return True

        return False


class OAuthLoginCallbacks(Protocol):
    """Protocol defining expected callbacks"""
    def on_oauth_login_success(self, tokens: OAuthTokens) -> None: ...
    def on_error(self, error: str) -> None: ...
    def on_log(self, message: str) -> None: ...


@dataclass
class OAuthLoginServiceCallbacks:
    """Callback container with defaults"""
    on_oauth_login_success: Optional[Callable[[OAuthTokens], None]] = None
    on_error: Optional[Callable[[str], None]] = None
    on_log: Optional[Callable[[str], None]] = None


class OAuthLoginService:
    """Handles browser-based OAuth authorization code flow."""

    def __init__(
        self,
        credentials: AppCredentials,
        redirect_uri: str,
        token_file: str,
    ):
        self._credentials = credentials
        self._redirect_uri = redirect_uri
        self._token_file = token_file
        self._callbacks = OAuthLoginServiceCallbacks()

    @classmethod
    def create(cls, token_file: str, redirect_uri: str) -> "OAuthLoginService":
        credentials = AppCredentials.from_file(token_file)
        return cls(
            credentials=credentials,
            redirect_uri=redirect_uri,
            token_file=token_file,
        )

    def set_callbacks(
        self,
        on_oauth_login_success: Optional[Callable[[OAuthTokens], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._callbacks = OAuthLoginServiceCallbacks(
            on_oauth_login_success=on_oauth_login_success,
            on_error=on_error,
            on_log=on_log,
        )

    def connect(self) -> None:
        thread = threading.Thread(target=self._run_flow, daemon=True)
        thread.start()

    def exchange_code(self, code: str) -> OAuthTokens:
        """Exchange authorization code for tokens and persist them."""
        tokens = self._exchange_code_for_token(code)
        tokens.save(self._token_file)
        return tokens

    # ─────────────────────────────────────────────────────────────
    # Internal workflow
    # ─────────────────────────────────────────────────────────────

    def _run_flow(self) -> None:
        try:
            auth_url = self._build_authorize_url()
            code = self._wait_for_code(auth_url, timeout_seconds=300)
            if not code:
                self._emit_error("OAuth authorization timed out.")
                return

            tokens = self.exchange_code(code)
            self._log("✅ OAuth tokens saved.")

            if self._callbacks.on_oauth_login_success:
                self._callbacks.on_oauth_login_success(tokens)
        except Exception as e:
            self._emit_error(str(e))

    def _build_authorize_url(self) -> str:
        base_url = "https://openapi.ctrader.com/apps/auth"
        params = {
            "client_id": self._credentials.client_id,
            "redirect_uri": self._redirect_uri,
            "scope": "trading",
        }
        return f"{base_url}?{urllib.parse.urlencode(params)}"

    def _exchange_code_for_token(self, code: str) -> OAuthTokens:
        token_url = "https://openapi.ctrader.com/apps/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self._credentials.client_id,
            "client_secret": self._credentials.client_secret,
            "code": code,
            "redirect_uri": self._redirect_uri,
        }
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(token_url, data=encoded, method="POST")

        with urllib.request.urlopen(req, timeout=15) as response:
            payload = response.read().decode("utf-8")
        parsed = self._safe_json_loads(payload)

        if "error" in parsed:
            raise RuntimeError(parsed.get("error_description") or parsed["error"])

        access_token = parsed.get("access_token", "")
        refresh_token = parsed.get("refresh_token", "")
        expires_in = parsed.get("expires_in")
        expires_at = None
        if isinstance(expires_in, int):
            expires_at = int(time.time()) + expires_in

        try:
            existing = OAuthTokens.from_file(self._token_file)
            account_id = existing.account_id
        except Exception:
            account_id = None

        return OAuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            account_id=account_id,
        )

    def _wait_for_code(self, auth_url: str, timeout_seconds: int) -> Optional[str]:
        host, port, path = self._parse_redirect_uri()

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)
                self.server.code = params.get("code", [None])[0]
                self.server.request_path = parsed.path
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"Authorization received. You can close this window."
                )

            def log_message(self, format, *args):
                return

        server = HTTPServer((host, port), _Handler)
        server.code = None
        server.request_path = None
        server.timeout = 1

        self._log(f"🌐 Opening browser for OAuth...")
        webbrowser.open(auth_url)

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            server.handle_request()
            if server.code:
                if path and server.request_path and server.request_path != path:
                    continue
                return server.code
        return None

    def _parse_redirect_uri(self) -> Tuple[str, int, str]:
        parsed = urllib.parse.urlparse(self._redirect_uri)
        host = parsed.hostname
        port = parsed.port
        path = parsed.path or "/"

        if not host or not port:
            raise ValueError("Invalid redirect URI. Host and port are required.")
        return host, port, path

    def _safe_json_loads(self, payload: str) -> dict:
        try:
            import json
            return json.loads(payload)
        except Exception as e:
            raise RuntimeError(f"Invalid token response: {e}")

    def _log(self, message: str) -> None:
        if self._callbacks.on_log:
            self._callbacks.on_log(message)
        else:
            print(message)

    def _emit_error(self, error: str) -> None:
        self._log(f"❌ {error}")
        if self._callbacks.on_error:
            self._callbacks.on_error(error)


class AccountListCallbacks(Protocol):
    """Protocol defining expected callbacks"""
    def on_accounts_received(self, accounts) -> None: ...
    def on_error(self, error: str) -> None: ...
    def on_log(self, message: str) -> None: ...


@dataclass
class AccountListServiceCallbacks:
    """Callback container with defaults"""
    on_accounts_received: Optional[Callable[[list], None]] = None
    on_error: Optional[Callable[[str], None]] = None
    on_log: Optional[Callable[[str], None]] = None


class AccountListService:
    """Fetch account list by access token."""

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
        self._callbacks = AccountListServiceCallbacks(
            on_accounts_received=on_accounts_received,
            on_error=on_error,
            on_log=on_log,
        )

    def fetch(self) -> None:
        if not self._access_token:
            self._emit_error("Missing access token.")
            return

        self._in_progress = True
        self._app_auth_service.add_message_handler(self._handle_message)

        request = ProtoOAGetAccountListByAccessTokenReq()
        request.accessToken = self._access_token
        self._log("📥 Fetching account list...")
        self._app_auth_service.get_client().send(request)

    def _handle_message(self, client: Client, msg) -> bool:
        if not self._in_progress:
            return False

        if msg.payloadType == ProtoOAPayloadType.PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES:
            self._in_progress = False
            accounts = []
            for account in msg.ctidTraderAccount:
                accounts.append({
                    "account_id": int(account.ctidTraderAccountId),
                    "is_live": bool(account.isLive),
                    "trader_login": int(account.traderLogin) if account.traderLogin else None,
                })
            self._log(f"✅ Accounts received: {len(accounts)}")
            if self._callbacks.on_accounts_received:
                self._callbacks.on_accounts_received(accounts)
            return True

        if msg.payloadType == ProtoOAPayloadType.PROTO_OA_ERROR_RES:
            self._in_progress = False
            error_msg = f"Error {msg.errorCode}: {msg.description}"
            self._emit_error(error_msg)
            return True

        return False

    def _log(self, message: str) -> None:
        if self._callbacks.on_log:
            self._callbacks.on_log(message)
        else:
            print(message)

    def _emit_error(self, error: str) -> None:
        self._log(f"❌ {error}")
        if self._callbacks.on_error:
            self._callbacks.on_error(error)
