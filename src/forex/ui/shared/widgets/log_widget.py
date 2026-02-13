"""
可重用的日誌顯示元件
"""
from datetime import datetime
import time
import re
from PySide6.QtCore import Qt, Signal, Slot, QThread
from PySide6.QtGui import QAction, QColor, QFontDatabase, QIcon, QTextCharFormat, QSyntaxHighlighter
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QLabel,
    QHBoxLayout,
    QPlainTextEdit,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from forex.ui.shared.utils.formatters import format_timestamped_message


class _LogSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document) -> None:
        super().__init__(document)
        self._timestamp_pattern = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]")
        self._level_pattern = re.compile(r"\[(DEBUG|INFO|OK|WARN|ERROR)\]", re.IGNORECASE)

        self._timestamp_format = QTextCharFormat()
        self._timestamp_format.setForeground(QColor("#9AA6B2"))

        self._level_formats: dict[str, QTextCharFormat] = {}
        for level, color in (
            ("DEBUG", "#8FA3B8"),
            ("INFO", "#78B8FF"),
            ("OK", "#5BD28B"),
            ("WARN", "#F1C66D"),
            ("ERROR", "#FF7A7A"),
        ):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(600)
            self._level_formats[level] = fmt

    def highlightBlock(self, text: str) -> None:
        ts_match = self._timestamp_pattern.search(text)
        if ts_match:
            self.setFormat(ts_match.start(), ts_match.end() - ts_match.start(), self._timestamp_format)

        for match in self._level_pattern.finditer(text):
            level = match.group(1).upper()
            fmt = self._level_formats.get(level)
            if fmt is not None:
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class LogWidget(QWidget):
    _FILTER_LEVELS = ["全部", "DEBUG", "INFO", "OK", "WARN", "ERROR", "其他"]
    _EVENT_CATALOG = {
        "request_history",
        "history_requested",
        "history_loaded",
        "unhandled_message",
        "invalid_request",
        "funds_received",
        "heartbeat_sent",
        "quotes_subscribed",
        "symbol_details_request",
        "symbol_details_received",
        "order_executed",
        "decision_input",
        "decision_normalized",
        "strategy_state",
        "same_side_capped",
        "same_side_add_allowed",
        "same_side_hold_near_full",
        "cost_check",
        "volume_scaling",
        "place_order",
        "close_position",
        "signal_throttled",
        "strategy_profile",
        "session_phase",
        "runtime_stalled",
        "runtime_resume",
    }
    appendRequested = Signal(str)
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
        max_entries: int = 100,
    ):
        super().__init__(parent)
        self._with_timestamp = with_timestamp
        self._monospace = monospace
        self._font_point_delta = font_point_delta
        self._entries: list[tuple[str, str]] = []
        self._max_entries = max(1, int(max_entries))
        self._level_pattern = re.compile(r"\[(DEBUG|TRADE|TRADING|INFO|OK|WARN|ERROR)\]", re.IGNORECASE)
        self._history_request_pattern = re.compile(
            r"取得\s+([A-Za-z0-9]+)\s+歷史資料：(\d+)\s+筆\s+\(milliseconds,\s*window=([^,]+),\s*from=([^,]+),\s*to=([^)]+)\)"
        )
        self._request_history_pattern = re.compile(r"Request history\s+\(account_id=(\d+),\s*symbol_id=(\d+)\)")
        self._loaded_candles_pattern = re.compile(r"Loaded\s+(\d+)\s+candles", re.IGNORECASE)
        self._unhandled_type_pattern = re.compile(r"未處理的訊息類型[:：]\s*(\d+)")
        self._error_invalid_pattern = re.compile(r"錯誤\s+INVALID_REQUEST[:：]\s*(.+)", re.IGNORECASE)
        self._strategy_profile_pattern = re.compile(
            r"strategy\s*profile\s*:\s*same-side\s+near-full\s+hold\s*=\s*(ON|OFF)",
            re.IGNORECASE,
        )
        self._current_filter = "全部"
        self._repeat_suppression_window_s = 5.0
        self._last_entry_text = ""
        self._last_entry_ts = 0.0
        self._last_repeat_notice_ts = 0.0
        self._repeat_suppressed_count = 0
        self._setup_ui(title)
        self.appendRequested.connect(self._append_on_ui_thread, Qt.QueuedConnection)
    
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

        self._btn_filter = QToolButton()
        self._btn_filter.setIcon(
            self._resolve_icon(["view-filter", "view-refresh"], QStyle.SP_FileDialogContentsView)
        )
        self._btn_filter.setToolTip("篩選層級：全部")
        self._btn_filter.setPopupMode(QToolButton.InstantPopup)
        self._btn_filter.setAutoRaise(True)
        self._btn_filter.setStyleSheet(
            """
            QToolButton {
                background: transparent;
                border: none;
                padding: 2px;
            }
            QToolButton:hover {
                background: rgba(255, 255, 255, 0.10);
                border-radius: 4px;
            }
            QToolButton:pressed {
                background: rgba(255, 255, 255, 0.16);
                border-radius: 4px;
            }
            """
        )
        self._filter_menu = QMenu(self)
        for level in self._FILTER_LEVELS:
            action = QAction(level, self)
            action.triggered.connect(lambda checked=False, lv=level: self._set_filter(lv))
            self._filter_menu.addAction(action)
        self._btn_filter.setMenu(self._filter_menu)
        header.addWidget(self._btn_filter)

        self._btn_copy = QToolButton()
        self._btn_copy.setIcon(self._resolve_icon(["edit-copy"], QStyle.SP_FileDialogDetailedView))
        self._btn_copy.setToolTip("複製")
        self._btn_copy.setAutoRaise(True)
        self._btn_copy.setStyleSheet(
            """
            QToolButton {
                background: transparent;
                border: none;
                padding: 2px;
            }
            QToolButton:hover {
                background: rgba(255, 255, 255, 0.10);
                border-radius: 4px;
            }
            QToolButton:pressed {
                background: rgba(255, 255, 255, 0.16);
                border-radius: 4px;
            }
            """
        )
        self._btn_copy.clicked.connect(self._copy_logs)
        header.addWidget(self._btn_copy)

        self._btn_clear = QToolButton()
        self._btn_clear.setIcon(self._resolve_icon(["edit-delete", "user-trash"], QStyle.SP_TrashIcon))
        self._btn_clear.setToolTip("清除")
        self._btn_clear.setAutoRaise(True)
        self._btn_clear.setStyleSheet(
            """
            QToolButton {
                background: transparent;
                border: none;
                padding: 2px;
            }
            QToolButton:hover {
                background: rgba(255, 255, 255, 0.10);
                border-radius: 4px;
            }
            QToolButton:pressed {
                background: rgba(255, 255, 255, 0.16);
                border-radius: 4px;
            }
            """
        )
        self._btn_clear.clicked.connect(self.clear_logs)
        header.addWidget(self._btn_clear)

        layout.addLayout(header)
        
        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)
        # Keep each log entry on a single row for stable visual alignment.
        self._text_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._text_edit.setStyleSheet(
            """
            QPlainTextEdit {
                background: #0f1115;
                border: 1px solid #2f3742;
            }
            QPlainTextEdit QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 2px;
            }
            QPlainTextEdit QScrollBar::handle:vertical {
                background: rgba(210, 220, 232, 0.18);
                min-height: 24px;
                border-radius: 4px;
            }
            QPlainTextEdit QScrollBar::handle:vertical:hover {
                background: rgba(210, 220, 232, 0.30);
            }
            QPlainTextEdit QScrollBar::add-line:vertical,
            QPlainTextEdit QScrollBar::sub-line:vertical,
            QPlainTextEdit QScrollBar::add-page:vertical,
            QPlainTextEdit QScrollBar::sub-page:vertical {
                background: transparent;
                height: 0px;
            }
            QPlainTextEdit QScrollBar:horizontal {
                background: transparent;
                height: 8px;
                margin: 2px;
            }
            QPlainTextEdit QScrollBar::handle:horizontal {
                background: rgba(210, 220, 232, 0.18);
                min-width: 24px;
                border-radius: 4px;
            }
            QPlainTextEdit QScrollBar::handle:horizontal:hover {
                background: rgba(210, 220, 232, 0.30);
            }
            QPlainTextEdit QScrollBar::add-line:horizontal,
            QPlainTextEdit QScrollBar::sub-line:horizontal,
            QPlainTextEdit QScrollBar::add-page:horizontal,
            QPlainTextEdit QScrollBar::sub-page:horizontal {
                background: transparent;
                width: 0px;
            }
            """
        )
        if self._monospace:
            font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
            if self._font_point_delta:
                font.setPointSize(max(1, font.pointSize() + self._font_point_delta))
            self._text_edit.setFont(font)
        self._syntax_highlighter = _LogSyntaxHighlighter(self._text_edit.document())
        layout.addWidget(self._text_edit)
    
    @Slot(str)
    def append(self, message: str) -> None:
        if QThread.currentThread() is not self.thread():
            self.appendRequested.emit(message)
            return
        self._append_on_ui_thread(message)

    @Slot(str)
    def _append_on_ui_thread(self, message: str) -> None:
        """新增訊息並捲動到底部"""
        message = self._normalize_message(message)
        if self._with_timestamp:
            ts = datetime.now().strftime("%H:%M:%S")
            message = format_timestamped_message(message, ts)
        if self._should_suppress_repeated_message(message):
            return
        level = self._extract_level(message)
        self._entries.append((level, message))
        refresh_required = False
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]
            refresh_required = True
        current_filter = self._current_filter
        if refresh_required:
            self._apply_filter(current_filter)
            return
        if current_filter == "全部" or current_filter == level:
            self._append_to_view(message)

    def _should_suppress_repeated_message(self, message: str) -> bool:
        now = time.time()
        same_as_last = message == self._last_entry_text
        within_window = (now - self._last_entry_ts) <= self._repeat_suppression_window_s
        self._last_entry_text = message
        self._last_entry_ts = now
        if not (same_as_last and within_window):
            return False
        self._repeat_suppressed_count += 1
        # Emit an occasional summary line instead of flooding identical rows.
        if now - self._last_repeat_notice_ts >= self._repeat_suppression_window_s:
            self._last_repeat_notice_ts = now
            summary = f"[INFO] repeated_message_suppressed | count={self._repeat_suppressed_count}"
            self._entries.append(("INFO", summary))
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries :]
            if self._current_filter == "全部" or self._current_filter == "INFO":
                self._append_to_view(summary)
        return True

    def clear_logs(self) -> None:
        """清除所有日誌"""
        self._entries.clear()
        self._last_entry_text = ""
        self._last_entry_ts = 0.0
        self._last_repeat_notice_ts = 0.0
        self._repeat_suppressed_count = 0
        self._text_edit.clear()

    def _extract_level(self, message: str) -> str:
        match = self._level_pattern.search(message)
        if match:
            level = match.group(1).upper()
            if level in {"TRADING", "TRADE"}:
                return "INFO"
            return level
        text = message.strip()
        lower = text.lower()
        if "[debug]" in lower:
            return "DEBUG"
        if text.startswith(("❌", "🛑")) or "錯誤" in text or "error" in lower:
            return "ERROR"
        if text.startswith(("⚠️", "⚠")) or "warn" in lower:
            return "WARN"
        if text.startswith("✅"):
            return "OK"
        if text.startswith(("ℹ️", "ℹ", "📥", "📡", "🔕", "💓", "📦", "➡️")):
            return "INFO"
        return "其他"

    def _normalize_message(self, message: str) -> str:
        text = str(message or "").strip()
        if not text:
            return text

        level_match = self._level_pattern.search(text)
        if level_match:
            level = level_match.group(1).upper()
            if level in {"TRADING", "TRADE"}:
                level = "INFO"
            body = text[level_match.end() :].strip()
            body = self._normalize_body(body)
            return f"[{level}] {body}"

        body = self._normalize_body(text)
        level = self._extract_level(body)
        if level == "其他":
            level = "INFO"
        return f"[{level}] {body}"

    def _normalize_body(self, text: str) -> str:
        body = text.strip()
        body = re.sub(r"^[^\w\[\]()=:|+-]+\s*", "", body, flags=re.UNICODE)
        body = re.sub(r"\s+", " ", body).strip()

        match = self._request_history_pattern.search(body)
        if match:
            return f"request_history | account_id={match.group(1)} | symbol_id={match.group(2)}"

        match = self._history_request_pattern.search(body)
        if match:
            tf, count, window, from_ts, to_ts = match.groups()
            return (
                "history_requested"
                f" | timeframe={tf} | count={count} | unit=milliseconds"
                f" | window={window} | from={from_ts} | to={to_ts}"
            )

        match = self._loaded_candles_pattern.search(body)
        if match:
            return f"history_loaded | candles={match.group(1)}"

        match = self._unhandled_type_pattern.search(body)
        if match:
            return f"unhandled_message | payload_type={match.group(1)}"

        match = self._error_invalid_pattern.search(body)
        if match:
            return f"invalid_request | detail={match.group(1)}"

        lower = body.lower()
        match = self._strategy_profile_pattern.search(body)
        if match:
            near_full_hold = match.group(1).upper()
            return f"strategy_profile | near_full_hold={near_full_hold} | threshold=0.95"

        if "funds received" in lower:
            return "funds_received"
        if "發送 heartbeat" in body or "sending heartbeat" in lower:
            return "heartbeat_sent"
        if "已送出報價訂閱" in body:
            value = body.split("：", 1)[-1].strip() if "：" in body else body.split(":", 1)[-1].strip()
            return f"quotes_subscribed | symbols={value}"
        if lower.startswith("order executed"):
            return body.replace("Order executed", "order_executed", 1)
        if "正在取得 symbol details" in body:
            return "symbol_details_request"
        if "已接收 symbol details" in body:
            return "symbol_details_received"
        return self._normalize_event_prefix(body)

    def _normalize_event_prefix(self, body: str) -> str:
        if "|" not in body:
            return body
        head, tail = body.split("|", 1)
        raw_event = head.strip()
        raw_event = re.sub(r"^[^\w]+", "", raw_event, flags=re.UNICODE).strip()
        event = raw_event.lower().replace(" ", "_").replace("-", "_")
        event = re.sub(r"[^a-z0-9_]+", "", event)
        event = event.strip("_")
        if event and event in self._EVENT_CATALOG:
            return f"{event} | {tail.strip()}"
        if event:
            return f"unknown_event | raw_event={raw_event} | {tail.strip()}"
        return body

    def _apply_filter(self, level: str) -> None:
        if level == "全部":
            items = [entry for _, entry in self._entries]
        else:
            items = [entry for entry_level, entry in self._entries if entry_level == level]
        self._text_edit.setPlainText("\n".join(items))
        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_to_view(self, message: str) -> None:
        self._text_edit.appendPlainText(message)
        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _copy_logs(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self._text_edit.toPlainText())

    def _set_filter(self, level: str) -> None:
        self._current_filter = level
        self._btn_filter.setToolTip(f"篩選層級：{level}")
        self._apply_filter(level)

    def _resolve_icon(self, theme_names: list[str], fallback: QStyle.StandardPixmap) -> QIcon:
        for theme_name in theme_names:
            icon = QIcon.fromTheme(theme_name)
            if not icon.isNull():
                return icon
        return self.style().standardIcon(fallback)
