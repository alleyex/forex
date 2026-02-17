"""
Reusable status display widget
"""
from typing import Dict, Tuple
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, Slot

from forex.config.constants import ConnectionStatus
from forex.ui.shared.utils.formatters import format_status_label


class StatusWidget(QLabel):
    """
    Status顯示元件
    
    根據 ConnectionStatus 顯示對應的文字和顏色
    """
    
    # 預設Status對應表
    DEFAULT_STATUS_MAP: Dict[ConnectionStatus, Tuple[str, str]] = {
        ConnectionStatus.DISCONNECTED: ("Disconnected", "color: red"),
        ConnectionStatus.CONNECTING: ("Connecting...", "color: orange"),
        ConnectionStatus.CONNECTED: ("Connected", "color: blue"),
        ConnectionStatus.APP_AUTHENTICATED: ("App authenticated ✓", "color: green"),
        ConnectionStatus.ACCOUNT_AUTHENTICATED: ("Account authenticated ✓", "color: green"),
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
        更新Status顯示
        
        Args:
            status: ConnectionStatus 的整數值
        """
        status_enum = ConnectionStatus(status) if isinstance(status, int) else status
        text, style = self._status_map.get(status_enum, ("Unknown", ""))
        self.setText(format_status_label(text))
        self.setStyleSheet(style)
    
