from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QTimer

from ui.train.dialogs.history_download_dialog import HistoryDownloadDialog
from ui.train.state.history_download_state import HistoryDownloadState
from ui.shared.utils.formatters import format_history_message


class HistoryDownloadPresenter(QObject):
    def __init__(self, state: HistoryDownloadState, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state = state
        self._dialog: Optional[HistoryDownloadDialog] = None

    def set_dialog(self, dialog: Optional[HistoryDownloadDialog]) -> None:
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
