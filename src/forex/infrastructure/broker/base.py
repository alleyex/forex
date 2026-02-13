"""
V2: 共用基礎類別與協定定義（Protocol + Generic + 型別安全）
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import (
    Callable,
    Generic,
    Optional,
    Protocol,
    TypeVar,
    cast,
    runtime_checkable,
)

from abc import ABC

from forex.config.constants import ConnectionStatus


# --- Type variables ---
TClient = TypeVar("TClient")
TMsg = TypeVar("TMsg")
TCb = TypeVar("TCb", bound="StatusCallbacks")
TCallbacks = TypeVar("TCallbacks", bound="BaseCallbacks")

logger = logging.getLogger(__name__)


# --- Callback Protocols (型別安全的回呼介面) ---
@runtime_checkable
class LoggingCallbacks(Protocol):
    on_error: Optional[Callable[[str], None]]
    on_log: Optional[Callable[[str], None]]


@runtime_checkable
class StatusCallbacks(LoggingCallbacks, Protocol):
    on_status_changed: Optional[Callable[[ConnectionStatus], None]]


# 如果你只想要「最小集合」的 callbacks，可以用這個資料類當預設實作
@dataclass
class BaseCallbacks:
    on_error: Optional[Callable[[str], None]] = None
    on_log: Optional[Callable[[str], None]] = None
    on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None


# Backward-compatible alias
DefaultCallbacks = BaseCallbacks


def build_callbacks(callback_cls: type[TCallbacks], **kwargs) -> TCallbacks:
    return callback_cls(**kwargs)


# --- Mixins ---
class LoggingMixin(Generic[TCb]):
    """
    提供日誌和錯誤發送功能的混入類別
    使用此混入的類別必須定義 _callbacks 屬性（符合 StatusCallbacks）
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
    """提供日誌歷史紀錄與回放"""

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
    提供狀態管理功能的混入類別
    需要：
    - _status: ConnectionStatus
    - _callbacks: StatusCallbacks
    """

    _status: ConnectionStatus
    _callbacks: TCb

    def _set_status(self, status: ConnectionStatus) -> None:
        self._status = status
        if self._callbacks.on_status_changed:
            self._callbacks.on_status_changed(status)


class OperationStateMixin:
    """追蹤異步/長操作是否進行中（防止重複觸發）"""

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
    服務基礎類別：整合 log/status/in-progress
    """

    _callbacks: TCb
    _status: ConnectionStatus

    def __init__(self, callbacks: Optional[TCb] = None):
        if callbacks is None:
            callbacks = cast(TCb, BaseCallbacks())
        self._log_history = []
        self._callbacks = callbacks
        self._in_progress = False
        self._status = ConnectionStatus.DISCONNECTED

    @property
    def status(self) -> ConnectionStatus:
        return self._status


# --- Auth service: msg handler 也型別安全 ---
MessageHandler = Callable[[TClient, TMsg], bool]


class BaseAuthService(BaseService[TCb], Generic[TCb, TClient, TMsg]):
    """
    認證服務基礎類別：提供訊息處理器註冊功能（型別安全）
    """

    def __init__(self, callbacks: Optional[TCb] = None):
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

    def _dispatch_to_handlers(self, client: TClient, msg: TMsg, *, stop_on_handled: bool = True) -> bool:
        """
        將訊息分發給已註冊的處理器

        Args:
            stop_on_handled:
                True  -> 任一 handler 回 True 就停止（常見、效率高）
                False -> 讓所有 handler 都有機會處理（做廣播/監聽時用）

        Returns:
            bool: 若任一處理器處理了訊息則回傳 True
        """
        handled_any = False

        for handler in list(self._message_handlers):  # 複製一份，避免迭代時被移除/新增造成問題
            try:
                handled = handler(client, msg)
                if handled:
                    handled_any = True
                    if stop_on_handled:
                        break
            except Exception as e:
                self._log(f"⚠️ 訊息處理器錯誤: {e}")

        return handled_any
