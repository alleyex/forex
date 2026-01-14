# ui/main_window.py
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QLabel,
    QMessageBox,
)
from PySide6.QtCore import Slot, Signal, QTimer
from PySide6.QtGui import QAction, QFont

from ui.widgets.trade_panel import TradePanel
from ui.widgets.log_panel import LogPanel
from ui.dialogs.app_auth_dialog import AppAuthDialog
from ui.dialogs.oauth_dialog import OAuthDialog
from broker.services.app_auth_service import AppAuthService
from broker.services.account_list_service import AccountListService
from broker.services.account_funds_service import AccountFundsService, AccountFunds
from broker.services.trendbar_service import TrendbarService
from broker.services.trendbar_history_service import TrendbarHistoryService
from broker.services.oauth_service import OAuthService
from broker.account import parse_accounts
from config.settings import OAuthTokens
from utils.reactor_manager import reactor_manager

from config.constants import ConnectionStatus


class MainWindow(QMainWindow):
    """Main application window"""

    logRequested = Signal(str)
    accountsReceived = Signal(list, object)
    fundsReceived = Signal(object)
    
    def __init__(
        self,
        service: Optional[AppAuthService] = None,
        oauth_service: Optional[OAuthService] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._service = service
        self._oauth_service = oauth_service
        self._account_list_service: Optional[AccountListService] = None
        self._account_funds_service: Optional[AccountFundsService] = None
        self._trendbar_service: Optional[TrendbarService] = None
        self._trendbar_history_service: Optional[TrendbarHistoryService] = None
        self._trendbar_active = False
        self._trendbar_symbol_id = 1
        self._price_digits = 5
        self._app_auth_dialog_open = False
        self._oauth_dialog_open = False
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(5000)
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)
        self._reconnect_logged = False
        
        self._setup_ui()
        self._connect_signals()
        if self._service:
            self.set_service(self._service)
        if self._oauth_service:
            self.set_oauth_service(self._oauth_service)

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
        self.logRequested.connect(self._handle_log_message)
        self.accountsReceived.connect(self._handle_accounts_received)
        self.fundsReceived.connect(self._handle_funds_received)
        status_bar = self.statusBar()
        self._app_auth_status_label = QLabel(self._format_app_auth_status())
        self._oauth_status_label = QLabel(self._format_oauth_status())
        status_bar.addWidget(self._app_auth_status_label)
        status_bar.addWidget(self._oauth_status_label)
        self._setup_menu_toolbar()

    def _connect_signals(self) -> None:
        """Connect panel signals"""
        self._trade_panel.trendbar_toggle_clicked.connect(self._on_trendbar_toggle_clicked)
        self._trade_panel.trendbar_history_clicked.connect(self._on_trendbar_history_clicked)
        self._action_fetch_account_info.triggered.connect(self._on_fetch_account_info)

    def _setup_menu_toolbar(self) -> None:
        """Create menu and toolbar actions"""
        auth_menu = self.menuBar().addMenu("認證")

        self._action_app_auth = auth_menu.addAction("App 認證")
        self._action_oauth = auth_menu.addAction("OAuth 認證")

        toolbar = self.addToolBar("認證")
        toolbar.addAction(self._action_oauth)
        toolbar.setFont(QFont("", 12))

        self._action_app_auth.triggered.connect(self._open_app_auth_dialog)
        self._action_oauth.triggered.connect(self._open_oauth_dialog)

        self._action_fetch_account_info = QAction("基本資料", self)
        toolbar.addAction(self._action_fetch_account_info)

    @Slot()
    def _on_trendbar_toggle_clicked(self) -> None:
        if self._trendbar_active:
            self._stop_trendbar()
        else:
            self._start_trendbar()

    def _start_trendbar(self) -> None:
        if not self._service:
            self._log_panel.add_log("⚠️ 尚未完成 App 認證")
            return
        if not self._service.is_app_authenticated:
            self._log_panel.add_log("⚠️ App 認證已中斷，請稍候自動重連")
            return
        if not self._oauth_service or self._oauth_service.status != ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log_panel.add_log("⚠️ 尚未完成 OAuth 帳戶認證")
            return
        try:
            tokens = OAuthTokens.from_file("token.json")
        except Exception as exc:
            self._log_panel.add_log(f"⚠️ 無法讀取 OAuth Token: {exc}")
            return
        if not tokens.account_id:
            self._log_panel.add_log("⚠️ 缺少帳戶 ID")
            return

        if self._trendbar_service is None:
            self._trendbar_service = TrendbarService(app_auth_service=self._service)

        self._trendbar_service.clear_log_history()
        self._trendbar_service.set_callbacks(
            on_trendbar=lambda data: self.logRequested.emit(
                f"📊 M1 {data['timestamp']} "
                f"O={self._format_price(data['open'])} "
                f"H={self._format_price(data['high'])} "
                f"L={self._format_price(data['low'])} "
                f"C={self._format_price(data['close'])}"
            ),
            on_error=lambda e: self.logRequested.emit(f"⚠️ 趨勢棒錯誤: {e}"),
            on_log=self.logRequested.emit,
        )

        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(
            self._trendbar_service.subscribe,
            tokens.account_id,
            self._trendbar_symbol_id,
        )
        self._trendbar_active = True
        self._trade_panel.set_trendbar_active(True)
        self._log_panel.add_log(f"📈 已開始 M1 趨勢棒：symbol {self._trendbar_symbol_id}")

    def _stop_trendbar(self) -> None:
        if not self._trendbar_service or not self._trendbar_service.in_progress:
            self._log_panel.add_log("ℹ️ 目前沒有趨勢棒訂閱")
            self._trendbar_active = False
            self._trade_panel.set_trendbar_active(False)
            return
        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(self._trendbar_service.unsubscribe)
        self._trendbar_active = False
        self._trade_panel.set_trendbar_active(False)

    @Slot()
    def _on_trendbar_history_clicked(self) -> None:
        if not self._service:
            self._log_panel.add_log("⚠️ 尚未完成 App 認證")
            return
        if not self._service.is_app_authenticated:
            self._log_panel.add_log("⚠️ App 認證已中斷，請稍候自動重連")
            return
        if not self._oauth_service or self._oauth_service.status != ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log_panel.add_log("⚠️ 尚未完成 OAuth 帳戶認證")
            return

        try:
            tokens = OAuthTokens.from_file("token.json")
        except Exception as exc:
            self._log_panel.add_log(f"⚠️ 無法讀取 OAuth Token: {exc}")
            return
        if not tokens.account_id:
            self._log_panel.add_log("⚠️ 缺少帳戶 ID")
            return

        if self._trendbar_history_service is None:
            self._trendbar_history_service = TrendbarHistoryService(app_auth_service=self._service)

        self._trendbar_history_service.clear_log_history()
        self._trendbar_history_service.set_callbacks(
            on_history_received=self._handle_trendbar_history,
            on_error=lambda e: self.logRequested.emit(f"⚠️ 歷史資料錯誤: {e}"),
            on_log=self.logRequested.emit,
        )

        reactor_manager.ensure_running()
        from twisted.internet import reactor
        bars_per_day = 24 * 12
        two_years_bars = 365 * 2 * bars_per_day
        reactor.callFromThread(
            self._trendbar_history_service.fetch,
            tokens.account_id,
            self._trendbar_symbol_id,
            two_years_bars,
        )

    def _handle_trendbar_history(self, bars: list) -> None:
        self.logRequested.emit("📚 M5 歷史資料（最近 2 年）")
        if not bars:
            self.logRequested.emit("⚠️ 歷史資料為空")
            return
        for bar in bars:
            self.logRequested.emit(
                f"🕒 {bar['timestamp']} "
                f"O={self._format_price(bar['open'])} "
                f"H={self._format_price(bar['high'])} "
                f"L={self._format_price(bar['low'])} "
                f"C={self._format_price(bar['close'])}"
            )

    @Slot()
    def _on_fetch_account_info(self) -> None:
        """Handle fetch account info click"""
        self._log_panel.add_log("📄 已送出取得基本資料請求")
        if not self._service:
            self._log_panel.add_log("⚠️ 尚未完成 App 認證")
            return
        if not self._service.is_app_authenticated:
            self._log_panel.add_log("⚠️ App 認證已中斷，請稍候自動重連")
            return
        if not self._oauth_service or self._oauth_service.status != ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log_panel.add_log("⚠️ OAuth 尚未完成認證，將自動重新認證")
            self._auto_oauth_connect()
            return
        try:
            tokens = OAuthTokens.from_file("token.json")
        except Exception as exc:
            self._log_panel.add_log(f"⚠️ 無法讀取 OAuth Token: {exc}")
            return
        if not tokens.access_token:
            self._log_panel.add_log("⚠️ 缺少 Access Token")
            return

        if self._account_list_service is not None and self._account_list_service.in_progress:
            self._log_panel.add_log("⏳ 正在取得帳戶列表，請稍候")
            return

        if self._account_list_service is None:
            self._account_list_service = AccountListService(
                app_auth_service=self._service,
                access_token=tokens.access_token,
            )
        else:
            if self._account_list_service.in_progress:
                self._log_panel.add_log("⏳ 正在取得帳戶列表，請稍候")
                return
            self._account_list_service.set_access_token(tokens.access_token)

        self._account_list_service.clear_log_history()
        self._account_list_service.set_callbacks(
            on_accounts_received=lambda accounts: self.accountsReceived.emit(
                accounts, tokens.account_id
            ),
            on_error=lambda e: self.logRequested.emit(f"⚠️ 取得帳戶失敗: {e}"),
            on_log=self.logRequested.emit,
        )

        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(self._account_list_service.fetch)

    def _handle_accounts_received(self, accounts: list, account_id: Optional[int]) -> None:
        try:
            self.logRequested.emit(f"📄 帳戶數量: {len(accounts)}")
            parsed = parse_accounts(accounts)
            if not parsed:
                self.logRequested.emit("⚠️ 帳戶列表為空")
                return

            selected = None
            if account_id:
                for item in parsed:
                    if item.account_id == int(account_id):
                        selected = item
                        break
            if selected is None:
                selected = parsed[0]

            env_text = "真實" if selected.is_live else "模擬"
            login_text = "-" if selected.trader_login is None else str(selected.trader_login)
            self.logRequested.emit("📄 帳戶基本資料")
            self.logRequested.emit(f"帳戶 ID: {selected.account_id}")
            self.logRequested.emit(f"環境: {env_text}")
            self.logRequested.emit(f"交易登入: {login_text}")
            self._fetch_account_funds(selected.account_id)
        except Exception as exc:
            self.logRequested.emit(f"⚠️ 帳戶資料解析失敗: {exc}")

    def _fetch_account_funds(self, account_id: int) -> None:
        if not self._service:
            self.logRequested.emit("⚠️ 尚未完成 App 認證")
            return

        if self._account_funds_service is not None and self._account_funds_service.in_progress:
            self.logRequested.emit("⏳ 正在取得帳戶資金，請稍候")
            return

        if self._account_funds_service is None:
            self._account_funds_service = AccountFundsService(app_auth_service=self._service)

        self._account_funds_service.clear_log_history()
        self._account_funds_service.set_callbacks(
            on_funds_received=lambda funds: self.fundsReceived.emit(funds),
            on_error=lambda e: self.logRequested.emit(f"⚠️ 取得帳戶資金失敗: {e}"),
            on_log=self.logRequested.emit,
        )

        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(self._account_funds_service.fetch, account_id)

    def _handle_funds_received(self, funds: AccountFunds) -> None:
        self.logRequested.emit("📄 帳戶資金狀態")
        money_digits = funds.money_digits if funds.money_digits is not None else 2
        self.logRequested.emit(f"餘額: {self._format_money(funds.balance, money_digits)}")
        self.logRequested.emit(f"淨值: {self._format_money(funds.equity, money_digits)}")
        self.logRequested.emit(f"可用資金: {self._format_money(funds.free_margin, money_digits)}")
        self.logRequested.emit(f"已用保證金: {self._format_money(funds.used_margin, money_digits)}")
        if funds.margin_level is None:
            margin_text = "-"
        else:
            margin_text = f"{funds.margin_level:.2f}%"
        self.logRequested.emit(f"保證金比例: {margin_text}")
        self.logRequested.emit(f"帳戶幣別: {funds.currency or '-'}")

    @staticmethod
    def _format_money(value: Optional[float], digits: int) -> str:
        if value is None:
            return "-"
        if digits <= 0:
            return str(int(round(value)))
        return f"{value:.{digits}f}"

    def _format_price(self, value: Optional[int]) -> str:
        if value is None:
            return "-"
        scale = 10 ** self._price_digits
        return f"{value / scale:.{self._price_digits}f}"

    def set_service(self, service: AppAuthService) -> None:
        """Set the authenticated service"""
        self._service = service
        self._trendbar_service = None
        self._trendbar_history_service = None
        self._trendbar_active = False
        self._trade_panel.set_trendbar_active(False)
        self._service.set_callbacks(
            on_app_auth_success=self._handle_app_auth_success,
            on_log=self.logRequested.emit,
            on_status_changed=self._handle_app_auth_status_changed,
        )
        self._app_auth_status_label.setText(self._format_app_auth_status())
        if self._service.is_app_authenticated:
            self._auto_oauth_connect()

    def set_oauth_service(self, service: OAuthService) -> None:
        """Set the OAuth service"""
        self._oauth_service = service
        self._oauth_service.set_callbacks(
            on_oauth_success=self._handle_oauth_success,
            on_log=self.logRequested.emit,
            on_status_changed=self._handle_oauth_status_changed,
        )
        self._oauth_status_label.setText(self._format_oauth_status())

    def _open_app_auth_dialog(self, auto_connect: bool = False) -> None:
        if self._app_auth_dialog_open:
            return
        self._app_auth_dialog_open = True
        dialog = AppAuthDialog(
            token_file="token.json",
            auto_connect=auto_connect,
            app_auth_service=self._service,
            parent=self,
        )
        if dialog.exec() == AppAuthDialog.Accepted:
            service = dialog.get_service()
            if service:
                self.set_service(service)
        self._app_auth_dialog_open = False

    def _open_oauth_dialog(self, auto_connect: bool = True) -> None:
        if self._oauth_dialog_open:
            return
        if not self._service:
            QMessageBox.warning(self, "需要 App 認證", "請先完成 App 認證，再進行 OAuth。")
            return
        if self._oauth_service and self._oauth_service.status == ConnectionStatus.ACCOUNT_AUTHENTICATED:
            auto_connect = False
        self._oauth_dialog_open = True
        dialog = OAuthDialog(
            token_file="token.json",
            auto_connect=auto_connect,
            app_auth_service=self._service,
            oauth_service=self._oauth_service,
            parent=self,
        )
        if dialog.exec() == OAuthDialog.Accepted:
            oauth_service = dialog.get_service()
            if oauth_service:
                self.set_oauth_service(oauth_service)
            self._on_fetch_account_info()
        self._oauth_dialog_open = False

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

    @Slot(str)
    def _handle_log_message(self, message: str) -> None:
        self._log_panel.add_log(message)

    def _handle_app_auth_success(self, _client) -> None:
        self._app_auth_status_label.setText(self._format_app_auth_status())
        self._log_panel.add_log("✅ 服務已連線")
        self._auto_oauth_connect()

    def _handle_app_auth_status_changed(self, status: ConnectionStatus) -> None:
        self._app_auth_status_label.setText(self._format_app_auth_status())
        if status == ConnectionStatus.DISCONNECTED and self._oauth_service:
            self._oauth_service.disconnect()
            self._oauth_status_label.setText(self._format_oauth_status())
            self._trendbar_service = None
            self._trendbar_history_service = None
            self._trendbar_active = False
            self._trade_panel.set_trendbar_active(False)
            if not self._reconnect_timer.isActive():
                self._reconnect_timer.start()
                if not self._reconnect_logged:
                    self._log_panel.add_log("🔄 偵測到斷線，將自動嘗試重新連線")
                    self._reconnect_logged = True
        if status >= ConnectionStatus.APP_AUTHENTICATED:
            if self._reconnect_timer.isActive():
                self._reconnect_timer.stop()
            self._reconnect_logged = False

    def _handle_oauth_success(self, _tokens) -> None:
        self._oauth_status_label.setText(self._format_oauth_status())
        self._log_panel.add_log("✅ OAuth 已連線")

    def _handle_oauth_status_changed(self, _status: ConnectionStatus) -> None:
        self._oauth_status_label.setText(self._format_oauth_status())

    def _auto_oauth_connect(self) -> None:
        if not self._service:
            return
        if self._oauth_service and self._oauth_service.status == ConnectionStatus.ACCOUNT_AUTHENTICATED:
            return
        if not self._oauth_service:
            try:
                self._oauth_service = OAuthService.create(self._service, "token.json")
            except Exception as exc:
                self.logRequested.emit(f"⚠️ 無法建立 OAuth 服務: {exc}")
                return
            self.set_oauth_service(self._oauth_service)

        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(self._oauth_service.connect)

    def _attempt_reconnect(self) -> None:
        if not self._service:
            return
        if self._service.is_app_authenticated:
            self._reconnect_timer.stop()
            self._reconnect_logged = False
            return
        if self._service.status == ConnectionStatus.CONNECTING:
            return
        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(self._service.connect)


    # Heartbeat display removed.
