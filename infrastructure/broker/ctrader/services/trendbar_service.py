"""
即時 K 線推播服務
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Protocol

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOASubscribeLiveTrendbarReq,
    ProtoOAUnsubscribeLiveTrendbarReq,
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
    訂閱即時 K 線推播
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
        """訂閱即時 K 線"""
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
        self._log(f"📡 已送出 K 線訂閱：{self._symbol_id} (M1)")
        self._start_operation()

    def unsubscribe(self) -> None:
        """取消訂閱即時 K 線"""
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
        self._log(f"🔕 已取消 K 線訂閱：{self._symbol_id} (M1)")

    def _handle_message(self, client: Client, msg: object) -> bool:
        if not self._in_progress:
            return False

        return dispatch_payload(
            msg,
            {
                ProtoOAPayloadType.PROTO_OA_SPOT_EVENT: self._on_spot_event,
                ProtoOAPayloadType.PROTO_OA_SUBSCRIBE_SPOTS_RES: self._on_spot_subscribe_confirmed,
                ProtoOAPayloadType.PROTO_OA_UNSUBSCRIBE_SPOTS_RES: self._on_spot_unsubscribe_confirmed,
                ProtoOAPayloadType.PROTO_OA_SUBSCRIBE_LIVE_TRENDBAR_RES: self._on_trendbar_subscribe_confirmed,
                ProtoOAPayloadType.PROTO_OA_UNSUBSCRIBE_LIVE_TRENDBAR_RES: self._on_trendbar_unsubscribe_confirmed,
                ProtoOAPayloadType.PROTO_OA_ERROR_RES: self._on_error,
            },
        )

    def _on_spot_subscribe_confirmed(self, _msg: object) -> None:
        self._log(
            format_confirm(
                "報價訂閱已確認",
                ProtoOAPayloadType.PROTO_OA_SUBSCRIBE_SPOTS_RES,
            )
        )

    def _on_spot_unsubscribe_confirmed(self, _msg: object) -> None:
        self._log(
            format_confirm(
                "報價退訂已確認",
                ProtoOAPayloadType.PROTO_OA_UNSUBSCRIBE_SPOTS_RES,
            )
        )

    def _on_trendbar_subscribe_confirmed(self, _msg: object) -> None:
        self._log(
            format_confirm(
                "K 線訂閱已確認",
                ProtoOAPayloadType.PROTO_OA_SUBSCRIBE_LIVE_TRENDBAR_RES,
            )
        )

    def _on_trendbar_unsubscribe_confirmed(self, _msg: object) -> None:
        self._log(
            format_confirm(
                "K 線退訂已確認",
                ProtoOAPayloadType.PROTO_OA_UNSUBSCRIBE_LIVE_TRENDBAR_RES,
            )
        )

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
        if is_already_subscribed(msg.errorCode, msg.description):
            return
        self._emit_error(format_error(msg.errorCode, msg.description))

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

    def _unsubscribe_spot(self) -> None:
        send_spot_unsubscribe(
            self._client,
            account_id=self._account_id,
            symbol_id=self._symbol_id,
            log=self._log,
        )
        self._spot_subscribed = False
