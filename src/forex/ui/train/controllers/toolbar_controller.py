from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow


@dataclass
class ToolbarActions:
    action_app_auth: QAction
    action_oauth: QAction
    action_toggle_connection: QAction
    action_fetch_account_info: QAction
    action_train_ppo: QAction
    action_simulation: QAction
    action_history_download: QAction
    action_data_check: QAction
    action_toggle_log: QAction


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
        on_data_check: Callable[[], None],
        on_toggle_log: Optional[Callable[[bool], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._actions = self._build_toolbar_actions(parent, log_visible)
        self._actions.action_app_auth.triggered.connect(on_app_auth)
        self._actions.action_oauth.triggered.connect(on_oauth)
        self._actions.action_toggle_connection.triggered.connect(on_toggle_connection)
        self._actions.action_fetch_account_info.triggered.connect(on_fetch_account_info)
        self._actions.action_train_ppo.triggered.connect(on_train_ppo)
        self._actions.action_simulation.triggered.connect(on_simulation)
        self._actions.action_history_download.triggered.connect(on_history_download)
        self._actions.action_data_check.triggered.connect(on_data_check)
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

    def _build_toolbar_actions(
        self,
        main_window: QMainWindow,
        log_visible: bool,
    ) -> ToolbarActions:
        auth_menu = main_window.menuBar().addMenu("認證")

        action_app_auth = auth_menu.addAction("App 認證")
        action_oauth = auth_menu.addAction("OAuth 認證")

        toolbar = main_window.addToolBar("認證")
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        action_toggle_connection = QAction("連線", main_window)
        toolbar.addAction(action_toggle_connection)

        action_fetch_account_info = QAction("帳戶資料", main_window)
        toolbar.addAction(action_fetch_account_info)

        action_train_ppo = QAction("PPO訓練", main_window)
        toolbar.addAction(action_train_ppo)

        action_simulation = QAction("回放", main_window)
        toolbar.addAction(action_simulation)

        action_history_download = QAction("歷史資料", main_window)
        toolbar.addAction(action_history_download)

        action_data_check = QAction("資料檢查", main_window)
        toolbar.addAction(action_data_check)

        action_toggle_log = QAction("日誌", main_window)
        action_toggle_log.setCheckable(True)
        action_toggle_log.setChecked(True)
        toolbar.addAction(action_toggle_log)
        action_toggle_log.setVisible(not log_visible)

        return ToolbarActions(
            action_app_auth=action_app_auth,
            action_oauth=action_oauth,
            action_toggle_connection=action_toggle_connection,
            action_fetch_account_info=action_fetch_account_info,
            action_train_ppo=action_train_ppo,
            action_simulation=action_simulation,
            action_history_download=action_history_download,
            action_data_check=action_data_check,
            action_toggle_log=action_toggle_log,
        )
