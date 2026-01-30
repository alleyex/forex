# ui/main_window.py
from typing import Optional
import sys

from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import Slot, Signal, Qt

from ui.layout.dock_manager import DockManagerController
from ui.layout.main_window_builder import (
    PanelBundle,
    StackBundle,
    StatusBundle,
    ToolbarBundle,
    build_docks,
    build_panel_switcher,
    build_panels,
    build_stack,
    build_status_bar,
    build_toolbar,
)

from ui.controllers import (
    ConnectionController,
    HistoryDownloadController,
    PPOTrainingController,
    SimulationController,
    ToolbarController,
    TrendbarController,
)

from application import (
    AppState,
    AppAuthServiceLike,
    BrokerUseCases,
    EventBus,
    OAuthServiceLike,
)
from domain import AccountFundsSnapshot
from config.settings import OAuthTokens
from utils.reactor_manager import reactor_manager

from config.constants import ConnectionStatus
from ui.utils.formatters import (
    format_app_auth_status,
    format_connection_message,
    format_oauth_status,
)


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
        self._ppo_controller: Optional[PPOTrainingController] = None
        self._simulation_controller: Optional[SimulationController] = None
        self._trendbar_controller = None
        self._history_download_controller = None
        self._dock_controller: Optional[DockManagerController] = None
        self._panel_switcher: Optional[PanelSwitcher] = None
        self._toolbar_controller: Optional[ToolbarController] = None
        self._connection_controller: Optional[ConnectionController] = None
        self._training_state = None
        self._training_presenter = None
        self._simulation_state = None
        self._simulation_presenter = None
        self._history_download_state = None

        self._setup_ui()
        self._setup_connection_controller()
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
        self._show_panel("training", show_log=True)

    def _setup_connection_controller(self) -> None:
        if not self._use_cases:
            return
        controller = ConnectionController(
            parent=self,
            use_cases=self._use_cases,
            app_state=self._app_state,
            event_bus=self._event_bus,
            on_service_ready=self.set_service,
            on_oauth_ready=self.set_oauth_service,
            on_reset_controllers=self._reset_controllers,
        )
        controller.seed_services(self._service, self._oauth_service)
        controller.logRequested.connect(self.logRequested.emit)
        controller.appAuthStatusChanged.connect(self.appAuthStatusChanged.emit)
        controller.oauthStatusChanged.connect(self.oauthStatusChanged.emit)
        self._connection_controller = controller

    def _setup_window(self) -> None:
        self.setWindowTitle("外匯交易應用程式")
        self.setMinimumSize(1280, 720)
        self.resize(1280, 720)

    def _setup_panels(self) -> None:
        bundle: PanelBundle = build_panels(
            self,
            on_optuna_best_params=self._on_optuna_best_params,
            on_simulation_summary=self._update_simulation_summary,
        )
        self._trade_panel = bundle.trade_panel
        self._training_panel = bundle.training_panel
        self._training_params_panel = bundle.training_params_panel
        self._simulation_panel = bundle.simulation_panel
        self._simulation_params_panel = bundle.simulation_params_panel
        self._log_panel = bundle.log_panel
        self._training_state = bundle.training_state
        self._training_presenter = bundle.training_presenter
        self._simulation_state = bundle.simulation_state
        self._simulation_presenter = bundle.simulation_presenter
        self._history_download_state = bundle.history_download_state

    def _setup_stack(self) -> None:
        stack_bundle: StackBundle = build_stack(
            self,
            trade_panel=self._trade_panel,
            training_panel=self._training_panel,
            simulation_panel=self._simulation_panel,
        )
        self._stack = stack_bundle.stack
        self._trade_container = stack_bundle.trade_container

    def _setup_docks(self) -> None:
        self._dock_controller = build_docks(
            log_panel=self._log_panel,
            training_params_panel=self._training_params_panel,
            simulation_params_panel=self._simulation_params_panel,
            main_window=self,
        )

    def _setup_panel_switcher(self) -> None:
        if self._dock_controller is None:
            return
        self._panel_switcher = build_panel_switcher(
            stack=self._stack,
            trade_container=self._trade_container,
            training_panel=self._training_panel,
            simulation_panel=self._simulation_panel,
            dock_controller=self._dock_controller,
        )

    def _setup_status_bar(self) -> None:
        status_bundle: StatusBundle = build_status_bar(
            self,
            app_auth_text=self._format_app_auth_status(),
            oauth_text=self._format_oauth_status(),
        )
        self._app_auth_status_label = status_bundle.app_auth_label
        self._oauth_status_label = status_bundle.oauth_label

    def _connect_signals(self) -> None:
        """Connect panel signals"""
        self._connect_core_signals()
        self._connect_panel_signals()

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
        self._training_params_panel.optuna_requested.connect(self._start_ppo_training)
        self._training_params_panel.tab_changed.connect(self._on_training_tab_changed)
        self._simulation_params_panel.start_requested.connect(self._start_simulation)
        self._simulation_params_panel.stop_requested.connect(self._stop_simulation)

    def _setup_menu_toolbar(self) -> None:
        """Create menu and toolbar actions"""
        if self._dock_controller is None:
            return
        toolbar_bundle: ToolbarBundle = build_toolbar(
            self,
            dock_controller=self._dock_controller,
            on_app_auth=self._open_app_auth_dialog,
            on_oauth=self._open_oauth_dialog,
            on_toggle_connection=self._toggle_connection,
            on_fetch_account_info=self._on_fetch_account_info,
            on_train_ppo=self._on_train_ppo_clicked,
            on_simulation=self._on_simulation_clicked,
            on_history_download=self._open_history_download_dialog,
            on_toggle_log=self._dock_controller.toggle_log,
        )
        self._toolbar_controller = toolbar_bundle.toolbar_controller
        self._action_toggle_connection = toolbar_bundle.action_toggle_connection

    @Slot()
    def _on_trendbar_toggle_requested(self) -> None:
        controller = self._get_trendbar_controller()
        if controller is None:
            return
        controller.toggle(self._trendbar_symbol_id)

    @Slot()
    def _on_train_ppo_clicked(self) -> None:
        self._show_panel("training", show_log=True)

    @Slot()
    def _on_simulation_clicked(self) -> None:
        self._show_panel("simulation", show_log=None)

    @Slot(dict)
    def _start_ppo_training(self, params: dict) -> None:
        if not params.get("optuna_only", False):
            self._training_panel.reset_metrics()
        if params.get("optuna_trials", 0) > 0:
            self._training_panel.reset_optuna_metrics()
            self._training_presenter.reset_optuna_results()
        controller = self._get_ppo_controller()
        if controller is None:
            return
        controller.start(params, params.get("data_path", ""))

    @Slot(dict)
    def _start_simulation(self, params: dict) -> None:
        controller = self._get_simulation_controller()
        if controller is None:
            return
        controller.start(params)

    @Slot()
    def _stop_simulation(self) -> None:
        controller = self._get_simulation_controller()
        if controller is None:
            return
        controller.stop()

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
            self._log_panel.append(format_connection_message("missing_use_cases"))
            return None
        if not self._service:
            self._log_panel.append(format_connection_message("missing_app_auth"))
            return None
        if not self._is_oauth_authenticated():
            self._log_panel.append(format_connection_message("missing_oauth"))
            return None

        if self._history_download_controller is None:
            self._history_download_controller = HistoryDownloadController(
                use_cases=self._use_cases,
                app_auth_service=self._service,
                oauth_service=self._oauth_service,
                parent=self,
                state=self._history_download_state,
            )
        return self._history_download_controller

    def _get_trendbar_controller(self) -> Optional[TrendbarController]:
        if not self._use_cases:
            self._log_panel.append(format_connection_message("missing_use_cases"))
            return None
        if not self._service:
            self._log_panel.append(format_connection_message("missing_app_auth"))
            return None
        if not self._is_oauth_authenticated():
            self._log_panel.append(format_connection_message("missing_oauth"))
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
            if not self._training_presenter or not self._training_state:
                return None
            self._ppo_controller = PPOTrainingController(
                parent=self,
                state=self._training_state,
                ingest_log=self._training_presenter.handle_log_line,
                ingest_optuna_log=self._training_presenter.handle_optuna_log_line,
                on_finished=lambda *_: self._training_panel.flush_plot(),
            )
            self._ppo_controller.best_params_found.connect(
                self._training_presenter.handle_best_params_found
            )
            self._ppo_controller.optuna_trial_logged.connect(
                self._training_presenter.handle_optuna_trial_summary
            )
            self._ppo_controller.optuna_best_params_logged.connect(
                self._training_presenter.handle_optuna_best_params
            )
        return self._ppo_controller

    @Slot(str)
    def _on_training_tab_changed(self, tab: str) -> None:
        if tab == "optuna":
            self._training_panel.show_optuna_plot()
        else:
            self._training_panel.show_training_plot()

    @Slot(dict)
    def _on_optuna_best_params(self, params: dict) -> None:
        if not self._training_params_panel.should_apply_optuna():
            return
        self._training_params_panel.apply_optuna_params(params)
        self._training_params_panel.update_optuna_best_params(params)

    def _get_simulation_controller(self) -> Optional[SimulationController]:
        if self._simulation_controller is None:
            self._simulation_controller = SimulationController(
                parent=self,
                state=self._simulation_state,
                presenter=self._simulation_presenter,
            )
        return self._simulation_controller

    @Slot(dict)
    def _update_simulation_summary(self, data: dict) -> None:
        self._simulation_params_panel.update_summary(**data)

    @Slot()
    def _on_fetch_account_info(self) -> None:
        """Handle fetch account info click"""
        self._show_panel("trade", show_log=None)

    def _show_panel(self, panel: str, *, show_log: Optional[bool]) -> None:
        if self._panel_switcher is None:
            return
        self._panel_switcher.show(panel, show_log=show_log)

    def _handle_accounts_received(self, accounts: list, account_id: Optional[int]) -> None:
        try:
            self.logRequested.emit(format_connection_message("account_count", count=len(accounts)))
            if not accounts:
                self.logRequested.emit(format_connection_message("account_list_empty"))
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
            self.logRequested.emit(format_connection_message("account_info_header"))
            self.logRequested.emit(
                format_connection_message("account_field", label="帳戶 ID", value=selected.account_id)
            )
            self.logRequested.emit(
                format_connection_message("account_field", label="環境", value=env_text)
            )
            self.logRequested.emit(
                format_connection_message("account_field", label="交易登入", value=login_text)
            )
            self._fetch_account_funds(selected.account_id)
        except Exception as exc:
            self.logRequested.emit(format_connection_message("account_parse_failed", error=exc))

    def _fetch_account_funds(self, account_id: int) -> None:
        if not self._service:
            self.logRequested.emit(format_connection_message("missing_app_auth"))
            return

        if self._use_cases is None:
            self.logRequested.emit(format_connection_message("missing_use_cases"))
            return
        if self._use_cases.account_funds_in_progress():
            self.logRequested.emit(format_connection_message("fetching_funds"))
            return
        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(
            self._use_cases.fetch_account_funds,
            self._service,
            account_id,
            lambda funds: self.fundsReceived.emit(funds),
            lambda e: self.logRequested.emit(format_connection_message("funds_error", error=e)),
            self.logRequested.emit,
        )

    def _handle_funds_received(self, funds: AccountFundsSnapshot) -> None:
        snapshot = funds
        self.logRequested.emit(format_connection_message("funds_header"))
        money_digits = snapshot.money_digits if snapshot.money_digits is not None else 2
        self.logRequested.emit(
            format_connection_message(
                "funds_field",
                label="餘額",
                value=self._format_money(snapshot.balance, money_digits),
            )
        )
        self.logRequested.emit(
            format_connection_message(
                "funds_field",
                label="淨值",
                value=self._format_money(snapshot.equity, money_digits),
            )
        )
        self.logRequested.emit(
            format_connection_message(
                "funds_field",
                label="可用資金",
                value=self._format_money(snapshot.free_margin, money_digits),
            )
        )
        self.logRequested.emit(
            format_connection_message(
                "funds_field",
                label="已用保證金",
                value=self._format_money(snapshot.used_margin, money_digits),
            )
        )
        if snapshot.margin_level is None:
            margin_text = "-"
        else:
            margin_text = f"{snapshot.margin_level:.2f}%"
        self.logRequested.emit(
            format_connection_message(
                "funds_field",
                label="保證金比例",
                value=margin_text,
            )
        )
        self.logRequested.emit(
            format_connection_message(
                "funds_field",
                label="帳戶幣別",
                value=snapshot.currency or "-",
            )
        )

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
        if self._connection_controller and self._connection_controller.service is not service:
            self._connection_controller.seed_services(service, self._oauth_service)
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
        if self._connection_controller and self._connection_controller.oauth_service is not service:
            self._connection_controller.seed_services(self._service, service)
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
        if not self._connection_controller:
            return
        self._connection_controller.open_app_auth_dialog(auto_connect=auto_connect)

    def _open_oauth_dialog(self, auto_connect: bool = True) -> None:
        if not self._connection_controller:
            return
        self._connection_controller.open_oauth_dialog(auto_connect=auto_connect)

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
        self._log_panel.append(format_connection_message("service_connected"))
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
        self._log_panel.append(format_connection_message("oauth_connected"))
        if self._app_state:
            self._app_state.update_oauth_status(int(self._oauth_service.status))
        self._sync_connection_action()

    def _handle_oauth_status_changed(self, status: ConnectionStatus) -> None:
        self._oauth_status_label.setText(self._format_oauth_status())
        if self._app_state:
            self._app_state.update_oauth_status(int(status))
        self._sync_connection_action()

    def _is_app_authenticated(self) -> bool:
        if self._connection_controller:
            return self._connection_controller.is_app_authenticated()
        if not self._service:
            return False
        is_auth = getattr(self._service, "is_app_authenticated", None)
        if isinstance(is_auth, bool):
            return is_auth
        return self._service.status >= ConnectionStatus.APP_AUTHENTICATED

    def _is_oauth_authenticated(self) -> bool:
        if self._connection_controller:
            return self._connection_controller.is_oauth_authenticated()
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
        if not self._connection_controller:
            self._log_panel.append(format_connection_message("missing_connection_controller"))
            return
        self._connection_controller.toggle_connection()

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
