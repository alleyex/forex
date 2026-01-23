"""
可重用的日誌顯示元件
"""
from datetime import datetime
from PySide6.QtCore import Slot
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from ui.utils.formatters import format_timestamped_message


class LogWidget(QWidget):
    """
    日誌顯示元件
    
    提供：
    - 唯讀的文字區域
    - 自動捲動到最新訊息
    - 可選的標題標籤
    """
    
    def __init__(
        self,
        title: str = "連線日誌:",
        parent=None,
        *,
        with_timestamp: bool = False,
        monospace: bool = False,
        font_point_delta: int = 0,
    ):
        super().__init__(parent)
        self._with_timestamp = with_timestamp
        self._monospace = monospace
        self._font_point_delta = font_point_delta
        self._setup_ui(title)
    
    def _setup_ui(self, title: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        if title:
            self._title_label = QLabel(title)
            layout.addWidget(self._title_label)
        
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        if self._monospace:
            font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
            if self._font_point_delta:
                font.setPointSize(max(1, font.pointSize() + self._font_point_delta))
            self._text_edit.setFont(font)
        layout.addWidget(self._text_edit)
    
    @Slot(str)
    def append(self, message: str) -> None:
        """新增訊息並捲動到底部"""
        if self._with_timestamp:
            ts = datetime.now().strftime("%H:%M:%S")
            message = format_timestamped_message(message, ts)
        self._text_edit.append(message)
        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_logs(self) -> None:
        """清除所有日誌"""
        self._text_edit.clear()
