"""
Shared OAuth token refresh helpers.
"""
from __future__ import annotations

from typing import Optional

from forex.config.settings import AppCredentials, OAuthTokens
from forex.infrastructure.broker.oauth.tokens import TokenExchanger


def refresh_tokens(
    *,
    token_file: str,
    refresh_token: str,
    existing_account_id: Optional[int] = None,
) -> OAuthTokens:
    credentials = AppCredentials.from_file(token_file)
    if credentials is None:
        raise RuntimeError("無法讀取 OAuth 憑證")
    exchanger = TokenExchanger(credentials)
    return exchanger.refresh_tokens(
        refresh_token,
        existing_account_id=existing_account_id,
    )

