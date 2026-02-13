import os
from dataclasses import dataclass
from typing import Optional

from forex.config.paths import TOKEN_FILE


@dataclass(frozen=True)
class AppConfig:
    token_file: str
    provider: str
    log_level: Optional[str]
    log_file: Optional[str]
    heartbeat_interval: float
    heartbeat_timeout: float
    request_timeout: float
    oauth_timeout: float
    oauth_login_timeout: float
    reconnect_delay: float
    reconnect_max_delay: float
    reconnect_max_attempts: int
    reconnect_jitter_ratio: float
    auto_reconnect: bool
    heartbeat_log_interval: float
    retry_max_attempts: int
    retry_backoff_seconds: float


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    backoff_seconds: float


def _get_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no", "off")


def load_config() -> AppConfig:
    return AppConfig(
        token_file=os.getenv("TOKEN_FILE", TOKEN_FILE),
        provider=os.getenv("BROKER_PROVIDER", "ctrader"),
        log_level=os.getenv("LOG_LEVEL"),
        log_file=os.getenv("LOG_FILE"),
        heartbeat_interval=_get_float_env("CTRADER_HEARTBEAT_INTERVAL", 10.0),
        heartbeat_timeout=_get_float_env("CTRADER_HEARTBEAT_TIMEOUT", 30.0),
        request_timeout=_get_float_env("CTRADER_REQUEST_TIMEOUT", 15.0),
        oauth_timeout=_get_float_env("CTRADER_OAUTH_TIMEOUT", 15.0),
        oauth_login_timeout=_get_float_env("CTRADER_OAUTH_LOGIN_TIMEOUT", 300.0),
        reconnect_delay=_get_float_env("CTRADER_RECONNECT_DELAY", 3.0),
        reconnect_max_delay=_get_float_env("CTRADER_RECONNECT_MAX_DELAY", 60.0),
        reconnect_max_attempts=_get_int_env("CTRADER_RECONNECT_MAX_ATTEMPTS", 0),
        reconnect_jitter_ratio=_get_float_env("CTRADER_RECONNECT_JITTER_RATIO", 0.15),
        auto_reconnect=_get_bool_env("CTRADER_AUTO_RECONNECT", True),
        heartbeat_log_interval=_get_float_env("CTRADER_HEARTBEAT_LOG_INTERVAL", 60.0),
        retry_max_attempts=_get_int_env("CTRADER_RETRY_MAX_ATTEMPTS", 0),
        retry_backoff_seconds=_get_float_env("CTRADER_RETRY_BACKOFF_SECONDS", 2.0),
    )


def retry_policy_from_config(config: AppConfig) -> Optional[RetryPolicy]:
    if config.retry_max_attempts <= 0:
        return None
    return RetryPolicy(
        max_attempts=config.retry_max_attempts,
        backoff_seconds=max(0.0, config.retry_backoff_seconds),
    )
