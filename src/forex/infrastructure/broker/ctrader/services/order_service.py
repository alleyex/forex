"""
Order service for cTrader.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol
import time
import uuid
import threading

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOANewOrderReq, ProtoOAClosePositionReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
    ProtoOAPayloadType,
    ProtoOAOrderType,
    ProtoOATradeSide,
)

from forex.infrastructure.broker.base import BaseCallbacks, build_callbacks
from forex.infrastructure.broker.ctrader.services.base import CTraderServiceBase
from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from forex.infrastructure.broker.ctrader.services.message_helpers import (
    dispatch_payload,
    format_error,
    format_request,
    format_success,
)
from forex.infrastructure.broker.errors import ErrorCode, error_message


class ExecutionMessage(Protocol):
    payloadType: int
    errorCode: str
    description: str
    ctidTraderAccountId: int
    order: object
    position: object
    deal: object


@dataclass
class OrderServiceCallbacks(BaseCallbacks):
    """OrderService callbacks."""

    on_execution: Optional[Callable[[dict], None]] = None


class OrderService(CTraderServiceBase[OrderServiceCallbacks]):
    """
    Minimal order service (market open + close position).
    """

    def __init__(self, app_auth_service: AppAuthService):
        super().__init__(app_auth_service=app_auth_service, callbacks=OrderServiceCallbacks())
        self._account_id: Optional[int] = None
        self._permission_scope: Optional[int] = None
        self._client_order_id: Optional[str] = None
        self._position_id: Optional[int] = None
        self._last_requested_volume: Optional[int] = None
        self._order_timeout_seconds: int = 20
        self._order_timeout_timer: Optional[threading.Timer] = None
        self._log(f"OrderService loaded from {__file__}")

    def set_callbacks(
        self,
        on_execution: Optional[Callable[[dict], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._callbacks = build_callbacks(
            OrderServiceCallbacks,
            on_execution=on_execution,
            on_error=on_error,
            on_log=on_log,
        )
        self._replay_log_history()

    def set_permission_scope(self, scope: Optional[int]) -> None:
        self._permission_scope = None if scope is None else int(scope)

    def place_market_order(
        self,
        *,
        account_id: int,
        symbol_id: int,
        trade_side: str,
        volume: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        relative_stop_loss: Optional[float] = None,
        relative_take_profit: Optional[float] = None,
        label: Optional[str] = None,
        comment: Optional[str] = None,
        client_order_id: Optional[str] = None,
        slippage_points: Optional[int] = None,
    ) -> Optional[str]:
        if not self._ensure_trade_allowed():
            return None
        if not self._start_operation():
            return None
        self._account_id = int(account_id)
        self._position_id = None
        self._client_order_id = client_order_id or self._generate_client_order_id()

        request = ProtoOANewOrderReq()
        request.ctidTraderAccountId = self._account_id
        request.symbolId = int(symbol_id)
        request.orderType = ProtoOAOrderType.MARKET
        request.tradeSide = (
            ProtoOATradeSide.BUY if trade_side.lower() == "buy" else ProtoOATradeSide.SELL
        )
        self._log(format_request(f"Order raw volume: {volume} ({type(volume).__name__})"))
        normalized_volume = self._normalize_volume(volume)
        self._last_requested_volume = normalized_volume
        if normalized_volume != int(volume):
            self._log(format_request(f"Order volume adjusted: {volume} -> {normalized_volume}"))
        self._log(format_request(f"Order volume final: {normalized_volume}"))
        request.volume = normalized_volume
        if relative_stop_loss is not None:
            request.relativeStopLoss = int(round(relative_stop_loss))
        elif stop_loss is not None:
            request.stopLoss = float(stop_loss)
        if relative_take_profit is not None:
            request.relativeTakeProfit = int(round(relative_take_profit))
        elif take_profit is not None:
            request.takeProfit = float(take_profit)
        if label:
            request.label = str(label)
        if comment:
            request.comment = str(comment)
        request.clientOrderId = self._client_order_id
        if slippage_points is not None:
            request.slippageInPoints = int(slippage_points)

        self._log(format_request("Sending market order..."))
        client = self._get_client_or_error()
        if client is None:
            return None
        self._bind_handler(self._handle_message)
        self._arm_order_timeout()
        client.send(request)
        return self._client_order_id

    def close_position(
        self,
        *,
        account_id: int,
        position_id: int,
        volume: int,
    ) -> bool:
        if not self._ensure_trade_allowed():
            return False
        if not self._start_operation():
            return False
        self._account_id = int(account_id)
        self._position_id = int(position_id)
        self._client_order_id = None

        request = ProtoOAClosePositionReq()
        request.ctidTraderAccountId = self._account_id
        request.positionId = self._position_id
        self._log(format_request(f"Close raw volume: {volume} ({type(volume).__name__})"))
        normalized_volume = self._normalize_volume(volume)
        self._last_requested_volume = normalized_volume
        if normalized_volume != int(volume):
            self._log(format_request(f"Close volume adjusted: {volume} -> {normalized_volume}"))
        self._log(format_request(f"Close volume final: {normalized_volume}"))
        request.volume = normalized_volume
        self._log(format_request("Sending close position..."))
        client = self._get_client_or_error()
        if client is None:
            return False
        self._bind_handler(self._handle_message)
        self._arm_order_timeout()
        client.send(request)
        return True

    def _handle_message(self, client: Client, msg: ExecutionMessage) -> bool:
        if not self._in_progress:
            return False
        return dispatch_payload(
            msg,
            {
                ProtoOAPayloadType.PROTO_OA_EXECUTION_EVENT: self._on_execution_event,
                ProtoOAPayloadType.PROTO_OA_ORDER_ERROR_EVENT: self._on_order_error,
                ProtoOAPayloadType.PROTO_OA_ERROR_RES: self._on_error,
            },
        )

    def _on_execution_event(self, msg: ExecutionMessage) -> None:
        if self._account_id and getattr(msg, "ctidTraderAccountId", None) != self._account_id:
            return

        order = getattr(msg, "order", None)
        position = getattr(msg, "position", None)
        deal = getattr(msg, "deal", None)
        client_order_id = getattr(order, "clientOrderId", None) if order else None
        position_id = getattr(position, "positionId", None) if position else None
        deal_position_id = getattr(deal, "positionId", None) if deal else None

        # Some execution events may omit clientOrderId even for successful fills.
        # Only reject when server explicitly provides a non-matching ID.
        if self._client_order_id and client_order_id and client_order_id != self._client_order_id:
            return
        if self._position_id and position_id not in (self._position_id, None) and deal_position_id != self._position_id:
            return

        self._cancel_order_timeout()
        self._end_operation()
        self._unbind_handler(self._handle_message)
        self._log(format_success("Order executed"))
        if self._callbacks.on_execution:
            self._callbacks.on_execution(
                {
                    "client_order_id": client_order_id,
                    "position_id": position_id or deal_position_id,
                    "order": order,
                    "position": position,
                    "deal": deal,
                    "requested_volume": self._last_requested_volume,
                }
            )

    def _normalize_volume(self, volume: int) -> int:
        try:
            vol = int(volume)
        except (TypeError, ValueError):
            vol = 0
        min_volume = 100000
        step = 100000
        self._log(format_request(f"Normalize volume: input={vol}, min={min_volume}, step={step}"))
        vol = max(vol, min_volume)
        if step > 1:
            vol = (vol // step) * step
            if vol < min_volume:
                vol = min_volume
        return vol

    def _on_order_error(self, msg: ExecutionMessage) -> None:
        self._cancel_order_timeout()
        self._end_operation()
        self._unbind_handler(self._handle_message)
        error_code = getattr(msg, "errorCode", "")
        description = getattr(msg, "description", "")
        order = getattr(msg, "order", None)
        order_volume = getattr(order, "volume", None) if order is not None else None
        order_id = getattr(order, "orderId", None) if order is not None else None
        client_order_id = getattr(order, "clientOrderId", None) if order is not None else None
        if order_volume is not None:
            self._log(format_request(f"Order error volume seen by server: {order_volume}"))
        if order_id is not None or client_order_id is not None:
            self._log(format_request(f"Order error ids: orderId={order_id}, clientOrderId={client_order_id}"))
        self._emit_error(format_error(error_code, description))

    def _on_error(self, msg: ExecutionMessage) -> None:
        self._cancel_order_timeout()
        self._end_operation()
        self._unbind_handler(self._handle_message)
        error_code = getattr(msg, "errorCode", "")
        description = getattr(msg, "description", "")
        self._emit_error(format_error(error_code, description))

    def _ensure_trade_allowed(self) -> bool:
        if self._permission_scope == 0:
            self._emit_error(error_message(ErrorCode.AUTH, "帳戶權限僅檢視，禁止交易"))
            return False
        return True

    @staticmethod
    def _generate_client_order_id() -> str:
        return f"auto-{int(time.time())}-{uuid.uuid4().hex[:6]}"

    def _arm_order_timeout(self) -> None:
        self._cancel_order_timeout()
        timer = threading.Timer(self._order_timeout_seconds, self._on_order_timeout)
        timer.daemon = True
        self._order_timeout_timer = timer
        timer.start()

    def _cancel_order_timeout(self) -> None:
        if self._order_timeout_timer is None:
            return
        try:
            self._order_timeout_timer.cancel()
        except Exception:
            pass
        self._order_timeout_timer = None

    def _on_order_timeout(self) -> None:
        # Safety valve: avoid getting stuck in in_progress forever when
        # broker doesn't send a matching execution/error callback.
        if not self._in_progress:
            return
        self._log(format_error("TIMEOUT", f"Order request timed out after {self._order_timeout_seconds}s"))
        self._end_operation()
        self._unbind_handler(self._handle_message)
