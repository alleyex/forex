# ui/main_window.py
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout
from PySide6.QtCore import Slot

from ui.widgets.trade_panel import TradePanel
from ui.widgets.log_panel import LogPanel
from broker.app_auth import AppAuthService


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self, service: Optional[AppAuthService] = None, parent=None):
        super().__init__(parent)
        self._service = service
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Initialize UI components"""
        self.setWindowTitle("Forex Trading Application")
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

    def _connect_signals(self) -> None:
        """Connect panel signals"""
        self._trade_panel.buy_clicked.connect(self._on_buy_clicked)
        self._trade_panel.sell_clicked.connect(self._on_sell_clicked)

    @Slot()
    def _on_buy_clicked(self) -> None:
        """Handle buy button click"""
        self._log_panel.add_log("🟢 BUY order requested")
        # TODO: Implement actual order logic using self._service

    @Slot()
    def _on_sell_clicked(self) -> None:
        """Handle sell button click"""
        self._log_panel.add_log("🔴 SELL order requested")
        # TODO: Implement actual order logic using self._service

    def set_service(self, service: AppAuthService) -> None:
        """Set the authenticated service"""
        self._service = service
        self._log_panel.add_log("✅ Service connected")
