# ui/main_window.py
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Slot

from ui.widgets.trade_panel import TradePanel
from ui.widgets.log_panel import LogPanel
from broker.app_auth import AppAuthService
from broker.oauth import OAuthService
from config.constants import ConnectionStatus


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(
        self,
        service: Optional[AppAuthService] = None,
        oauth_service: Optional[OAuthService] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._service = service
        self._oauth_service = oauth_service
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Initialize UI components"""
        self.setWindowTitle("外匯交易應用程式")
        self.setMinimumSize(1000, 600)
        
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        self._trade_panel = TradePanel()
        self._log_panel = LogPanel()
        
        layout.addWidget(self._trade_panel, stretch=2)
        layout.addWidget(self._log_panel, stretch=3)
        
        self.setCentralWidget(central)
        status_bar = self.statusBar()
        self._app_auth_status_label = QLabel(self._format_app_auth_status())
        self._oauth_status_label = QLabel(self._format_oauth_status())
        status_bar.addWidget(self._app_auth_status_label)
        status_bar.addWidget(self._oauth_status_label)

    def _connect_signals(self) -> None:
        """Connect panel signals"""
        self._trade_panel.buy_clicked.connect(self._on_buy_clicked)
        self._trade_panel.sell_clicked.connect(self._on_sell_clicked)

    @Slot()
    def _on_buy_clicked(self) -> None:
        """Handle buy button click"""
        self._log_panel.add_log("🟢 已送出買入請求")
        # TODO: Implement actual order logic using self._service

    @Slot()
    def _on_sell_clicked(self) -> None:
        """Handle sell button click"""
        self._log_panel.add_log("🔴 已送出賣出請求")
        # TODO: Implement actual order logic using self._service

    def set_service(self, service: AppAuthService) -> None:
        """Set the authenticated service"""
        self._service = service
        self._log_panel.add_log("✅ 服務已連線")
        self._app_auth_status_label.setText(self._format_app_auth_status())

    def set_oauth_service(self, service: OAuthService) -> None:
        """Set the OAuth service"""
        self._oauth_service = service
        self._log_panel.add_log("✅ OAuth 已連線")
        self._oauth_status_label.setText(self._format_oauth_status())

    def _format_app_auth_status(self) -> str:
        """Format app auth status for display"""
        if not self._service:
            return "App 認證狀態: ⛔ 未連線"

        status_map = {
            ConnectionStatus.DISCONNECTED: "⛔ 已斷線",
            ConnectionStatus.CONNECTING: "⏳ 連線中...",
            ConnectionStatus.CONNECTED: "🔗 已連線",
            ConnectionStatus.APP_AUTHENTICATED: "✅ 已認證",
            ConnectionStatus.ACCOUNT_AUTHENTICATED: "✅ 帳戶已認證",
        }

        text = status_map.get(self._service.status, "❓ 未知")
        return f"App 認證狀態: {text}"

    def _format_oauth_status(self) -> str:
        """Format OAuth status for display"""
        if not self._oauth_service:
            return "OAuth 狀態: ⛔ 未連線"

        status_map = {
            ConnectionStatus.DISCONNECTED: "⛔ 已斷線",
            ConnectionStatus.CONNECTING: "⏳ 連線中...",
            ConnectionStatus.CONNECTED: "🔗 已連線",
            ConnectionStatus.APP_AUTHENTICATED: "✅ 已認證",
            ConnectionStatus.ACCOUNT_AUTHENTICATED: "🔐 帳戶已授權",
        }

        text = status_map.get(self._oauth_service.status, "❓ 未知")
        return f"OAuth 狀態: {text}"
