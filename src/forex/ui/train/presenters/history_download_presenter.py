from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from forex.ui.shared.utils.formatters import format_history_message
from forex.ui.train.dialogs.history_download_dialog import HistoryDownloadDialog
from forex.ui.train.state.history_download_state import HistoryDownloadState


class HistoryDownloadPresenter(QObject):
    def __init__(self, state: HistoryDownloadState, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._dialog: HistoryDownloadDialog | None = None

    def set_dialog(self, dialog: HistoryDownloadDialog | None) -> None:
        self._dialog = dialog

    def emit(self, key: str, **kwargs) -> None:
        self._state.log_message.emit(format_history_message(key, **kwargs))

    def emit_async(self, key: str, **kwargs) -> None:
        QTimer.singleShot(0, self._state, lambda: self.emit(key, **kwargs))

    def emit_async_message(self, message: str) -> None:
        QTimer.singleShot(0, self._state, lambda: self._state.log_message.emit(message))

    def update_symbols(self, payload: list[dict]) -> None:
        if self._dialog and self._dialog.isVisible():
            self._dialog.set_symbols(payload)
