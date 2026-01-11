# ui/dialogs/app_auth_dialog.py
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QTextEdit, QComboBox,
)
from PySide6.QtCore import Signal, Slot, Qt

from broker.app_auth import AppAuthService
from config.constants import ConnectionStatus
from utils.reactor_manager import reactor_manager


class AppAuthDialog(QDialog):
    """Dialog for cTrader application authentication"""
    
    # Signals for thread-safe communication
    authSucceeded = Signal(object)  # Emits Client
    authFailed = Signal(str)        # Emits error message
    logReceived = Signal(str)       # Emits log message
    statusChanged = Signal(int)     # Emits ConnectionStatus

    def __init__(self, token_file: str = "token.json", parent=None):
        super().__init__(parent)
        self._token_file = token_file
        self._service: Optional[AppAuthService] = None
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Initialize UI components"""
        self.setWindowTitle("cTrader App Authentication")
        self.setMinimumSize(500, 350)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Host selection
        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("Environment:"))
        self._host_combo = QComboBox()
        self._host_combo.addItems(["demo", "live"])
        host_layout.addWidget(self._host_combo)
        host_layout.addStretch()
        layout.addLayout(host_layout)
        
        # Connect button
        self._btn_connect = QPushButton("🔗 Connect")
        self._btn_connect.setMinimumHeight(40)
        layout.addWidget(self._btn_connect)
        
        # Status indicator
        self._status_label = QLabel("Status: Disconnected")
        self._status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_label)
        
        # Log area
        layout.addWidget(QLabel("Connection Log:"))
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        layout.addWidget(self._log_text)

    def _connect_signals(self) -> None:
        """Connect signals to slots"""
        self._btn_connect.clicked.connect(self._start_auth)
        self.logReceived.connect(self._append_log)
        self.authSucceeded.connect(self._handle_success)
        self.authFailed.connect(self._handle_error)
        self.statusChanged.connect(self._update_status_display)

    @Slot()
    def _start_auth(self) -> None:
        """Initiate authentication process"""
        host_type = self._host_combo.currentText()
        
        try:
            self._service = AppAuthService.create(host_type, self._token_file)
        except FileNotFoundError as e:
            self._append_log(f"❌ {e}")
            return
        except ValueError as e:
            self._append_log(f"❌ {e}")
            return
        
        self._btn_connect.setEnabled(False)
        self._host_combo.setEnabled(False)
        
        self._service.set_callbacks(
            on_app_auth_success=self._on_auth_success,
            on_error=self._on_auth_error,
            on_log=self._on_log_received,
            on_status_changed=self._on_status_changed,
        )
        
        # Ensure reactor is running and connect
        reactor_manager.ensure_running()
        
        # Use callFromThread to safely interact with reactor
        from twisted.internet import reactor
        reactor.callFromThread(self._service.connect)

    # ─────────────────────────────────────────────────────────────
    # Callbacks (called from Twisted thread)
    # ─────────────────────────────────────────────────────────────

    def _on_auth_success(self, client) -> None:
        """Called from Twisted thread on success"""
        self.authSucceeded.emit(client)

    def _on_auth_error(self, error: str) -> None:
        """Called from Twisted thread on error"""
        self.authFailed.emit(error)

    def _on_log_received(self, message: str) -> None:
        """Called from Twisted thread for logging"""
        self.logReceived.emit(message)

    def _on_status_changed(self, status: ConnectionStatus) -> None:
        """Called from Twisted thread on status change"""
        self.statusChanged.emit(int(status))

    # ─────────────────────────────────────────────────────────────
    # Slots (run in GUI thread)
    # ─────────────────────────────────────────────────────────────

    @Slot(str)
    def _append_log(self, message: str) -> None:
        """Append message to log (GUI thread)"""
        self._log_text.append(message)
        scrollbar = self._log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot(object)
    def _handle_success(self, client) -> None:
        """Handle successful authentication (GUI thread)"""
        self._append_log("✅ Application authenticated successfully!")
        self.accept()

    @Slot(str)
    def _handle_error(self, error: str) -> None:
        """Handle authentication error (GUI thread)"""
        self._append_log(f"❌ {error}")
        self._btn_connect.setEnabled(True)
        self._host_combo.setEnabled(True)

    @Slot(int)
    def _update_status_display(self, status: int) -> None:
        """Update status label (GUI thread)"""
        status_map = {
            ConnectionStatus.DISCONNECTED: ("Disconnected", "color: red"),
            ConnectionStatus.CONNECTING: ("Connecting...", "color: orange"),
            ConnectionStatus.CONNECTED: ("Connected", "color: blue"),
            ConnectionStatus.APP_AUTHENTICATED: ("Authenticated ✓", "color: green"),
        }
        
        text, style = status_map.get(status, ("Unknown", ""))
        self._status_label.setText(f"Status: {text}")
        self._status_label.setStyleSheet(style)

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def get_service(self) -> Optional[AppAuthService]:
        """Get the authenticated service instance"""
        return self._service