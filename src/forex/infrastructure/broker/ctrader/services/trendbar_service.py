"""
即時 K 線推播服務
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Callable, Optional, Protocol

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOASubscribeLiveTrendbarReq,
    ProtoOAUnsubscribeLiveTrendbarReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType, ProtoOATrendbarPeriod

from forex.infrastructure.broker.base import BaseCallbacks, LogHistoryMixin, OperationStateMixin, build_callbacks
from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from forex.infrastructure.broker.ctrader.services.message_helpers import (
    dispatch_payload,
    format_confirm,
    format_error,
    format_sent_subscribe,
    format_sent_unsubscribe,
    is_already_subscribed,
)
from forex.infrastructure.broker.ctrader.services.spot_subscription import (
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
        self._period_name: str = "M1"
        self._period_minutes: int = 1
        self._last_bar: Optional[dict] = None
        self._spot_subscribed = False
        self._await_spot_subscribe = False
        self._pending_trendbar_request: Optional[ProtoOASubscribeLiveTrendbarReq] = None
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

    def subscribe(self, account_id: int, symbol_id: int, timeframe: str = "M1") -> None:
        """訂閱即時 K 線"""
        if self._in_progress:
            self.unsubscribe()

        self._account_id = int(account_id)
        self._symbol_id = int(symbol_id)
        self._period_name, self._period, self._period_minutes = self._resolve_period(timeframe)
        self._app_auth_service.add_message_handler(self._handle_message)

        try:
            self._client = self._app_auth_service.get_client()
        except Exception as exc:
            self._emit_error(str(exc))
            self._app_auth_service.remove_message_handler(self._handle_message)
            return

        self._start_operation()
        self._pending_trendbar_request = ProtoOASubscribeLiveTrendbarReq()
        self._pending_trendbar_request.ctidTraderAccountId = self._account_id
        self._pending_trendbar_request.symbolId = self._symbol_id
        self._pending_trendbar_request.period = self._period

        if self._spot_subscribed:
            self._send_trendbar_request()
        else:
            self._await_spot_subscribe = True
            self._ensure_spot_subscription()

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
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._end_operation()
        self._log(
            format_sent_unsubscribe(
                f"已取消 K 線訂閱：{self._symbol_id} ({self._period_name})"
            )
        )

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
        if self._await_spot_subscribe:
            self._await_spot_subscribe = False
            self._send_trendbar_request()

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
        latest = trendbars[-1] if trendbars else None
        if latest is not None and latest.period == self._period:
            self._seed_from_trendbar(latest, msg.symbolId)
            if self._last_bar is not None and self._callbacks.on_trendbar:
                self._callbacks.on_trendbar(self._last_bar)
            return

        updated = self._update_from_spot(msg)
        if updated is None and self._last_bar is None:
            price = self._extract_price(msg)
            bucket = self._extract_bucket_minutes(msg)
            if price is not None and bucket is not None:
                ts = bucket * 60
                ts_text = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M")
                self._last_bar = {
                    "symbol_id": msg.symbolId,
                    "period": self._period_name,
                    "timestamp": ts_text,
                    "utc_timestamp_minutes": bucket,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                }
                self._last_bar_ts = bucket
                updated = dict(self._last_bar)

        if updated is not None and self._callbacks.on_trendbar:
            self._callbacks.on_trendbar(updated)
        return

    def _seed_from_trendbar(self, bar: TrendbarMessage, symbol_id: int) -> None:
        ts_minutes = int(bar.utcTimestampInMinutes)
        if self._last_bar_ts is not None and ts_minutes < self._last_bar_ts:
            return
        self._last_bar_ts = ts_minutes
        low = int(bar.low)
        open_price = low + int(bar.deltaOpen)
        close_price = low + int(bar.deltaClose)
        high = low + int(bar.deltaHigh)
        divisor = 100000.0
        ts = ts_minutes * 60
        ts_text = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M")
        self._last_bar = {
            "symbol_id": symbol_id,
            "period": self._period_name,
            "timestamp": ts_text,
            "utc_timestamp_minutes": ts_minutes,
            "open": open_price / divisor,
            "high": high / divisor,
            "low": low / divisor,
            "close": close_price / divisor,
        }

    def _update_from_spot(self, msg: SpotEventMessage) -> Optional[dict]:
        price = self._extract_price(msg)
        if price is None:
            return None
        ts_minutes = self._extract_bucket_minutes(msg)
        if ts_minutes is None:
            return None
        if self._last_bar is None:
            return None
        if self._last_bar.get("utc_timestamp_minutes") != ts_minutes:
            return None
        self._last_bar["high"] = max(self._last_bar["high"], price)
        self._last_bar["low"] = min(self._last_bar["low"], price)
        self._last_bar["close"] = price
        self._last_bar_ts = ts_minutes
        return dict(self._last_bar)

    @staticmethod
    def _extract_price(msg: SpotEventMessage) -> Optional[float]:
        bid = getattr(msg, "bid", None)
        ask = getattr(msg, "ask", None)
        has_bid = getattr(msg, "hasBid", None)
        has_ask = getattr(msg, "hasAsk", None)
        if has_bid is False:
            bid = None
        if has_ask is False:
            ask = None
        bid_val = float(bid) if bid is not None and bid != 0 else None
        ask_val = float(ask) if ask is not None and ask != 0 else None
        if bid_val is not None and ask_val is not None:
            return (bid_val + ask_val) / 2.0
        if bid_val is not None:
            return bid_val
        if ask_val is not None:
            return ask_val
        return None

    def _extract_bucket_minutes(self, msg: SpotEventMessage) -> Optional[int]:
        ts = getattr(msg, "spotTimestamp", None)
        if ts is None:
            ts = getattr(msg, "timestamp", None)
        if ts is None or int(ts) == 0:
            ts_seconds = int(time.time())
        else:
            ts_seconds = self._normalize_timestamp_seconds(int(ts))
        if ts_seconds <= 0:
            return None
        minutes = ts_seconds // 60
        bucket = (minutes // self._period_minutes) * self._period_minutes
        return int(bucket)

    @staticmethod
    def _normalize_timestamp_seconds(ts: int) -> int:
        if ts > 10**17:
            return ts // 10**9
        if ts > 10**14:
            return ts // 10**6
        if ts > 10**11:
            return ts // 10**3
        return ts

    @staticmethod
    def _resolve_period(timeframe: str) -> tuple[str, int, int]:
        mapping = {
            "M1": (ProtoOATrendbarPeriod.M1, 1),
            "M2": (ProtoOATrendbarPeriod.M2, 2),
            "M3": (ProtoOATrendbarPeriod.M3, 3),
            "M4": (ProtoOATrendbarPeriod.M4, 4),
            "M5": (ProtoOATrendbarPeriod.M5, 5),
            "M10": (ProtoOATrendbarPeriod.M10, 10),
            "M15": (ProtoOATrendbarPeriod.M15, 15),
            "M30": (ProtoOATrendbarPeriod.M30, 30),
            "H1": (ProtoOATrendbarPeriod.H1, 60),
            "H4": (ProtoOATrendbarPeriod.H4, 240),
            "H12": (ProtoOATrendbarPeriod.H12, 720),
            "D1": (ProtoOATrendbarPeriod.D1, 1440),
            "W1": (ProtoOATrendbarPeriod.W1, 10080),
            "MN1": (ProtoOATrendbarPeriod.MN1, 43200),
        }
        name = timeframe.upper()
        if name not in mapping:
            name = "M1"
        period, minutes = mapping[name]
        return name, period, minutes

    def _on_error(self, msg: ErrorMessage) -> None:
        if is_already_subscribed(msg.errorCode, msg.description):
            if self._await_spot_subscribe:
                self._await_spot_subscribe = False
                self._send_trendbar_request()
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

    def _send_trendbar_request(self) -> None:
        if not self._pending_trendbar_request or not self._client:
            return
        self._client.send(self._pending_trendbar_request)
        self._log(
            format_sent_subscribe(
                f"已送出 K 線訂閱：{self._symbol_id} ({self._period_name})"
            )
        )
        self._pending_trendbar_request = None
