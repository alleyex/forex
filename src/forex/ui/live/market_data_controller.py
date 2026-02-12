from __future__ import annotations

import time

from forex.config.constants import ConnectionStatus


class LiveMarketDataController:
    def __init__(self, window) -> None:
        self._window = window

    def set_trade_timeframe(self, timeframe: str) -> None:
        w = self._window
        next_timeframe = str(timeframe or "").strip().upper()
        if not next_timeframe or next_timeframe == w._timeframe:
            return
        w._timeframe = next_timeframe
        w._history_requested = False
        w._pending_history = False
        w._last_history_request_key = None
        w._last_history_success_key = None
        w._stop_live_trendbar()
        w._chart_frozen = True
        w._candles = []
        w.set_candles([])
        w._flush_chart_update()
        if (
            w._oauth_service
            and getattr(w._oauth_service, "status", 0) >= ConnectionStatus.ACCOUNT_AUTHENTICATED
            and w._app_state
            and w._app_state.selected_account_id
        ):
            w._request_recent_history()

    def request_recent_history(self) -> None:
        w = self._window
        if w._account_switch_in_progress:
            return
        if w._history_requested:
            return
        if not w._service:
            w.logRequested.emit("⚠️ App auth service unavailable. Cannot fetch candles.")
            return
        account_id = None if not w._app_state else w._app_state.selected_account_id
        if not account_id:
            w._pending_history = True
            w.logRequested.emit("⏳ Waiting for account selection to fetch candle history")
            return
        w.logRequested.emit(f"➡️ Request history (account_id={account_id}, symbol_id={w._symbol_id})")
        w._pending_history = False
        now = time.time()
        symbol_id = int(w._symbol_id)
        history_count = self.history_lookback_count()
        key = (int(account_id), symbol_id, w._timeframe, history_count)
        if w._last_history_request_key == key and now - w._last_history_request_ts < 10.0:
            return
        timeframe_seconds = max(60, self.timeframe_minutes() * 60)
        success_cooldown = max(30.0, min(300.0, timeframe_seconds / 2.0))
        if w._last_history_success_key == key and now - w._last_history_success_ts < success_cooldown:
            return

        if w._history_service is None:
            w._history_service = w._use_cases.create_trendbar_history(w._service)

        def handle_history(rows: list[dict]) -> None:
            w.historyReceived.emit(rows)

        w._history_service.clear_log_history()

        def handle_error(error: str) -> None:
            w._history_requested = False
            w._awaiting_history_after_symbol_change = False
            w.logRequested.emit(f"❌ History error: {error}")

        w._history_service.set_callbacks(
            on_history_received=handle_history,
            on_error=handle_error,
            on_log=w.logRequested.emit,
        )

        from forex.utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        w._history_requested = True
        w._last_history_request_key = key
        w._last_history_request_ts = now
        reactor.callFromThread(
            w._history_service.fetch,
            account_id=account_id,
            symbol_id=symbol_id,
            count=history_count,
            timeframe=w._timeframe,
        )

    def handle_history_received(self, rows: list[dict]) -> None:
        w = self._window
        if not rows:
            w.logRequested.emit("⚠️ No candle data received")
            w._history_requested = False
            w._awaiting_history_after_symbol_change = False
            return
        digits = w._price_digits
        rows_sorted = sorted(rows, key=lambda r: r.get("utc_timestamp_minutes", 0))
        candles: list[tuple[float, float, float, float, float]] = []
        for row in rows_sorted:
            ts_minutes = float(row.get("utc_timestamp_minutes", 0))
            ts = ts_minutes * 60
            open_price = w._normalize_price(row.get("open", 0), digits=digits)
            high_price = w._normalize_price(row.get("high", 0), digits=digits)
            low_price = w._normalize_price(row.get("low", 0), digits=digits)
            close_price = w._normalize_price(row.get("close", 0), digits=digits)
            if None in (open_price, high_price, low_price, close_price):
                continue
            open_price = round(float(open_price), digits)
            high_price = round(float(high_price), digits)
            low_price = round(float(low_price), digits)
            close_price = round(float(close_price), digits)
            candles.append((ts, float(open_price), float(high_price), float(low_price), float(close_price)))
        previous_last_ts = w._candles[-1][0] if w._candles else None
        w._candles = candles
        w._chart_frozen = False
        w.set_candles(w._candles)
        w._flush_chart_update()
        w.logRequested.emit(f"✅ Loaded {len(candles)} candles")
        w._history_requested = False
        w._awaiting_history_after_symbol_change = False
        if w._app_state and w._app_state.selected_account_id:
            key = (
                int(w._app_state.selected_account_id),
                int(w._symbol_id),
                w._timeframe,
                self.history_lookback_count(),
            )
            w._last_history_success_key = key
            w._last_history_success_ts = time.time()
        if not getattr(w, "_history_only_chart_mode", False):
            self.start_live_trendbar()

        latest_ts = w._candles[-1][0] if w._candles else None
        if (
            getattr(w, "_history_only_chart_mode", False)
            and latest_ts is not None
            and previous_last_ts is not None
            and latest_ts > previous_last_ts
            and getattr(w, "_auto_enabled", False)
        ):
            w._run_auto_trade_on_close()

    def history_lookback_count(self) -> int:
        # Keep enough bars per timeframe for feature stability and model context.
        mapping = {
            "M1": 200,
            "M2": 200,
            "M3": 200,
            "M4": 200,
            "M5": 200,
            "M10": 220,
            "M15": 240,
            "M30": 260,
            "H1": 300,
            "H4": 300,
            "H12": 300,
            "D1": 240,
            "W1": 220,
            "MN1": 180,
        }
        return mapping.get(self._window._timeframe, 200)

    def start_live_trendbar(self) -> None:
        w = self._window
        if getattr(w, "_history_only_chart_mode", False):
            return
        if w._trendbar_active:
            return
        if not w._service:
            return
        account_id = None if not w._app_state else w._app_state.selected_account_id
        if not account_id:
            return
        if w._trendbar_service is None:
            w._trendbar_service = w._use_cases.create_trendbar(w._service)

        def handle_trendbar(data: dict) -> None:
            w.trendbarReceived.emit(data)

        w._trendbar_service.clear_log_history()
        w._trendbar_service.set_callbacks(
            on_trendbar=handle_trendbar,
            on_error=lambda e: self.handle_trendbar_error(e),
            on_log=w.logRequested.emit,
        )

        from forex.utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        w._trendbar_active = True
        reactor.callFromThread(
            w._trendbar_service.subscribe,
            account_id=account_id,
            symbol_id=w._symbol_id,
            timeframe=w._timeframe,
        )

    def stop_live_trendbar(self) -> None:
        w = self._window
        if not w._trendbar_service or not w._trendbar_active:
            return
        from forex.utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        reactor.callFromThread(w._trendbar_service.unsubscribe)
        w._trendbar_active = False

    def handle_trendbar_received(self, data: dict) -> None:
        w = self._window
        if not data:
            return
        if not getattr(w, "_logged_first_trendbar", False):
            w._logged_first_trendbar = True
        symbol_id = data.get("symbol_id")
        if symbol_id is not None:
            try:
                if int(symbol_id) != int(w._symbol_id):
                    # Ignore late trendbars from previous symbol subscriptions.
                    return
            except (TypeError, ValueError):
                return
        if symbol_id is not None:
            digits = w._quote_row_digits.get(int(symbol_id), w._price_digits)
        else:
            digits = w._price_digits
        ts_minutes = float(data.get("utc_timestamp_minutes", 0))
        step_minutes = self.timeframe_minutes()
        if step_minutes > 0:
            ts_min_int = int(ts_minutes)
            # Drop malformed trendbars that are not aligned to timeframe boundary.
            if ts_min_int % step_minutes != 0:
                if hasattr(w, "_auto_debug_log"):
                    w._auto_debug_log(
                        f"drop trendbar: misaligned bucket ts={ts_min_int} step={step_minutes}"
                    )
                return
            now_minutes = int(time.time() // 60)
            current_bucket = (now_minutes // step_minutes) * step_minutes
            # Allow slight local/server clock skew; only reject clearly abnormal future buckets.
            max_future_skew = max(step_minutes, 2)
            if ts_min_int > current_bucket + max_future_skew:
                if hasattr(w, "_auto_debug_log"):
                    w._auto_debug_log(
                        "drop trendbar: future bucket "
                        f"ts={ts_min_int} current={current_bucket} skew={max_future_skew}"
                    )
                return
        ts = ts_minutes * 60
        open_price = w._normalize_price(data.get("open", 0), digits=digits)
        high_price = w._normalize_price(data.get("high", 0), digits=digits)
        low_price = w._normalize_price(data.get("low", 0), digits=digits)
        close_price = w._normalize_price(data.get("close", 0), digits=digits)
        if None in (open_price, high_price, low_price, close_price):
            return
        open_price = round(float(open_price), digits)
        high_price = round(float(high_price), digits)
        low_price = round(float(low_price), digits)
        close_price = round(float(close_price), digits)
        candle = (ts, float(open_price), float(high_price), float(low_price), float(close_price))
        appended = False
        if not w._candles:
            w._candles = [candle]
            appended = True
        elif w._candles[-1][0] == candle[0]:
            w._candles[-1] = candle
        elif w._candles[-1][0] < candle[0]:
            self.fill_missing_candles(candle)
            w._candles.append(candle)
            appended = True
        else:
            if hasattr(w, "_auto_debug_log"):
                w._auto_debug_log(
                    "drop trendbar: out-of-order "
                    f"incoming={int(candle[0])} last={int(w._candles[-1][0])}"
                )
            return
        if len(w._candles) > 50:
            w._candles = w._candles[-50:]
        # Mark only validated/accepted trendbars as "alive" feed.
        w._auto_last_trendbar_ts = time.time()
        w.set_candles(w._candles)
        if appended:
            w._run_auto_trade_on_close()

    def handle_trendbar_error(self, error: str) -> None:
        w = self._window
        w._trendbar_active = False
        w.logRequested.emit(f"❌ Live candle error: {error}")

    def fill_missing_candles(self, next_candle: tuple[float, float, float, float, float]) -> None:
        w = self._window
        if not w._candles:
            return
        step_seconds = self.timeframe_minutes() * 60
        last_time = w._candles[-1][0]
        next_time = next_candle[0]
        if step_seconds <= 0 or next_time <= last_time + step_seconds:
            return
        fill_price = w._candles[-1][4]
        t = last_time + step_seconds
        while t < next_time:
            w._candles.append((t, fill_price, fill_price, fill_price, fill_price))
            t += step_seconds

    def timeframe_minutes(self) -> int:
        mapping = {
            "M1": 1,
            "M2": 2,
            "M3": 3,
            "M4": 4,
            "M5": 5,
            "M10": 10,
            "M15": 15,
            "M30": 30,
            "H1": 60,
            "H4": 240,
            "H12": 720,
            "D1": 1440,
            "W1": 10080,
            "MN1": 43200,
        }
        return mapping.get(self._window._timeframe, 1)
