"""
可重用的狀態顯示元件
"""
from typing import Dict, Tuple
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, Slot

from config.constants import ConnectionStatus


class StatusWidget(QLabel):
    """
    狀態顯示元件
    
    根據 ConnectionStatus 顯示對應的文字和顏色
    """
    
    # 預設狀態對應表
    DEFAULT_STATUS_MAP: Dict[ConnectionStatus, Tuple[str, str]] = {
        ConnectionStatus.DISCONNECTED: ("已斷線", "color: red"),
        ConnectionStatus.CONNECTING: ("連線中...", "color: orange"),
        ConnectionStatus.CONNECTED: ("已連線", "color: blue"),
        ConnectionStatus.APP_AUTHENTICATED: ("應用程式已認證 ✓", "color: green"),
        ConnectionStatus.ACCOUNT_AUTHENTICATED: ("帳戶已認證 ✓", "color: green"),
    }
    
    def __init__(
        self, 
        parent=None, 
        status_map: Dict[ConnectionStatus, Tuple[str, str]] = None
    ):
        super().__init__(parent)
        self._status_map = status_map or self.DEFAULT_STATUS_MAP
        self.setAlignment(Qt.AlignCenter)
        self.update_status(ConnectionStatus.DISCONNECTED)
    
    @Slot(int)
    def update_status(self, status: int) -> None:
        """
        更新狀態顯示
        
        Args:
            status: ConnectionStatus 的整數值
        """
        status_enum = ConnectionStatus(status) if isinstance(status, int) else status
        text, style = self._status_map.get(status_enum, ("未知", ""))
        self.setText(f"狀態: {text}")
        self.setStyleSheet(style)
    
    def set_custom_status(self, text: str, style: str = "") -> None:
        """設定自訂狀態文字和樣式"""
        self.setText(f"狀態: {text}")
        self.setStyleSheet(style)