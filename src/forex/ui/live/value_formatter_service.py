from __future__ import annotations

from datetime import datetime
from typing import Optional

from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATradeSide


class LiveValueFormatterService:
    """Formats prices/timestamps and derives quote-based current price text."""

    def __init__(self, window) -> None:
        self._window = window

    def current_price_text(self, *, symbol_id: Optional[int], side_value: Optional[int]) -> str:
        w = self._window
        if symbol_id is None:
            return "-"
        bid = w._quote_last_bid.get(int(symbol_id))
        ask = w._quote_last_ask.get(int(symbol_id))
        mid = w._quote_last_mid.get(int(symbol_id))
        current = None
        if side_value == ProtoOATradeSide.BUY:
            current = bid if bid else mid
        elif side_value == ProtoOATradeSide.SELL:
            current = ask if ask else mid
        else:
            current = mid
        if current is None:
            return "-"
        digits = w._quote_row_digits.get(int(symbol_id), w._price_digits)
        return self.format_price(current, digits=digits)

    def format_spot_time(self, spot_ts) -> str:
        if spot_ts in (None, 0, "0", "0.0"):
            return datetime.utcnow().strftime("%H:%M:%S")
        try:
            ts_val = float(spot_ts)
        except (TypeError, ValueError):
            return datetime.utcnow().strftime("%H:%M:%S")
        if ts_val > 1e12:
            ts_val = ts_val / 1000.0
        return datetime.utcfromtimestamp(ts_val).strftime("%H:%M:%S")

    def format_time(self, timestamp) -> str:
        if timestamp in (None, 0, "0", "0.0"):
            return datetime.utcnow().strftime("%H:%M:%S")
        try:
            ts_val = float(timestamp)
        except (TypeError, ValueError):
            return datetime.utcnow().strftime("%H:%M:%S")
        if ts_val > 1e12:
            ts_val = ts_val / 1000.0
        return datetime.utcfromtimestamp(ts_val).strftime("%H:%M:%S")

    def normalize_price(self, value, *, digits: Optional[int] = None) -> Optional[float]:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if numeric == 0:
            return 0.0
        is_int_like = isinstance(value, int) or numeric.is_integer()
        if is_int_like:
            if abs(numeric) >= 1_000_000:
                return numeric / 100000.0
            if digits is not None:
                scale = 10 ** digits
                if abs(numeric) >= scale:
                    return numeric / scale
            if abs(numeric) >= 100000:
                return numeric / 100000.0
        if isinstance(value, int):
            return numeric / 100000.0
        return numeric

    def format_price(self, value, *, digits: Optional[int] = None) -> str:
        w = self._window
        normalized = self.normalize_price(value, digits=digits)
        if normalized is None:
            return "-"
        use_digits = w._price_digits if digits is None else digits
        return f"{normalized:.{use_digits}f}"

