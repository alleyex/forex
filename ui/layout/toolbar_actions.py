from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
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
    action_toggle_log: QAction


def build_toolbar_actions(main_window: QMainWindow, log_visible: bool) -> ToolbarActions:
    auth_menu = main_window.menuBar().addMenu("認證")

    action_app_auth = auth_menu.addAction("App 認證")
    action_oauth = auth_menu.addAction("OAuth 認證")

    toolbar = main_window.addToolBar("認證")
    toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

    action_toggle_connection = QAction("連線", main_window)
    toolbar.addAction(action_toggle_connection)

    action_fetch_account_info = QAction("基本資料", main_window)
    toolbar.addAction(action_fetch_account_info)

    action_train_ppo = QAction("PPO訓練", main_window)
    toolbar.addAction(action_train_ppo)

    action_simulation = QAction("回放", main_window)
    toolbar.addAction(action_simulation)

    action_history_download = QAction("歷史資料", main_window)
    toolbar.addAction(action_history_download)

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
        action_toggle_log=action_toggle_log,
    )
