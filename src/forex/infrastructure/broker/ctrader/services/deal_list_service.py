"""Deal history retrieval service for cTrader."""
from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOADealListReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType, ProtoOATradeSide

from forex.infrastructure.broker.base import (
    BaseCallbacks,
    LogHistoryMixin,
    OperationStateMixin,
    build_callbacks,
)
from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from forex.infrastructure.broker.ctrader.services.base import CTraderRequestLifecycleMixin
from forex.infrastructure.broker.ctrader.services.message_helpers import (
    dispatch_payload,
    format_error,
    format_request,
    format_success,
    format_warning,
)
from forex.infrastructure.broker.ctrader.services.timeout_tracker import TimeoutTracker
from forex.infrastructure.broker.errors import ErrorCode, error_message


class DealCloseDetailMessage(Protocol):
    grossProfit: int | None
    moneyDigits: int | None
    closedVolume: int | None


class DealMessage(Protocol):
    dealId: int | None
    orderId: int | None
    positionId: int | None
    volume: int | None
    filledVolume: int | None
    symbolId: int | None
    createTimestamp: int | None
    executionTimestamp: int | None
    utcLastUpdateTimestamp: int | None
    executionPrice: float | None
    tradeSide: int | None
    dealStatus: int | None
    moneyDigits: int | None
    closePositionDetail: DealCloseDetailMessage | None


class DealListMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str
    ctidTraderAccountId: int
    deal: Sequence[DealMessage]
    hasMore: bool


@dataclass
class DealListServiceCallbacks(BaseCallbacks):
    on_deals_received: Callable[[list[dict]], None] | None = None


