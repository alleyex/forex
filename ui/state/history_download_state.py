from __future__ import annotations

from PySide6.QtCore import Signal

from ui.state.base import StateBase


class HistoryDownloadState(StateBase):
    log_message = Signal(str)
