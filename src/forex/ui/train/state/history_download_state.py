from PySide6.QtCore import Signal

from forex.ui.train.state.base import StateBase


class HistoryDownloadState(StateBase):
    log_message = Signal(str)
