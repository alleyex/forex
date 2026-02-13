from __future__ import annotations

from typing import Optional
from datetime import datetime
import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot, QTimer, QMetaObject, QThread, QSize, QCoreApplication
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QGridLayout,
    QSplitter,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QToolButton,
    QToolBar,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
    QApplication,
)

try:
    import pyqtgraph as pg
    from pyqtgraph.Qt import QtCore, QtGui
except Exception:  # pragma: no cover - optional dependency
    pg = None
    QtCore = None
    QtGui = None
else:
    try:
        pg.setConfigOptions(useOpenGL=False, antialias=False)
    except Exception:
        pass

from forex.application.broker.protocols import AppAuthServiceLike, OAuthServiceLike
from forex.application.broker.use_cases import BrokerUseCases
from forex.application.events import EventBus
from forex.application.state import AppState
from forex.config.constants import ConnectionStatus
from forex.config.paths import MODEL_DIR, SYMBOL_LIST_FILE, TOKEN_FILE
from forex.config.settings import OAuthTokens
from forex.ui.live.account_controller import LiveAccountController
from forex.ui.live.auto_lifecycle_service import LiveAutoLifecycleService
from forex.ui.live.auto_log_service import LiveAutoLogService
from forex.ui.live.auto_recovery_service import LiveAutoRecoveryService
from forex.ui.live.auto_runtime_service import LiveAutoRuntimeService
from forex.ui.live.auto_settings_persistence import LiveAutoSettingsPersistence
from forex.ui.live.auto_settings_validator import AutoTradeSettingsValidator
from forex.ui.live.autotrade_coordinator import LiveAutoTradeCoordinator
from forex.ui.live.chart_coordinator import LiveChartCoordinator
from forex.ui.live.market_data_controller import LiveMarketDataController
from forex.ui.live.positions_controller import LivePositionsController
from forex.ui.live.quote_controller import LiveQuoteController
from forex.ui.live.symbol_list_service import LiveSymbolListService
from forex.ui.live.value_formatter_service import LiveValueFormatterService
from forex.ui.live.layout_coordinator import LiveLayoutCoordinator
from forex.ui.live.symbol_controller import LiveSymbolController
from forex.ui.live.session_orchestrator import LiveSessionOrchestrator
from forex.ui.live.ui_builder import LiveUIBuilder
from forex.ui.live.window_state import initialize_live_window_state
from forex.ui.shared.controllers.connection_controller import ConnectionController
from forex.ui.shared.controllers.service_binding import clear_log_history_safe, set_callbacks_safe
from forex.ui.shared.utils.formatters import (
    format_app_auth_status,
    format_connection_message,
    format_oauth_status,
)
from forex.ui.shared.widgets.log_widget import LogWidget


