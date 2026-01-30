from __future__ import annotations

from PySide6.QtCore import Signal

from ui_train.state.base import StateBase


class HistoryDownloadState(StateBase):
    log_message = Signal(str)
