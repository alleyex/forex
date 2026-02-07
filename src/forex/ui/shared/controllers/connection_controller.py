from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtWidgets import QMessageBox, QWidget

from forex.application.broker.protocols import AppAuthServiceLike, OAuthServiceLike
from forex.application.broker.use_cases import BrokerUseCases
from forex.config.constants import ConnectionStatus
from forex.config.paths import TOKEN_FILE
from forex.ui.shared.dialogs.app_auth_dialog import AppAuthDialog
from forex.ui.shared.dialogs.oauth_dialog import OAuthDialog
from forex.ui.shared.utils.formatters import format_connection_message


class ConnectionController(QObject):
    logRequested = Signal(str)
    appAuthStatusChanged = Signal(int)
    oauthStatusChanged = Signal(int)
    appAuthSucceeded = Signal(object)
    oauthSucceeded = Signal(object)

    def __init__(
        self,
        *,
        parent: QWidget,
        use_cases: BrokerUseCases,
        app_state=None,
        event_bus=None,
        on_service_ready: Optional[Callable[[AppAuthServiceLike], None]] = None,
        on_oauth_ready: Optional[Callable[[OAuthServiceLike], None]] = None,
        on_reset_controllers: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._parent = parent
        self._use_cases = use_cases
        self._app_state = app_state
        self._event_bus = event_bus
        self._on_service_ready = on_service_ready
        self._on_oauth_ready = on_oauth_ready
        self._on_reset_controllers = on_reset_controllers
        self._service: Optional[AppAuthServiceLike] = None
        self._oauth_service: Optional[OAuthServiceLike] = None
        self._app_auth_dialog_open = False
        self._oauth_dialog_open = False
        self._connection_in_progress = False

    @property
    def service(self) -> Optional[AppAuthServiceLike]:
        return self._service

    @property
    def oauth_service(self) -> Optional[OAuthServiceLike]:
        return self._oauth_service

    def set_service(self, service: AppAuthServiceLike) -> None:
        self._service = service
        if self._on_service_ready:
            self._on_service_ready(service)

    def set_oauth_service(self, service: OAuthServiceLike) -> None:
        self._oauth_service = service
        if self._on_oauth_ready:
            self._on_oauth_ready(service)

    def seed_services(
        self,
        service: Optional[AppAuthServiceLike],
        oauth_service: Optional[OAuthServiceLike],
    ) -> None:
        self._service = service
        self._oauth_service = oauth_service

    def is_app_authenticated(self) -> bool:
        if not self._service:
            return False
        is_auth = getattr(self._service, "is_app_authenticated", None)
        if isinstance(is_auth, bool):
            return is_auth
        return self._service.status >= ConnectionStatus.APP_AUTHENTICATED

    def is_oauth_authenticated(self) -> bool:
        if not self._oauth_service:
            return False
        return self._oauth_service.status >= ConnectionStatus.ACCOUNT_AUTHENTICATED

    @Slot()
    def toggle_connection(self) -> None:
        if self._connection_in_progress:
            self.logRequested.emit(format_connection_message("in_progress"))
            return

        if self.is_oauth_authenticated() or self.is_app_authenticated():
            self._connection_in_progress = True
            try:
                oauth_service = self._oauth_service
                if oauth_service and oauth_service.status != ConnectionStatus.DISCONNECTED:
                    logout = getattr(oauth_service, "logout", None)
                    if callable(logout):
                        try:
                            self.logRequested.emit(format_connection_message("logout_pending"))
                            logout()
                        except Exception:
                            pass
                    QTimer.singleShot(2500, lambda: oauth_service.disconnect())
                self._oauth_service = None
                self.oauthStatusChanged.emit(int(ConnectionStatus.DISCONNECTED))

                if self._service and getattr(self._service, "status", None) != ConnectionStatus.DISCONNECTED:
                    self._service.disconnect()
                if self._service and hasattr(self._service, "clear_log_history"):
                    try:
                        self._service.clear_log_history()
                    except Exception:
                        pass
                self._service = None
                self.appAuthStatusChanged.emit(int(ConnectionStatus.DISCONNECTED))

                if self._on_reset_controllers:
                    self._on_reset_controllers()
                self.logRequested.emit(format_connection_message("disconnected"))
            finally:
                self._connection_in_progress = False
            return

        self._connection_in_progress = True
        try:
            self.open_app_auth_dialog(auto_connect=True)
            if not self.is_app_authenticated():
                return
            self.open_oauth_dialog(auto_connect=True)
            if self.is_oauth_authenticated():
                self.logRequested.emit(format_connection_message("connected_done"))
        finally:
            self._connection_in_progress = False

    def open_app_auth_dialog(self, *, auto_connect: bool = False) -> None:
        if self._app_auth_dialog_open:
            return
        self._app_auth_dialog_open = True
        dialog = AppAuthDialog(
            token_file=TOKEN_FILE,
            auto_connect=auto_connect,
            app_auth_service=self._service,
            use_cases=self._use_cases,
            event_bus=self._event_bus,
            app_state=self._app_state,
            parent=self._parent,
        )
        if dialog.exec() == AppAuthDialog.Accepted:
            service = dialog.get_service()
            if service:
                self.set_service(service)
        self._app_auth_dialog_open = False

    def open_oauth_dialog(self, *, auto_connect: bool = True) -> None:
        if self._oauth_dialog_open:
            return
        if not self._service:
            QMessageBox.warning(self._parent, "需要 App 認證", "請先完成 App 認證，再進行 OAuth。")
            return
        if self._oauth_service and self._oauth_service.status == ConnectionStatus.ACCOUNT_AUTHENTICATED:
            auto_connect = False
        self._oauth_dialog_open = True
        dialog = OAuthDialog(
            token_file=TOKEN_FILE,
            auto_connect=auto_connect,
            app_auth_service=self._service,
            oauth_service=self._oauth_service,
            use_cases=self._use_cases,
            event_bus=self._event_bus,
            app_state=self._app_state,
            parent=self._parent,
        )
        if dialog.exec() == OAuthDialog.Accepted:
            oauth_service = dialog.get_service()
            if oauth_service is not None:
                self.set_oauth_service(oauth_service)
            else:
                self.logRequested.emit(format_connection_message("oauth_service_failed"))
        self._oauth_dialog_open = False
