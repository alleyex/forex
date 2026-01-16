"""
即時趨勢棒推播服務
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Protocol

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOASubscribeLiveTrendbarReq,
    ProtoOAUnsubscribeLiveTrendbarReq,
    ProtoOASubscribeSpotsReq,
    ProtoOAUnsubscribeSpotsReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType, ProtoOATrendbarPeriod

from broker.base import BaseCallbacks, LogHistoryMixin, OperationStateMixin, build_callbacks
from infrastructure.broker.ctrader.services.app_auth_service import AppAuthService


class TrendbarMessage(Protocol):
    period: int
    low: int
    deltaOpen: int
    deltaClose: int
    deltaHigh: int
    utcTimestampInMinutes: int


class SpotEventMessage(Protocol):
    payloadType: int
    ctidTraderAccountId: int
    symbolId: int
    trendbar: list[TrendbarMessage]


class ErrorMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str


@dataclass
class TrendbarServiceCallbacks(BaseCallbacks):
    """TrendbarService 的回調函式"""
    on_trendbar: Optional[Callable[[dict], None]] = None


class TrendbarService(LogHistoryMixin[TrendbarServiceCallbacks], OperationStateMixin):
    """
    訂閱即時趨勢棒推播
    """

    def __init__(self, app_auth_service: AppAuthService):
        self._app_auth_service = app_auth_service
        self._callbacks = TrendbarServiceCallbacks()
        self._in_progress = False
        self._log_history = []
        self._account_id: Optional[int] = None
        self._symbol_id: Optional[int] = None
        self._period: int = ProtoOATrendbarPeriod.M1
        self._spot_subscribed = False
        self._last_bar_ts: Optional[int] = None
        self._client: Optional[Client] = None

    def set_callbacks(
        self,
        on_trendbar: Optional[Callable[[dict], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        """設定回調函式"""
        self._callbacks = build_callbacks(
            TrendbarServiceCallbacks,
            on_trendbar=on_trendbar,
            on_error=on_error,
            on_log=on_log,
        )
        self._replay_log_history()

    def subscribe(self, account_id: int, symbol_id: int) -> None:
        """訂閱即時趨勢棒"""
        if self._in_progress:
            self.unsubscribe()

        self._account_id = int(account_id)
        self._symbol_id = int(symbol_id)
        self._app_auth_service.add_message_handler(self._handle_message)

        try:
            self._client = self._app_auth_service.get_client()
        except Exception as exc:
            self._emit_error(str(exc))
            self._app_auth_service.remove_message_handler(self._handle_message)
            return

        self._ensure_spot_subscription()

        request = ProtoOASubscribeLiveTrendbarReq()
        request.ctidTraderAccountId = self._account_id
        request.symbolId = self._symbol_id
        request.period = self._period
        self._client.send(request)
        self._log(f"📡 已送出趨勢棒訂閱：{self._symbol_id} (M1)")
        self._start_operation()

    def unsubscribe(self) -> None:
        """取消訂閱即時趨勢棒"""
        if not self._in_progress or self._account_id is None or self._symbol_id is None:
            return
        request = ProtoOAUnsubscribeLiveTrendbarReq()
        request.ctidTraderAccountId = self._account_id
        request.symbolId = self._symbol_id
        request.period = self._period
        try:
            client = self._app_auth_service.get_client()
        except Exception as exc:
            self._emit_error(str(exc))
            self._app_auth_service.remove_message_handler(self._handle_message)
            self._end_operation()
            return
        client.send(request)
        if self._spot_subscribed:
            self._unsubscribe_spot()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._end_operation()
        self._log(f"🔕 已取消趨勢棒訂閱：{self._symbol_id} (M1)")

    def _handle_message(self, client: Client, msg: object) -> bool:
        if not self._in_progress:
            return False

        payload = getattr(msg, "payloadType", None)

        if payload == ProtoOAPayloadType.PROTO_OA_SPOT_EVENT:
            self._on_spot_event(msg)
            return True

        if payload == ProtoOAPayloadType.PROTO_OA_ERROR_RES:
            self._on_error(msg)
            return True

        return False

    def _on_spot_event(self, msg: SpotEventMessage) -> None:
        if self._account_id and msg.ctidTraderAccountId != self._account_id:
            return
        if self._symbol_id and msg.symbolId != self._symbol_id:
            return
        trendbars = list(getattr(msg, "trendbar", []))
        if not trendbars:
            return

        latest = trendbars[-1]
        if latest.period != self._period:
            return
        if self._last_bar_ts == int(latest.utcTimestampInMinutes):
            return
        self._last_bar_ts = int(latest.utcTimestampInMinutes)

        low = int(latest.low)
        open_price = low + int(latest.deltaOpen)
        close_price = low + int(latest.deltaClose)
        high = low + int(latest.deltaHigh)
        ts = int(latest.utcTimestampInMinutes) * 60
        ts_text = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M")

        data = {
            "symbol_id": msg.symbolId,
            "period": "M1",
            "timestamp": ts_text,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close_price,
        }
        if self._callbacks.on_trendbar:
            self._callbacks.on_trendbar(data)

    def _on_error(self, msg: ErrorMessage) -> None:
        if "ALREADY_SUBSCRIBED" in f"{msg.errorCode}" or "ALREADY_SUBSCRIBED" in msg.description:
            return
        self._emit_error(f"錯誤 {msg.errorCode}: {msg.description}")

    def _ensure_spot_subscription(self) -> None:
        if self._account_id is None or self._symbol_id is None:
            return
        request = ProtoOASubscribeSpotsReq()
        request.ctidTraderAccountId = self._account_id
        request.symbolId.append(self._symbol_id)
        request.subscribeToSpotTimestamp = True
        self._client.send(request)
        self._spot_subscribed = True
        self._log(f"📡 已送出報價訂閱：{self._symbol_id}")

    def _unsubscribe_spot(self) -> None:
        request = ProtoOAUnsubscribeSpotsReq()
        request.ctidTraderAccountId = self._account_id
        request.symbolId.append(self._symbol_id)
        self._client.send(request)
        self._spot_subscribed = False
