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


def format_simulation_message(event: str, **kwargs) -> str:
    templates = {
        "already_running": "ℹ️ 回放模擬仍在進行中",
        "not_running": "ℹ️ 回放模擬未在進行中",
        "start": "▶️ 開始回放模擬",
        "start_failed": "⚠️ 回放模擬尚在執行",
        "stop_requested": "⏹️ 已要求停止回放模擬",
        "stop_failed": "⚠️ 回放模擬停止失敗",
    }
    if event == "finished":
        exit_status = kwargs.get("exit_status")
        exit_code = kwargs.get("exit_code")
        status = "完成" if exit_status else "異常結束"
        return f"⏹️ 回放模擬{status} (exit={exit_code})"
    if event == "param_error":
        return f"⚠️ {kwargs.get('message', '').strip()}"
    return templates.get(event, "")


def format_training_message(event: str, **kwargs) -> str:
    templates = {
        "already_running": "ℹ️ PPO 訓練仍在進行中",
        "start": "▶️ 開始 PPO 訓練",
        "start_failed": "⚠️ PPO 訓練尚在執行",
        "optuna_trials_required": "⚠️ Optuna 試驗次數需大於 0",
    }
    if event == "stderr":
        return f"⚠️ {kwargs.get('line', '').strip()}"
    if event == "finished":
        exit_status = kwargs.get("exit_status")
        exit_code = kwargs.get("exit_code")
        status = "完成" if exit_status else "異常結束"
        return f"⏹️ PPO 訓練{status} (exit={exit_code})"
    return templates.get(event, "")


def format_trendbar_message(event: str, **kwargs) -> str:
    templates = {
        "app_auth_missing": "⚠️ 尚未完成 App 認證",
        "app_auth_disconnected": "⚠️ App 認證已中斷，請稍候自動重連",
        "oauth_missing": "⚠️ 尚未完成 OAuth 帳戶認證",
        "account_id_missing": "⚠️ 缺少帳戶 ID",
        "no_subscription": "ℹ️ 目前沒有 K 線訂閱",
    }
    if event == "token_read_failed":
        return f"⚠️ 無法讀取 OAuth Token: {kwargs.get('error')}"
    if event == "trendbar_started":
        return f"📈 已開始 M1 K 線：symbol {kwargs.get('symbol_id')}"
    if event == "trendbar_error":
        return f"⚠️ K 線錯誤: {kwargs.get('error')}"
    if event == "trendbar_bar":
        return (
            f"📊 {kwargs.get('timeframe', 'M1')} {kwargs.get('timestamp')} "
            f"O={kwargs.get('open')} H={kwargs.get('high')} "
            f"L={kwargs.get('low')} C={kwargs.get('close')}"
        )
    return templates.get(event, "")


def format_history_message(event: str, **kwargs) -> str:
    templates = {
        "app_auth_missing": "⚠️ 尚未完成 App 認證",
        "app_auth_disconnected": "⚠️ App 認證已中斷，請稍候自動重連",
        "oauth_missing": "⚠️ 尚未完成 OAuth 帳戶認證",
        "account_id_missing": "⚠️ 缺少帳戶 ID",
        "symbol_list_incomplete": "📥 symbol list 不完整，正在重新取得...",
        "symbol_list_fetching": "📥 正在取得 symbol list...",
        "symbol_list_empty": "⚠️ symbol list 為空",
    }
    if event == "token_read_failed":
        return f"⚠️ 無法讀取 OAuth Token: {kwargs.get('error')}"
    if event == "symbol_list_write_start":
        return f"📦 正在寫入 symbol list：{kwargs.get('path')} ({kwargs.get('count')} 筆)"
    if event == "symbol_list_write_failed":
        return f"⚠️ 無法寫入 symbol list: {kwargs.get('error')}"
    if event == "symbol_list_saved":
        return f"✅ 已儲存 symbol list：{kwargs.get('path')}"
    if event == "timeframes_write_failed":
        return f"⚠️ 無法寫入 timeframes.json: {kwargs.get('error')}"
    if event == "history_saved":
        return f"✅ 已儲存歷史資料：{kwargs.get('path')}"
    if event == "history_error":
        return f"⚠️ 歷史資料錯誤: {kwargs.get('error')}"
    if event == "symbol_list_error":
        return f"⚠️ symbol list 錯誤: {kwargs.get('error')}"
    return templates.get(event, "")
