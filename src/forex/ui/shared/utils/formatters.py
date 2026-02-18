import re
from typing import Optional

from forex.config.constants import ConnectionStatus


def format_app_auth_status(status: Optional[ConnectionStatus]) -> str:
    if status is None:
        return "App Auth Status: ⛔ Disconnected"

    status_map = {
        ConnectionStatus.DISCONNECTED: "⛔ Disconnected",
        ConnectionStatus.CONNECTING: "⏳ Connecting...",
        ConnectionStatus.CONNECTED: "🔗 Connected",
        ConnectionStatus.APP_AUTHENTICATED: "✅ Authenticated",
        ConnectionStatus.ACCOUNT_AUTHENTICATED: "✅ Account Authenticated",
    }
    text = status_map.get(status, "❓ Unknown")
    return f"App Auth Status: {text}"


def format_oauth_status(status: Optional[ConnectionStatus]) -> str:
    if status is None:
        return "OAuth Status: ⛔ Disconnected"

    status_map = {
        ConnectionStatus.DISCONNECTED: "⛔ Disconnected",
        ConnectionStatus.CONNECTING: "⏳ Connecting...",
        ConnectionStatus.CONNECTED: "🔗 Connected",
        ConnectionStatus.APP_AUTHENTICATED: "✅ Authenticated",
        ConnectionStatus.ACCOUNT_AUTHENTICATED: "🔐 Account Authorized",
    }
    text = status_map.get(status, "❓ Unknown")
    return f"OAuth Status: {text}"


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
    return f"Status: {text}"


def format_timestamped_message(message: str, timestamp: Optional[str] = None) -> str:
    if timestamp:
        return f"[{timestamp}] {message}"
    return message


def format_simulation_message(event: str, **kwargs) -> str:
    templates = {
        "already_running": "ℹ️ Playback is still running",
        "not_running": "ℹ️ Playback is not running",
        "start": "▶️ Start playback",
        "start_failed": "⚠️ Playback is already running",
        "stop_requested": "⏹️ Stop requested for playback",
        "stop_failed": "⚠️ Failed to stop playback",
    }
    if event == "finished":
        exit_status = kwargs.get("exit_status")
        exit_code = kwargs.get("exit_code")
        status = "finished" if exit_status else "abnormal end"
        return f"⏹️ Playback {status} (exit={exit_code})"
    if event == "param_error":
        return f"⚠️ {kwargs.get('message', '').strip()}"
    return templates.get(event, "")


def format_training_message(event: str, **kwargs) -> str:
    templates = {
        "already_running": "ℹ️ PPO training is still running",
        "start": "▶️ Start PPO training",
        "start_failed": "⚠️ PPO training is already running",
        "optuna_trials_required": "⚠️ Optuna trial count must be greater than 0",
    }
    if event == "stderr":
        return f"⚠️ {kwargs.get('line', '').strip()}"
    if event == "finished":
        exit_status = kwargs.get("exit_status")
        exit_code = kwargs.get("exit_code")
        status = "finished" if exit_status else "abnormal end"
        return f"⏹️ PPO training {status} (exit={exit_code})"
    return templates.get(event, "")


def format_history_message(event: str, **kwargs) -> str:
    templates = {
        "app_auth_missing": "⚠️ App auth not completed",
        "app_auth_disconnected": "⚠️ App auth disconnected, waiting for auto reconnect",
        "oauth_missing": "⚠️ OAuth account auth not completed",
        "account_id_missing": "⚠️ Missing account ID",
        "symbol_list_incomplete": "📥 symbol list is incomplete, refetching...",
        "symbol_list_fetching": "📥 Fetching symbol list...",
        "symbol_list_empty": "⚠️ symbol list is empty",
    }
    if event == "token_read_failed":
        return f"⚠️ Failed to read OAuth token: {kwargs.get('error')}"
    if event == "symbol_list_write_start":
        return f"📦 Writing symbol list: {kwargs.get('path')} ({kwargs.get('count')} rows)"
    if event == "symbol_list_write_failed":
        return f"⚠️ Failed to write symbol list: {kwargs.get('error')}"
    if event == "symbol_list_saved":
        return f"✅ Saved symbol list: {kwargs.get('path')}"
    if event == "timeframes_write_failed":
        return f"⚠️ Failed to write timeframes.json: {kwargs.get('error')}"
    if event == "history_saved":
        return f"✅ Saved history data: {kwargs.get('path')}"
    if event == "history_error":
        return f"⚠️ History data error: {kwargs.get('error')}"
    if event == "symbol_list_error":
        return f"⚠️ symbol list error: {kwargs.get('error')}"
    return templates.get(event, "")


