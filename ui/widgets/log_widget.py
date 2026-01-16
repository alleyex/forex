"""
可重用的日誌顯示元件
"""
from PySide6.QtWidgets import QTextEdit, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Slot


class LogWidget(QWidget):
    """
    日誌顯示元件
    
    提供：
    - 唯讀的文字區域
    - 自動捲動到最新訊息
    - 可選的標題標籤
    """
    
    def __init__(self, title: str = "連線日誌:", parent=None):
        super().__init__(parent)
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
        layout.addWidget(self._text_edit)
    
    @Slot(str)
    def append(self, message: str) -> None:
        """新增訊息並捲動到底部"""
        self._text_edit.append(message)
        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
