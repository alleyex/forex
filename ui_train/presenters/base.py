from __future__ import annotations

from PySide6.QtCore import QObject


class PresenterBase(QObject):
    def __init__(self, *, parent: QObject, state: QObject) -> None:
        super().__init__(parent)
        self._state = state

    @property
    def state(self) -> QObject:
        return self._state
