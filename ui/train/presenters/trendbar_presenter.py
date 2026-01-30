from __future__ import annotations

from PySide6.QtCore import QObject

from ui.shared.utils.formatters import format_trendbar_message
from ui.train.presenters.base import PresenterBase
from ui.train.state.trendbar_state import TrendbarState


class TrendbarPresenter(PresenterBase):
    def __init__(self, *, parent: QObject, state: TrendbarState) -> None:
        super().__init__(parent=parent, state=state)

    def log_event(self, event: str, **kwargs) -> None:
        message = format_trendbar_message(event, **kwargs)
        if message:
            self._state.log_message.emit(message)

    def log_raw(self, message: str) -> None:
        if message:
            self._state.log_message.emit(message)

    def set_active(self, active: bool) -> None:
        self._state.active_changed.emit(active)
