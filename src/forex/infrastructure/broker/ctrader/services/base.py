"""
cTrader service base helpers.
"""
from __future__ import annotations

from typing import Optional, TypeVar, Generic

from ctrader_open_api import Client

from forex.infrastructure.broker.base import BaseService, BaseAuthService, BaseCallbacks

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService


TCb = TypeVar("TCb", bound=BaseCallbacks)
TMsg = TypeVar("TMsg")


class CTraderServiceBase(BaseService[TCb], Generic[TCb]):
    """Base class for cTrader services using an authenticated AppAuthService."""

    def __init__(self, app_auth_service: "AppAuthService", callbacks: Optional[TCb] = None):
        super().__init__(callbacks=callbacks)
        self._app_auth_service = app_auth_service

    def _bind_handler(self, handler) -> None:
        self._app_auth_service.add_message_handler(handler)

    def _unbind_handler(self, handler) -> None:
        self._app_auth_service.remove_message_handler(handler)

    def _get_client_or_error(self) -> Optional[Client]:
        try:
            return self._app_auth_service.get_client()
        except Exception as exc:
            self._emit_error(str(exc))
            self._end_operation()
            return None


class CTraderAuthServiceBase(BaseAuthService[TCb, Client, TMsg], Generic[TCb, TMsg]):
    """Base class for cTrader auth services."""

    def __init__(self, callbacks: Optional[TCb] = None):
        super().__init__(callbacks=callbacks)
