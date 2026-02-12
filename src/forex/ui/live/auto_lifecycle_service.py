from __future__ import annotations

import time

from forex.config.constants import ConnectionStatus


class LiveAutoLifecycleService:
    """Controls Auto Trade start/stop lifecycle transitions."""

    def __init__(self, window) -> None:
        self._window = window

    def toggle(self, enabled: bool) -> None:
        if enabled:
            self._start()
            return
        self._stop()

    def _start(self) -> None:
        w = self._window
        if w._app_state and w._app_state.selected_account_scope == 0:
            w._auto_log("⚠️ 帳戶權限為僅檢視，無法啟用交易")
            w._auto_trade_toggle.setChecked(False)
            return
        valid, errors = w._auto_settings_validator.validate_start()
        if not valid:
            for err in errors:
                w._auto_log(f"⚠️ Invalid auto trade setting: {err}")
            w._auto_trade_toggle.setChecked(False)
            return
        if not w._load_auto_model():
            w._auto_trade_toggle.setChecked(False)
            return
        w._auto_enabled = True
        w._auto_trade_toggle.setText("Stop")
        w._auto_position = 0.0
        w._auto_position_id = None
        w._auto_last_action_ts = None
        w._auto_peak_balance = None
        w._auto_day_balance = None
        w._auto_day_key = None
        w._auto_started_ts = time.time()
        w._auto_last_decision_ts = 0.0
        w._auto_last_watchdog_warn_ts = 0.0
        w._auto_last_trendbar_ts = 0.0
        w._auto_last_resubscribe_ts = 0.0
        w._auto_order_busy_since = None
        w._auto_order_busy_warn_ts = 0.0
        trade_symbol = w._trade_symbol.currentText()
        if trade_symbol and trade_symbol != w._symbol_name:
            w._symbol_name = trade_symbol
            w._symbol_id = w._resolve_symbol_id(trade_symbol)
            w._price_digits = w._quote_digits.get(
                trade_symbol, w._infer_quote_digits(trade_symbol)
            )
            w._history_requested = False
            w._pending_history = False
            w._stop_live_trendbar()
            if w._oauth_service and getattr(w._oauth_service, "status", 0) >= ConnectionStatus.ACCOUNT_AUTHENTICATED:
                w._request_recent_history()
        w._ensure_order_service()
        if not w._order_service:
            w._auto_enabled = False
            w._auto_trade_toggle.setChecked(False)
            w._auto_log("⚠️ Order service unavailable; auto trade not started.")
            return
        w._request_positions()
        w._refresh_account_balance()
        if w._auto_watchdog_timer:
            w._auto_watchdog_timer.start()
        if getattr(w, "_history_only_chart_mode", False):
            w._start_history_polling()
        near_full_text = "ON" if bool(w._near_full_hold.isChecked()) else "OFF"
        w._auto_log(
            "ℹ️ Strategy profile: "
            f"same-side near-full hold={near_full_text} (|desired|>=0.95)."
        )
        w._auto_log("✅ Auto trading started")

    def _stop(self) -> None:
        w = self._window
        w._auto_enabled = False
        w._auto_trade_toggle.setText("Start")
        if w._auto_watchdog_timer and w._auto_watchdog_timer.isActive():
            w._auto_watchdog_timer.stop()
        w._auto_order_busy_since = None
        w._auto_log("🛑 Auto trading stopped")

