from __future__ import annotations

from datetime import datetime
import time

from PySide6.QtCore import QTimer

class LiveChartCoordinator:
    """Encapsulates live chart update and range-control behavior."""

    def __init__(self, window) -> None:
        self._window = window

    def set_quote_chart_mode(self, enabled: bool) -> None:
        w = self._window
        ready_fn = getattr(w, "_is_broker_runtime_ready", None)
        runtime_ready = bool(ready_fn()) if callable(ready_fn) else True
        enabled = bool(enabled)
        w._quote_affects_chart_candles = enabled
        w._history_only_chart_mode = not enabled
        if enabled:
            w._auto_log("ℹ️ Quote-candle mode enabled (chart candles can be refined by live feed).")
            w._stop_history_polling()
            if runtime_ready and w._app_state and w._app_state.selected_account_id:
                w._request_recent_history()
                w._start_live_trendbar()
        else:
            w._auto_log("ℹ️ History-only chart mode enabled (recommended for stable model input).")
            w._stop_live_trendbar()
            if runtime_ready and w._app_state and w._app_state.selected_account_id:
                w._request_recent_history()
                w._start_history_polling()

    def set_candles(self, candles: list[tuple[float, float, float, float, float]]) -> None:
        self._window._pending_candles = candles

    def flush_chart_update(self) -> None:
        w = self._window
        if w._pending_candles is None:
            return
        candles = w._pending_candles
        w._pending_candles = None
        if not w._candlestick_item or not w._chart_plot:
            return
        if w._chart_frozen:
            return
        if not candles:
            if w._chart_ready:
                w._candlestick_item.setData([])
                if w._last_price_line:
                    w._last_price_line.hide()
                if w._last_price_label:
                    w._last_price_label.hide()
            return
        if not w._chart_ready:
            w._chart_ready = True
        plot_candles = candles[-50:]
        w._candlestick_item.setData(plot_candles)
        w._chart_plot.enableAutoRange(False, False)
        step_seconds = w._timeframe_minutes() * 60
        if step_seconds <= 0:
            step_seconds = 60
        last_ts = plot_candles[-1][0]
        first_ts = last_ts - (49 * step_seconds)
        if plot_candles[0][0] > first_ts:
            first_ts = plot_candles[0][0]
        right_padding_candles = 4
        right_ts = last_ts + (right_padding_candles * step_seconds)
        w._chart_plot.setXRange(
            first_ts,
            right_ts,
            padding=0.0,
        )
        y_low, y_high = self.compute_chart_y_range(plot_candles)
        w._chart_plot.setYRange(y_low, y_high, padding=0.0)
        w._chart_data_y_low = y_low
        w._chart_data_y_high = y_high
        last_close = plot_candles[-1][4]
        if w._last_price_line:
            w._last_price_line.setValue(last_close)
            w._last_price_line.show()
        if w._last_price_label:
            label = f"{last_close:.{w._price_digits}f}"
            w._last_price_label.setText(label)
            x_offset = step_seconds * 0.8
            y_offset = max(0.0, (y_high - y_low) * 0.015)
            w._last_price_label.setPos(last_ts + x_offset, last_close + y_offset)
            w._last_price_label.show()

    def update_chart_from_quote(self, symbol_id: int, bid, ask, spot_ts) -> None:
        w = self._window
        self.update_chart_last_price_from_quote(symbol_id, bid, ask)
        if not getattr(w, "_quote_affects_chart_candles", False):
            return
        if getattr(w, "_history_only_chart_mode", False):
            return
        if w._trendbar_active:
            self.update_current_candle_from_quote(symbol_id, bid, ask, spot_ts)
            return
        if getattr(w, "_awaiting_history_after_symbol_change", False):
            return
        if w._chart_frozen:
            if w._candles:
                return
            w._chart_frozen = False
        if int(symbol_id) != int(w._symbol_id):
            return
        digits = w._quote_row_digits.get(int(symbol_id), w._price_digits)
        price = self._resolve_quote_price(symbol_id, bid, ask, digits=digits)
        if price is None:
            return
        ts_val = spot_ts
        if ts_val is None or ts_val == 0:
            ts_seconds = int(time.time())
        else:
            try:
                ts_seconds = int(float(ts_val))
            except (TypeError, ValueError):
                ts_seconds = int(time.time())
            if ts_seconds > 10**12:
                ts_seconds = ts_seconds // 1000
        step_seconds = w._timeframe_minutes() * 60
        if step_seconds <= 0:
            step_seconds = 60
        bucket = (ts_seconds // step_seconds) * step_seconds
        price = round(float(price), digits)
        candle = (bucket, price, price, price, price)
        if not w._candles:
            w._candles = [candle]
            self.set_candles(w._candles)
            self.flush_chart_update()
            return
        last_time = w._candles[-1][0]
        if bucket == last_time:
            open_price, high_price, low_price, _ = w._candles[-1][1:5]
            high_price = max(high_price, price)
            low_price = min(low_price, price)
            w._candles[-1] = (bucket, open_price, high_price, low_price, price)
        elif bucket > last_time:
            w._fill_missing_candles(candle)
            w._candles.append(candle)
            if len(w._candles) > 50:
                w._candles = w._candles[-50:]
        else:
            return
        self.set_candles(w._candles)
        self.flush_chart_update()

    def update_current_candle_from_quote(self, symbol_id: int, bid, ask, spot_ts) -> None:
        w = self._window
        if int(symbol_id) != int(w._symbol_id):
            return
        if not w._candles:
            return
        digits = w._quote_row_digits.get(int(symbol_id), w._price_digits)
        price = self._resolve_quote_price(symbol_id, bid, ask, digits=digits)
        if price is None:
            return
        ts_val = spot_ts
        if ts_val is None or ts_val == 0:
            ts_seconds = int(time.time())
        else:
            try:
                ts_seconds = int(float(ts_val))
            except (TypeError, ValueError):
                ts_seconds = int(time.time())
            if ts_seconds > 10**12:
                ts_seconds = ts_seconds // 1000
        step_seconds = w._timeframe_minutes() * 60
        if step_seconds <= 0:
            return
        bucket = (ts_seconds // step_seconds) * step_seconds
        now_bucket = (int(time.time()) // step_seconds) * step_seconds
        if bucket > now_bucket:
            return
        last_time = w._candles[-1][0]
        if bucket < last_time:
            return
        price = round(float(price), digits)
        if bucket > last_time:
            prev_close = w._candles[-1][4]
            open_price = prev_close
            high_price = max(open_price, price)
            low_price = min(open_price, price)
            w._candles.append((bucket, open_price, high_price, low_price, price))
            if len(w._candles) > 50:
                w._candles = w._candles[-50:]
            self.set_candles(w._candles)
            self.flush_chart_update()
            # In quote-candle mode, quote ticks can advance to a new time bucket
            # before trendbar append is observed. Trigger one decision cycle on
            # bucket rollover so auto-trade does not go "quiet" spuriously.
            if getattr(w, "_auto_enabled", False):
                w._run_auto_trade_on_close()
            return
        open_price, high_price, low_price, _close = w._candles[-1][1:5]
        high_price = max(high_price, price)
        low_price = min(low_price, price)
        w._candles[-1] = (last_time, open_price, high_price, low_price, price)
        self.set_candles(w._candles)
        self.flush_chart_update()

    def update_chart_last_price_from_quote(self, symbol_id: int, bid, ask) -> None:
        w = self._window
        if not w._chart_plot or not w._last_price_line or not w._last_price_label:
            return
        if int(symbol_id) != int(w._symbol_id):
            return
        digits = w._quote_row_digits.get(int(symbol_id), w._price_digits)
        live_price = self._resolve_quote_price(symbol_id, bid, ask, digits=digits)
        if live_price is None:
            return
        w._last_price_line.setValue(live_price)
        w._last_price_line.show()
        label = f"{live_price:.{w._price_digits}f}"
        w._last_price_label.setText(label)
        if w._candles:
            step_seconds = w._timeframe_minutes() * 60
            if step_seconds <= 0:
                step_seconds = 60
            x_offset = step_seconds * 0.8
            plot_candles = w._candles[-50:]
            highs = [candle[2] for candle in plot_candles]
            lows = [candle[3] for candle in plot_candles]
            y_offset = (max(highs) - min(lows)) * 0.015 if highs and lows else 0
            w._last_price_label.setPos(
                plot_candles[-1][0] + x_offset,
                live_price + y_offset,
            )
        w._last_price_label.show()

    def _resolve_quote_price(self, symbol_id: int, bid, ask, *, digits: int) -> float | None:
        w = self._window
        symbol_id = int(symbol_id)
        bid_val = w._normalize_price(bid, digits=digits)
        ask_val = w._normalize_price(ask, digits=digits)

        if bid_val is None:
            bid_val = w._quote_last_bid.get(symbol_id)
        if ask_val is None:
            ask_val = w._quote_last_ask.get(symbol_id)

        if bid_val is not None and ask_val is not None:
            return (float(bid_val) + float(ask_val)) / 2.0
        if bid_val is not None:
            return float(bid_val)
        if ask_val is not None:
            return float(ask_val)
        return None

    def handle_chart_range_changed(self, *_args) -> None:
        w = self._window
        if not w._chart_plot or w._chart_adjusting_range:
            return
        if not w._candles:
            return
        y_low = w._chart_data_y_low
        y_high = w._chart_data_y_high
        if y_low is None or y_high is None:
            return
        data_span = max(1e-8, float(y_high) - float(y_low))
        try:
            view_range = w._chart_plot.getViewBox().viewRange()
            current_y_low, current_y_high = view_range[1]
        except Exception:
            return
        current_span = abs(float(current_y_high) - float(current_y_low))
        max_reasonable_span = max(data_span * 1.25, data_span + 1e-6)
        if current_span <= max_reasonable_span:
            return
        w._chart_adjusting_range = True
        try:
            w._chart_plot.setYRange(float(y_low), float(y_high), padding=0.0)
        finally:
            w._chart_adjusting_range = False

    def handle_chart_auto_button_clicked(self, *_args) -> None:
        w = self._window
        w._auto_debug_log("chart auto button clicked; reapply 50-candle range")
        self.reapply_chart_window_from_latest()
        QTimer.singleShot(0, self.reapply_chart_window_from_latest)
        QTimer.singleShot(80, self.reapply_chart_window_from_latest)
        QTimer.singleShot(250, self.reapply_chart_window_from_latest)
        QTimer.singleShot(600, self.reapply_chart_window_from_latest)

    def guard_chart_range(self) -> None:
        w = self._window
        if not w._chart_plot or w._chart_adjusting_range:
            return
        if not w._candles:
            return
        y_low = w._chart_data_y_low
        y_high = w._chart_data_y_high
        if y_low is None or y_high is None:
            y_low, y_high = self.compute_chart_y_range(w._candles[-50:])
            w._chart_data_y_low = y_low
            w._chart_data_y_high = y_high
        data_span = max(1e-8, float(y_high) - float(y_low))
        try:
            view_range = w._chart_plot.getViewBox().viewRange()
            current_y_low, current_y_high = view_range[1]
        except Exception:
            return
        current_span = abs(float(current_y_high) - float(current_y_low))
        min_reasonable = max(data_span * 0.5, data_span - 1e-6)
        max_reasonable = max(data_span * 1.6, data_span + 1e-6)
        if min_reasonable <= current_span <= max_reasonable:
            return
        self.reapply_chart_window_from_latest()

    def reapply_chart_window_from_latest(self) -> None:
        w = self._window
        if not w._chart_plot or not w._candles:
            return
        plot_candles = w._candles[-50:]
        step_seconds = w._timeframe_minutes() * 60
        if step_seconds <= 0:
            step_seconds = 60
        last_ts = plot_candles[-1][0]
        first_ts = last_ts - (49 * step_seconds)
        if plot_candles[0][0] > first_ts:
            first_ts = plot_candles[0][0]
        right_padding_candles = 4
        right_ts = last_ts + (right_padding_candles * step_seconds)
        y_low, y_high = self.compute_chart_y_range(plot_candles)
        w._chart_data_y_low = y_low
        w._chart_data_y_high = y_high
        w._chart_adjusting_range = True
        try:
            w._chart_plot.enableAutoRange(False, False)
            w._chart_plot.setXRange(float(first_ts), float(right_ts), padding=0.0)
            w._chart_plot.setYRange(float(y_low), float(y_high), padding=0.0)
        finally:
            w._chart_adjusting_range = False

    @staticmethod
    def compute_chart_y_range(candles: list[tuple[float, float, float, float, float]]) -> tuple[float, float]:
        lows = [float(c[3]) for c in candles]
        highs = [float(c[2]) for c in candles]
        raw_low = min(lows)
        raw_high = max(highs)
        raw_span = max(1e-8, raw_high - raw_low)

        body_lows = [min(float(c[1]), float(c[4])) for c in candles]
        body_highs = [max(float(c[1]), float(c[4])) for c in candles]
        body_low = min(body_lows)
        body_high = max(body_highs)
        body_span = max(1e-8, body_high - body_low)

        if raw_span > body_span * 4.0:
            pad = max(body_span * 0.35, raw_span * 0.08)
            y_low = body_low - pad
            y_high = body_high + pad
        else:
            pad = raw_span * 0.12
            y_low = raw_low - pad
            y_high = raw_high + pad

        if y_low == y_high:
            pad = max(0.0001, abs(y_low) * 0.0001)
            y_low -= pad
            y_high += pad
        return y_low, y_high
