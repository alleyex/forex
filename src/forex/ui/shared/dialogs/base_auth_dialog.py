"""
基礎認證對話框
"""
from dataclasses import dataclass
import json
import os
from typing import Optional

from forex.application.events import EventBus

from PySide6.QtWidgets import QDialog
from PySide6.QtCore import Slot

from forex.ui.shared.widgets.log_widget import LogWidget
from forex.ui.shared.widgets.status_widget import StatusWidget
from forex.ui.shared.utils.formatters import (
    format_log_error,
    format_log_info,
    format_log_ok,
    format_log_warn,
)


@dataclass
class DialogState:
    """共用對話框狀態"""
    in_progress: bool = False


class BaseAuthDialog(QDialog):
    """提供共用 UI 與日誌/狀態功能的基底對話框"""

    def __init__(
        self,
        token_file: str,
        parent=None,
        auto_connect: bool = False,
        event_bus: Optional[EventBus] = None,
    ):
        super().__init__(parent)
        self._token_file = token_file
        self._auto_connect = auto_connect
        self._state = DialogState()
        self._event_bus = event_bus

        self._log_widget: Optional[LogWidget] = None
        self._status_widget: Optional[StatusWidget] = None

        self._connect_common_signals()

        # Defer auto start to subclasses after they finish initialization.

    # ─────────────────────────────────────────────────────────────
    # 共用 UI
    # ─────────────────────────────────────────────────────────────

    def _create_log_widget(self, title: str = "連線日誌:") -> LogWidget:
        self._log_widget = LogWidget(title=title, parent=self)
        return self._log_widget

    def _create_status_widget(self) -> StatusWidget:
        self._status_widget = StatusWidget(parent=self)
        return self._status_widget

    # ─────────────────────────────────────────────────────────────
    # 日誌處理
    # ─────────────────────────────────────────────────────────────

    def _append_log(self, message: str) -> None:
        if self._log_widget is not None:
            self._log_widget.append(message)
        if self._event_bus:
            self._event_bus.publish("log", message)

    def _log_info(self, message: str) -> None:
        self._append_log(format_log_info(message))

    def _log_success(self, message: str) -> None:
        self._append_log(format_log_ok(message))

    def _log_warning(self, message: str) -> None:
        self._append_log(format_log_warn(message))

    def _log_error(self, message: str) -> None:
        self._append_log(format_log_error(message))

    # ─────────────────────────────────────────────────────────────
    # 狀態處理
    # ─────────────────────────────────────────────────────────────

    @Slot(int)
    def _update_status(self, status: int) -> None:
        if self._status_widget is not None:
            self._status_widget.update_status(status)

    # ─────────────────────────────────────────────────────────────
    # 資料處理
    # ─────────────────────────────────────────────────────────────

    def _read_json_file(self) -> Optional[dict]:
        if not os.path.exists(self._token_file):
            return None
        try:
            with open(self._token_file, "r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError as exc:
            self._log_error(f"Token 檔案格式錯誤: {exc}")
        except OSError as exc:
            self._log_error(f"無法讀取 Token 檔案: {exc}")
        return None

    # ─────────────────────────────────────────────────────────────
    # 內部連接
    # ─────────────────────────────────────────────────────────────

    def _connect_common_signals(self) -> None:
        log_signal = getattr(self, "logReceived", None)
        if log_signal is not None and hasattr(log_signal, "connect"):
            log_signal.connect(self._log_info)

        status_signal = getattr(self, "statusChanged", None)
        if status_signal is not None and hasattr(status_signal, "connect"):
            status_signal.connect(self._update_status)

    def _auto_start_if_available(self) -> None:
        start_method = getattr(self, "_start_auth", None)
        if callable(start_method):
            start_method()

    def _maybe_auto_start(self) -> None:
        if self._auto_connect:
            self._auto_start_if_available()
