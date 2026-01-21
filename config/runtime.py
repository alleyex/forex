import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AppConfig:
    token_file: str
    provider: str
    log_level: Optional[str]
    heartbeat_interval: float
    heartbeat_timeout: float
    reconnect_delay: float
    auto_reconnect: bool
    heartbeat_log_interval: float


def _get_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no", "off")


def load_config() -> AppConfig:
    return AppConfig(
        token_file=os.getenv("TOKEN_FILE", "token.json"),
        provider=os.getenv("BROKER_PROVIDER", "ctrader"),
        log_level=os.getenv("LOG_LEVEL"),
        heartbeat_interval=_get_float_env("CTRADER_HEARTBEAT_INTERVAL", 10.0),
        heartbeat_timeout=_get_float_env("CTRADER_HEARTBEAT_TIMEOUT", 30.0),
        reconnect_delay=_get_float_env("CTRADER_RECONNECT_DELAY", 3.0),
        auto_reconnect=_get_bool_env("CTRADER_AUTO_RECONNECT", True),
        heartbeat_log_interval=_get_float_env("CTRADER_HEARTBEAT_LOG_INTERVAL", 60.0),
    )
