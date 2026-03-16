"""OAuth token exchange utilities."""

import json
import time
from urllib import parse, request

from forex.config.settings import AppCredentials, OAuthTokens


class TokenExchanger:
    """
    Handle OAuth token exchange operations.

    Responsibilities:
    - build the authorization URL
    - exchange an authorization code for tokens
    """
    
    TOKEN_URL = "https://openapi.ctrader.com/apps/token"
    AUTH_URL = "https://openapi.ctrader.com/apps/auth"

    def __init__(self, credentials: AppCredentials, redirect_uri: str | None = None):
        self._credentials = credentials
        self._redirect_uri = redirect_uri

    def build_authorize_url(self) -> str:
        """Build the OAuth authorization URL."""
        if not self._redirect_uri:
            raise ValueError("redirect_uri is required to build authorize URL")
        params = {
            "client_id": self._credentials.client_id,
            "redirect_uri": self._redirect_uri,
            "scope": "trading",
        }
        return f"{self.AUTH_URL}?{parse.urlencode(params)}"

    def exchange_code(
        self,
        code: str,
        existing_account_id: int | None = None,
    ) -> OAuthTokens:
        """
        Exchange an authorization code for tokens.

        Args:
            code: Authorization code.
            existing_account_id: Existing account id to preserve, if available.

        Returns:
            OAuthTokens instance.

        Raises:
            RuntimeError: Token exchange failed.
        """
        if not self._redirect_uri:
            raise ValueError("redirect_uri is required to exchange code")
        data = {
            "grant_type": "authorization_code",
            "client_id": self._credentials.client_id,
            "client_secret": self._credentials.client_secret,
            "code": code,
            "redirect_uri": self._redirect_uri,
        }
        response = self._post_request(data)
        return self._parse_token_response(response, existing_account_id)

    def refresh_tokens(
        self,
        refresh_token: str,
        existing_account_id: int | None = None,
    ) -> OAuthTokens:
        data = {
            "grant_type": "refresh_token",
            "client_id": self._credentials.client_id,
            "client_secret": self._credentials.client_secret,
            "refresh_token": refresh_token,
        }
        response = self._post_request(data)
        return self._parse_token_response(response, existing_account_id)
    
    def _post_request(self, data: dict) -> dict:
        """Send a POST request and return the parsed JSON response."""
        encoded = parse.urlencode(data).encode()
        req = request.Request(self.TOKEN_URL, data=encoded, method="POST")

        with request.urlopen(req, timeout=15) as response:
            payload = response.read().decode("utf-8")

        return self._safe_json_loads(payload)

    def _parse_token_response(
        self,
        parsed: dict,
        existing_account_id: int | None,
    ) -> OAuthTokens:
        """Parse the token response."""
        if "error" in parsed:
            raise RuntimeError(parsed.get("error_description") or parsed["error"])

        expires_in = parsed.get("expires_in")
        expires_at = int(time.time()) + expires_in if isinstance(expires_in, int) else None

        return OAuthTokens(
            access_token=parsed.get("access_token", ""),
            refresh_token=parsed.get("refresh_token", ""),
            expires_at=expires_at,
            account_id=existing_account_id,
        )
    
    @staticmethod
    def _safe_json_loads(payload: str) -> dict:
        """Safely parse JSON."""
        try:
            return json.loads(payload)
        except Exception as exc:
            raise RuntimeError(f"Invalid token response: {exc}") from exc
