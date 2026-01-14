"""
取得趨勢棒歷史資料服務
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Callable, Optional, Protocol, Sequence

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAGetTrendbarsReq,
    ProtoOASubscribeSpotsReq,
    ProtoOAUnsubscribeSpotsReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType, ProtoOATrendbarPeriod

from broker.base import BaseCallbacks, LogHistoryMixin, OperationStateMixin, build_callbacks
from broker.services.app_auth_service import AppAuthService


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
    取得指定週期的趨勢棒歷史資料
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

    def fetch(self, account_id: int, symbol_id: int, count: int = 100) -> None:
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
        self._period = ProtoOATrendbarPeriod.M5
        self._prepare_request(count, use_seconds=False, window_minutes=count * 5)
        self._ensure_spot_subscription()
        self._await_spot_subscribe = False
        self._maybe_send_request()

    def _prepare_request(self, count: int, *, use_seconds: bool, window_minutes: int) -> None:
        request = ProtoOAGetTrendbarsReq()
        request.ctidTraderAccountId = self._account_id
        request.symbolId = self._symbol_id
        request.period = self._period
        now_ms = int(time.time() * 1000)
        aligned_to = (now_ms // (5 * 60 * 1000)) * (5 * 60 * 1000)
        request.toTimestamp = aligned_to
        request.fromTimestamp = max(0, request.toTimestamp - (window_minutes * 60 * 1000))
        self._last_request_mode = "milliseconds"
        request.count = int(count)
        self._last_request_count = int(count)
        self._last_request_window = int(window_minutes)
        self._pending_request = request

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

        payload = getattr(msg, "payloadType", None)

        if payload == ProtoOAPayloadType.PROTO_OA_SUBSCRIBE_SPOTS_RES:
            self._await_spot_subscribe = False
            self._maybe_send_request()
            return True

        if payload == ProtoOAPayloadType.PROTO_OA_GET_TRENDBARS_RES:
            self._on_history(msg)
            return True

        if payload == ProtoOAPayloadType.PROTO_OA_ERROR_RES:
            self._on_error(msg)
            return True

        return False

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
            )
            self._maybe_send_request()
            return
        if not bars:
            self._log(
                f"⚠️ 歷史資料為空 (symbol={msg.symbolId}, period={msg.period}, "
                f"timestamp={msg.timestamp})"
            )
        history = [self._to_dict(bar) for bar in bars]
        if self._callbacks.on_history_received:
            self._callbacks.on_history_received(history)
        self._cleanup()

    def _to_dict(self, bar: TrendbarMessage) -> dict:
        low = int(bar.low)
        open_price = low + int(bar.deltaOpen)
        close_price = low + int(bar.deltaClose)
        high = low + int(bar.deltaHigh)
        ts = int(bar.utcTimestampInMinutes) * 60
        ts_text = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        return {
            "timestamp": ts_text,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close_price,
        }

    def _on_error(self, msg: ErrorMessage) -> None:
        if "ALREADY_SUBSCRIBED" in f"{msg.errorCode}" or "ALREADY_SUBSCRIBED" in msg.description:
            return
        self._emit_error(f"錯誤 {msg.errorCode}: {msg.description}")
        self._cleanup()

    def _cleanup(self) -> None:
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._unsubscribe_spot()

    def _ensure_spot_subscription(self) -> None:
        if self._account_id is None or self._symbol_id is None:
            return
        request = ProtoOASubscribeSpotsReq()
        request.ctidTraderAccountId = self._account_id
        request.symbolId.append(self._symbol_id)
        request.subscribeToSpotTimestamp = True
        self._client.send(request)
        self._spot_subscribed = True
        self._await_spot_subscribe = True
        self._log(f"📡 已送出報價訂閱：{self._symbol_id}")

    def _unsubscribe_spot(self) -> None:
        if not self._spot_subscribed or self._account_id is None or self._symbol_id is None:
            return
        request = ProtoOAUnsubscribeSpotsReq()
        request.ctidTraderAccountId = self._account_id
        request.symbolId.append(self._symbol_id)
        self._client.send(request)
        self._spot_subscribed = False
