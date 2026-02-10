"""
Symbol list service
"""
from dataclasses import dataclass
import time
from typing import Callable, Optional, Protocol, Sequence

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOASymbolsListReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType

from forex.infrastructure.broker.base import BaseCallbacks, LogHistoryMixin, OperationStateMixin, build_callbacks
from forex.infrastructure.broker.errors import ErrorCode, error_message
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
from forex.utils.metrics import metrics


class LightSymbolMessage(Protocol):
    symbolId: int
    symbolName: str


class SymbolListMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str
    symbol: Sequence[LightSymbolMessage]


@dataclass
class SymbolListServiceCallbacks(BaseCallbacks):
    on_symbols_received: Optional[Callable[[list], None]] = None


class SymbolListService(
    CTraderRequestLifecycleMixin,
    LogHistoryMixin[SymbolListServiceCallbacks],
    OperationStateMixin,
):
    """
    Fetch symbol list for a given account.
    """

    def __init__(self, app_auth_service: AppAuthService):
        self._app_auth_service = app_auth_service
        self._callbacks = SymbolListServiceCallbacks()
        self._in_progress = False
        self._timeout_tracker = TimeoutTracker(self._on_timeout)
        self._log_history = []
        self._account_id: Optional[int] = None
        self._include_archived = False

    def set_callbacks(
        self,
        on_symbols_received: Optional[Callable[[list], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._callbacks = build_callbacks(
            SymbolListServiceCallbacks,
            on_symbols_received=on_symbols_received,
            on_error=on_error,
            on_log=on_log,
        )
        self._replay_log_history()

    def fetch(
        self,
        account_id: int,
        include_archived: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        if not account_id:
            self._emit_error(error_message(ErrorCode.VALIDATION, "缺少帳戶 ID"))
            return

        if not self._start_operation():
            return

        self._account_id = int(account_id)
        self._include_archived = bool(include_archived)
        self._begin_request_lifecycle(
            timeout_tracker=self._timeout_tracker,
            timeout_seconds=timeout_seconds,
            retry_request=self._retry_request,
            handler=self._handle_message,
            send_request=self._send_request,
        )

    def _send_request(self) -> None:
        request = ProtoOASymbolsListReq()
        request.ctidTraderAccountId = int(self._account_id or 0)
        request.includeArchivedSymbols = bool(self._include_archived)
        self._log(format_request("正在取得 symbol list..."))
        if not self._send_request_with_client(
            request=request,
            timeout_tracker=self._timeout_tracker,
            handler=self._handle_message,
        ):
            return

    def _handle_message(self, client: Client, msg: SymbolListMessage) -> bool:
        if not self._in_progress:
            return False
        return dispatch_payload(
            msg,
            {
                ProtoOAPayloadType.PROTO_OA_SYMBOLS_LIST_RES: self._on_symbols_received,
                ProtoOAPayloadType.PROTO_OA_ERROR_RES: self._on_error,
            },
        )

    def _on_symbols_received(self, msg: SymbolListMessage) -> None:
        self._cleanup_request_lifecycle(timeout_tracker=self._timeout_tracker, handler=self._handle_message)
        symbols = self._parse_symbols(msg.symbol)
        self._log(format_success(f"已接收 symbol: {len(symbols)} 筆"))
        metrics.inc("ctrader.symbol_list.success")
        started_at = getattr(self, "_metrics_started_at", None)
        if started_at is not None:
            metrics.observe("ctrader.symbol_list.latency_s", time.monotonic() - started_at)
        if self._callbacks.on_symbols_received:
            self._callbacks.on_symbols_received(symbols)

    def _on_error(self, msg: SymbolListMessage) -> None:
        self._cleanup_request_lifecycle(timeout_tracker=self._timeout_tracker, handler=self._handle_message)
        metrics.inc("ctrader.symbol_list.error")
        self._emit_error(format_error(msg.errorCode, msg.description))

    def _on_timeout(self) -> None:
        if not self._in_progress:
            return
        self._cleanup_request_lifecycle(timeout_tracker=self._timeout_tracker, handler=self._handle_message)
        metrics.inc("ctrader.symbol_list.timeout")
        self._emit_error(error_message(ErrorCode.TIMEOUT, "取得 symbol list 逾時"))

    def _retry_request(self, attempt: int) -> None:
        if not self._in_progress:
            return
        self._log(format_warning(f"symbol list 逾時，重試第 {attempt} 次"))
        metrics.inc("ctrader.symbol_list.retry")
        self._send_request()

    @staticmethod
    def _parse_symbols(raw_symbols: Sequence[LightSymbolMessage]) -> list:
        symbols: list[dict] = []
        for symbol in raw_symbols:
            symbols.append(
                {
                    "symbol_id": int(getattr(symbol, "symbolId", 0)),
                    "symbol_name": str(getattr(symbol, "symbolName", "")),
                }
            )
        return symbols
