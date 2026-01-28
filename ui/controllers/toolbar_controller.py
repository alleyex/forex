from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow

from ui.layout.toolbar_actions import build_toolbar_actions, ToolbarActions


class ToolbarController(QObject):
    def __init__(
        self,
        *,
        parent: QMainWindow,
        log_visible: bool,
        on_app_auth: Callable[[], None],
        on_oauth: Callable[[], None],
        on_toggle_connection: Callable[[], None],
        on_fetch_account_info: Callable[[], None],
        on_train_ppo: Callable[[], None],
        on_simulation: Callable[[], None],
        on_history_download: Callable[[], None],
        on_toggle_log: Optional[Callable[[bool], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._actions = build_toolbar_actions(parent, log_visible)
        self._actions.action_app_auth.triggered.connect(on_app_auth)
        self._actions.action_oauth.triggered.connect(on_oauth)
        self._actions.action_toggle_connection.triggered.connect(on_toggle_connection)
        self._actions.action_fetch_account_info.triggered.connect(on_fetch_account_info)
        self._actions.action_train_ppo.triggered.connect(on_train_ppo)
        self._actions.action_simulation.triggered.connect(on_simulation)
        self._actions.action_history_download.triggered.connect(on_history_download)
        if on_toggle_log is not None:
            self._actions.action_toggle_log.toggled.connect(on_toggle_log)

    @property
    def actions(self) -> ToolbarActions:
        return self._actions

    @property
    def action_toggle_connection(self) -> QAction:
        return self._actions.action_toggle_connection

    @property
    def action_toggle_log(self) -> QAction:
        return self._actions.action_toggle_log
