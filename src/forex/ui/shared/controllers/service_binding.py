from __future__ import annotations

from inspect import signature
from typing import Any, Callable


def clear_log_history_safe(service: object) -> None:
    clear_history = getattr(service, "clear_log_history", None)
    if not callable(clear_history):
        return
    try:
        clear_history()
    except Exception:
        pass


def set_callbacks_safe(service: object, **callbacks: Callable[..., Any]) -> None:
    setter = getattr(service, "set_callbacks", None)
    if not callable(setter):
        return

    filtered = {name: callback for name, callback in callbacks.items() if callback is not None}
    if not filtered:
        return

    try:
        sig = signature(setter)
    except Exception:
        setter(**filtered)
        return

    supports_kwargs = any(param.kind == param.VAR_KEYWORD for param in sig.parameters.values())
    if not supports_kwargs:
        filtered = {
            name: callback for name, callback in filtered.items() if name in sig.parameters
        }
        if not filtered:
            return

    setter(**filtered)
