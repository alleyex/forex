"""
V2: shared base classes and protocol definitions
(Protocol + Generic + type-safe contracts)
"""
from __future__ import annotations

import logging
from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

from forex.config.constants import ConnectionStatus

# --- Type variables ---
TClient = TypeVar("TClient")
TMsg = TypeVar("TMsg")
TCb = TypeVar("TCb", bound="BaseCallbacks")
TCallbacks = TypeVar("TCallbacks", bound="BaseCallbacks")

logger = logging.getLogger(__name__)


# --- Callback dataclass ---
@dataclass
class BaseCallbacks:
    on_error: Callable[[str], None] | None = None
    on_log: Callable[[str], None] | None = None
    on_status_changed: Callable[[ConnectionStatus], None] | None = None


def build_callbacks(callback_cls: type[TCallbacks], **kwargs) -> TCallbacks:
    return callback_cls(**kwargs)


# --- Mixins ---
class LoggingMixin(Generic[TCb]):
    """
    Mixin that provides log and error emission helpers.
    Classes using this mixin must define a _callbacks attribute compatible with BaseCallbacks.
    """

    _callbacks: TCb

    def _log(self, message: str) -> None:
        cb = getattr(self, "_callbacks", None)
        if cb and cb.on_log:
            cb.on_log(message)
        else:
            logger.info(message)

    def _emit_error(self, error: str) -> None:
        self._log(f"❌ {error}")
        cb = getattr(self, "_callbacks", None)
        if cb and cb.on_error:
            cb.on_error(error)


class LogHistoryMixin(LoggingMixin[TCb], Generic[TCb]):
    """Provide log history storage and replay."""

    _log_history: list[str]

    def _log(self, message: str) -> None:
        self._log_history.append(message)
        super()._log(message)

    def _replay_log_history(self) -> None:
        cb = getattr(self, "_callbacks", None)
        if cb and cb.on_log:
            for message in self._log_history:
                cb.on_log(message)

    def clear_log_history(self) -> None:
        self._log_history.clear()


class StatusMixin(Generic[TCb]):
    """
    Mixin that provides status management.
    Requires:
    - _status: ConnectionStatus
    - _callbacks: BaseCallbacks
    """

    _status: ConnectionStatus
    _callbacks: TCb

    def _set_status(self, status: ConnectionStatus) -> None:
        self._status = status
        if self._callbacks.on_status_changed:
            self._callbacks.on_status_changed(status)


class OperationStateMixin:
    """Track whether an async or long-running operation is in progress."""

    _in_progress: bool = False

    @property
    def in_progress(self) -> bool:
        return self._in_progress

    def _start_operation(self) -> bool:
        if self._in_progress:
            return False
        self._in_progress = True
        return True

    def _end_operation(self) -> None:
        self._in_progress = False


class BaseService(LogHistoryMixin[TCb], StatusMixin[TCb], OperationStateMixin, ABC, Generic[TCb]):
    """
    Base service class integrating log, status, and in-progress state.
    """

    _callbacks: TCb
    _status: ConnectionStatus

    def __init__(self, callbacks: TCb | None = None):
        if callbacks is None:
            callbacks = cast(TCb, BaseCallbacks())
        self._log_history = []
        self._callbacks = callbacks
        self._in_progress = False
        self._status = ConnectionStatus.DISCONNECTED

    @property
    def status(self) -> ConnectionStatus:
        return self._status


# --- Auth service: message handlers remain type-safe ---
MessageHandler = Callable[[TClient, TMsg], bool]


class BaseAuthService(BaseService[TCb], Generic[TCb, TClient, TMsg]):
    """
    Base authentication service with type-safe message handler registration.
    """

    def __init__(self, callbacks: TCb | None = None):
        super().__init__(callbacks=callbacks)
        self._message_handlers: list[MessageHandler[TClient, TMsg]] = []

    def add_message_handler(self, handler: MessageHandler[TClient, TMsg]) -> None:
        if handler in self._message_handlers:
            return
        self._message_handlers.append(handler)

    def remove_message_handler(self, handler: MessageHandler[TClient, TMsg]) -> None:
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)

    def clear_message_handlers(self) -> None:
        self._message_handlers.clear()

    def has_message_handler(self, handler: MessageHandler[TClient, TMsg]) -> bool:
        return handler in self._message_handlers

    def message_handler_count(self) -> int:
        return len(self._message_handlers)

    def _dispatch_to_handlers(
        self,
        client: TClient,
        msg: TMsg,
        *,
        stop_on_handled: bool = True,
    ) -> bool:
        """
        Dispatch a message to registered handlers.

        Args:
            stop_on_handled:
                True  -> stop after the first handler returns True.
                False -> let all handlers process the message.

        Returns:
            bool: True if any handler processed the message.
        """
        handled_any = False

        for handler in list(self._message_handlers):  # Copy to avoid mutation during iteration.
            try:
                handled = handler(client, msg)
                if handled:
                    handled_any = True
                    if stop_on_handled:
                        break
            except Exception as e:
                self._log(f"⚠️ Message handler error: {e}")

        return handled_any
