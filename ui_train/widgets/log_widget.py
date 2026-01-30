"""
可重用的日誌顯示元件
"""
from datetime import datetime
import re
from PySide6.QtCore import Slot
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QHBoxLayout,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui_train.utils.formatters import format_timestamped_message


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
        self._entries: list[tuple[str, str]] = []
        self._max_entries = 2000
        self._level_pattern = re.compile(r"\[(INFO|OK|WARN|ERROR)\]")
        self._setup_ui(title)
    
    def _setup_ui(self, title: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        if title:
            self._title_label = QLabel(title)
            header.addWidget(self._title_label)

        header.addStretch(1)

        self._level_filter = QComboBox()
        self._level_filter.addItems(["全部", "INFO", "OK", "WARN", "ERROR", "其他"])
        self._level_filter.currentTextChanged.connect(self._apply_filter)
        header.addWidget(self._level_filter)

        self._btn_copy = QToolButton()
        self._btn_copy.setText("複製")
        self._btn_copy.clicked.connect(self._copy_logs)
        header.addWidget(self._btn_copy)

        self._btn_clear = QToolButton()
        self._btn_clear.setText("清除")
        self._btn_clear.clicked.connect(self.clear_logs)
        header.addWidget(self._btn_clear)

        layout.addLayout(header)
        
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
        level = self._extract_level(message)
        self._entries.append((level, message))
        refresh_required = False
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]
            refresh_required = True
        current_filter = self._level_filter.currentText()
        if refresh_required:
            self._apply_filter(current_filter)
            return
        if current_filter == "全部" or current_filter == level:
            self._append_to_view(message)

    def clear_logs(self) -> None:
        """清除所有日誌"""
        self._entries.clear()
        self._text_edit.clear()

    def _extract_level(self, message: str) -> str:
        match = self._level_pattern.search(message)
        if match:
            return match.group(1)
        return "其他"

    def _apply_filter(self, level: str) -> None:
        if level == "全部":
            items = [entry for _, entry in self._entries]
        else:
            items = [entry for entry_level, entry in self._entries if entry_level == level]
        self._text_edit.setPlainText("\n".join(items))
        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_to_view(self, message: str) -> None:
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        if self._text_edit.toPlainText():
            cursor.insertText("\n")
        cursor.insertText(message)
        self._text_edit.setTextCursor(cursor)
        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _copy_logs(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self._text_edit.toPlainText())
