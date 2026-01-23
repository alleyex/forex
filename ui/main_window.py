# ui/main_window.py
from typing import Optional
import sys

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QStackedWidget,
)
from PySide6.QtCore import Slot, Signal, Qt
from PySide6.QtGui import QAction

from ui.layout.dock_manager import DockManager
from ui.layout.panel_switcher import PanelSet, PanelSwitcher
from ui.layout.toolbar_actions import build_toolbar_actions, ToolbarActions

from ui.widgets.trade_panel import TradePanel
from ui.widgets.simulation_panel import SimulationPanel, SimulationParamsPanel
from ui.widgets.training_panel import TrainingPanel, TrainingParamsPanel
from ui.widgets.log_widget import LogWidget
from ui.controllers import PPOTrainingController, SimulationController, TrendbarController
from ui.dialogs.app_auth_dialog import AppAuthDialog
from ui.controllers import HistoryDownloadController
from ui.dialogs.oauth_dialog import OAuthDialog

from application import (
    AppState,
    AppAuthServiceLike,
    BrokerUseCases,
    EventBus,
    OAuthServiceLike,
)
from domain import AccountFundsSnapshot
from config.settings import OAuthTokens
from config.paths import TOKEN_FILE
from utils.reactor_manager import reactor_manager

from config.constants import ConnectionStatus
from ui.utils.formatters import format_app_auth_status, format_oauth_status


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
        self._history_download_controller: Optional[HistoryDownloadController] = None
        self._trendbar_controller: Optional[TrendbarController] = None
        self._trendbar_symbol_id = 1
        self._price_digits = 5
        self._app_auth_dialog_open = False
        self._oauth_dialog_open = False
        self._ppo_controller: Optional[PPOTrainingController] = None
        self._simulation_controller: Optional[SimulationController] = None
        self._log_collapsed = False
        self._connection_in_progress = False
        self._trendbar_controller = None
        self._history_download_controller = None
        self._dock_manager: Optional[DockManager] = None
        self._panel_switcher: Optional[PanelSwitcher] = None
        self._toolbar_actions: Optional[ToolbarActions] = None

        self._setup_ui()
        self._connect_signals()
        if self._app_state:
            self._app_state.subscribe(self._sync_status_from_state)
        if self._event_bus:
            self._event_bus.subscribe("log", self._log_panel.append)
        if self._service:
            self.set_service(self._service)
        if self._oauth_service:
            self.set_oauth_service(self._oauth_service)

    def _setup_ui(self) -> None:
        """Initialize UI components"""
        self._setup_window()
        self._setup_panels()
        self._setup_stack()
        self._setup_docks()
        self._setup_panel_switcher()
        self._setup_status_bar()
        self._setup_menu_toolbar()

    def _setup_window(self) -> None:
        self.setWindowTitle("外匯交易應用程式")
        self.setMinimumSize(1280, 720)
        self.resize(1280, 720)

    def _setup_panels(self) -> None:
        self._trade_panel = TradePanel()
        self._training_panel = TrainingPanel()
        self._training_params_panel = TrainingParamsPanel()
        self._simulation_panel = SimulationPanel()
        self._simulation_params_panel = SimulationParamsPanel()

        self._log_panel = LogWidget(
            title="",
            with_timestamp=True,
            monospace=True,
            font_point_delta=2,
        )

    def _setup_stack(self) -> None:
        self._stack = QStackedWidget()
        self._trade_container = QWidget()
        trade_layout = QHBoxLayout(self._trade_container)
        trade_layout.setContentsMargins(10, 10, 10, 10)
        trade_layout.setSpacing(10)
        trade_layout.addWidget(self._trade_panel)

        self._stack.addWidget(self._trade_container)
        self._stack.addWidget(self._training_panel)
        self._stack.addWidget(self._simulation_panel)
        self.setCentralWidget(self._stack)

    def _setup_docks(self) -> None:
        self._dock_manager = DockManager(
            self,
            log_panel=self._log_panel,
            training_params_panel=self._training_params_panel,
            simulation_params_panel=self._simulation_params_panel,
        )
        self._dock_manager.add_docks()
        self._log_dock = self._dock_manager.docks.log
        self._training_params_dock = self._dock_manager.docks.training_params
        self._simulation_params_dock = self._dock_manager.docks.simulation_params

    def _setup_panel_switcher(self) -> None:
        self._panel_switcher = PanelSwitcher(
            stack=self._stack,
            panels=PanelSet(
                trade=self._trade_container,
                training=self._training_panel,
                simulation=self._simulation_panel,
            ),
            dock_manager=self._dock_manager,
        )

    def _setup_status_bar(self) -> None:
        status_bar = self.statusBar()
        self._app_auth_status_label = QLabel(self._format_app_auth_status())
        self._oauth_status_label = QLabel(self._format_oauth_status())
        status_bar.addWidget(self._app_auth_status_label)
        status_bar.addWidget(self._oauth_status_label)

    def _connect_signals(self) -> None:
        """Connect panel signals"""
        self._connect_core_signals()
        self._connect_panel_signals()
        self._connect_toolbar_signals()

    def _connect_core_signals(self) -> None:
        self.logRequested.connect(self._handle_log_message)
        self.accountsReceived.connect(self._handle_accounts_received)
        self.fundsReceived.connect(self._handle_funds_received)
        self.appAuthStatusChanged.connect(self._handle_app_auth_status_changed)
        self.oauthStatusChanged.connect(self._handle_oauth_status_changed)
        self.appAuthSucceeded.connect(self._handle_app_auth_success)
        self.oauthSucceeded.connect(self._handle_oauth_success)

    def _connect_panel_signals(self) -> None:
        self._trade_panel.trendbar_toggle_requested.connect(self._on_trendbar_toggle_requested)
        self._trade_panel.history_download_requested.connect(self._on_history_download_requested)
        self._trade_panel.account_info_requested.connect(self._on_fetch_account_info)
        self._trade_panel.symbol_list_requested.connect(self._on_symbol_list_requested)
        self._training_params_panel.start_requested.connect(self._start_ppo_training)
        self._simulation_params_panel.start_requested.connect(self._start_simulation)
        self._log_dock.visibilityChanged.connect(self._sync_log_toggle_action)

    def _connect_toolbar_signals(self) -> None:
        self._action_fetch_account_info.triggered.connect(self._on_fetch_account_info)
        self._action_train_ppo.triggered.connect(self._on_train_ppo_clicked)
        self._action_simulation.triggered.connect(self._on_simulation_clicked)
        self._action_history_download.triggered.connect(self._open_history_download_dialog)
        self._action_toggle_log.toggled.connect(self._toggle_log_dock)

    def _setup_menu_toolbar(self) -> None:
        """Create menu and toolbar actions"""
        self._toolbar_actions = build_toolbar_actions(self, self._log_dock.isVisible())
        self._action_app_auth = self._toolbar_actions.action_app_auth
        self._action_oauth = self._toolbar_actions.action_oauth
        self._action_toggle_connection = self._toolbar_actions.action_toggle_connection
        self._action_fetch_account_info = self._toolbar_actions.action_fetch_account_info
        self._action_train_ppo = self._toolbar_actions.action_train_ppo
        self._action_simulation = self._toolbar_actions.action_simulation
        self._action_history_download = self._toolbar_actions.action_history_download
        self._action_toggle_log = self._toolbar_actions.action_toggle_log

        self._action_app_auth.triggered.connect(self._open_app_auth_dialog)
        self._action_oauth.triggered.connect(self._open_oauth_dialog)
        self._action_toggle_connection.triggered.connect(self._toggle_connection)

    @Slot()
    def _on_trendbar_toggle_requested(self) -> None:
        controller = self._get_trendbar_controller()
        if controller is None:
            return
        controller.toggle(self._trendbar_symbol_id)

    @Slot(bool)
    def _toggle_log_dock(self, visible: bool) -> None:
        if self._dock_manager is None:
            return
        self._dock_manager.toggle_log(visible)

    @Slot(bool)
    def _sync_log_toggle_action(self, visible: bool) -> None:
        self._action_toggle_log.blockSignals(True)
        try:
            self._action_toggle_log.setChecked(visible)
            self._action_toggle_log.setVisible(not visible)
        finally:
            self._action_toggle_log.blockSignals(False)

    @Slot()
    def _on_train_ppo_clicked(self) -> None:
        self._show_panel("training", show_log=True)

    @Slot()
    def _on_simulation_clicked(self) -> None:
        self._show_panel("simulation", show_log=None)

    @Slot(dict)
    def _start_ppo_training(self, params: dict) -> None:
        self._training_panel.reset_metrics()
        controller = self._get_ppo_controller()
        if controller is None:
            return
        controller.start(params, params.get("data_path", ""))

    @Slot(dict)
    def _start_simulation(self, params: dict) -> None:
        controller = self._get_simulation_controller()
        if controller is None:
            return
        self._simulation_params_panel.reset_summary()
        controller.start(params)

    @Slot()
    def _on_history_download_requested(self) -> None:
        controller = self._get_history_download_controller()
        if controller is None:
            return
        controller.request_quick_download(self._trendbar_symbol_id, timeframe="M5")

    @Slot()
    def _open_history_download_dialog(self) -> None:
        controller = self._get_history_download_controller()
        if controller is None:
            return
        controller.open_download_dialog(self._trendbar_symbol_id)

    def _on_symbol_list_requested(self) -> None:
        controller = self._get_history_download_controller()
        if controller is None:
            return
        controller.request_symbol_list()

    def _get_history_download_controller(self) -> Optional[HistoryDownloadController]:
        if not self._use_cases:
            self._log_panel.append("⚠️ 缺少 broker 用例配置")
            return None
        if not self._service:
            self._log_panel.append("⚠️ 尚未完成 App 認證")
            return None
        if not self._is_oauth_authenticated():
            self._log_panel.append("⚠️ 尚未完成 OAuth 帳戶認證")
            return None

        if self._history_download_controller is None:
            self._history_download_controller = HistoryDownloadController(
                use_cases=self._use_cases,
                app_auth_service=self._service,
                oauth_service=self._oauth_service,
                parent=self,
                log=self._log_panel.append,
                log_async=self.logRequested.emit,
            )
        return self._history_download_controller

    def _get_trendbar_controller(self) -> Optional[TrendbarController]:
        if not self._use_cases:
            self._log_panel.append("⚠️ 缺少 broker 用例配置")
            return None
        if not self._service:
            self._log_panel.append("⚠️ 尚未完成 App 認證")
            return None
        if not self._is_oauth_authenticated():
            self._log_panel.append("⚠️ 尚未完成 OAuth 帳戶認證")
            return None

        if self._trendbar_controller is None:
            self._trendbar_controller = TrendbarController(
                use_cases=self._use_cases,
                app_auth_service=self._service,
                oauth_service=self._oauth_service,
                parent=self,
                log=self._log_panel.append,
                log_async=self.logRequested.emit,
                set_active=self._trade_panel.set_trendbar_active,
                format_price=self._format_price,
            )
        return self._trendbar_controller

    def _get_ppo_controller(self) -> Optional[PPOTrainingController]:
        if self._ppo_controller is None:
            self._ppo_controller = PPOTrainingController(
                parent=self,
                log=self._log_panel.append,
                ingest_log=self._training_panel.ingest_log_line,
            )
        return self._ppo_controller

    def _get_simulation_controller(self) -> Optional[SimulationController]:
        if self._simulation_controller is None:
            self._simulation_controller = SimulationController(
                parent=self,
                log=self._log_panel.append,
                reset_plot=self._simulation_panel.reset_plot,
                ingest_equity=self._simulation_panel.ingest_equity,
                update_summary=self._simulation_params_panel.update_summary,
                update_trade_stats=self._simulation_params_panel.update_trade_stats,
                update_streak_stats=self._simulation_params_panel.update_streak_stats,
                update_holding_stats=self._simulation_params_panel.update_holding_stats,
                update_action_distribution=self._simulation_params_panel.update_action_distribution,
                update_playback_range=self._simulation_params_panel.update_playback_range,
            )
        return self._simulation_controller

    @Slot()
    def _on_fetch_account_info(self) -> None:
        """Handle fetch account info click"""
        self._show_panel("trade", show_log=None)

    def _show_panel(self, panel: str, *, show_log: Optional[bool]) -> None:
        if self._panel_switcher is None:
            return
        self._panel_switcher.show(panel, show_log)

    def _set_log_collapsed(self, collapsed: bool) -> None:
        self._log_collapsed = collapsed
        if self._dock_manager is None:
            return
        self._dock_manager.set_log_collapsed(collapsed)
        self._action_toggle_log.blockSignals(True)
        self._action_toggle_log.setChecked(not collapsed)
        self._action_toggle_log.blockSignals(False)

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
        if self._trendbar_controller:
            self._trendbar_controller.reset()
        if hasattr(self._service, "clear_log_history"):
            try:
                self._service.clear_log_history()
            except Exception:
                pass
        self._service.set_callbacks(
            on_app_auth_success=lambda c: self.appAuthSucceeded.emit(c),
            on_log=self.logRequested.emit,
            on_status_changed=lambda s: self.appAuthStatusChanged.emit(int(s)),
        )
        self._app_auth_status_label.setText(self._format_app_auth_status())
        if self._app_state:
            self._app_state.update_app_status(int(service.status))
        self._sync_connection_action()

    def set_oauth_service(self, service: OAuthServiceLike) -> None:
        """Set the OAuth service"""
        self._oauth_service = service
        if hasattr(self._oauth_service, "clear_log_history"):
            try:
                self._oauth_service.clear_log_history()
            except Exception:
                pass
        self._oauth_service.set_callbacks(
            on_oauth_success=lambda t: self.oauthSucceeded.emit(t),
            on_log=self.logRequested.emit,
            on_status_changed=lambda s: self.oauthStatusChanged.emit(int(s)),
        )
        self._oauth_status_label.setText(self._format_oauth_status())
        if self._app_state:
            self._app_state.update_oauth_status(int(service.status))
        self._sync_connection_action()

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
            if oauth_service is not None:
                self.set_oauth_service(oauth_service)
            else:
                self._log_panel.append("⚠️ OAuth 服務建立失敗")
        self._oauth_dialog_open = False

    def _format_app_auth_status(self) -> str:
        """Format app auth status for display"""
        status = None if not self._service else self._service.status
        return format_app_auth_status(status)

    def _format_oauth_status(self) -> str:
        """Format OAuth status for display"""
        status = None if not self._oauth_service else self._oauth_service.status
        return format_oauth_status(status)

    @Slot(str)
    def _handle_log_message(self, message: str) -> None:
        self._log_panel.append(message)

    def _handle_app_auth_success(self, _client) -> None:
        self._app_auth_status_label.setText(self._format_app_auth_status())
        self._log_panel.append("✅ 服務已連線")
        if self._app_state:
            self._app_state.update_app_status(int(self._service.status))
        self._sync_connection_action()

    def _handle_app_auth_status_changed(self, status: ConnectionStatus) -> None:
        self._app_auth_status_label.setText(self._format_app_auth_status())
        if self._app_state:
            self._app_state.update_app_status(int(status))
        if (
            status == ConnectionStatus.DISCONNECTED
            and self._oauth_service
            and self._oauth_service.status != ConnectionStatus.DISCONNECTED
        ):
            self._oauth_service.disconnect()
            self._oauth_status_label.setText(self._format_oauth_status())
            if self._trendbar_controller:
                self._trendbar_controller.reset()
        self._sync_connection_action()
        if status >= ConnectionStatus.APP_AUTHENTICATED:
            pass

    def _handle_oauth_success(self, _tokens) -> None:
        self._oauth_status_label.setText(self._format_oauth_status())
        self._log_panel.append("✅ OAuth 已連線")
        if self._app_state:
            self._app_state.update_oauth_status(int(self._oauth_service.status))
        self._sync_connection_action()

    def _handle_oauth_status_changed(self, status: ConnectionStatus) -> None:
        self._oauth_status_label.setText(self._format_oauth_status())
        if self._app_state:
            self._app_state.update_oauth_status(int(status))
        self._sync_connection_action()

    def _is_app_authenticated(self) -> bool:
        if not self._service:
            return False
        is_auth = getattr(self._service, "is_app_authenticated", None)
        if isinstance(is_auth, bool):
            return is_auth
        return self._service.status >= ConnectionStatus.APP_AUTHENTICATED

    def _is_oauth_authenticated(self) -> bool:
        if not self._oauth_service:
            return False
        return self._oauth_service.status >= ConnectionStatus.ACCOUNT_AUTHENTICATED

    def _sync_connection_action(self) -> None:
        if not hasattr(self, "_action_toggle_connection"):
            return
        if self._is_oauth_authenticated():
            self._action_toggle_connection.setText("斷線")
        else:
            self._action_toggle_connection.setText("連線")

    @Slot()
    def _toggle_connection(self) -> None:
        if self._connection_in_progress:
            self._log_panel.append("⏳ 連線流程進行中，請稍候")
            return

        # 已連線時執行「斷線」
        if self._is_oauth_authenticated() or self._is_app_authenticated():
            self._connection_in_progress = True
            try:
                if self._oauth_service and self._oauth_service.status != ConnectionStatus.DISCONNECTED:
                    self._oauth_service.disconnect()
                self._oauth_service = None
                if self._app_state:
                    self._app_state.update_oauth_status(int(ConnectionStatus.DISCONNECTED))
                self._oauth_status_label.setText(self._format_oauth_status())

                if self._service and getattr(self._service, "status", None) != ConnectionStatus.DISCONNECTED:
                    self._service.disconnect()
                if self._service and hasattr(self._service, "clear_log_history"):
                    try:
                        self._service.clear_log_history()
                    except Exception:
                        pass
                self._service = None
                if self._app_state:
                    self._app_state.update_app_status(int(ConnectionStatus.DISCONNECTED))
                self._app_auth_status_label.setText(self._format_app_auth_status())

                self._reset_controllers()
                self._log_panel.append("🔌 已斷線")
            finally:
                self._connection_in_progress = False
            return

        # 未連線時執行「連線」
        self._connection_in_progress = True
        try:
            self._open_app_auth_dialog(auto_connect=True)
            if not self._is_app_authenticated():
                return
            self._open_oauth_dialog(auto_connect=True)
            if self._is_oauth_authenticated():
                self._log_panel.append("✅ 已完成連線")
        finally:
            self._connection_in_progress = False

    def _reset_controllers(self) -> None:
        if self._trendbar_controller:
            try:
                self._trendbar_controller.reset()
            except Exception:
                pass
        self._trendbar_controller = None
        self._history_download_controller = None

    def _sync_status_from_state(self, state: AppState) -> None:
        if state.app_status is not None:
            self._app_auth_status_label.setText(self._format_app_auth_status())
        if state.oauth_status is not None:
            self._oauth_status_label.setText(self._format_oauth_status())
