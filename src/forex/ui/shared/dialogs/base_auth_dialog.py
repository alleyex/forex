"""
Base authentication dialog.
"""
import json
import os
from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import QApplication, QDialog

from forex.application.events import EventBus
from forex.ui.shared.utils.formatters import (
    format_log_error,
    format_log_info,
    format_log_ok,
    format_log_warn,
)
from forex.ui.shared.widgets.log_widget import LogWidget
from forex.ui.shared.widgets.status_widget import StatusWidget


@dataclass
class DialogState:
    """Shared dialog state."""
    in_progress: bool = False


class BaseAuthDialog(QDialog):
    """Base dialog with shared UI, logging, and status helpers."""

    uiCallRequested = Signal(object)

    def __init__(
        self,
        token_file: str,
        parent=None,
        auto_connect: bool = False,
        event_bus: EventBus | None = None,
    ):
        super().__init__(parent)
        self._token_file = token_file
        self._auto_connect = auto_connect
        self._state = DialogState()
        self._event_bus = event_bus

        self._log_widget: LogWidget | None = None
        self._status_widget: StatusWidget | None = None

        self._connect_common_signals()

        # Defer auto start to subclasses after they finish initialization.

    # ─────────────────────────────────────────────────────────────
    # Shared UI
    # ─────────────────────────────────────────────────────────────

    def _create_log_widget(self, title: str = "Connection Log:") -> LogWidget:
        self._log_widget = LogWidget(title=title, parent=self)
        return self._log_widget

    def _create_status_widget(self) -> StatusWidget:
        self._status_widget = StatusWidget(parent=self)
        return self._status_widget

    @Slot(object)
    def _run_ui_call(self, callback) -> None:
        if callable(callback):
            callback()

    def _call_on_ui_thread(self, callback) -> None:
        app = QApplication.instance()
        if app is None or QThread.currentThread() == app.thread():
            callback()
            return
        self.uiCallRequested.emit(callback)

    # ─────────────────────────────────────────────────────────────
    # Log handling
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
    # Status handling
    # ─────────────────────────────────────────────────────────────

    @Slot(int)
    def _update_status(self, status: int) -> None:
        if self._status_widget is not None:
            self._status_widget.update_status(status)

    # ─────────────────────────────────────────────────────────────
    # Data handling
    # ─────────────────────────────────────────────────────────────

    def _read_json_file(self) -> dict | None:
        if not os.path.exists(self._token_file):
            return None
        try:
            with open(self._token_file, encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError as exc:
            self._log_error(f"Invalid token file format: {exc}")
        except OSError as exc:
            self._log_error(f"Failed to read token file: {exc}")
        return None

    # ─────────────────────────────────────────────────────────────
    # Internal wiring
    # ─────────────────────────────────────────────────────────────

    def _connect_common_signals(self) -> None:
        self.uiCallRequested.connect(self._run_ui_call)
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
