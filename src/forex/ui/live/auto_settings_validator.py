from __future__ import annotations

from typing import List, Tuple


class AutoTradeSettingsValidator:
    """Validates Auto Trade UI settings before starting trading."""

    _TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4"}

    def __init__(self, window) -> None:
        self._window = window

    def validate_start(self) -> Tuple[bool, List[str]]:
        w = self._window
        errors: List[str] = []

        symbol = ""
        timeframe = ""
        try:
            symbol = str(w._trade_symbol.currentText()).strip()
        except Exception:
            pass
        try:
            timeframe = str(w._trade_timeframe.currentText()).strip().upper()
        except Exception:
            pass

        if not symbol:
            errors.append("Symbol is empty.")
        if timeframe not in self._TIMEFRAMES:
            errors.append(f"Unsupported timeframe: {timeframe or '(empty)'}")

        try:
            max_positions = int(w._max_positions.value())
            if max_positions < 1:
                errors.append("Max positions must be >= 1.")
        except Exception:
            errors.append("Invalid Max positions.")

        try:
            min_interval = int(w._min_signal_interval.value())
            if min_interval < 0:
                errors.append("Min interval must be >= 0.")
        except Exception:
            errors.append("Invalid Min interval.")

        try:
            confidence = float(w._confidence.value())
            if not 0.0 <= confidence <= 1.0:
                errors.append("Confidence must be between 0 and 1.")
        except Exception:
            errors.append("Invalid Confidence.")

        try:
            step = float(w._position_step.value())
            if not 0.0 <= step <= 1.0:
                errors.append("Position step must be between 0 and 1.")
        except Exception:
            errors.append("Invalid Position step.")

        try:
            lot_value = float(w._lot_value.value())
            if w._lot_risk.isChecked():
                if lot_value <= 0.0:
                    errors.append("Risk % must be > 0.")
            else:
                if lot_value <= 0.0:
                    errors.append("Fixed lot must be > 0.")
        except Exception:
            errors.append("Invalid Lot / Risk% value.")

        return len(errors) == 0, errors

