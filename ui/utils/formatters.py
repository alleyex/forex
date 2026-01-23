from __future__ import annotations

import re
from typing import Optional

from config.constants import ConnectionStatus


def format_app_auth_status(status: Optional[ConnectionStatus]) -> str:
    if status is None:
        return "App 認證狀態: ⛔ 未連線"

    status_map = {
        ConnectionStatus.DISCONNECTED: "⛔ 已斷線",
        ConnectionStatus.CONNECTING: "⏳ 連線中...",
        ConnectionStatus.CONNECTED: "🔗 已連線",
        ConnectionStatus.APP_AUTHENTICATED: "✅ 已認證",
        ConnectionStatus.ACCOUNT_AUTHENTICATED: "✅ 帳戶已認證",
    }
    text = status_map.get(status, "❓ 未知")
    return f"App 認證狀態: {text}"


def format_oauth_status(status: Optional[ConnectionStatus]) -> str:
    if status is None:
        return "OAuth 狀態: ⛔ 未連線"

    status_map = {
        ConnectionStatus.DISCONNECTED: "⛔ 已斷線",
        ConnectionStatus.CONNECTING: "⏳ 連線中...",
        ConnectionStatus.CONNECTED: "🔗 已連線",
        ConnectionStatus.APP_AUTHENTICATED: "✅ 已認證",
        ConnectionStatus.ACCOUNT_AUTHENTICATED: "🔐 帳戶已授權",
    }
    text = status_map.get(status, "❓ 未知")
    return f"OAuth 狀態: {text}"


def format_kv_lines(text: str, label_map: Optional[dict[str, str]] = None) -> str:
    if not text or text.strip() == "-":
        return "-"
    pattern = re.compile(r"(\\w+)=([^=]+?)(?=\\s+\\w+=|$)")
    matches = pattern.findall(text)
    if not matches:
        return text
    lines = []
    for key, value in matches:
        label = label_map.get(key, key) if label_map else key
        label = label.replace("_", " ")
        lines.append(f"{label}: {value.strip()}")
    return "\n".join(lines)


def format_log_message(level: str, message: str) -> str:
    level_map = {
        "info": "INFO",
        "ok": "OK",
        "warn": "WARN",
        "error": "ERROR",
    }
    tag = level_map.get(level.lower(), level.upper())
    return f"[{tag}] {message}"


def format_log_info(message: str) -> str:
    return format_log_message("info", message)


def format_log_ok(message: str) -> str:
    return format_log_message("ok", message)


def format_log_warn(message: str) -> str:
    return format_log_message("warn", message)


def format_log_error(message: str) -> str:
    return format_log_message("error", message)


def format_status_label(text: str) -> str:
    return f"狀態: {text}"


def format_timestamped_message(message: str, timestamp: Optional[str] = None) -> str:
    if timestamp:
        return f"[{timestamp}] {message}"
    return message
