"""OAuth callback server."""

import time
import webbrowser
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib import parse


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callbacks."""

    def do_GET(self) -> None:
        """Handle a GET request."""
        parsed = parse.urlparse(self.path)
        params = parse.parse_qs(parsed.query)
        self.server.code = params.get("code", [None])[0]
        self.server.request_path = parsed.path

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Authorization complete. You can close this window.")

    def log_message(self, _format: str, *args) -> None:
        """Suppress default log output."""
        pass


class CallbackServer:
    """
    Local server that receives OAuth callbacks.

    Responsibilities:
    - start a local HTTP server
    - open the browser for authorization
    - wait for and capture the authorization code
    """

    DEFAULT_TIMEOUT = 300  # 5 minutes

    def __init__(self, redirect_uri: str):
        self._host, self._port, self._path = self._parse_uri(redirect_uri)

    @staticmethod
    def _parse_uri(redirect_uri: str) -> tuple[str, int, str]:
        """
        Parse a redirect URI.

        Args:
            redirect_uri: Full redirect URI.

        Returns:
            Tuple of (host, port, path).

        Raises:
            ValueError: URI format is invalid.
        """
        parsed = parse.urlparse(redirect_uri)
        host = parsed.hostname
        port = parsed.port
        path = parsed.path or "/"

        if not host or not port:
            raise ValueError("Invalid redirect URI: host and port are required")
        return host, port, path

    def wait_for_code(
        self,
        auth_url: str,
        timeout_seconds: int = DEFAULT_TIMEOUT,
        on_log: Callable[[str], None] | None = None,
    ) -> str | None:
        """
        Wait for an OAuth authorization code.

        Args:
            auth_url: Authorization URL.
            timeout_seconds: Timeout in seconds.
            on_log: Optional logging callback.

        Returns:
            Authorization code, or None on timeout.
        """
        try:
            server = self._create_server()
        except OSError as exc:
            if on_log:
                on_log(f"⚠️ Unable to start callback server; the port may already be in use: {exc}")
                on_log("ℹ️ Fall back to the manual authorization-code flow if needed")
            return None

        if on_log:
            on_log("🌐 Opening the browser for OAuth authorization...")
        webbrowser.open(auth_url)

        return self._wait_for_callback(server, timeout_seconds)

    def _create_server(self) -> HTTPServer:
        """Create and configure the HTTP server."""
        server = HTTPServer((self._host, self._port), OAuthCallbackHandler)
        server.code = None
        server.request_path = None
        server.timeout = 1
        return server
    
    def _wait_for_callback(self, server: HTTPServer, timeout_seconds: int) -> str | None:
        """Wait for the callback and return the authorization code."""
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            server.handle_request()
            if server.code:
                # Verify that the callback path matches.
                if self._path and server.request_path:
                    if server.request_path != self._path:
                        continue
                return server.code

        return None
