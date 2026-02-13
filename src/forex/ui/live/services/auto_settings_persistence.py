from __future__ import annotations

import json


class LiveAutoSettingsPersistence:
    """Handles Auto Trade settings persistence and lot/risk UI mode syncing."""

    def __init__(self, window) -> None:
        self._window = window

    def sync_lot_value_style(self) -> None:
        w = self._window
        if w._lot_risk.isChecked():
            w._lot_value.setSuffix(" %")
            w._lot_value.setSingleStep(0.1)
            w._lot_value.setRange(0.1, 50.0)
        else:
            w._lot_value.setSuffix(" lots")
            w._lot_value.setSingleStep(0.01)
            w._lot_value.setRange(0.01, 100.0)

    def setup(self) -> None:
        w = self._window
        self.load()

        def _bind(widget, signal_name: str):
            signal = getattr(widget, signal_name, None)
            if signal is not None:
                signal.connect(self.save)

        _bind(w._model_path, "textChanged")
        _bind(w._trade_symbol, "currentTextChanged")
        _bind(w._trade_timeframe, "currentTextChanged")
        _bind(w._lot_fixed, "toggled")
        _bind(w._lot_risk, "toggled")
        _bind(w._lot_value, "valueChanged")
        _bind(w._max_positions, "valueChanged")
        _bind(w._stop_loss, "valueChanged")
        _bind(w._take_profit, "valueChanged")
        _bind(w._risk_guard, "toggled")
        _bind(w._max_drawdown, "valueChanged")
        _bind(w._daily_loss, "valueChanged")
        _bind(w._min_signal_interval, "valueChanged")
        _bind(w._slippage_bps, "valueChanged")
        _bind(w._fee_bps, "valueChanged")
        _bind(w._confidence, "valueChanged")
        _bind(w._position_step, "valueChanged")
        _bind(w._near_full_hold, "toggled")
        _bind(w._same_side_rebalance, "toggled")
        _bind(w._scale_lot_by_signal, "toggled")
        _bind(w._auto_debug, "toggled")
        _bind(w._quote_affects_chart, "toggled")

    def save(self) -> None:
        w = self._window
        if w._autotrade_loading:
            return
        payload = {
            "model_path": w._normalize_model_path_text(w._model_path.text().strip()),
            "symbol": w._trade_symbol.currentText(),
            "timeframe": w._trade_timeframe.currentText(),
            "sizing_mode": "risk" if w._lot_risk.isChecked() else "fixed",
            "lot_value": float(w._lot_value.value()),
            "max_positions": int(w._max_positions.value()),
            "stop_loss": float(w._stop_loss.value()),
            "take_profit": float(w._take_profit.value()),
            "risk_guard": bool(w._risk_guard.isChecked()),
            "max_drawdown": float(w._max_drawdown.value()),
            "daily_loss": float(w._daily_loss.value()),
            "min_signal_interval": int(w._min_signal_interval.value()),
            "slippage_bps": float(w._slippage_bps.value()),
            "fee_bps": float(w._fee_bps.value()),
            "confidence": float(w._confidence.value()),
            "position_step": float(w._position_step.value()),
            "near_full_hold": bool(w._near_full_hold.isChecked()),
            "same_side_rebalance": bool(w._same_side_rebalance.isChecked()),
            "scale_lot_by_signal": bool(w._scale_lot_by_signal.isChecked()),
            "debug_logs": bool(w._auto_debug.isChecked()),
            "quote_affects_candles": bool(w._quote_affects_chart.isChecked()),
        }
        try:
            w._autotrade_settings_path.parent.mkdir(parents=True, exist_ok=True)
            w._autotrade_settings_path.write_text(
                json.dumps(payload, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def load(self) -> None:
        w = self._window
        if not w._autotrade_settings_path.exists():
            return
        try:
            data = json.loads(w._autotrade_settings_path.read_text(encoding="utf-8"))
        except Exception:
            return
        w._autotrade_loading = True
        try:
            model_path = str(data.get("model_path", "")).strip()
            if model_path:
                w._model_path.setText(w._normalize_model_path_text(model_path))
            symbol = str(data.get("symbol", "")).strip()
            if symbol:
                idx = w._trade_symbol.findText(symbol)
                if idx >= 0:
                    w._trade_symbol.setCurrentIndex(idx)
            timeframe = str(data.get("timeframe", "")).strip()
            if timeframe:
                idx = w._trade_timeframe.findText(timeframe)
                if idx >= 0:
                    w._trade_timeframe.setCurrentIndex(idx)
            sizing_mode = str(data.get("sizing_mode", "fixed")).lower()
            w._lot_risk.setChecked(sizing_mode == "risk")
            w._lot_fixed.setChecked(sizing_mode != "risk")
            if "lot_value" in data:
                w._lot_value.setValue(float(data.get("lot_value", w._lot_value.value())))
            if "max_positions" in data:
                w._max_positions.setValue(int(data.get("max_positions", w._max_positions.value())))
            if "stop_loss" in data:
                w._stop_loss.setValue(float(data.get("stop_loss", w._stop_loss.value())))
            if "take_profit" in data:
                w._take_profit.setValue(float(data.get("take_profit", w._take_profit.value())))
            if "risk_guard" in data:
                w._risk_guard.setChecked(bool(data.get("risk_guard", False)))
            if "max_drawdown" in data:
                w._max_drawdown.setValue(float(data.get("max_drawdown", w._max_drawdown.value())))
            if "daily_loss" in data:
                w._daily_loss.setValue(float(data.get("daily_loss", w._daily_loss.value())))
            if "min_signal_interval" in data:
                w._min_signal_interval.setValue(
                    int(data.get("min_signal_interval", w._min_signal_interval.value()))
                )
            if "slippage_bps" in data:
                w._slippage_bps.setValue(float(data.get("slippage_bps", w._slippage_bps.value())))
            if "fee_bps" in data:
                w._fee_bps.setValue(float(data.get("fee_bps", w._fee_bps.value())))
            if "confidence" in data:
                w._confidence.setValue(float(data.get("confidence", w._confidence.value())))
            if "position_step" in data:
                w._position_step.setValue(float(data.get("position_step", w._position_step.value())))
            if "near_full_hold" in data:
                w._near_full_hold.setChecked(bool(data.get("near_full_hold", True)))
            if "same_side_rebalance" in data:
                w._same_side_rebalance.setChecked(bool(data.get("same_side_rebalance", False)))
            if "scale_lot_by_signal" in data:
                w._scale_lot_by_signal.setChecked(bool(data.get("scale_lot_by_signal", False)))
            if "debug_logs" in data:
                w._auto_debug.setChecked(bool(data.get("debug_logs", False)))
            if "quote_affects_candles" in data:
                w._quote_affects_chart.setChecked(bool(data.get("quote_affects_candles", False)))
            self.sync_lot_value_style()
        finally:
            w._autotrade_loading = False

