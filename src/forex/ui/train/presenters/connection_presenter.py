from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QLabel

from forex.application.broker.protocols import AppAuthServiceLike, OAuthServiceLike
from forex.application.state import AppState
from forex.config.constants import ConnectionStatus
from forex.ui.shared.utils.formatters import (
    format_app_auth_status,
    format_connection_message,
    format_oauth_status,
)
from forex.ui.shared.widgets.log_widget import LogWidget


class ConnectionPresenter(QObject):
    def __init__(
        self,
        *,
        parent: QObject,
        log_panel: LogWidget,
        app_auth_label: QLabel,
        oauth_label: QLabel,
        toggle_action,
        app_state: Optional[AppState] = None,
        on_app_disconnected: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._log_panel = log_panel
        self._app_auth_label = app_auth_label
        self._oauth_label = oauth_label
        self._toggle_action = toggle_action
        self._app_state = app_state
        self._on_app_disconnected = on_app_disconnected
        self._service: Optional[AppAuthServiceLike] = None
        self._oauth_service: Optional[OAuthServiceLike] = None

    def set_services(
        self,
        service: Optional[AppAuthServiceLike],
        oauth_service: Optional[OAuthServiceLike],
    ) -> None:
        self._service = service
        self._oauth_service = oauth_service

    def refresh_status_labels(self) -> None:
        self._app_auth_label.setText(self._format_app_auth_status())
        self._oauth_label.setText(self._format_oauth_status())
        self._sync_connection_action()

    def handle_log_message(self, message: str) -> None:
        self._log_panel.append(message)

    def handle_app_auth_success(self, _client) -> None:
        self._app_auth_label.setText(self._format_app_auth_status())
        self._log_panel.append(format_connection_message("service_connected"))
        if self._app_state and self._service:
            self._app_state.update_app_status(int(self._service.status))
        self._sync_connection_action()

    def handle_app_auth_status_changed(self, status: ConnectionStatus) -> None:
        self._app_auth_label.setText(self._format_app_auth_status())
        if self._app_state:
            self._app_state.update_app_status(int(status))
        if (
            status == ConnectionStatus.DISCONNECTED
            and self._oauth_service
            and self._oauth_service.status != ConnectionStatus.DISCONNECTED
        ):
            self._oauth_service.disconnect()
            self._oauth_label.setText(self._format_oauth_status())
            if self._on_app_disconnected:
                self._on_app_disconnected()
        self._sync_connection_action()

    def handle_oauth_success(self, _tokens) -> None:
        self._oauth_label.setText(self._format_oauth_status())
        self._log_panel.append(format_connection_message("oauth_connected"))
        if self._app_state and self._oauth_service:
            self._app_state.update_oauth_status(int(self._oauth_service.status))
        self._sync_connection_action()

    def handle_oauth_status_changed(self, status: ConnectionStatus) -> None:
        self._oauth_label.setText(self._format_oauth_status())
        if self._app_state:
            self._app_state.update_oauth_status(int(status))
        self._sync_connection_action()

    def _format_app_auth_status(self) -> str:
        status = None if not self._service else self._service.status
        return format_app_auth_status(status)

    def _format_oauth_status(self) -> str:
        status = None if not self._oauth_service else self._oauth_service.status
        return format_oauth_status(status)

    def _sync_connection_action(self) -> None:
        if self._oauth_service and self._oauth_service.status >= ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._toggle_action.setText("斷線")
        else:
            self._toggle_action.setText("連線")
