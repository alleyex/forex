from __future__ import annotations

import time

class LiveAutoRecoveryService:
    """Owns watchdog and history-poll recovery logic for auto trade."""

    def __init__(self, window) -> None:
        self._window = window

    def auto_watchdog_tick(self) -> None:
        w = self._window
        ready_fn = getattr(w, "_is_broker_runtime_ready", None)
        runtime_ready = bool(ready_fn()) if callable(ready_fn) else True
        if not w._auto_enabled:
            return
        now = time.time()
        history_only_mode = bool(getattr(w, "_history_only_chart_mode", False))
        timeframe_seconds = max(60, w._timeframe_minutes() * 60)
        silence_threshold = max(120, timeframe_seconds * 2)
        stale_feed_threshold = max(90, timeframe_seconds * 2)
        reference_ts = w._auto_last_decision_ts or w._auto_started_ts or now
        silence_seconds = max(0.0, now - reference_ts)
        if history_only_mode:
            trendbar_reference = (
                w._last_history_success_ts
                or w._last_history_request_ts
                or w._auto_started_ts
                or now
            )
        else:
            trendbar_reference = w._auto_last_trendbar_ts or w._auto_started_ts or now
        trendbar_silence = max(0.0, now - trendbar_reference)

        history_request_timeout = max(25.0, float(timeframe_seconds))
        if (
            history_only_mode
            and w._history_requested
            and w._last_history_request_ts > 0
            and now - w._last_history_request_ts >= history_request_timeout
            and now - w._auto_last_resubscribe_ts >= 30
        ):
            w._auto_last_resubscribe_ts = now
            w._auto_log(
                "♻️ Auto recover: history request timed out "
                f"({int(now - w._last_history_request_ts)}s). Resetting history pipeline..."
            )
            w._history_requested = False
            w._pending_history = False
            w._last_history_request_key = None
            w._dispose_history_service()
            w._request_recent_history()

        if silence_seconds >= silence_threshold:
            if now - w._auto_last_watchdog_warn_ts >= 120:
                if history_only_mode:
                    trendbar_state = "history-poll"
                else:
                    trendbar_state = "active" if w._trendbar_active else "inactive"
                w._auto_log(
                    "⚠️ Auto trade quiet for "
                    f"{int(silence_seconds)}s (tf={w._timeframe}, trendbar={trendbar_state}, "
                    f"candles={len(w._candles)}, trendbar_idle={int(trendbar_silence)}s)."
                )
                w._auto_last_watchdog_warn_ts = now

        latest_candle_ts = w._candles[-1][0] if w._candles else 0.0
        latest_candle_age = max(0.0, now - float(latest_candle_ts or 0.0))
        if (
            not history_only_mode
            and w._trendbar_active
            and silence_seconds >= silence_threshold
            and latest_candle_ts
            and latest_candle_age >= timeframe_seconds * 2
            and now - w._auto_last_resubscribe_ts >= 90
        ):
            w._auto_last_resubscribe_ts = now
            w._auto_log(
                "♻️ Auto recover: no new closed candle "
                f"for {int(latest_candle_age)}s (tf={w._timeframe}). Resyncing history/trendbar..."
            )
            w._stop_live_trendbar()
            w._dispose_trendbar_service()
            if runtime_ready and w._app_state and w._app_state.selected_account_id:
                w._history_requested = False
                w._pending_history = False
                w._dispose_history_service()
                w._request_recent_history()
            else:
                w._start_live_trendbar()
            return
        if (
            not history_only_mode
            and w._trendbar_active
            and trendbar_silence >= stale_feed_threshold
            and now - w._auto_last_resubscribe_ts >= 90
        ):
            w._auto_last_resubscribe_ts = now
            w._auto_log(
                "♻️ Auto recover: trendbar feed stale "
                f"({int(trendbar_silence)}s). Rebuilding subscription..."
            )
            w._stop_live_trendbar()
            w._dispose_trendbar_service()
            w._auto_last_trendbar_ts = now
            if runtime_ready and w._app_state and w._app_state.selected_account_id:
                w._history_requested = False
                w._pending_history = False
                w._dispose_history_service()
                w._request_recent_history()
            else:
                w._start_live_trendbar()

        if w._order_service and getattr(w._order_service, "in_progress", False):
            if w._auto_order_busy_since is None:
                w._auto_order_busy_since = now
            busy_seconds = now - w._auto_order_busy_since
            if busy_seconds >= 120 and now - w._auto_order_busy_warn_ts >= 120:
                w._auto_log(
                    f"⚠️ Order service busy for {int(busy_seconds)}s; waiting broker response."
                )
                w._auto_order_busy_warn_ts = now
        else:
            w._auto_order_busy_since = None

    def history_poll_tick(self) -> None:
        w = self._window
        ready_fn = getattr(w, "_is_broker_runtime_ready", None)
        runtime_ready = bool(ready_fn()) if callable(ready_fn) else True
        history_only_mode = bool(getattr(w, "_history_only_chart_mode", False))
        # In stream mode, do not use periodic history polling.
        if not history_only_mode:
            w._stop_history_polling()
            return
        if getattr(w, "_account_authorization_blocked", False):
            return
        if not runtime_ready:
            return
        if w._history_requested and w._last_history_request_ts > 0:
            now = time.time()
            request_age = now - w._last_history_request_ts
            timeout = max(25.0, float(max(60, w._timeframe_minutes() * 60)))
            if request_age >= timeout:
                w._auto_log(
                    "♻️ Auto recover: stale history in-flight request "
                    f"({int(request_age)}s). Retrying..."
                )
                w._history_requested = False
                w._pending_history = False
                w._last_history_request_key = None
                w._dispose_history_service()
            else:
                # Skip duplicate poll requests while an in-flight history request
                # is still within its expected response window.
                return
        w._request_recent_history()
