from dataclasses import dataclass
from typing import Optional
import json
import os


@dataclass
class AppCredentials:
    """Application credentials container"""
    client_id: str
    client_secret: str

    @classmethod
    def from_file(cls, filepath: str) -> Optional["AppCredentials"]:
        """Load credentials from JSON file"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Credentials file not found: {filepath}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")
        
        if not client_id or not client_secret:
            raise ValueError("Missing client_id or client_secret in credentials file")
        
        return cls(client_id=client_id, client_secret=client_secret)


@dataclass 
class ConnectionConfig:
    """Connection configuration"""
    host_type: str  # "demo" or "live"
    token_file: str = "token.json"
    
    def __post_init__(self):
        if self.host_type not in ("demo", "live"):
            raise ValueError(f"Invalid host type: {self.host_type}")
        