class DealListService(
    CTraderRequestLifecycleMixin,
    LogHistoryMixin[DealListServiceCallbacks],
    OperationStateMixin,
):
    """Fetch recent deal history entries for an authenticated trading account."""

    def __init__(self, app_auth_service: AppAuthService):
        self._app_auth_service = app_auth_service
        self._callbacks = DealListServiceCallbacks()
        self._in_progress = False
        self._timeout_tracker = TimeoutTracker(self._on_timeout)
        self._log_history = []
        self._account_id: int | None = None
        self._max_rows: int = 15
        self._from_timestamp: int | None = None
        self._to_timestamp: int | None = None

    def set_callbacks(
        self,
        on_deals_received: Callable[[list[dict]], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self._callbacks = build_callbacks(
            DealListServiceCallbacks,
            on_deals_received=on_deals_received,
            on_error=on_error,
            on_log=on_log,
        )
        self._replay_log_history()

    def fetch(
        self,
        account_id: int,
        *,
        max_rows: int = 15,
        to_timestamp: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        if not account_id:
            self._emit_error(error_message(ErrorCode.VALIDATION, "Missing account ID"))
            return
        if max_rows <= 0:
            self._emit_error(error_message(ErrorCode.VALIDATION, "max_rows must be positive"))
            return
        if not self._start_operation():
            return

        self._account_id = int(account_id)
        self._max_rows = int(max_rows)
        self._to_timestamp = (
            int(to_timestamp) if to_timestamp is not None else int(time.time() * 1000)
        )
        # cTrader's protobuf schema requires a time window for deal history.
        # Use a generous recent window and let maxRows cap the returned entries.
        self._from_timestamp = int(self._to_timestamp - (30 * 24 * 60 * 60 * 1000))
        self._begin_request_lifecycle(
            timeout_tracker=self._timeout_tracker,
            timeout_seconds=timeout_seconds,
            retry_request=self._retry_request,
            handler=self._handle_message,
            send_request=self._send_request,
        )

    def _send_request(self) -> None:
        request = ProtoOADealListReq()
        request.ctidTraderAccountId = int(self._account_id or 0)
        request.maxRows = int(self._max_rows)
        request.fromTimestamp = int(self._from_timestamp or 0)
        if self._to_timestamp is not None:
            request.toTimestamp = int(self._to_timestamp)
        self._log(format_request(f"Fetching trade history: latest {self._max_rows} deals"))
        if not self._send_request_with_client(
            request=request,
            timeout_tracker=self._timeout_tracker,
            handler=self._handle_message,
        ):
            return

    def _handle_message(self, client: Client, msg: DealListMessage) -> bool:
        if not self._in_progress:
            return False
        return dispatch_payload(
            msg,
            {
                ProtoOAPayloadType.PROTO_OA_DEAL_LIST_RES: self._on_deals_received,
                ProtoOAPayloadType.PROTO_OA_ERROR_RES: self._on_error,
            },
        )

    def _on_deals_received(self, msg: DealListMessage) -> None:
        self._cleanup_request_lifecycle(
            timeout_tracker=self._timeout_tracker,
            handler=self._handle_message,
        )
        deals = self._parse_deals(getattr(msg, "deal", []))
        self._log(format_success(f"Received trade history entries: {len(deals)}"))
        if self._callbacks.on_deals_received:
            self._callbacks.on_deals_received(deals)

    def _on_error(self, msg: DealListMessage) -> None:
        self._cleanup_request_lifecycle(
            timeout_tracker=self._timeout_tracker,
            handler=self._handle_message,
        )
        self._emit_error(format_error(msg.errorCode, msg.description))

    def _on_timeout(self) -> None:
        if not self._in_progress:
            return
        self._cleanup_request_lifecycle(
            timeout_tracker=self._timeout_tracker,
            handler=self._handle_message,
        )
        self._emit_error(error_message(ErrorCode.TIMEOUT, "Trade history request timed out"))

    def _retry_request(self, attempt: int) -> None:
        if not self._in_progress:
            return
        self._log(format_warning(f"Trade history timed out, retry attempt {attempt}"))
        self._send_request()

    @staticmethod
    def _parse_deals(raw_deals: Sequence[DealMessage]) -> list[dict]:
        deals: list[dict] = []
        for deal in raw_deals:
            trade_side = getattr(deal, "tradeSide", None)
            if trade_side == ProtoOATradeSide.BUY:
                side_text = "BUY"
            elif trade_side == ProtoOATradeSide.SELL:
                side_text = "SELL"
            else:
                side_text = "-"

            close_detail = getattr(deal, "closePositionDetail", None)
            event = "Close" if close_detail else "Open"
            volume_value = getattr(deal, "filledVolume", None) or getattr(deal, "volume", None) or 0
            execution_ts = (
                getattr(deal, "executionTimestamp", None)
                or getattr(deal, "createTimestamp", None)
                or getattr(deal, "utcLastUpdateTimestamp", None)
            )
            realized_pnl = None
            if close_detail is not None:
                gross_profit = getattr(close_detail, "grossProfit", None)
                money_digits = getattr(close_detail, "moneyDigits", None)
                try:
                    if gross_profit is not None:
                        digits = int(money_digits or 0)
                        realized_pnl = float(gross_profit) / (10**digits) if digits > 0 else float(
                            gross_profit
                        )
                except (TypeError, ValueError):
                    realized_pnl = None
            deals.append(
                {
                    "deal_id": int(getattr(deal, "dealId", 0) or 0),
                    "order_id": int(getattr(deal, "orderId", 0) or 0),
                    "position_id": int(getattr(deal, "positionId", 0) or 0),
                    "symbol_id": int(getattr(deal, "symbolId", 0) or 0),
                    "timestamp": int(execution_ts or 0),
                    "side": side_text,
                    "event": event,
                    "volume": int(volume_value or 0),
                    "execution_price": float(getattr(deal, "executionPrice", 0.0) or 0.0),
                    "realized_pnl": realized_pnl,
                    "deal_status": int(getattr(deal, "dealStatus", 0) or 0),
                }
            )
        deals.sort(key=lambda item: int(item.get("timestamp", 0)), reverse=True)
        return deals
