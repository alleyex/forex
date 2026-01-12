"""
共用基礎類別和協定定義
"""
from typing import Callable, Optional, TypeVar, Generic
from dataclasses import dataclass
from abc import ABC, abstractmethod

from config.constants import ConnectionStatus


@dataclass
class BaseCallbacks:
    """基礎回調容器，包含日誌和錯誤處理"""
    on_error: Optional[Callable[[str], None]] = None
    on_log: Optional[Callable[[str], None]] = None


class LoggingMixin:
    """
    提供日誌和錯誤發送功能的混入類別
    
    使用此混入的類別必須定義 _callbacks 屬性
    """
    
    _callbacks: BaseCallbacks
    
    def _log(self, message: str) -> None:
        """透過回調函式或 print 輸出日誌"""
        if self._callbacks.on_log:
            self._callbacks.on_log(message)
        else:
            print(message)

    def _emit_error(self, error: str) -> None:
        """透過回調函式發送錯誤"""
        self._log(f"❌ {error}")
        if self._callbacks.on_error:
            self._callbacks.on_error(error)


class StatusMixin:
    """
    提供狀態管理功能的混入類別
    
    使用此混入的類別必須定義：
    - _status 屬性
    - _callbacks 屬性（需包含 on_status_changed）
    """
    
    _status: ConnectionStatus
    _callbacks: object  # 應包含 on_status_changed
    
    def _set_status(self, status: ConnectionStatus) -> None:
        """更新狀態並通知回調"""
        self._status = status
        callback = getattr(self._callbacks, 'on_status_changed', None)
        if callback:
            callback(status)


class OperationStateMixin:
    """
    提供操作狀態管理功能的混入類別
    
    用於追蹤異步操作是否正在進行中
    """
    
    _in_progress: bool = False
    
    @property
    def in_progress(self) -> bool:
        return self._in_progress
    
    def _start_operation(self) -> bool:
        """
        標記操作開始
        
        Returns:
            bool: 若操作成功開始回傳 True，若已在進行中回傳 False
        """
        if self._in_progress:
            return False
        self._in_progress = True
        return True
    
    def _end_operation(self) -> None:
        """標記操作完成"""
        self._in_progress = False


class BaseService(LoggingMixin, StatusMixin, OperationStateMixin, ABC):
    """
    服務基礎類別
    
    整合日誌、狀態管理和操作狀態追蹤功能
    """
    
    def __init__(self):
        self._in_progress = False
        self._status = ConnectionStatus.DISCONNECTED
    
    @property
    def status(self) -> ConnectionStatus:
        return self._status


class BaseAuthService(BaseService):
    """
    認證服務基礎類別
    
    提供訊息處理器註冊功能
    """
    
    def __init__(self):
        super().__init__()
        self._message_handlers: list[Callable[[object, object], bool]] = []
    
    def add_message_handler(self, handler: Callable[[object, object], bool]) -> None:
        """
        註冊額外的訊息處理器
        
        Args:
            handler: 處理函式，回傳 True 表示已處理該訊息
        """
        self._message_handlers.append(handler)
    
    def remove_message_handler(self, handler: Callable[[object, object], bool]) -> None:
        """移除訊息處理器"""
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)
    
    def _dispatch_to_handlers(self, client: object, msg: object) -> bool:
        """
        將訊息分發給已註冊的處理器
        
        Returns:
            bool: 若任一處理器處理了訊息則回傳 True
        """
        handled = False
        for handler in self._message_handlers:
            try:
                if handler(client, msg):
                    handled = True
            except Exception as e:
                self._log(f"⚠️ 訊息處理器錯誤: {e}")
        return handled