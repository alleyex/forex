from dataclasses import dataclass
from typing import Optional


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
    expires_at: Optional[int]
    account_id: Optional[int]
