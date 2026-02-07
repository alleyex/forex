"""
Shared message helpers for cTrader services.
"""
from typing import Any, Callable, Mapping

from forex.infrastructure.broker.ctrader.auth.errors import describe_error_code


def is_already_subscribed(error_code: Any, description: str) -> bool:
    return "ALREADY_SUBSCRIBED" in f"{error_code}" or "ALREADY_SUBSCRIBED" in description


def format_confirm(message: str, payload_type: int) -> str:
    return f"✅ {message}({int(payload_type)})"


def format_error(error_code: Any, description: str) -> str:
    name = describe_error_code(error_code)
    if name:
        return f"錯誤 {error_code}({name}): {description}"
    return f"錯誤 {error_code}: {description}"


def format_success(message: str) -> str:
    return f"✅ {message}"


def format_warning(message: str) -> str:
    return f"⚠️ {message}"


def format_request(message: str) -> str:
    return f"📥 {message}"


def format_sent_subscribe(message: str) -> str:
    return f"📡 {message}"


def format_sent_unsubscribe(message: str) -> str:
    return f"🔕 {message}"


def format_unhandled(payload_type: int) -> str:
    return f"📩 未處理的訊息類型: {int(payload_type)}"


def dispatch_payload(msg: Any, handlers: Mapping[int, Callable[[Any], None]]) -> bool:
    payload = getattr(msg, "payloadType", None)
    handler = handlers.get(payload)
    if handler:
        handler(msg)
        return True
    return False
