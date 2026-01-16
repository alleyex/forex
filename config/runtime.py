import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AppConfig:
    token_file: str
    provider: str
    log_level: Optional[str]


def load_config() -> AppConfig:
    return AppConfig(
        token_file=os.getenv("TOKEN_FILE", "token.json"),
        provider=os.getenv("BROKER_PROVIDER", "ctrader"),
        log_level=os.getenv("LOG_LEVEL"),
    )
