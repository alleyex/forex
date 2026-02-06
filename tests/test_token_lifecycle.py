import time

from forex.config.settings import OAuthTokens


def test_token_expiry_checks() -> None:
    now = int(time.time())
    tokens = OAuthTokens(
        access_token="a",
        refresh_token="r",
        expires_at=now + 120,
        account_id=1,
    )
    assert tokens.is_expired(leeway_seconds=10) is False
    assert tokens.seconds_to_expiry() is not None


def test_token_expired_with_leeway() -> None:
    now = int(time.time())
    tokens = OAuthTokens(
        access_token="a",
        refresh_token="r",
        expires_at=now + 5,
        account_id=1,
    )
    assert tokens.is_expired(leeway_seconds=10) is True
