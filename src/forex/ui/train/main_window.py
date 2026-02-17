# ui/train/main_window.py
from typing import Optional

from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import Slot, Signal

from forex.ui.train.layout.dock_manager import DockManagerController
from forex.ui.train.layout.main_window_builder import (
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
from forex.ui.train.layout.panel_switcher import PanelSwitcher

from forex.ui.shared.controllers.connection_controller import ConnectionController
from forex.ui.shared.controllers.service_binding import clear_log_history_safe, set_callbacks_safe
from forex.ui.train.controllers.history_download_controller import HistoryDownloadController
from forex.ui.train.controllers.account_info_controller import AccountInfoController
from forex.ui.train.controllers.ppo_training_controller import PPOTrainingController
from forex.ui.train.controllers.simulation_controller import SimulationController
from forex.ui.train.presenters.connection_presenter import ConnectionPresenter
from forex.ui.train.presenters.history_download_presenter import HistoryDownloadPresenter

from forex.application.broker.protocols import AppAuthServiceLike, OAuthServiceLike
from forex.application.broker.use_cases import BrokerUseCases
from forex.application.events import EventBus
from forex.application.state import AppState
from forex.config.constants import ConnectionStatus
from forex.config.paths import TOKEN_FILE
from forex.config.settings import OAuthTokens
from forex.ui.shared.utils.formatters import (
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
        self._trendbar_symbol_id = 1
        self._ppo_controller: Optional[PPOTrainingController] = None
        self._simulation_controller: Optional[SimulationController] = None
        self._account_info_controller: Optional[AccountInfoController] = None
        self._dock_controller: Optional[DockManagerController] = None
        self._panel_switcher: Optional[PanelSwitcher] = None
        self._connection_controller: Optional[ConnectionController] = None
        self._connection_presenter: Optional[ConnectionPresenter] = None
        self._training_state = None
        self._training_presenter = None
        self._simulation_state = None
        self._simulation_presenter = None
        self._history_download_state = None
        self._history_download_presenter = None

        self._setup_ui()
        self._setup_connection_presenter()
        self._setup_connection_controller()
        self._setup_account_info_controller()
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

    def _setup_account_info_controller(self) -> None:
        self._account_info_controller = AccountInfoController(
            parent=self,
            log=self.logRequested.emit,
            use_cases=self._use_cases,
            service=self._service,
        )

    def _setup_window(self) -> None:
        self.setWindowTitle("Forex Trading App")
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
        self._history_integrity_panel = bundle.history_integrity_panel
        self._simulation_params_panel = bundle.simulation_params_panel
        self._log_panel = bundle.log_panel
        self._training_state = bundle.training_state
        self._training_presenter = bundle.training_presenter
        self._simulation_state = bundle.simulation_state
        self._simulation_presenter = bundle.simulation_presenter
        self._history_download_state = bundle.history_download_state
        self._history_download_presenter = HistoryDownloadPresenter(self._history_download_state)

    def _setup_stack(self) -> None:
        stack_bundle: StackBundle = build_stack(
            self,
            trade_panel=self._trade_panel,
            training_panel=self._training_panel,
            simulation_panel=self._simulation_panel,
            history_integrity_panel=self._history_integrity_panel,
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
            history_integrity_panel=self._history_integrity_panel,
            dock_controller=self._dock_controller,
        )

    def _setup_status_bar(self) -> None:
        app_auth_text = format_app_auth_status(None if not self._service else self._service.status)
        oauth_text = format_oauth_status(None if not self._oauth_service else self._oauth_service.status)
        status_bundle: StatusBundle = build_status_bar(
            self,
            app_auth_text=app_auth_text,
            oauth_text=oauth_text,
        )
        self._app_auth_status_label = status_bundle.app_auth_label
        self._oauth_status_label = status_bundle.oauth_label

    def _connect_signals(self) -> None:
        """Connect panel signals"""
        self._connect_core_signals()
        self._connect_panel_signals()

    def _connect_core_signals(self) -> None:
        if self._connection_presenter:
            self.logRequested.connect(self._connection_presenter.handle_log_message)
            self.appAuthStatusChanged.connect(self._connection_presenter.handle_app_auth_status_changed)
            self.oauthStatusChanged.connect(self._connection_presenter.handle_oauth_status_changed)
            self.appAuthSucceeded.connect(self._connection_presenter.handle_app_auth_success)
            self.oauthSucceeded.connect(self._connection_presenter.handle_oauth_success)
        else:
            self.logRequested.connect(self._log_panel.append)
        if self._account_info_controller is not None:
            self.accountsReceived.connect(self._account_info_controller.handle_accounts_received)
            self.fundsReceived.connect(self._account_info_controller.handle_funds_received)
            self._account_info_controller.accountSelected.connect(self._trade_panel.update_account_info)
            self._account_info_controller.fundsUpdated.connect(self._trade_panel.update_trader_info)

    def _connect_panel_signals(self) -> None:
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
            on_data_check=self._open_data_check_dialog,
            on_toggle_log=self._dock_controller.toggle_log,
        )
        _ = toolbar_bundle.toolbar_controller
        self._action_toggle_connection = toolbar_bundle.action_toggle_connection

    def _setup_connection_presenter(self) -> None:
        if not hasattr(self, "_action_toggle_connection"):
            return
        self._connection_presenter = ConnectionPresenter(
            parent=self,
            log_panel=self._log_panel,
            app_auth_label=self._app_auth_status_label,
            oauth_label=self._oauth_status_label,
            toggle_action=self._action_toggle_connection,
            app_state=self._app_state,
            on_app_disconnected=self._reset_controllers,
        )
        self._connection_presenter.set_services(self._service, self._oauth_service)
        self._connection_presenter.refresh_status_labels()

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
    def _open_history_download_dialog(self) -> None:
        if not self._ensure_account_info_connection():
            return
        controller = self._get_history_download_controller()
        if controller is None:
            return
        controller.open_download_dialog(self._trendbar_symbol_id)

    @Slot()
    def _open_data_check_dialog(self) -> None:
        self._show_panel("data_check", show_log=None)

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
                presenter=self._history_download_presenter,
            )
        return self._history_download_controller

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
        if not self._ensure_account_info_connection():
            return
        self._fetch_account_info()

    def _ensure_account_info_connection(self) -> bool:
        if not self._connection_controller:
            self.logRequested.emit(format_connection_message("missing_connection_controller"))
            return False

        if not self._is_app_authenticated():
            self._open_app_auth_dialog(auto_connect=True)
        if not self._is_app_authenticated():
            self.logRequested.emit(format_connection_message("missing_app_auth"))
            return False

        if not self._is_oauth_authenticated():
            self._open_oauth_dialog(auto_connect=True)
        if not self._is_oauth_authenticated():
            self.logRequested.emit(format_connection_message("missing_oauth"))
            return False

        return True

    def _load_tokens_for_accounts(self) -> Optional[OAuthTokens]:
        try:
            return OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self.logRequested.emit(f"⚠️ Failed to read token file: {exc}")
            return None

    def _fetch_account_info(self) -> None:
        if not self._use_cases:
            self.logRequested.emit(format_connection_message("missing_use_cases"))
            return
        if not self._service:
            self.logRequested.emit(format_connection_message("missing_app_auth"))
            return
        tokens = self._load_tokens_for_accounts()
        access_token = "" if tokens is None else str(tokens.access_token or "").strip()
        if not access_token:
            self.logRequested.emit("⚠️ Missing Access Token. Complete OAuth authorization first")
            return

        from forex.utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        selected_account_id = None if tokens is None else tokens.account_id

        if tokens is not None:
            expires_at = None
            try:
                expires_at = int(tokens.expires_at) if tokens.expires_at is not None else None
            except Exception:
                expires_at = None
            seconds_to_expiry = None
            try:
                seconds_to_expiry = tokens.seconds_to_expiry()
            except Exception:
                seconds_to_expiry = None
            self._trade_panel.update_token_info(expires_at, seconds_to_expiry)

        if tokens is not None and tokens.account_id:
            if self._use_cases.symbol_by_id_in_progress():
                self.logRequested.emit("⏳ Fetching symbol details, please wait")
            else:
                symbol_id = int(self._trendbar_symbol_id or 0)
                if symbol_id:
                    reactor.callFromThread(
                        self._use_cases.fetch_symbol_by_id,
                        self._service,
                        int(tokens.account_id),
                        [symbol_id],
                        False,
                        lambda symbols: self._trade_panel.update_symbol_commission_info(
                            symbols[0] if symbols else {}
                        ),
                        lambda e: self.logRequested.emit(f"⚠️ Failed to fetch symbol details: {e}"),
                        self.logRequested.emit,
                    )
                else:
                    self.logRequested.emit("⚠️ Missing symbol ID. Cannot fetch commission settings")

        if self._use_cases.account_list_in_progress():
            self.logRequested.emit("⏳ Fetching account list, please wait")
        else:
            reactor.callFromThread(
                self._use_cases.fetch_accounts,
                self._service,
                access_token,
                lambda accounts: self.accountsReceived.emit(accounts, selected_account_id),
                lambda e: self.logRequested.emit(f"⚠️ Failed to fetch account list: {e}"),
                self.logRequested.emit,
            )

        if self._use_cases.ctid_profile_in_progress():
            self.logRequested.emit("⏳ Fetching CTID profile, please wait")
            return

        reactor.callFromThread(
            self._use_cases.fetch_ctid_profile,
            self._service,
            access_token,
            lambda profile: self._trade_panel.update_profile_info(profile.user_id),
            lambda e: self.logRequested.emit(f"⚠️ Failed to fetch CTID profile: {e}"),
            self.logRequested.emit,
        )


    def _show_panel(self, panel: str, *, show_log: Optional[bool]) -> None:
        if self._panel_switcher is None:
            return
        self._panel_switcher.show(panel, show_log=show_log)

    def set_service(self, service: AppAuthServiceLike) -> None:
        """Set the authenticated service"""
        self._service = service
        if self._connection_controller and self._connection_controller.service is not service:
            self._connection_controller.seed_services(service, self._oauth_service)
        if self._account_info_controller:
            self._account_info_controller.set_service(service)
        clear_log_history_safe(self._service)
        set_callbacks_safe(
            self._service,
            on_app_auth_success=lambda c: self.appAuthSucceeded.emit(c),
            on_log=self.logRequested.emit,
            on_status_changed=lambda s: self.appAuthStatusChanged.emit(int(s)),
        )
        if self._connection_presenter:
            self._connection_presenter.set_services(self._service, self._oauth_service)
            self._connection_presenter.refresh_status_labels()
        if self._app_state:
            self._app_state.update_app_status(int(service.status))

    def set_oauth_service(self, service: OAuthServiceLike) -> None:
        """Set the OAuth service"""
        self._oauth_service = service
        if self._connection_controller and self._connection_controller.oauth_service is not service:
            self._connection_controller.seed_services(self._service, service)
        clear_log_history_safe(self._oauth_service)
        set_callbacks_safe(
            self._oauth_service,
            on_oauth_success=lambda t: self.oauthSucceeded.emit(t),
            on_log=self.logRequested.emit,
            on_status_changed=lambda s: self.oauthStatusChanged.emit(int(s)),
        )
        if self._connection_presenter:
            self._connection_presenter.set_services(self._service, self._oauth_service)
            self._connection_presenter.refresh_status_labels()
        if self._app_state:
            self._app_state.update_oauth_status(int(service.status))

    def _open_app_auth_dialog(self, auto_connect: bool = False) -> None:
        if not self._connection_controller:
            return
        self._connection_controller.open_app_auth_dialog(auto_connect=auto_connect)

    def _open_oauth_dialog(self, auto_connect: bool = True) -> None:
        if not self._connection_controller:
            return
        self._connection_controller.open_oauth_dialog(auto_connect=auto_connect)


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

    @Slot()
    def _toggle_connection(self) -> None:
        if not self._connection_controller:
            self._log_panel.append(format_connection_message("missing_connection_controller"))
            return
        self._connection_controller.toggle_connection()

    def _reset_controllers(self) -> None:
        self._history_download_controller = None

    def _sync_status_from_state(self, state: AppState) -> None:
        if not self._connection_presenter:
            return
        if state.app_status is not None or state.oauth_status is not None:
            self._connection_presenter.refresh_status_labels()
