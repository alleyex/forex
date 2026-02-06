"""
Symbol-by-id service for cTrader.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol, Sequence

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOASymbolByIdReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType

from forex.infrastructure.broker.base import BaseCallbacks, LogHistoryMixin, OperationStateMixin, build_callbacks
from forex.infrastructure.broker.errors import ErrorCode, error_message
from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from forex.infrastructure.broker.ctrader.services.message_helpers import (
    dispatch_payload,
    format_error,
    format_request,
    format_success,
    is_already_subscribed,
)


class FullSymbolMessage(Protocol):
    symbolId: int
    symbolName: str


class SymbolByIdMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str
    symbol: Sequence[FullSymbolMessage]


@dataclass
class SymbolByIdServiceCallbacks(BaseCallbacks):
    on_symbols_received: Optional[Callable[[list], None]] = None


class SymbolByIdService(LogHistoryMixin[SymbolByIdServiceCallbacks], OperationStateMixin):
    """
    Fetch full symbol details by id.
    """

    def __init__(self, app_auth_service: AppAuthService):
        self._app_auth_service = app_auth_service
        self._callbacks = SymbolByIdServiceCallbacks()
        self._in_progress = False
        self._log_history = []
        self._account_id: Optional[int] = None

    def set_callbacks(
        self,
        on_symbols_received: Optional[Callable[[list], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._callbacks = build_callbacks(
            SymbolByIdServiceCallbacks,
            on_symbols_received=on_symbols_received,
            on_error=on_error,
            on_log=on_log,
        )
        self._replay_log_history()

    def fetch(
        self,
        *,
        account_id: int,
        symbol_ids: Sequence[int],
        include_archived: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        if not account_id:
            self._emit_error(error_message(ErrorCode.VALIDATION, "缺少帳戶 ID"))
            return
        if not symbol_ids:
            self._emit_error(error_message(ErrorCode.VALIDATION, "缺少 Symbol ID"))
            return
        if not self._start_operation():
            return
        self._account_id = int(account_id)
        request = ProtoOASymbolByIdReq()
        request.ctidTraderAccountId = self._account_id
        if hasattr(request, "symbolId"):
            for symbol_id in symbol_ids:
                request.symbolId.append(int(symbol_id))
        if hasattr(request, "includeArchivedSymbols"):
            request.includeArchivedSymbols = bool(include_archived)
        self._log(format_request("正在取得 symbol details..."))
        try:
            client: Client = self._app_auth_service.get_client()
        except Exception as exc:
            self._emit_error(str(exc))
            self._end_operation()
            return
        self._app_auth_service.add_message_handler(self._handle_message)
        client.send(request)

    def _handle_message(self, client: Client, msg: SymbolByIdMessage) -> bool:
        if not self._in_progress:
            return False
        return dispatch_payload(
            msg,
            {
                ProtoOAPayloadType.PROTO_OA_SYMBOL_BY_ID_RES: self._on_symbols_received,
                ProtoOAPayloadType.PROTO_OA_ERROR_RES: self._on_error,
            },
        )

    def _on_symbols_received(self, msg: SymbolByIdMessage) -> None:
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        symbols = self._parse_symbols(getattr(msg, "symbol", []))
        self._log(format_success(f"已接收 symbol details: {len(symbols)} 筆"))
        if self._callbacks.on_symbols_received:
            self._callbacks.on_symbols_received(symbols)

    def _on_error(self, msg: SymbolByIdMessage) -> None:
        if is_already_subscribed(msg.errorCode, msg.description):
            return
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._emit_error(format_error(msg.errorCode, msg.description))

    @staticmethod
    def _parse_symbols(raw_symbols: Sequence[FullSymbolMessage]) -> list:
        symbols: list[dict] = []
        for symbol in raw_symbols:
            payload = {
                "symbol_id": int(getattr(symbol, "symbolId", 0)),
                "symbol_name": str(getattr(symbol, "symbolName", "")),
            }
            for key, attr in (
                ("min_volume", "minVolume"),
                ("max_volume", "maxVolume"),
                ("volume_step", "volumeStep"),
                ("lot_size", "lotSize"),
                ("digits", "digits"),
            ):
                value = getattr(symbol, attr, None)
                if value is not None:
                    payload[key] = value
            symbols.append(payload)
        return symbols
