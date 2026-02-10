"""
取得 K 線歷史資料服務
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import time
import threading
from typing import Callable, Optional, Protocol, Sequence

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAGetTrendbarsReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType, ProtoOATrendbarPeriod

from forex.infrastructure.broker.base import BaseCallbacks, LogHistoryMixin, OperationStateMixin, build_callbacks
from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from forex.infrastructure.broker.ctrader.services.base import CTraderRequestLifecycleMixin
from forex.infrastructure.broker.ctrader.services.message_helpers import (
    dispatch_payload,
    format_error,
    is_already_subscribed,
    is_non_subscribed_trendbar_unsubscribe,
)


class TrendbarMessage(Protocol):
    period: int
    low: int
    deltaOpen: int
    deltaClose: int
    deltaHigh: int
    utcTimestampInMinutes: int


class TrendbarHistoryMessage(Protocol):
    payloadType: int
    symbolId: int
    period: int
    timestamp: int
    trendbar: Sequence[TrendbarMessage]


class ErrorMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str


@dataclass
class TrendbarHistoryCallbacks(BaseCallbacks):
    """TrendbarHistoryService 的回調函式"""
    on_history_received: Optional[Callable[[list], None]] = None


class TrendbarHistoryService(
    CTraderRequestLifecycleMixin,
    LogHistoryMixin[TrendbarHistoryCallbacks],
    OperationStateMixin,
):
    """
    取得指定週期的 K 線歷史資料
    """

    _MIN_TIMESTAMP_MS = 0
    _MAX_TIMESTAMP_MS = 2147483646000
    _PERIOD_LABELS = {
        ProtoOATrendbarPeriod.M1: "M1",
        ProtoOATrendbarPeriod.M2: "M2",
        ProtoOATrendbarPeriod.M3: "M3",
        ProtoOATrendbarPeriod.M4: "M4",
        ProtoOATrendbarPeriod.M5: "M5",
        ProtoOATrendbarPeriod.M10: "M10",
        ProtoOATrendbarPeriod.M15: "M15",
        ProtoOATrendbarPeriod.M30: "M30",
        ProtoOATrendbarPeriod.H1: "H1",
        ProtoOATrendbarPeriod.H4: "H4",
        ProtoOATrendbarPeriod.H12: "H12",
        ProtoOATrendbarPeriod.D1: "D1",
        ProtoOATrendbarPeriod.W1: "W1",
        ProtoOATrendbarPeriod.MN1: "MN1",
    }

    def __init__(self, app_auth_service: AppAuthService):
        self._app_auth_service = app_auth_service
        self._callbacks = TrendbarHistoryCallbacks()
        self._in_progress = False
        self._log_history = []
        self._client: Optional[Client] = None
        self._retried_wide = False
        self._retried_m1 = False
        self._last_request_count = 0
        self._last_request_mode = "milliseconds"
        self._last_request_window = 0
        self._history_buffer: list[dict] = []
        self._request_ranges: list[tuple[int, int]] = []
        self._current_range: Optional[tuple[int, int]] = None
        self._total_ranges = 0
        self._completed_ranges = 0
        self._period = ProtoOATrendbarPeriod.M5
        self._last_request_ts: float = 0.0
        self._min_request_interval: float = 0.2
        self._send_timer: Optional[threading.Timer] = None
        self._last_pagination_to_ts: Optional[int] = None

    def set_callbacks(
        self,
        on_history_received: Optional[Callable[[list], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        """設定回調函式"""
        self._callbacks = build_callbacks(
            TrendbarHistoryCallbacks,
            on_history_received=on_history_received,
            on_error=on_error,
            on_log=on_log,
        )
        self._replay_log_history()

    def fetch(
        self,
        account_id: int,
        symbol_id: int,
        count: int = 25000,
        timeframe: str = "M5",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> None:
        if not self._start_operation():
            self._log("⚠️ 歷史資料查詢進行中")
            return
        self._account_id = int(account_id)
        self._symbol_id = int(symbol_id)
        self._app_auth_service.add_message_handler(self._handle_message)
        try:
            self._client = self._app_auth_service.get_client()
        except Exception as exc:
            self._emit_error(str(exc))
            self._cleanup()
            return
        self._retried_wide = False
        self._retried_m1 = False
        self._period = self._resolve_period(timeframe)
        self._history_buffer = []
        self._request_ranges = []
        self._current_range = None
        self._total_ranges = 0
        self._completed_ranges = 0
        self._build_ranges(count, from_ts, to_ts)
        if self._request_ranges:
            self._total_ranges = len(self._request_ranges)
            first_range = self._request_ranges.pop(0)
            self._prepare_request(
                count,
                use_seconds=False,
                window_minutes=max(1, int((first_range[1] - first_range[0]) / 60000)),
                from_ts=first_range[0],
                to_ts=first_range[1],
            )
        else:
            self._prepare_request(
                count,
                use_seconds=False,
                window_minutes=count * self._period_minutes(),
                from_ts=from_ts,
                to_ts=to_ts,
            )
        self._maybe_send_request()

    def _prepare_request(
        self,
        count: int,
        *,
        use_seconds: bool,
        window_minutes: int,
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> None:
        request = ProtoOAGetTrendbarsReq()
        request.ctidTraderAccountId = self._account_id
        request.symbolId = self._symbol_id
        request.period = self._period
        if to_ts is None:
            now_ms = int(time.time() * 1000)
            period_ms = max(1, self._period_minutes()) * 60 * 1000
            aligned_to = (now_ms // period_ms) * period_ms
            request.toTimestamp = min(aligned_to, self._MAX_TIMESTAMP_MS)
        else:
            request.toTimestamp = min(max(int(to_ts), self._MIN_TIMESTAMP_MS), self._MAX_TIMESTAMP_MS)
        if from_ts is None:
            request.fromTimestamp = max(self._MIN_TIMESTAMP_MS, request.toTimestamp - (window_minutes * 60 * 1000))
        else:
            request.fromTimestamp = min(max(int(from_ts), self._MIN_TIMESTAMP_MS), self._MAX_TIMESTAMP_MS)
        if request.fromTimestamp > request.toTimestamp:
            request.fromTimestamp = max(
                self._MIN_TIMESTAMP_MS, request.toTimestamp - (window_minutes * 60 * 1000)
            )
        self._last_request_mode = "milliseconds"
        request.count = int(count)
        self._last_request_count = int(count)
        self._last_request_window = int(window_minutes)
        self._pending_request = request
        self._current_range = (request.fromTimestamp, request.toTimestamp)

    @staticmethod
    def _resolve_period(timeframe: str) -> int:
        mapping = {
            "M1": "M1",
            "M2": "M2",
            "M3": "M3",
            "M4": "M4",
            "M5": "M5",
            "M10": "M10",
            "M15": "M15",
            "M30": "M30",
            "H1": "H1",
            "H4": "H4",
            "H12": "H12",
            "D1": "D1",
            "W1": "W1",
            "MN1": "MN1",
        }
        name = mapping.get(timeframe.upper(), "M5")
        return getattr(ProtoOATrendbarPeriod, name, ProtoOATrendbarPeriod.M5)

    def _build_ranges(self, count: int, from_ts: Optional[int], to_ts: Optional[int]) -> None:
        if from_ts is None or to_ts is None or count <= 0:
            return
        period_minutes = self._period_minutes()
        if period_minutes <= 0:
            return
        step_ms = int(count * period_minutes * 60 * 1000)
        if step_ms <= 0:
            return
        start = int(from_ts)
        end = int(to_ts)
        if end <= start:
            return
        ranges: list[tuple[int, int]] = []
        current = start
        while current < end:
            chunk_end = min(end, current + step_ms)
            ranges.append((current, chunk_end))
            current = chunk_end
        self._request_ranges = ranges

    def _period_minutes(self) -> int:
        period_map = {
            ProtoOATrendbarPeriod.M1: 1,
            ProtoOATrendbarPeriod.M2: 2,
            ProtoOATrendbarPeriod.M3: 3,
            ProtoOATrendbarPeriod.M4: 4,
            ProtoOATrendbarPeriod.M5: 5,
            ProtoOATrendbarPeriod.M10: 10,
            ProtoOATrendbarPeriod.M15: 15,
            ProtoOATrendbarPeriod.M30: 30,
            ProtoOATrendbarPeriod.H1: 60,
            ProtoOATrendbarPeriod.H4: 240,
            ProtoOATrendbarPeriod.H12: 720,
            ProtoOATrendbarPeriod.D1: 1440,
            ProtoOATrendbarPeriod.W1: 10080,
            ProtoOATrendbarPeriod.MN1: 43200,
        }
        return period_map.get(self._period, 5)

    def _maybe_send_request(self) -> None:
        if not hasattr(self, "_pending_request"):
            return
        now = time.monotonic()
        elapsed = now - self._last_request_ts
        if elapsed < self._min_request_interval:
            if self._send_timer is not None:
                return
            delay = max(0.0, self._min_request_interval - elapsed)
            self._send_timer = threading.Timer(delay, self._send_pending_request)
            self._send_timer.daemon = True
            self._send_timer.start()
            return
        self._send_pending_request()

    def _send_pending_request(self) -> None:
        if not hasattr(self, "_pending_request"):
            return
        self._send_timer = None
        self._last_request_ts = time.monotonic()
        try:
            self._client.send(self._pending_request)
        except Exception as exc:
            self._emit_error(str(exc))
            self._cleanup()
            return
        period_label = self._period_label()
        self._log(
            f"📥 取得 {period_label} 歷史資料：{self._last_request_count} 筆 "
            f"({self._last_request_mode}, window={self._last_request_window}, "
            f"from={self._pending_request.fromTimestamp}, to={self._pending_request.toTimestamp})"
        )

    def _handle_message(self, client: Client, msg: object) -> bool:
        if not self._in_progress:
            return False
        return dispatch_payload(
            msg,
            {
                ProtoOAPayloadType.PROTO_OA_GET_TRENDBARS_RES: self._on_history,
                ProtoOAPayloadType.PROTO_OA_ERROR_RES: self._on_error,
            },
        )

    def _on_history(self, msg: TrendbarHistoryMessage) -> None:
        bars = list(getattr(msg, "trendbar", []))
        if not bars and not self._retried_wide:
            self._retried_wide = True
            wide_window = 60 * 24 * 14
            self._log("⚠️ 歷史資料為空，改用較大時間區間重新嘗試")
            self._prepare_request(
                self._last_request_count,
                use_seconds=False,
                window_minutes=wide_window,
                from_ts=self._current_range[0] if self._current_range else None,
                to_ts=self._current_range[1] if self._current_range else None,
            )
            self._maybe_send_request()
            return
        if not bars and not self._retried_m1:
            self._retried_m1 = True
            prev_period_label = self._period_label()
            self._period = ProtoOATrendbarPeriod.M1
            self._log(f"⚠️ {prev_period_label} 為空，改用 M1 嘗試")
            self._prepare_request(
                self._last_request_count,
                use_seconds=False,
                window_minutes=self._last_request_count,
                from_ts=self._current_range[0] if self._current_range else None,
                to_ts=self._current_range[1] if self._current_range else None,
            )
            self._maybe_send_request()
            return
        if not bars:
            self._log(
                f"⚠️ 歷史資料為空 (symbol={msg.symbolId}, period={msg.period}, "
                f"timestamp={msg.timestamp})"
            )
        else:
            self._history_buffer.extend(self._to_dict(bar) for bar in bars)

        has_more = bool(getattr(msg, "hasMore", False))
        if has_more and not self._request_ranges and bars:
            oldest_minutes = min(int(bar.utcTimestampInMinutes) for bar in bars)
            oldest_ts = oldest_minutes * 60 * 1000
            if self._last_pagination_to_ts == oldest_ts:
                has_more = False
            else:
                self._last_pagination_to_ts = oldest_ts
                self._prepare_request(
                    self._last_request_count,
                    use_seconds=False,
                    window_minutes=self._last_request_window,
                    from_ts=max(self._MIN_TIMESTAMP_MS, oldest_ts - (self._last_request_window * 60 * 1000)),
                    to_ts=oldest_ts,
                )
                self._maybe_send_request()
                return

        if self._total_ranges:
            self._completed_ranges += 1
            range_text = self._format_range(self._current_range)
            suffix = f" ({range_text})" if range_text else ""
            self._log(f"📦 已完成 {self._completed_ranges}/{self._total_ranges}{suffix}")

        if self._request_ranges:
            next_range = self._request_ranges.pop(0)
            self._prepare_request(
                self._last_request_count,
                use_seconds=False,
                window_minutes=max(1, int((next_range[1] - next_range[0]) / 60000)),
                from_ts=next_range[0],
                to_ts=next_range[1],
            )
            self._maybe_send_request()
            return

        if self._callbacks.on_history_received:
            self._callbacks.on_history_received(self._history_buffer)
        self._cleanup()

    def _to_dict(self, bar: TrendbarMessage) -> dict:
        low = int(bar.low)
        open_price = low + int(bar.deltaOpen)
        close_price = low + int(bar.deltaClose)
        high = low + int(bar.deltaHigh)
        divisor = 100000.0
        ts_minutes = int(bar.utcTimestampInMinutes)
        ts = ts_minutes * 60
        ts_text = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        return {
            "utc_timestamp_minutes": ts_minutes,
            "timestamp": ts_text,
            "open": open_price / divisor,
            "high": high / divisor,
            "low": low / divisor,
            "close": close_price / divisor,
            "volume": int(getattr(bar, "volume", 0)),
            "period": int(getattr(bar, "period", 0)),
        }

    @staticmethod
    def _format_range(range_pair: Optional[tuple[int, int]]) -> str:
        if not range_pair:
            return ""
        start_ms, end_ms = range_pair
        if start_ms is None or end_ms is None:
            return ""
        start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
        return f"{start_dt:%Y-%m-%d} ~ {end_dt:%Y-%m-%d}"

    def _on_error(self, msg: ErrorMessage) -> None:
        if is_already_subscribed(msg.errorCode, msg.description):
            return
        if is_non_subscribed_trendbar_unsubscribe(msg.errorCode, msg.description):
            return
        self._emit_error(format_error(msg.errorCode, msg.description))
        self._cleanup()

    def _cleanup(self) -> None:
        self._cleanup_request_lifecycle(timeout_tracker=None, handler=self._handle_message)
        if self._send_timer is not None:
            self._send_timer.cancel()
            self._send_timer = None

    def _period_label(self) -> str:
        return self._PERIOD_LABELS.get(self._period, f"period={self._period}")
