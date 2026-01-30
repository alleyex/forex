from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from application import AppAuthServiceLike, AppState, BrokerUseCases, EventBus, OAuthServiceLike
from config.constants import ConnectionStatus
from ui_train.controllers.connection_controller import ConnectionController
from ui_train.utils.formatters import (
    format_app_auth_status,
    format_connection_message,
    format_oauth_status,
)
from ui_train.widgets.log_widget import LogWidget


class LiveMainWindow(QMainWindow):
    """Live trading application window."""

    logRequested = Signal(str)
    appAuthStatusChanged = Signal(int)
    oauthStatusChanged = Signal(int)

    def __init__(
        self,
        *,
        use_cases: BrokerUseCases,
        event_bus: Optional[EventBus] = None,
        app_state: Optional[AppState] = None,
        service: Optional[AppAuthServiceLike] = None,
        oauth_service: Optional[OAuthServiceLike] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._use_cases = use_cases
        self._event_bus = event_bus
        self._app_state = app_state
        self._service = service
        self._oauth_service = oauth_service
        self._connection_controller: Optional[ConnectionController] = None

        self._setup_ui()
        self._setup_connection_controller()
        self._connect_signals()

        if self._event_bus:
            self._event_bus.subscribe("log", self._log_panel.append)

        if self._service:
            self.set_service(self._service)
        if self._oauth_service:
            self.set_oauth_service(self._oauth_service)

    def set_service(self, service: AppAuthServiceLike) -> None:
        self._service = service
        if self._connection_controller:
            self._connection_controller.set_service(service)

    def set_oauth_service(self, service: OAuthServiceLike) -> None:
        self._oauth_service = service
        if self._connection_controller:
            self._connection_controller.set_oauth_service(service)

    def _setup_ui(self) -> None:
        self.setWindowTitle("外匯交易應用程式 - 實盤")
        self.setMinimumSize(1280, 720)
        self.resize(1280, 720)

        self._log_panel = LogWidget(
            title="",
            with_timestamp=True,
            monospace=True,
            font_point_delta=2,
        )

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)

        headline = QLabel("實盤交易")
        headline.setProperty("class", "section_title")
        content_layout.addWidget(headline)

        placeholder = QLabel("實盤交易面板將在此顯示。")
        placeholder.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        placeholder.setProperty("class", "placeholder")
        content_layout.addWidget(placeholder, 1)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(content)
        splitter.addWidget(self._log_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        self._setup_toolbar()
        self._setup_status_bar()

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Live toolbar", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._action_toggle_connection = QAction("連線/斷線", self)
        toolbar.addAction(self._action_toggle_connection)
        self._action_toggle_connection.triggered.connect(self._toggle_connection)

    def _setup_status_bar(self) -> None:
        status_bar = self.statusBar()
        self._app_auth_label = QLabel(format_app_auth_status(None))
        self._oauth_label = QLabel(format_oauth_status(None))
        status_bar.addWidget(self._app_auth_label)
        status_bar.addWidget(self._oauth_label)

    def _setup_connection_controller(self) -> None:
        controller = ConnectionController(
            parent=self,
            use_cases=self._use_cases,
            app_state=self._app_state,
            event_bus=self._event_bus,
            on_service_ready=self.set_service,
            on_oauth_ready=self.set_oauth_service,
        )
        controller.seed_services(self._service, self._oauth_service)
        controller.logRequested.connect(self.logRequested.emit)
        controller.appAuthStatusChanged.connect(self.appAuthStatusChanged.emit)
        controller.oauthStatusChanged.connect(self.oauthStatusChanged.emit)
        self._connection_controller = controller

    def _connect_signals(self) -> None:
        self.logRequested.connect(self._log_panel.append)
        self.appAuthStatusChanged.connect(self._handle_app_auth_status)
        self.oauthStatusChanged.connect(self._handle_oauth_status)

    @Slot()
    def _toggle_connection(self) -> None:
        if not self._connection_controller:
            self.logRequested.emit(format_connection_message("missing_use_cases"))
            return
        self._connection_controller.toggle_connection()

    @Slot(int)
    def _handle_app_auth_status(self, status: int) -> None:
        self._app_auth_label.setText(format_app_auth_status(ConnectionStatus(status)))

    @Slot(int)
    def _handle_oauth_status(self, status: int) -> None:
        self._oauth_label.setText(format_oauth_status(ConnectionStatus(status)))
