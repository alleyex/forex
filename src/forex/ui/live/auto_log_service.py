from __future__ import annotations

import re
from typing import Optional


class LiveAutoLogService:
    """Formats and emits Auto Trade logs for LiveMainWindow."""

    _LOG_LEVEL_PREFIX = re.compile(r"^\s*\[(DEBUG|TRADE|TRADING|INFO|OK|WARN|ERROR)\]\s*", re.IGNORECASE)

    def __init__(self, window) -> None:
        self._window = window

    def infer_level(self, message: str) -> str:
        text = str(message).strip()
        lower = text.lower()
        trading_markers = (
            "order",
            "position",
            "volume",
            "trade skipped by cost filter",
            "risk guard blocked new trades",
            "closing existing position",
            "place_order",
            "close_position",
            "reverse_close_first",
        )
        if any(marker in lower for marker in trading_markers):
            return "INFO"
        if "[debug]" in lower:
            return "DEBUG"
        if text.startswith(("❌", "🛑")) or "錯誤" in text or "error" in lower:
            return "ERROR"
        if text.startswith(("⚠️", "⚠")) or "warn" in lower:
            return "WARN"
        if text.startswith("✅"):
            return "OK"
        return "INFO"

    def emit(self, message: str, *, level: Optional[str] = None) -> None:
        text = str(message).strip()
        if not text:
            return
        match = self._LOG_LEVEL_PREFIX.match(text)
        if match:
            normalized_level = match.group(1).upper()
            if normalized_level in {"TRADING", "TRADE"}:
                normalized_level = "INFO"
            body = text[match.end() :].lstrip()
            formatted = f"[{normalized_level}] {body}"
        else:
            normalized_level = (str(level).upper() if level else self.infer_level(text))
            if normalized_level in {"TRADING", "TRADE"}:
                normalized_level = "INFO"
            formatted = f"[{normalized_level}] {text}"
        if self._window._auto_log_panel:
            self._window._auto_log_panel.append(formatted)
        self._window.logRequested.emit(formatted)
