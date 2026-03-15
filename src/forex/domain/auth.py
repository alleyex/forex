from dataclasses import dataclass


@dataclass
class Credentials:
    """Application credentials."""
    host: str
    client_id: str
    client_secret: str


@dataclass
class Tokens:
    """OAuth token bundle."""

    access_token: str
    refresh_token: str
    expires_at: int | None
    account_id: int | None
