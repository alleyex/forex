"""
cTrader service base helpers.
"""
from __future__ import annotations

import time
from typing import Callable, Optional, Protocol, TypeVar, Generic

from ctrader_open_api import Client

from forex.config.runtime import load_config, retry_policy_from_config
from forex.infrastructure.broker.base import BaseService, BaseAuthService, BaseCallbacks

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService


TCb = TypeVar("TCb", bound=BaseCallbacks)
TMsg = TypeVar("TMsg")


class TimeoutTrackerLike(Protocol):
    def configure_retry(self, policy, _retry_cb: Callable[[int], None]) -> None:
        ...

    def start(self, timeout_seconds: int) -> None:
        ...

    def cancel(self) -> None:
        ...


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


class CTraderRequestLifecycleMixin:
    """Shared request lifecycle helpers for cTrader request/response services."""

    _app_auth_service: "AppAuthService"

    def _begin_request_lifecycle(
        self,
        *,
        timeout_tracker: TimeoutTrackerLike,
        timeout_seconds: Optional[int],
        retry_request: Callable[[int], None],
        handler,
        send_request: Callable[[], None],
    ) -> None:
        runtime = load_config()
        self._metrics_started_at = time.monotonic()
        timeout_tracker.configure_retry(
            retry_policy_from_config(runtime),
            retry_request,
        )
        self._app_auth_service.add_message_handler(handler)
        timeout_tracker.start(timeout_seconds or runtime.request_timeout)
        send_request()

    def _cleanup_request_lifecycle(
        self,
        *,
        timeout_tracker: Optional[TimeoutTrackerLike],
        handler,
    ) -> None:
        self._end_operation()
        self._app_auth_service.remove_message_handler(handler)
        if timeout_tracker is not None:
            timeout_tracker.cancel()

    def _send_request_with_client(
        self,
        *,
        request,
        timeout_tracker: Optional[TimeoutTrackerLike],
        handler,
    ) -> bool:
        try:
            client = self._app_auth_service.get_client()
        except Exception as exc:
            self._emit_error(str(exc))
            self._cleanup_request_lifecycle(timeout_tracker=timeout_tracker, handler=handler)
            return False
        client.send(request)
        return True