class LiveMainWindow(QMainWindow):
    """Live trading application window."""

    logRequested = Signal(str)
    appAuthStatusChanged = Signal(int)
    oauthStatusChanged = Signal(int)
    oauthError = Signal(str)
    oauthSuccess = Signal(object)
    appStateChanged = Signal(object)
    positionsUpdated = Signal(object)
    accountSummaryUpdated = Signal(object)
    historyReceived = Signal(list)
    trendbarReceived = Signal(dict)
    quoteUpdated = Signal(int, object, object, object)
    _CARD_LINE_TITLE_COLOR = "#3a4452"
    _CARD_LINE_TITLE_FONT_SIZE_PX = 10
    _CARD_LINE_TITLE_OFFSET_PX = -20

    # Initialization
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
        self._symbol_controller = LiveSymbolController(self)
        initialize_live_window_state(self)
        self._account_controller = LiveAccountController(self)
        self._autotrade_coordinator = LiveAutoTradeCoordinator(self)
        self._chart_coordinator = LiveChartCoordinator(self)
        self._market_data_controller = LiveMarketDataController(self)
        self._quote_controller = LiveQuoteController(self)
        self._positions_controller = LivePositionsController(self)
        self._value_formatter = LiveValueFormatterService(self)
        self._symbol_list_service = LiveSymbolListService(self)
        self._layout_coordinator = LiveLayoutCoordinator(self)
        self._session_orchestrator = LiveSessionOrchestrator(self)
        self._auto_lifecycle_service = LiveAutoLifecycleService(self)
        self._auto_log_service = LiveAutoLogService(self)
        self._auto_recovery_service = LiveAutoRecoveryService(self)
        self._auto_runtime_service = LiveAutoRuntimeService(self)
        self._auto_settings_persistence = LiveAutoSettingsPersistence(self)
        self._auto_settings_validator = AutoTradeSettingsValidator(self)
        self._ui_builder = LiveUIBuilder(self)

        self._setup_ui()
        self._setup_autotrade_persistence()
        self._setup_connection_controller()
        self._connect_signals()
        self._auto_connect_timer.start(1000)

        if self._event_bus:
            self._event_bus.subscribe("log", self._log_panel.append)

        if self._service:
            self.set_service(self._service)
        if self._oauth_service:
            self.set_oauth_service(self._oauth_service)

        if self._app_state:
            self._app_state.subscribe(self.appStateChanged.emit)

        self._ensure_positions_handler()

    # Service Wiring
    def set_service(self, service: AppAuthServiceLike) -> None:
        if self._service and self._spot_message_handler:
            try:
                self._service.remove_message_handler(self._spot_message_handler)
            except Exception:
                pass
        self._service = service
        if self._connection_controller and self._connection_controller.service is not service:
            self._connection_controller.seed_services(service, self._oauth_service)
        clear_log_history_safe(self._service)
        set_callbacks_safe(
            self._service,
            on_log=self.logRequested.emit,
            on_status_changed=lambda s: self.appAuthStatusChanged.emit(int(s)),
        )
        if getattr(self._service, "status", None) is not None:
            self._app_auth_label.setText(
                format_app_auth_status(ConnectionStatus(self._service.status))
            )
        self._ensure_quote_handler()

    def set_oauth_service(self, service: OAuthServiceLike) -> None:
        self._oauth_service = service
        if self._connection_controller and self._connection_controller.oauth_service is not service:
            self._connection_controller.seed_services(self._service, service)
        clear_log_history_safe(self._oauth_service)
        set_callbacks_safe(
            self._oauth_service,
            on_log=self.logRequested.emit,
            on_error=lambda e: self.oauthError.emit(str(e)),
            on_oauth_success=lambda t: self.oauthSuccess.emit(t),
            on_status_changed=lambda s: self.oauthStatusChanged.emit(int(s)),
        )
        if getattr(self._oauth_service, "status", None) is not None:
            status = ConnectionStatus(self._oauth_service.status)
            self._oauth_label.setText(format_oauth_status(status))
            self._handle_oauth_status(int(status))

    # UI Construction
    def _setup_ui(self) -> None:
        self.setWindowTitle("Forex Trading App - Live")
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
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        chart_panel = self._build_chart_panel()
        autotrade_panel = self._build_autotrade_panel()
        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.addWidget(autotrade_panel)
        top_splitter.addWidget(chart_panel)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 2)
        self._top_splitter = top_splitter
        content_layout.addWidget(top_splitter, 1)

        quotes_panel = self._build_quotes_panel()
        positions_panel = self._build_positions_panel()
        self._quotes_panel_widget = quotes_panel
        self._positions_panel_widget = positions_panel
        bottom_splitter = QSplitter(Qt.Horizontal)
        bottom_splitter.addWidget(quotes_panel)
        bottom_splitter.addWidget(positions_panel)
        bottom_splitter.addWidget(self._log_panel)
        bottom_splitter.setStretchFactor(0, 1)
        bottom_splitter.setStretchFactor(1, 2)
        bottom_splitter.setStretchFactor(2, 1)
        self._bottom_splitter = bottom_splitter
        QTimer.singleShot(0, self._align_panels_at_startup)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(content)
        splitter.addWidget(bottom_splitter)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self._main_splitter = splitter
        QTimer.singleShot(0, self._init_main_splitter_sizes)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(12, 12, 12, 12)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        self._setup_toolbar()
        self._setup_status_bar()

    def _build_positions_panel(self) -> QWidget:
        panel = QGroupBox("Positions")
        layout = QVBoxLayout(panel)

        account_combo = QComboBox()
        account_combo.setObjectName("accountSelector")
        account_combo.setMinimumWidth(220)
        account_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        account_combo.addItem("Select account", None)
        account_combo.currentIndexChanged.connect(self._handle_account_combo_changed)
        account_combo.setVisible(False)
        self._account_combo = account_combo

        refresh_button = QToolButton()
        refresh_button.setObjectName("accountRefresh")
        refresh_button.setAutoRaise(True)
        refresh_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_button.setToolTip("Refresh accounts")
        refresh_button.clicked.connect(self._refresh_accounts)
        refresh_button.setVisible(False)
        self._account_refresh_button = refresh_button

        summary = QFrame()
        summary.setObjectName("accountSummary")
        summary_layout = QGridLayout(summary)
        summary_layout.setContentsMargins(8, 6, 8, 6)
        summary_layout.setHorizontalSpacing(18)
        summary_layout.setVerticalSpacing(6)

        def _summary_item(title: str, key: str) -> QWidget:
            box = QWidget()
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 0)
            box_layout.setSpacing(2)
            title_label = QLabel(title)
            title_label.setObjectName("summaryTitle")
            value_label = QLabel("-")
            value_label.setObjectName("summaryValue")
            box_layout.addWidget(title_label)
            box_layout.addWidget(value_label)
            self._account_summary_labels[key] = value_label
            return box

        summary_items = [
            ("Balance", "balance"),
            ("Equity", "equity"),
            ("Free Margin", "free_margin"),
            ("Used Margin", "used_margin"),
            ("Margin Level", "margin_level"),
            ("Net P/L", "net_pnl"),
            ("Currency", "currency"),
        ]
        row = 0
        col = 0
        for title, key in summary_items:
            summary_layout.addWidget(_summary_item(title, key), row, col)
            col += 1
            if col >= 4:
                row += 1
                col = 0

        summary.setStyleSheet(
            """
            QFrame#accountSummary {
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 10);
                border-radius: 6px;
            }
            QLabel#summaryTitle {
                color: #9aa6b2;
                font-size: 11px;
            }
            QLabel#summaryValue {
                color: #e3e9ef;
                font-weight: 600;
            }
            """
        )
        layout.addWidget(summary)

        table = QTableWidget(0, 10)
        table.setObjectName("positionsTable")
        table.setHorizontalHeaderLabels(
            ["Symbol", "Side", "Volume", "Entry", "Current", "P/L", "SL", "TP", "Open Time", "Pos ID"]
        )
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setStyleSheet(
            """
            QTableWidget#positionsTable QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 2px;
            }
            QTableWidget#positionsTable QScrollBar::handle:vertical {
                background: rgba(210, 220, 232, 0.18);
                min-height: 24px;
                border-radius: 4px;
            }
            QTableWidget#positionsTable QScrollBar::handle:vertical:hover {
                background: rgba(210, 220, 232, 0.30);
            }
            QTableWidget#positionsTable QScrollBar::add-line:vertical,
            QTableWidget#positionsTable QScrollBar::sub-line:vertical,
            QTableWidget#positionsTable QScrollBar::add-page:vertical,
            QTableWidget#positionsTable QScrollBar::sub-page:vertical {
                background: transparent;
                height: 0px;
            }
            QTableWidget#positionsTable QScrollBar:horizontal {
                background: transparent;
                height: 8px;
                margin: 2px;
            }
            QTableWidget#positionsTable QScrollBar::handle:horizontal {
                background: rgba(210, 220, 232, 0.18);
                min-width: 24px;
                border-radius: 4px;
            }
            QTableWidget#positionsTable QScrollBar::handle:horizontal:hover {
                background: rgba(210, 220, 232, 0.30);
            }
            QTableWidget#positionsTable QScrollBar::add-line:horizontal,
            QTableWidget#positionsTable QScrollBar::sub-line:horizontal,
            QTableWidget#positionsTable QScrollBar::add-page:horizontal,
            QTableWidget#positionsTable QScrollBar::sub-page:horizontal {
                background: transparent;
                width: 0px;
            }
            """
        )

        layout.addWidget(table)
        self._positions_table = table
        return panel

    def _build_quotes_panel(self) -> QWidget:
        panel = QGroupBox("Quotes")
        layout = QVBoxLayout(panel)

        rows = max(1, len(self._quote_symbols))
        table = QTableWidget(rows, 5)
        table.setObjectName("quotesTable")
        table.setHorizontalHeaderLabels(["Symbol", "Bid", "Ask", "Spread", "Time"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setStyleSheet(
            """
            QTableWidget#quotesTable QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 2px;
            }
            QTableWidget#quotesTable QScrollBar::handle:vertical {
                background: rgba(210, 220, 232, 0.18);
                min-height: 24px;
                border-radius: 4px;
            }
            QTableWidget#quotesTable QScrollBar::handle:vertical:hover {
                background: rgba(210, 220, 232, 0.30);
            }
            QTableWidget#quotesTable QScrollBar::add-line:vertical,
            QTableWidget#quotesTable QScrollBar::sub-line:vertical,
            QTableWidget#quotesTable QScrollBar::add-page:vertical,
            QTableWidget#quotesTable QScrollBar::sub-page:vertical {
                background: transparent;
                height: 0px;
            }
            QTableWidget#quotesTable QScrollBar:horizontal {
                background: transparent;
                height: 8px;
                margin: 2px;
            }
            QTableWidget#quotesTable QScrollBar::handle:horizontal {
                background: rgba(210, 220, 232, 0.18);
                min-width: 24px;
                border-radius: 4px;
            }
            QTableWidget#quotesTable QScrollBar::handle:horizontal:hover {
                background: rgba(210, 220, 232, 0.30);
            }
            QTableWidget#quotesTable QScrollBar::add-line:horizontal,
            QTableWidget#quotesTable QScrollBar::sub-line:horizontal,
            QTableWidget#quotesTable QScrollBar::add-page:horizontal,
            QTableWidget#quotesTable QScrollBar::sub-page:horizontal {
                background: transparent;
                width: 0px;
            }
            """
        )

        layout.addWidget(table)
        self._quotes_table = table
        self._rebuild_quotes_table()
        return panel

    def _build_autotrade_panel(self) -> QWidget:
        return self._ui_builder.build_autotrade_panel()

    # Layout Coordination
    def _init_splitter_sizes(self, splitter: QSplitter) -> None:
        self._layout_coordinator.init_splitter_sizes(splitter)

    def _sync_field_widths(self) -> None:
        self._layout_coordinator.sync_field_widths()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not getattr(self, "_panel_alignment_done", False):
            self._align_panels_at_startup()
        if getattr(self, "_main_splitter_done", False):
            self._apply_main_splitter_sizes()

    def _sync_top_splitter_sizes(self) -> None:
        self._layout_coordinator.sync_top_splitter_sizes()

    def _sync_bottom_splitter_sizes(self) -> None:
        self._layout_coordinator.sync_bottom_splitter_sizes()

    def _align_panels_at_startup(self) -> None:
        self._layout_coordinator.align_panels_at_startup()

    def _init_main_splitter_sizes(self) -> None:
        self._layout_coordinator.init_main_splitter_sizes()

    def _bottom_preferred_height(self) -> int:
        return self._layout_coordinator.bottom_preferred_height()

    def _apply_main_splitter_sizes(self) -> None:
        self._layout_coordinator.apply_main_splitter_sizes()

    def _init_bottom_splitter_sizes(self, splitter: QSplitter) -> None:
        self._layout_coordinator.init_bottom_splitter_sizes(splitter)

    # Model Path Helpers
    def _browse_model_file(self) -> None:
        current_text = self._model_path.text().strip()
        current_path = self._resolve_model_path(current_text) if current_text else Path.cwd()
        start_path = current_path if current_path.exists() else current_path.parent
        path, _ = QFileDialog.getOpenFileName(
            self, "Select model file", str(start_path), "Model (*.zip);;All files (*)"
        )
        if path:
            self._model_path.setText(self._normalize_model_path_text(path))

    def _resolve_model_path(self, path_text: str) -> Path:
        raw = str(path_text).strip()
        if raw.startswith("models/"):
            suffix = raw[len("models/") :]
            return (Path(MODEL_DIR).expanduser().resolve() / suffix).resolve()
        path = Path(raw).expanduser()
        if path.is_absolute():
            return path
        return (Path.cwd() / path).resolve()

    def _normalize_model_path_text(self, path_text: str) -> str:
        raw = str(path_text).strip()
        if not raw:
            return ""
        if raw.startswith("models/"):
            return raw.replace("\\", "/")
        path = Path(raw).expanduser()
        if not path.is_absolute():
            return raw
        model_dir = Path(MODEL_DIR).expanduser().resolve()
        resolved = path.resolve()
        try:
            relative_model = resolved.relative_to(model_dir)
            return f"models/{relative_model.as_posix()}"
        except Exception:
            pass
        try:
            relative = resolved.relative_to(Path.cwd().resolve())
        except Exception:
            return str(path)
        return relative.as_posix()

    # Auto Trade Logging / Debug
    def _infer_auto_log_level(self, message: str) -> str:
        return self._auto_log_service.infer_level(message)

    def _auto_log(self, message: str, *, level: Optional[str] = None) -> None:
        self._auto_log_service.emit(message, level=level)

    def _auto_debug_enabled(self) -> bool:
        return bool(getattr(self, "_auto_debug", None) and self._auto_debug.isChecked())

    def _auto_debug_log(self, message: str) -> None:
        if not self._auto_debug_enabled():
            return
        self._auto_log(message, level="DEBUG")

    def _auto_debug_fields(self, event: str, **fields) -> None:
        lines = [str(event)]
        for key, value in fields.items():
            lines.append(f"  {key}={value}")
        payload = "\n".join(lines)
        if self._auto_debug_enabled():
            self._auto_log(payload, level="DEBUG")
            return
        panel = getattr(self, "_auto_log_panel", None)
        if panel is not None and hasattr(panel, "append"):
            panel.append(f"[DEBUG] {payload}")

    # Auto Trade Recovery / Polling
    def _auto_watchdog_tick(self) -> None:
        self._auto_recovery_service.auto_watchdog_tick()

    def _history_poll_tick(self) -> None:
        self._auto_recovery_service.history_poll_tick()

    def _start_history_polling(self) -> None:
        if getattr(self, "_history_poll_timer", None) and not self._history_poll_timer.isActive():
            self._history_poll_timer.start()

    def _stop_history_polling(self) -> None:
        if getattr(self, "_history_poll_timer", None) and self._history_poll_timer.isActive():
            self._history_poll_timer.stop()

    def _set_quote_chart_mode(self, enabled: bool) -> None:
        self._chart_coordinator.set_quote_chart_mode(enabled)

    # Auto Trade Lifecycle / Runtime
    def _toggle_auto_trade(self, enabled: bool) -> None:
        self._auto_lifecycle_service.toggle(enabled)

    def _load_auto_model(self) -> bool:
        return self._auto_runtime_service.load_auto_model()

    def _ensure_order_service(self) -> None:
        self._auto_runtime_service.ensure_order_service()

    def _handle_order_execution(self, payload: dict) -> None:
        self._auto_runtime_service.handle_order_execution(payload)

    def _handle_trade_timeframe_changed(self, timeframe: str) -> None:
        self._market_data_controller.set_trade_timeframe(timeframe)

    # Auto Trade UI State / Persistence
    def _trading_widgets(self) -> list[QWidget]:
        return [
            self._auto_trade_toggle,
            self._trade_symbol,
            self._trade_timeframe,
            self._lot_fixed,
            self._lot_risk,
            self._lot_value,
            self._max_positions,
            self._stop_loss,
            self._take_profit,
            self._risk_guard,
            self._max_drawdown,
            self._daily_loss,
            self._min_signal_interval,
            self._slippage_bps,
            self._fee_bps,
            self._confidence,
            self._position_step,
            self._near_full_hold,
            self._same_side_rebalance,
            self._scale_lot_by_signal,
            self._auto_debug,
            self._quote_affects_chart,
        ]

    def _apply_trade_permission(self, scope: Optional[int]) -> None:
        trading_allowed = scope != 0
        for widget in self._trading_widgets():
            if widget:
                widget.setEnabled(trading_allowed)

        if self._autotrade_tabs:
            if getattr(self, "_basic_tab", None):
                basic_idx = self._autotrade_tabs.indexOf(self._basic_tab)
                if basic_idx >= 0:
                    self._autotrade_tabs.setTabEnabled(basic_idx, trading_allowed)
            if getattr(self, "_trade_tab", None):
                trade_idx = self._autotrade_tabs.indexOf(self._trade_tab)
                if trade_idx >= 0:
                    self._autotrade_tabs.setTabEnabled(trade_idx, trading_allowed)
            if getattr(self, "_advanced_tab", None):
                adv_idx = self._autotrade_tabs.indexOf(self._advanced_tab)
                if adv_idx >= 0:
                    self._autotrade_tabs.setTabEnabled(adv_idx, trading_allowed)

        if self._order_service:
            set_scope = getattr(self._order_service, "set_permission_scope", None)
            if callable(set_scope):
                set_scope(scope)

        if not trading_allowed:
            if self._auto_trade_toggle and self._auto_trade_toggle.isChecked():
                self._auto_trade_toggle.setChecked(False)
            self._auto_log("⚠️ 帳戶權限為僅檢視，交易功能已停用")
        self._history_requested = False
        self._pending_history = False
        self._last_history_request_key = None
        self._last_history_success_key = None
        self._stop_live_trendbar()
        if self._is_broker_runtime_ready():
            self._session_orchestrator.try_resume_runtime_loops(reason="trade_permission_updated")

    def _refresh_symbol_list(self) -> None:
        self._symbol_list_service.refresh_symbol_list()

    def _queue_symbol_list_apply(self, symbols: list) -> None:
        self._symbol_list_service.queue_symbol_list_apply(symbols)

    @Slot()
    def _apply_symbol_list_update(self) -> None:
        self._symbol_list_service.apply_symbol_list_update()

    def _trade_symbol_choices(self) -> list[str]:
        return self._symbol_list_service.trade_symbol_choices()

    def _sync_trade_symbol_choices(self, preferred_symbol: Optional[str] = None) -> None:
        self._symbol_list_service.sync_trade_symbol_choices(preferred_symbol=preferred_symbol)

    def _sync_lot_value_style(self) -> None:
        self._auto_settings_persistence.sync_lot_value_style()

    def _setup_autotrade_persistence(self) -> None:
        self._auto_settings_persistence.setup()

    def _save_autotrade_settings(self) -> None:
        self._auto_settings_persistence.save()

    def _load_autotrade_settings(self) -> None:
        self._auto_settings_persistence.load()

    # Auto Trade Hooks Used by Controllers/Services
    def _run_auto_trade_on_close(self) -> None:
        self._autotrade_coordinator.run_auto_trade_on_close()

    def _sync_auto_position_from_positions(self, positions: list[object]) -> None:
        self._autotrade_coordinator.sync_auto_position_from_positions(positions)

    def _refresh_account_balance(self) -> None:
        self._autotrade_coordinator.refresh_account_balance()

    # Quotes / Positions Controllers
    def _ensure_quote_handler(self) -> None:
        self._quote_controller.ensure_quote_handler()

    def _ensure_positions_handler(self) -> None:
        self._positions_controller.ensure_positions_handler()

    def _request_positions(self) -> None:
        self._positions_controller.request_positions()

    def _ensure_quote_subscription(self) -> None:
        self._quote_controller.ensure_quote_subscription()

    def _stop_quote_subscription(self) -> None:
        self._quote_controller.stop_quote_subscription()

    def _schedule_positions_refresh(self) -> None:
        self._positions_controller.schedule_positions_refresh()

    def _apply_positions_refresh(self) -> None:
        self._positions_controller.apply_positions_refresh()

    @staticmethod
    def _volume_to_lots(volume_value: float) -> float:
        return LivePositionsController.volume_to_lots(volume_value)

    def _current_price_text(self, *, symbol_id: Optional[int], side_value: Optional[int]) -> str:
        return self._value_formatter.current_price_text(symbol_id=symbol_id, side_value=side_value)

    def _format_spot_time(self, spot_ts) -> str:
        return self._value_formatter.format_spot_time(spot_ts)

    def _format_time(self, timestamp) -> str:
        return self._value_formatter.format_time(timestamp)

    def _symbol_list_path(self) -> Path:
        return self._project_root / SYMBOL_LIST_FILE

    def _normalize_price(self, value, *, digits: Optional[int] = None) -> Optional[float]:
        return self._value_formatter.normalize_price(value, digits=digits)

    def _format_price(self, value, *, digits: Optional[int] = None) -> str:
        return self._value_formatter.format_price(value, digits=digits)

    # Connection / Account Orchestration
    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Live toolbar", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._action_toggle_connection = QAction("Connect/Disconnect", self)
        toolbar.addAction(self._action_toggle_connection)
        self._action_toggle_connection.triggered.connect(self._toggle_connection)

    def _setup_status_bar(self) -> None:
        status_bar = self.statusBar()
        self._app_auth_label = QLabel(format_app_auth_status(None))
        self._oauth_label = QLabel(format_oauth_status(None))
        self._reconnect_label = QLabel("Reconnect: Idle")
        status_bar.addWidget(self._app_auth_label)
        status_bar.addWidget(self._oauth_label)
        status_bar.addWidget(self._reconnect_label)
        self._update_reconnect_status()

    def _is_broker_runtime_ready(self) -> bool:
        return self._session_orchestrator.broker_runtime_ready()

    def _suspend_runtime_loops(self) -> None:
        self._session_orchestrator.suspend_runtime_loops()

    def _update_reconnect_status(self, *, reason: str = "status_refresh") -> None:
        text = self._session_orchestrator.reconnect_status_text(reason=reason)
        self._reconnect_label.setText(text)

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
        self.logRequested.connect(self._on_log_requested)
        self.logRequested.connect(self._log_panel.append)
        self.appAuthStatusChanged.connect(self._handle_app_auth_status)
        self.oauthStatusChanged.connect(self._handle_oauth_status)
        self.oauthError.connect(self._handle_oauth_error)
        self.oauthSuccess.connect(self._handle_oauth_success)
        self.appStateChanged.connect(self._handle_app_state_changed)
        self.positionsUpdated.connect(self._positions_controller.apply_positions_update)
        self.accountSummaryUpdated.connect(self._handle_account_summary_updated)
        self.historyReceived.connect(self._handle_history_received)
        self.trendbarReceived.connect(self._handle_trendbar_received)
        self.quoteUpdated.connect(self._handle_quote_updated)

    @Slot(str)
    def _on_log_requested(self, _message: str) -> None:
        self._ui_diag_log_total += 1
        message = str(_message or "")
        if self._is_not_authorized_message(message):
            # During reconnect/auth handshake, broker may reject account-scoped
            # requests transiently. Avoid entering lockout until auth is settled.
            app_status = int(getattr(self._service, "status", 0) or 0)
            oauth_status = int(getattr(self._oauth_service, "status", 0) or 0)
            if (
                app_status < int(ConnectionStatus.APP_AUTHENTICATED)
                or oauth_status < int(ConnectionStatus.ACCOUNT_AUTHENTICATED)
            ):
                return
            now = time.time()
            # Throttle lockout trigger for bursts of identical broker errors.
            if now - float(getattr(self, "_last_auth_error_log_ts", 0.0)) >= 1.0:
                self._last_auth_error_log_ts = now
                self._enter_account_authorization_lockout()

    @Slot()
    def _toggle_connection(self) -> None:
        self._session_orchestrator.handle_toggle_connection()

    @Slot(int)
    def _handle_app_auth_status(self, status: int) -> None:
        self._app_auth_label.setText(format_app_auth_status(ConnectionStatus(status)))
        self._session_orchestrator.handle_app_auth_status(status)
        if self._oauth_service:
            oauth_status = int(getattr(self._oauth_service, "status", 0) or 0)
            if int(status) >= int(ConnectionStatus.APP_AUTHENTICATED):
                self._oauth_label.setText(format_oauth_status(ConnectionStatus(oauth_status)))
        self._update_reconnect_status(reason="app_auth_status_changed")

    @Slot(int)
    def _handle_oauth_status(self, status: int) -> None:
        self._oauth_label.setText(format_oauth_status(ConnectionStatus(status)))
        self.logRequested.emit(f"ℹ️ OAuth status -> {ConnectionStatus(status).name}")
        self._session_orchestrator.handle_oauth_status(status)
        self._update_reconnect_status(reason="oauth_status_changed")

    def _handle_oauth_success(self, tokens: OAuthTokens) -> None:
        if tokens and tokens.account_id:
            self._last_authorized_account_id = int(tokens.account_id)
            self.logRequested.emit(f"✅ OAuth authorized account: {tokens.account_id}")

    def _handle_oauth_error(self, error: str) -> None:
        message = str(error)
        self.logRequested.emit(message)
        if "Trading account is not authorized" not in message:
            self._update_reconnect_status(reason="oauth_error")
            return
        token_account = getattr(getattr(self._oauth_service, "tokens", None), "account_id", None)
        if token_account:
            try:
                self._unauthorized_accounts.add(int(token_account))
            except Exception:
                pass
        self._account_switch_in_progress = False
        self.logRequested.emit("⚠️ Selected account is not authorized for Open API.")
        self._enter_account_authorization_lockout()
        self._update_reconnect_status(reason="oauth_error_unauthorized")
        if self._last_authorized_account_id and token_account and int(token_account) != int(self._last_authorized_account_id):
            self.logRequested.emit("ℹ️ 帳戶未授權，請切回可用帳戶並手動重新連線")

    @staticmethod
    def _is_not_authorized_message(message: str) -> bool:
        lower = str(message or "").lower()
        return "trading account is not authorized" in lower

    def _enter_account_authorization_lockout(self) -> None:
        self._session_orchestrator.enter_authorization_lockout()
        self._update_reconnect_status(reason="authorization_lockout")

    def _load_tokens_for_accounts(self) -> Optional[OAuthTokens]:
        try:
            return OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self.logRequested.emit(f"⚠️ 無法讀取 token 檔案: {exc}")
            return None

    def _refresh_accounts(self) -> None:
        self._account_controller.refresh_accounts()

    def _handle_accounts_received(self, accounts: list[object]) -> None:
        self._account_controller.handle_accounts_received(accounts)

    def _handle_accounts_error(self, error: str) -> None:
        self._account_controller.handle_accounts_error(error)

    def _handle_account_combo_changed(self, index: int) -> None:
        self._account_controller.handle_account_combo_changed(index)

    def _apply_selected_account(
        self,
        account_id: int,
        *,
        save_token: bool,
        log: bool,
        user_initiated: bool,
    ) -> None:
        self._account_controller.apply_selected_account(
            account_id,
            save_token=save_token,
            log=log,
            user_initiated=user_initiated,
        )

    def _resolve_account_scope(self, account_id: int) -> Optional[int]:
        return self._account_controller.resolve_account_scope(account_id)

    def _sync_account_combo(self, account_id: Optional[int]) -> None:
        self._account_controller.sync_account_combo(account_id)

    @Slot()
    def _schedule_full_reconnect(self) -> None:
        app = QApplication.instance()
        if app is not None and QThread.currentThread() != app.thread():
            QMetaObject.invokeMethod(self, "_schedule_full_reconnect", Qt.QueuedConnection)
            return
        if self._pending_full_reconnect:
            return
        if not self._connection_controller:
            return
        self._pending_full_reconnect = True

        def _do_reconnect() -> None:
            self._pending_full_reconnect = False
            controller = self._connection_controller
            if not controller:
                return
            if getattr(controller, "transition_in_progress", False):
                self.logRequested.emit("⏳ Reconnect skipped: transition already in progress")
                return
            self.logRequested.emit("🔁 Reconnecting to apply account switch")
            app_auth = bool(controller.is_app_authenticated())
            oauth_auth = bool(controller.is_oauth_authenticated())
            if app_auth or oauth_auth:
                controller.disconnect_flow()
                QTimer.singleShot(1200, self._connect_after_forced_disconnect)
            else:
                controller.connect_flow()

        QTimer.singleShot(500, _do_reconnect)

    @Slot()
    def _connect_after_forced_disconnect(self) -> None:
        controller = self._connection_controller
        if not controller:
            return
        if getattr(controller, "transition_in_progress", False):
            self.logRequested.emit("⏳ Reconnect connect-phase skipped: transition already in progress")
            return
        if controller.is_app_authenticated() or controller.is_oauth_authenticated():
            # Still authenticated; wait for next reconnect trigger rather than re-entering.
            return
        controller.connect_flow()

    def _handle_app_state_changed(self, state: AppState) -> None:
        if self._session_orchestrator.handle_app_state_changed(state):
            return
        self._session_orchestrator.handle_authenticated_app_state(state)

    # Market Data / Chart Runtime
    def _request_recent_history(self, *, force: bool = False) -> None:
        self._market_data_controller.request_recent_history(force=force)

    def _dispose_history_service(self) -> None:
        self._market_data_controller.dispose_history_service()

    def _dispose_trendbar_service(self) -> None:
        self._market_data_controller.dispose_trendbar_service()

    @Slot(object)
    def _handle_account_summary_updated(self, summary) -> None:
        self._session_orchestrator.mark_data_activity()
        self._positions_controller.apply_account_summary_update(summary)

    def _handle_history_received(self, rows: list[dict]) -> None:
        self._ui_diag_history_total += 1
        self._session_orchestrator.mark_data_activity()
        self._market_data_controller.handle_history_received(rows)

    def _start_live_trendbar(self) -> None:
        self._market_data_controller.start_live_trendbar()

    def _stop_live_trendbar(self) -> None:
        self._market_data_controller.stop_live_trendbar()

    def _handle_trendbar_received(self, data: dict) -> None:
        self._ui_diag_trendbar_total += 1
        self._session_orchestrator.mark_data_activity()
        self._market_data_controller.handle_trendbar_received(data)

    @Slot(int, object, object, object)
    def _handle_quote_updated(self, symbol_id: int, bid, ask, spot_ts) -> None:
        self._ui_diag_quote_total += 1
        self._session_orchestrator.mark_data_activity()
        self._quote_controller.handle_quote_updated(symbol_id, bid, ask, spot_ts)

    def _ui_heartbeat_tick(self) -> None:
        self._session_orchestrator.runtime_watchdog_tick()
        now = time.perf_counter()
        interval_s = 1.0
        if getattr(self, "_ui_heartbeat_timer", None):
            interval_s = max(0.1, float(self._ui_heartbeat_timer.interval()) / 1000.0)

        if self._ui_heartbeat_expected_ts <= 0:
            self._ui_heartbeat_expected_ts = now + interval_s
            self._ui_heartbeat_last_report_ts = now
            return

        lag_ms = max(0.0, (now - self._ui_heartbeat_expected_ts) * 1000.0)
        self._ui_heartbeat_expected_ts = now + interval_s
        if lag_ms > self._ui_heartbeat_max_lag_ms:
            self._ui_heartbeat_max_lag_ms = lag_ms

        qt_pending = False
        try:
            qt_pending = bool(QCoreApplication.hasPendingEvents())
        except Exception:
            qt_pending = False

        if qt_pending:
            self._ui_heartbeat_pending_streak += 1
        else:
            self._ui_heartbeat_pending_streak = 0

        queue_hint = 0
        queue_hint += int(self._pending_candles is not None)
        queue_hint += int(bool(self._history_requested))
        queue_hint += int(bool(self._positions_refresh_pending))
        queue_hint += len(getattr(self, "_quote_subscribe_inflight", set()) or set())
        queue_hint += int(qt_pending)

        if lag_ms >= 1500.0 and now - self._ui_heartbeat_last_warn_ts >= 30.0:
            self._ui_heartbeat_last_warn_ts = now
            self.logRequested.emit(
                "⚠️ UI heartbeat lag spike: "
                f"lag={lag_ms:.0f}ms queue_hint={queue_hint} "
                f"pending_streak={self._ui_heartbeat_pending_streak}"
            )

        elapsed = now - self._ui_heartbeat_last_report_ts
        if elapsed < 60.0:
            return

        logs_delta = self._ui_diag_log_total - self._ui_diag_last_log_total
        history_delta = self._ui_diag_history_total - self._ui_diag_last_history_total
        trendbar_delta = self._ui_diag_trendbar_total - self._ui_diag_last_trendbar_total
        quote_delta = self._ui_diag_quote_total - self._ui_diag_last_quote_total

        self._ui_diag_last_log_total = self._ui_diag_log_total
        self._ui_diag_last_history_total = self._ui_diag_history_total
        self._ui_diag_last_trendbar_total = self._ui_diag_trendbar_total
        self._ui_diag_last_quote_total = self._ui_diag_quote_total
        self._ui_heartbeat_last_report_ts = now

        logs_pm = (logs_delta / elapsed) * 60.0 if elapsed > 0 else 0.0
        history_pm = (history_delta / elapsed) * 60.0 if elapsed > 0 else 0.0
        trendbar_pm = (trendbar_delta / elapsed) * 60.0 if elapsed > 0 else 0.0
        quote_pm = (quote_delta / elapsed) * 60.0 if elapsed > 0 else 0.0

        log_entries = len(getattr(self._log_panel, "_entries", [])) if self._log_panel else 0
        auto_entries = len(getattr(self._auto_log_panel, "_recent_raw", [])) if self._auto_log_panel else 0
        handler_count = 0
        service = getattr(self, "_service", None)
        if service is not None:
            getter = getattr(service, "message_handler_count", None)
            if callable(getter):
                try:
                    handler_count = int(getter())
                except Exception:
                    handler_count = 0

        self.logRequested.emit(
            "🫀 UI heartbeat: "
            f"lag_now={lag_ms:.0f}ms lag_max={self._ui_heartbeat_max_lag_ms:.0f}ms "
            f"queue_hint={queue_hint} pending_streak={self._ui_heartbeat_pending_streak} "
            f"log_rate={logs_pm:.0f}/min history_rate={history_pm:.1f}/min "
            f"trendbar_rate={trendbar_pm:.1f}/min quote_rate={quote_pm:.1f}/min "
            f"log_entries={log_entries} auto_entries={auto_entries} handlers={handler_count}"
        )
        self._ui_heartbeat_max_lag_ms = 0.0

    def _update_chart_from_quote(self, symbol_id: int, bid, ask, spot_ts) -> None:
        self._chart_coordinator.update_chart_from_quote(symbol_id, bid, ask, spot_ts)

    def _update_current_candle_from_quote(self, symbol_id: int, bid, ask, spot_ts) -> None:
        self._chart_coordinator.update_current_candle_from_quote(symbol_id, bid, ask, spot_ts)

    def _update_chart_last_price_from_quote(self, symbol_id: int, bid, ask) -> None:
        self._chart_coordinator.update_chart_last_price_from_quote(symbol_id, bid, ask)

    def _handle_chart_range_changed(self, *_args) -> None:
        self._chart_coordinator.handle_chart_range_changed(*_args)

    def _handle_chart_auto_button_clicked(self, *_args) -> None:
        self._chart_coordinator.handle_chart_auto_button_clicked(*_args)

    def _guard_chart_range(self) -> None:
        self._chart_coordinator.guard_chart_range()

    def _reapply_chart_window_from_latest(self) -> None:
        self._chart_coordinator.reapply_chart_window_from_latest()

    @staticmethod
    def _compute_chart_y_range(candles: list[tuple[float, float, float, float, float]]) -> tuple[float, float]:
        return LiveChartCoordinator.compute_chart_y_range(candles)

    def _handle_trendbar_error(self, error: str) -> None:
        self._market_data_controller.handle_trendbar_error(error)

    # Chart Construction / Updates
    def _build_chart_panel(self) -> QWidget:
        panel = QGroupBox("Live Candlestick Chart")
        layout = QVBoxLayout(panel)

        if pg is None:
            notice = QLabel("PyQtGraph is not installed. Please install pyqtgraph to view the chart.")
            notice.setProperty("class", "placeholder")
            layout.addWidget(notice)
            return panel

        plot = pg.PlotWidget(axisItems={"bottom": TimeAxisItem(orientation="bottom")})
        plot.setBackground("#1f2328")
        plot.showGrid(x=True, y=True, alpha=0.15)
        plot.setLabel("bottom", "time")
        plot.setLabel("left", "price")
        plot.enableAutoRange(False, False)
        plot.setXRange(0, 1, padding=0)
        plot.setYRange(0, 1, padding=0)
        axis_pen = pg.mkPen("#5b6370")
        axis_text = pg.mkPen("#c9d1d9")
        plot.getAxis("bottom").setPen(axis_pen)
        plot.getAxis("bottom").setTextPen(axis_text)
        plot.getAxis("left").setPen(axis_pen)
        plot.getAxis("left").setTextPen(axis_text)
        try:
            plot_item = plot.getPlotItem()
            plot.getViewBox().sigRangeChangedFinished.connect(self._handle_chart_range_changed)
            auto_button = getattr(plot_item, "autoBtn", None)
            if auto_button is not None and hasattr(auto_button, "clicked"):
                # Override pyqtgraph default auto-range behavior: it can include
                # non-candle items and flatten the chart. We fully handle "A"
                # with our own 50-candle normalization.
                try:
                    auto_button.clicked.disconnect(plot_item.autoBtnClicked)
                except Exception:
                    pass
                auto_button.clicked.connect(self._handle_chart_auto_button_clicked)
        except Exception:
            pass
        layout.addWidget(plot)

        self._candlestick_item = CandlestickItem([])
        plot.addItem(self._candlestick_item)
        self._last_price_line = pg.InfiniteLine(
            angle=0,
            pen=pg.mkPen("#9ca3af", width=1, style=Qt.DashLine),
            movable=False,
        )
        plot.addItem(self._last_price_line)
        # Anchor on the left so the text grows to the right and stays off candles.
        self._last_price_label = pg.TextItem(color="#e5e7eb", anchor=(0, 0.5))
        self._last_price_label.setZValue(10)
        plot.addItem(self._last_price_label)
        self._chart_plot = plot

        return panel

    def set_candles(self, candles: list[tuple[float, float, float, float, float]]) -> None:
        self._chart_coordinator.set_candles(candles)

    def _flush_chart_update(self) -> None:
        self._chart_coordinator.flush_chart_update()

    def _fill_missing_candles(self, next_candle: tuple[float, float, float, float, float]) -> None:
        self._market_data_controller.fill_missing_candles(next_candle)

    def _timeframe_minutes(self) -> int:
        return self._market_data_controller.timeframe_minutes()

    # Symbol Facade
    def _resolve_symbol_id(self, symbol_name: str) -> int:
        return self._symbol_controller.resolve_symbol_id(symbol_name)

    def _handle_trade_symbol_changed(self, symbol: str) -> None:
        self._symbol_controller.handle_trade_symbol_changed(symbol)

    def _fetch_symbol_details(self, symbol_name: str) -> None:
        self._symbol_controller.fetch_symbol_details(symbol_name)

    def _load_symbol_catalog(self) -> tuple[list[str], dict[str, int]]:
        return self._symbol_controller.load_symbol_catalog()

    def _filter_fx_symbols(self, names: list[str]) -> list[str]:
        return self._symbol_controller.filter_fx_symbols(names)

    def _default_quote_symbols(self) -> list[str]:
        return self._symbol_controller.default_quote_symbols()

    def _infer_quote_digits(self, symbol: str) -> int:
        return self._symbol_controller.infer_quote_digits(symbol)

    def _rebuild_quotes_table(self) -> None:
        self._symbol_controller.rebuild_quotes_table()


if pg is not None:
    class TimeAxisItem(pg.AxisItem):
        def tickStrings(self, values, scale, spacing) -> list[str]:
            labels = []
            for value in values:
                try:
                    labels.append(datetime.utcfromtimestamp(value).strftime("%H:%M"))
                except (OSError, ValueError, OverflowError):
                    labels.append("")
            return labels

    class CandlestickItem(pg.GraphicsObject):
        def __init__(self, data: list[tuple[float, float, float, float, float]]):
            super().__init__()
            self._data = data
            self._picture = QtGui.QPicture()
            self._bounds = QtCore.QRectF(0.0, 0.0, 1.0, 1.0)
            self._generate_picture()

        def setData(self, data: list[tuple[float, float, float, float, float]]) -> None:
            self.prepareGeometryChange()
            self._data = data
            self._generate_picture()
            self.update()

        def _generate_picture(self) -> None:
            self._picture = QtGui.QPicture()
            painter = QtGui.QPainter(self._picture)
            if not self._data:
                self._bounds = QtCore.QRectF(0.0, 0.0, 1.0, 1.0)
                painter.end()
                return
            width = self._infer_half_width()
            times = [float(point[0]) for point in self._data]
            lows = [float(point[3]) for point in self._data]
            highs = [float(point[2]) for point in self._data]
            min_x = min(times) - width
            max_x = max(times) + width
            min_y = min(lows)
            max_y = max(highs)
            self._bounds = QtCore.QRectF(min_x, min_y, max(max_x - min_x, 1.0), max(max_y - min_y, 1e-8))
            for time, open_price, high, low, close in self._data:
                wick_pen = pg.mkPen("#9ca3af", width=1)
                painter.setPen(wick_pen)
                painter.drawLine(QtCore.QPointF(time, low), QtCore.QPointF(time, high))
                if open_price > close:
                    color = "#ef4444"
                    rect = QtCore.QRectF(time - width, close, width * 2, open_price - close)
                else:
                    color = "#10b981"
                    rect = QtCore.QRectF(time - width, open_price, width * 2, close - open_price)
                if rect.height() == 0:
                    painter.setPen(pg.mkPen(color, width=2))
                    painter.drawLine(
                        QtCore.QPointF(time - width, open_price),
                        QtCore.QPointF(time + width, open_price),
                    )
                else:
                    painter.setPen(pg.mkPen(color, width=2))
                    painter.setBrush(pg.mkBrush(color))
                    painter.drawRect(rect)
            painter.end()

        def _infer_half_width(self) -> float:
            if len(self._data) < 2:
                return 20.0
            times = [point[0] for point in self._data]
            diffs = [b - a for a, b in zip(times, times[1:]) if b > a]
            if not diffs:
                return 20.0
            diffs.sort()
            step = diffs[len(diffs) // 2]
            return max(1.0, step * 0.225)

        def paint(self, painter, *args) -> None:
            painter.drawPicture(0, 0, self._picture)

        def boundingRect(self) -> QtCore.QRectF:
            return QtCore.QRectF(self._bounds)

        def dataBounds(self, ax: int, frac: float = 1.0, orthoRange=None):
            if not self._data:
                return None
            if ax == 0:
                return [self._bounds.left(), self._bounds.right()]
            if ax == 1:
                return [self._bounds.top(), self._bounds.bottom()]
            return None
