"""
Shared message helpers for cTrader services.
"""
from typing import Any, Callable, Mapping


def is_already_subscribed(error_code: Any, description: str) -> bool:
    return "ALREADY_SUBSCRIBED" in f"{error_code}" or "ALREADY_SUBSCRIBED" in description


def format_confirm(message: str, payload_type: int) -> str:
    return f"✅ {message}({int(payload_type)})"


def format_error(error_code: Any, description: str) -> str:
    return f"錯誤 {error_code}: {description}"


def format_success(message: str) -> str:
    return f"✅ {message}"


def dispatch_payload(msg: Any, handlers: Mapping[int, Callable[[Any], None]]) -> bool:
    payload = getattr(msg, "payloadType", None)
    handler = handlers.get(payload)
    if handler:
        handler(msg)
        return True
    return False