def format_connection_message(event: str, **kwargs) -> str:
    templates = {
        "in_progress": "⏳ Connection flow in progress, please wait",
        "disconnected": "🔌 Disconnected",
        "connected_done": "✅ Connected",
        "oauth_service_failed": "⚠️ Failed to create OAuth service",
        "service_connected": "✅ Service connected",
        "oauth_connected": "✅ OAuth connected",
        "logout_pending": "🚪 Logging out, waiting for server disconnect confirmation",
        "missing_connection_controller": "⚠️ Missing connection controller",
        "missing_use_cases": "⚠️ Missing broker use-case configuration",
        "missing_app_auth": "⚠️ App auth not completed",
        "missing_oauth": "⚠️ OAuth account auth not completed",
        "account_list_empty": "⚠️ Account list is empty",
        "account_info_header": "📄 Account basics",
        "funds_header": "📄 Account funds",
        "fetching_funds": "⏳ Fetching account funds, please wait",
    }
    if event == "account_count":
        return f"📄 Account count: {kwargs.get('count', 0)}"
    if event == "account_field":
        return f"{kwargs.get('label')}: {kwargs.get('value')}"
    if event == "funds_field":
        return f"{kwargs.get('label')}: {kwargs.get('value')}"
    if event == "account_parse_failed":
        return f"⚠️ Failed to parse account data: {kwargs.get('error')}"
    if event == "funds_error":
        return f"⚠️ Failed to fetch account funds: {kwargs.get('error')}"
    return templates.get(event, "")


def format_optuna_trial_summary(text: str) -> str:
    match = re.search(
        r"Trial\s+(?P<trial>\d+):\s+value=(?P<value>[-+0-9.eE]+)\s+\|\s+best=(?P<best>[-+0-9.eE]+)\s+\(trial\s+(?P<best_trial>\d+)\)",
        text,
    )
    if not match:
        return text
    trial_raw = match.group("trial")
    best_trial_raw = match.group("best_trial")
    try:
        trial = str(int(trial_raw) + 1)
    except (TypeError, ValueError):
        trial = trial_raw
    try:
        best_trial = str(int(best_trial_raw) + 1)
    except (TypeError, ValueError):
        best_trial = best_trial_raw
    try:
        value_num = float(match.group("value"))
        value = f"{value_num:.6g}"
    except (TypeError, ValueError):
        value = match.group("value")
    try:
        best_num = float(match.group("best"))
        best = f"{best_num:.6g}"
    except (TypeError, ValueError):
        best = match.group("best")
    return (
        f"Trial #{trial}\n"
        f"Value      : {value}\n"
        f"Best so far: {best} (trial {best_trial})"
    )


def format_optuna_best_params(params: dict) -> str:
    groups = [
        (
            "PPO core",
            [
                "learning_rate",
                "gamma",
                "gae_lambda",
                "clip_range",
                "ent_coef",
                "vf_coef",
                "n_steps",
                "batch_size",
                "n_epochs",
            ],
        ),
        (
            "Environment",
            [
                "episode_length",
                "reward_clip",
                "min_position_change",
                "position_step",
                "risk_aversion",
                "max_position",
            ],
        ),
    ]
    label_map = {
        "learning_rate": "Learning rate",
        "gamma": "Gamma",
        "gae_lambda": "GAE lambda",
        "clip_range": "Clip range",
        "ent_coef": "Entropy coef",
        "vf_coef": "Value fn coef",
        "n_steps": "Rollout steps",
        "batch_size": "Batch size",
        "n_epochs": "Epochs/update",
        "episode_length": "Episode length",
        "reward_clip": "Reward clip",
        "min_position_change": "Min position chg",
        "position_step": "Position step",
        "risk_aversion": "Risk aversion",
        "max_position": "Max position",
    }

    def _fmt(value) -> str:
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    lines: list[str] = []
    for title, keys in groups:
        rows: list[tuple[str, str]] = []
        for key in keys:
            if key not in params:
                continue
            rows.append((label_map.get(key, key), _fmt(params[key])))
        if not rows:
            continue
        label_width = max(len(label) for label, _ in rows)
        lines.append(f"[{title}]")
        for label, value in rows:
            lines.append(f"{label:<{label_width}} : {value}")
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) if lines else "—"


def format_optuna_empty_trial() -> str:
    return "Trial not finished yet"


def format_trade_stats(text: str) -> str:
    label_map = {
        "count": "Trades",
        "wins": "Winning trades",
        "win_rate": "Win rate",
        "avg_pnl": "Average PnL",
        "avg_cost": "Average Cost",
    }
    return format_kv_lines(text, label_map)


def format_streak_stats(text: str) -> str:
    label_map = {
        "max_win": "Max win streak",
        "max_loss": "Max loss streak",
    }
    return format_kv_lines(text, label_map)


def format_holding_stats(text: str) -> str:
    label_map = {
        "max_steps": "Max holding",
        "avg_steps": "Average holding",
    }
    return format_kv_lines(text, label_map)


def format_action_distribution(text: str) -> str:
    label_map = {
        "long": "Long ratio",
        "short": "Short ratio",
        "flat": "Flat ratio",
        "avg": "Average holding",
    }
    return format_kv_lines(text, label_map)


def format_playback_range(text: str) -> str:
    label_map = {
        "start": "Start",
        "end": "End",
        "steps": "Steps",
    }
    return format_kv_lines(text, label_map)


def format_optuna_empty_best() -> str:
    return "Best params: —"
