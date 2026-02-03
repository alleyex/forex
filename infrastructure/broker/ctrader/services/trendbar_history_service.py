"""
取得 K 線歷史資料服務
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Callable, Optional, Protocol, Sequence

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAGetTrendbarsReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType, ProtoOATrendbarPeriod

from broker.base import BaseCallbacks, LogHistoryMixin, OperationStateMixin, build_callbacks
from infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from infrastructure.broker.ctrader.services.message_helpers import (
    dispatch_payload,
    format_confirm,
    format_error,
    is_already_subscribed,
)
from infrastructure.broker.ctrader.services.spot_subscription import (
    send_spot_subscribe,
    send_spot_unsubscribe,
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


class TrendbarHistoryService(LogHistoryMixin[TrendbarHistoryCallbacks], OperationStateMixin):
    """
    取得指定週期的 K 線歷史資料
    """

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
        self._spot_subscribed = False
        self._await_spot_subscribe = False
        self._period = ProtoOATrendbarPeriod.M5

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
        count: int = 100000,
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
                window_minutes=count * 5,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        self._ensure_spot_subscription()
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
            request.toTimestamp = aligned_to
        else:
            request.toTimestamp = int(to_ts)
        if from_ts is None:
            request.fromTimestamp = max(0, request.toTimestamp - (window_minutes * 60 * 1000))
        else:
            request.fromTimestamp = int(from_ts)
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
            "M5": "M5",
            "M10": "M10",
            "M15": "M15",
            "H1": "H1",
            "H4": "H4",
            "D1": "D1",
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
        if self._await_spot_subscribe:
            return
        self._client.send(self._pending_request)
        self._log(
            f"📥 取得 M5 歷史資料：{self._last_request_count} 筆 "
            f"({self._last_request_mode}, window={self._last_request_window}, "
            f"from={self._pending_request.fromTimestamp}, to={self._pending_request.toTimestamp})"
        )

    def _handle_message(self, client: Client, msg: object) -> bool:
        if not self._in_progress:
            return False
        return dispatch_payload(
            msg,
            {
                ProtoOAPayloadType.PROTO_OA_SUBSCRIBE_SPOTS_RES: self._on_spot_subscribed,
                ProtoOAPayloadType.PROTO_OA_UNSUBSCRIBE_SPOTS_RES: self._on_spot_unsubscribe_confirmed,
                ProtoOAPayloadType.PROTO_OA_SPOT_EVENT: self._on_spot_event,
                ProtoOAPayloadType.PROTO_OA_GET_TRENDBARS_RES: self._on_history,
                ProtoOAPayloadType.PROTO_OA_ERROR_RES: self._on_error,
            },
        )

    def _on_spot_subscribed(self, _msg: object) -> None:
        self._await_spot_subscribe = False
        self._maybe_send_request()

    def _on_spot_unsubscribe_confirmed(self, _msg: object) -> None:
        self._log(
            format_confirm(
                "報價退訂已確認",
                ProtoOAPayloadType.PROTO_OA_UNSUBSCRIBE_SPOTS_RES,
            )
        )

    def _on_spot_event(self, _msg: object) -> None:
        return

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
            self._period = ProtoOATrendbarPeriod.M1
            self._log("⚠️ M5 為空，改用 M1 嘗試")
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
        ts_minutes = int(bar.utcTimestampInMinutes)
        ts = ts_minutes * 60
        ts_text = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        return {
            "utc_timestamp_minutes": ts_minutes,
            "timestamp": ts_text,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close_price,
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
        self._emit_error(format_error(msg.errorCode, msg.description))
        self._cleanup()

    def _cleanup(self) -> None:
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._unsubscribe_spot()

    def _ensure_spot_subscription(self) -> None:
        if self._account_id is None or self._symbol_id is None:
            return
        send_spot_subscribe(
            self._client,
            account_id=self._account_id,
            symbol_id=self._symbol_id,
            log=self._log,
            subscribe_to_spot_timestamp=True,
        )
        self._spot_subscribed = True
        self._await_spot_subscribe = True

    def _unsubscribe_spot(self) -> None:
        if not self._spot_subscribed or self._account_id is None or self._symbol_id is None:
            return
        send_spot_unsubscribe(
            self._client,
            account_id=self._account_id,
            symbol_id=self._symbol_id,
            log=self._log,
        )
        self._spot_subscribed = False
