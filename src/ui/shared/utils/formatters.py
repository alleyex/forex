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


def format_connection_message(event: str, **kwargs) -> str:
    templates = {
        "in_progress": "⏳ 連線流程進行中，請稍候",
        "disconnected": "🔌 已斷線",
        "connected_done": "✅ 已完成連線",
        "oauth_service_failed": "⚠️ OAuth 服務建立失敗",
        "service_connected": "✅ 服務已連線",
        "oauth_connected": "✅ OAuth 已連線",
        "missing_connection_controller": "⚠️ 缺少連線控制器",
        "missing_use_cases": "⚠️ 缺少 broker 用例配置",
        "missing_app_auth": "⚠️ 尚未完成 App 認證",
        "missing_oauth": "⚠️ 尚未完成 OAuth 帳戶認證",
        "account_list_empty": "⚠️ 帳戶列表為空",
        "account_info_header": "📄 帳戶基本資料",
        "funds_header": "📄 帳戶資金狀態",
        "fetching_funds": "⏳ 正在取得帳戶資金，請稍候",
    }
    if event == "account_count":
        return f"📄 帳戶數量: {kwargs.get('count', 0)}"
    if event == "account_field":
        return f"{kwargs.get('label')}: {kwargs.get('value')}"
    if event == "funds_field":
        return f"{kwargs.get('label')}: {kwargs.get('value')}"
    if event == "account_parse_failed":
        return f"⚠️ 帳戶資料解析失敗: {kwargs.get('error')}"
    if event == "funds_error":
        return f"⚠️ 取得帳戶資金失敗: {kwargs.get('error')}"
    return templates.get(event, "")


def format_optuna_trial_summary(text: str) -> str:
    match = re.search(
        r"Trial\s+(?P<trial>\d+):\s+value=(?P<value>[-+0-9.eE]+)\s+\|\s+best=(?P<best>[-+0-9.eE]+)\s+\(trial\s+(?P<best_trial>\d+)\)",
        text,
    )
    if not match:
        return text
    trial = match.group("trial")
    value = match.group("value")
    best = match.group("best")
    best_trial = match.group("best_trial")
    return f"Trial {trial}\nValue: {value}\nBest so far: {best} (trial {best_trial})"


def format_optuna_best_params(params: dict) -> str:
    order = ["n_steps", "batch_size", "learning_rate", "gamma", "ent_coef"]
    items = []
    for key in order:
        if key not in params:
            continue
        value = params[key]
        if isinstance(value, float):
            formatted = f"{value:.6g}"
        else:
            formatted = str(value)
        items.append(f"{key}={formatted}")
    return "\n".join(items) if items else "—"


def format_optuna_empty_trial() -> str:
    return "尚未完成試驗"


def format_trade_stats(text: str) -> str:
    label_map = {
        "count": "交易次數",
        "wins": "獲利筆數",
        "win_rate": "勝率",
        "avg_pnl": "平均盈虧",
        "avg_cost": "平均成本",
    }
    return format_kv_lines(text, label_map)


def format_streak_stats(text: str) -> str:
    label_map = {
        "max_win": "最大連勝",
        "max_loss": "最大連敗",
    }
    return format_kv_lines(text, label_map)


def format_holding_stats(text: str) -> str:
    label_map = {
        "max_steps": "最長持倉",
        "avg_steps": "平均持倉",
    }
    return format_kv_lines(text, label_map)


def format_action_distribution(text: str) -> str:
    label_map = {
        "long": "多單比例",
        "short": "空單比例",
        "flat": "空手比例",
        "avg": "平均持倉",
    }
    return format_kv_lines(text, label_map)


def format_playback_range(text: str) -> str:
    label_map = {
        "start": "開始",
        "end": "結束",
        "steps": "步數",
    }
    return format_kv_lines(text, label_map)


def format_optuna_empty_best() -> str:
    return "最佳參數：—"
