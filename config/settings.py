from dataclasses import dataclass
from typing import Optional, Union
import json
import os


@dataclass
class AppCredentials:
    """Application credentials container"""
    host: str
    client_id: str
    client_secret: str

    @classmethod
    def from_file(cls, filepath: str) -> Optional["AppCredentials"]:
        """Load credentials from JSON file"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Credentials file not found: {filepath}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        host_type = data.get("host_type", "demo")
        client_id = data.get("client_id", "")
        client_secret = data.get("client_secret", "")

        if host_type not in ("demo", "live"):
            raise ValueError(f"Invalid host type in credentials file: {host_type}")
        
        return cls(
            host=host_type,
            client_id=client_id, 
            client_secret=client_secret
            )
    
    def save(self, filepath: str) -> None:
        """Save credentials to JSON file"""
        data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as file:
                    data = json.load(file)
            except Exception:
                data = {}

        data.update({
            "host_type": self.host,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        })

        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)


@dataclass
class OAuthTokens:
    """OAuth tokens container"""
    access_token: str
    refresh_token: str
    expires_at: Optional[Union[int, str]]
    account_id: Optional[int]

    @classmethod
    def from_file(cls, filepath: str) -> Optional["OAuthTokens"]:
        """Load tokens from JSON file"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Token file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            expires_at=data.get("expires_at"),
            account_id=data.get("account_id"),
        )

    def save(self, filepath: str) -> None:
        """Save tokens to JSON file"""
        data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as file:
                    data = json.load(file)
            except Exception:
                data = {}

        data.update({
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "account_id": self.account_id,
        })

        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
