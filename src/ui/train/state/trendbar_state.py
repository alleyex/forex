from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class TrendbarState(QObject):
    log_message = Signal(str)
    active_changed = Signal(bool)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
