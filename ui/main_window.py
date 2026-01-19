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

from application import (
    AppState,
    AppAuthServiceLike,
    BrokerUseCases,
    EventBus,
    OAuthServiceLike,
    TrendbarHistoryServiceLike,
    TrendbarServiceLike,
)
from application.broker.history_pipeline import HistoryPipeline
from domain import AccountFundsSnapshot
from config.settings import OAuthTokens
from config.paths import TOKEN_FILE
from utils.reactor_manager import reactor_manager

from config.constants import ConnectionStatus


class MainWindow(QMainWindow):
    """Main application window"""

    logRequested = Signal(str)
    accountsReceived = Signal(list, object)
    fundsReceived = Signal(object)
    appAuthStatusChanged = Signal(int)
    oauthStatusChanged = Signal(int)
    appAuthSucceeded = Signal(object)
    oauthSucceeded = Signal(object)

    def __init__(
        self,
        service: Optional[AppAuthServiceLike] = None,
        oauth_service: Optional[OAuthServiceLike] = None,
        use_cases: Optional[BrokerUseCases] = None,
        event_bus: Optional[EventBus] = None,
        app_state: Optional[AppState] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._use_cases: Optional[BrokerUseCases] = use_cases
        self._event_bus = event_bus
        self._app_state = app_state
        self._service = service
        self._oauth_service = oauth_service
        self._trendbar_service: Optional[TrendbarServiceLike] = None
        self._trendbar_history_service: Optional[TrendbarHistoryServiceLike] = None
        self._history_pipeline: Optional[HistoryPipeline] = None
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
        if self._app_state:
            self._app_state.subscribe(self._sync_status_from_state)
        if self._event_bus:
            self._event_bus.subscribe("log", self._log_panel.add_log)
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
        self.appAuthStatusChanged.connect(self._handle_app_auth_status_changed)
        self.oauthStatusChanged.connect(self._handle_oauth_status_changed)
        self.appAuthSucceeded.connect(self._handle_app_auth_success)
        self.oauthSucceeded.connect(self._handle_oauth_success)
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
        if not self._is_app_authenticated():
            self._log_panel.add_log("⚠️ App 認證已中斷，請稍候自動重連")
            return
        if not self._oauth_service or self._oauth_service.status != ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log_panel.add_log("⚠️ 尚未完成 OAuth 帳戶認證")
            return

        try:
            tokens = OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self._log_panel.add_log(f"⚠️ 無法讀取 OAuth Token: {exc}")
            return
        if not tokens.account_id:
            self._log_panel.add_log("⚠️ 缺少帳戶 ID")
            return

        if self._trendbar_service is None:
            if self._use_cases is None:
                self._log_panel.add_log("⚠️ 缺少 broker 用例配置")
                return
            self._trendbar_service = self._use_cases.create_trendbar(app_auth_service=self._service)

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
        if not self._is_app_authenticated():
            self._log_panel.add_log("⚠️ App 認證已中斷，請稍候自動重連")
            return
        if not self._oauth_service or self._oauth_service.status != ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log_panel.add_log("⚠️ 尚未完成 OAuth 帳戶認證")
            return

        try:
            tokens = OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self._log_panel.add_log(f"⚠️ 無法讀取 OAuth Token: {exc}")
            return
        if not tokens.account_id:
            self._log_panel.add_log("⚠️ 缺少帳戶 ID")
            return

        if self._history_pipeline is None:
            if self._use_cases is None:
                self._log_panel.add_log("⚠️ 缺少 broker 用例配置")
                return
            self._history_pipeline = HistoryPipeline(
                broker_use_cases=self._use_cases,
                app_auth_service=self._service,
            )

        reactor_manager.ensure_running()
        from twisted.internet import reactor
        bars_per_day = 24 * 12
        two_years_bars = 365 * 2 * bars_per_day
        reactor.callFromThread(
            self._history_pipeline.fetch_to_raw,
            tokens.account_id,
            self._trendbar_symbol_id,
            two_years_bars,
            timeframe="M5",
            on_saved=lambda path: self.logRequested.emit(f"✅ 已儲存歷史資料：{path}"),
            on_error=lambda e: self.logRequested.emit(f"⚠️ 歷史資料錯誤: {e}"),
            on_log=self.logRequested.emit,
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
        if not self._is_app_authenticated():
            self._log_panel.add_log("⚠️ App 認證已中斷，請稍候自動重連")
            return
        if not self._oauth_service or self._oauth_service.status != ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log_panel.add_log("⚠️ OAuth 尚未完成認證，將自動重新認證")
            self._auto_oauth_connect()
            return
        try:
            tokens = OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self._log_panel.add_log(f"⚠️ 無法讀取 OAuth Token: {exc}")
            return
        if not tokens.access_token:
            self._log_panel.add_log("⚠️ 缺少 Access Token")
            return

        if self._use_cases is None:
            self._log_panel.add_log("⚠️ 缺少 broker 用例配置")
            return
        if self._use_cases.account_list_in_progress():
            self._log_panel.add_log("⏳ 正在取得帳戶列表，請稍候")
            return
        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(
            self._use_cases.fetch_accounts,
            self._service,
            tokens.access_token,
            lambda accounts: self.accountsReceived.emit(accounts, tokens.account_id),
            lambda e: self.logRequested.emit(f"⚠️ 取得帳戶失敗: {e}"),
            self.logRequested.emit,
        )

    def _handle_accounts_received(self, accounts: list, account_id: Optional[int]) -> None:
        try:
            self.logRequested.emit(f"📄 帳戶數量: {len(accounts)}")
            if not accounts:
                self.logRequested.emit("⚠️ 帳戶列表為空")
                return

            selected = None
            if account_id:
                for item in accounts:
                    if item.account_id == int(account_id):
                        selected = item
                        break
            if selected is None:
                selected = accounts[0]

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

        if self._use_cases is None:
            self.logRequested.emit("⚠️ 缺少 broker 用例配置")
            return
        if self._use_cases.account_funds_in_progress():
            self.logRequested.emit("⏳ 正在取得帳戶資金，請稍候")
            return
        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(
            self._use_cases.fetch_account_funds,
            self._service,
            account_id,
            lambda funds: self.fundsReceived.emit(funds),
            lambda e: self.logRequested.emit(f"⚠️ 取得帳戶資金失敗: {e}"),
            self.logRequested.emit,
        )

    def _handle_funds_received(self, funds: AccountFundsSnapshot) -> None:
        snapshot = funds
        self.logRequested.emit("📄 帳戶資金狀態")
        money_digits = snapshot.money_digits if snapshot.money_digits is not None else 2
        self.logRequested.emit(f"餘額: {self._format_money(snapshot.balance, money_digits)}")
        self.logRequested.emit(f"淨值: {self._format_money(snapshot.equity, money_digits)}")
        self.logRequested.emit(f"可用資金: {self._format_money(snapshot.free_margin, money_digits)}")
        self.logRequested.emit(f"已用保證金: {self._format_money(snapshot.used_margin, money_digits)}")
        if snapshot.margin_level is None:
            margin_text = "-"
        else:
            margin_text = f"{snapshot.margin_level:.2f}%"
        self.logRequested.emit(f"保證金比例: {margin_text}")
        self.logRequested.emit(f"帳戶幣別: {snapshot.currency or '-'}")

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

    def set_service(self, service: AppAuthServiceLike) -> None:
        """Set the authenticated service"""
        self._service = service
        self._trendbar_service = None
        self._trendbar_history_service = None
        self._trendbar_active = False
        self._trade_panel.set_trendbar_active(False)
        self._service.set_callbacks(
            on_app_auth_success=lambda c: self.appAuthSucceeded.emit(c),
            on_log=self.logRequested.emit,
            on_status_changed=lambda s: self.appAuthStatusChanged.emit(int(s)),
        )
        self._app_auth_status_label.setText(self._format_app_auth_status())
        if self._app_state:
            self._app_state.update_app_status(int(service.status))
        if self._is_app_authenticated():
            self._auto_oauth_connect()

    def set_oauth_service(self, service: OAuthServiceLike) -> None:
        """Set the OAuth service"""
        self._oauth_service = service
        self._oauth_service.set_callbacks(
            on_oauth_success=lambda t: self.oauthSucceeded.emit(t),
            on_log=self.logRequested.emit,
            on_status_changed=lambda s: self.oauthStatusChanged.emit(int(s)),
        )
        self._oauth_status_label.setText(self._format_oauth_status())
        if self._app_state:
            self._app_state.update_oauth_status(int(service.status))

    def _open_app_auth_dialog(self, auto_connect: bool = False) -> None:
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
            token_file=TOKEN_FILE,
            auto_connect=auto_connect,
            app_auth_service=self._service,
            oauth_service=self._oauth_service,
            use_cases=self._use_cases,
            event_bus=self._event_bus,
            app_state=self._app_state,
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
        if self._app_state:
            self._app_state.update_app_status(int(self._service.status))
        self._auto_oauth_connect()

    def _handle_app_auth_status_changed(self, status: ConnectionStatus) -> None:
        self._app_auth_status_label.setText(self._format_app_auth_status())
        if self._app_state:
            self._app_state.update_app_status(int(status))
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
        if self._app_state:
            self._app_state.update_oauth_status(int(self._oauth_service.status))

    def _handle_oauth_status_changed(self, status: ConnectionStatus) -> None:
        self._oauth_status_label.setText(self._format_oauth_status())
        if self._app_state:
            self._app_state.update_oauth_status(int(status))

    def _auto_oauth_connect(self) -> None:
        if not self._service:
            return
        if self._oauth_service and self._oauth_service.status == ConnectionStatus.ACCOUNT_AUTHENTICATED:
            return
        if not self._oauth_service:
            if self._use_cases is None:
                self.logRequested.emit("⚠️ 缺少 broker 用例配置")
                return
            try:
                self._oauth_service = self._use_cases.create_oauth(self._service, TOKEN_FILE)
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
        if self._is_app_authenticated():
            self._reconnect_timer.stop()
            self._reconnect_logged = False
            return
        if self._service.status == ConnectionStatus.CONNECTING:
            return
        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(self._service.connect)

    def _is_app_authenticated(self) -> bool:
        if not self._service:
            return False
        is_auth = getattr(self._service, "is_app_authenticated", None)
        if isinstance(is_auth, bool):
            return is_auth
        return self._service.status >= ConnectionStatus.APP_AUTHENTICATED

    def _sync_status_from_state(self, state: AppState) -> None:
        if state.app_status is not None:
            self._app_auth_status_label.setText(self._format_app_auth_status())
        if state.oauth_status is not None:
            self._oauth_status_label.setText(self._format_oauth_status())
