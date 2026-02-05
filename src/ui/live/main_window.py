from __future__ import annotations

from typing import Optional
from datetime import datetime
import time
import json
from pathlib import Path

from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAReconcileReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType, ProtoOATradeSide
import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QMetaObject, QThread
from PySide6.QtGui import QAction
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
    QTableWidgetItem,
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

from application.broker.protocols import AppAuthServiceLike, OAuthServiceLike, OrderServiceLike
from application.broker.use_cases import BrokerUseCases
from application.events import EventBus
from application.state import AppState
from config.constants import ConnectionStatus
from config.paths import SYMBOL_LIST_FILE, TOKEN_FILE
from config.settings import OAuthTokens
from infrastructure.broker.ctrader.services.spot_subscription import (
    send_spot_subscribe,
    send_spot_unsubscribe,
)
from ml.rl.features.feature_builder import build_features
from ui.shared.controllers.connection_controller import ConnectionController
from ui.shared.utils.formatters import (
    format_app_auth_status,
    format_connection_message,
    format_oauth_status,
)
from ui.shared.widgets.log_widget import LogWidget


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
        self._history_service = None
        self._history_requested = False
        self._pending_history = False
        self._last_history_request_key: Optional[tuple[int, int, str, int]] = None
        self._last_history_request_ts: float = 0.0
        self._last_history_success_key: Optional[tuple[int, int, str, int]] = None
        self._last_history_success_ts: float = 0.0
        self._trendbar_service = None
        self._trendbar_active = False
        self._order_service: Optional[OrderServiceLike] = None
        self._auto_enabled = False
        self._auto_model = None
        self._auto_position = 0.0
        self._auto_position_id: Optional[int] = None
        self._auto_last_action_ts: Optional[float] = None
        self._auto_balance: Optional[float] = None
        self._auto_peak_balance: Optional[float] = None
        self._auto_day_balance: Optional[float] = None
        self._auto_day_key: Optional[str] = None
        self._auto_log_panel: Optional[LogWidget] = None
        self._positions_table = None
        self._positions_message_handler = None
        self._account_summary_labels: dict[str, QLabel] = {}
        self._position_pnl_by_id: dict[int, float] = {}
        self._accounts: list[object] = []
        self._account_combo: Optional[QComboBox] = None
        self._account_refresh_button: Optional[QToolButton] = None
        self._account_switch_in_progress = False
        self._last_authorized_account_id: Optional[int] = None
        self._unauthorized_accounts: set[int] = set()
        self._pending_full_reconnect = False
        self._account_funds_uc = None
        self._symbol_list_uc = None
        self._symbol_by_id_uc = None
        self._last_funds_fetch_ts: float = 0.0
        self._candles: list[tuple[float, float, float, float, float]] = []
        self._chart_plot = None
        self._candlestick_item = None
        self._last_price_line = None
        self._last_price_label = None
        self._project_root = Path(__file__).resolve().parents[2]
        self._symbol_names, self._symbol_id_map = self._load_symbol_catalog()
        self._symbol_id_to_name = {symbol_id: name for name, symbol_id in self._symbol_id_map.items()}
        self._symbol_volume_constraints: dict[str, tuple[int, int]] = {}
        self._symbol_volume_loaded = False
        self._symbol_details_by_id: dict[int, dict] = {}
        self._symbol_digits_by_name: dict[str, int] = {}
        self._symbol_overrides: dict[str, dict] = {}
        self._symbol_overrides_loaded = False
        self._symbol_details_unavailable: set[int] = set()
        self._fx_symbols = self._filter_fx_symbols(self._symbol_names)
        self._symbol_name = (
            "EURUSD" if "EURUSD" in self._symbol_id_map else (self._fx_symbols[0] if self._fx_symbols else "EURUSD")
        )
        self._symbol_id = self._resolve_symbol_id(self._symbol_name)
        self._timeframe = "M1"
        self._price_digits = 5
        self._chart_ready = False
        self._pending_candles: Optional[list[tuple[float, float, float, float, float]]] = None
        self._chart_frozen = True
        self._chart_timer = QTimer(self)
        self._chart_timer.setInterval(200)
        self._chart_timer.timeout.connect(self._flush_chart_update)
        self._chart_timer.start()
        self._funds_timer = QTimer(self)
        self._funds_timer.setInterval(5000)
        self._funds_timer.timeout.connect(self._refresh_account_balance)
        self._positions_refresh_timer = QTimer(self)
        self._positions_refresh_timer.setSingleShot(True)
        self._positions_refresh_timer.setInterval(300)
        self._positions_refresh_timer.timeout.connect(self._apply_positions_refresh)
        self._positions_refresh_pending = False
        self._auto_connect_timer = QTimer(self)
        self._auto_connect_timer.setSingleShot(True)
        self._auto_connect_timer.timeout.connect(self._toggle_connection)
        self._autotrade_settings_path = Path("data/auto_trade_settings.json")
        self._autotrade_loading = False
        self._quotes_table = None
        self._max_quote_rows = 2
        self._quote_symbols = self._default_quote_symbols()
        self._quote_digits = {
            "EURUSD": 5,
            "USDJPY": 3,
        }
        self._quote_symbol_ids = {name: self._resolve_symbol_id(name) for name in self._quote_symbols}
        self._quote_rows: dict[int, int] = {}
        self._quote_row_digits: dict[int, int] = {}
        self._quote_last_mid: dict[int, float] = {}
        self._quote_last_bid: dict[int, float] = {}
        self._quote_last_ask: dict[int, float] = {}
        self._quote_subscribed = False
        self._quote_subscribed_ids: set[int] = set()
        self._quote_subscribe_inflight: set[int] = set()
        self._spot_message_handler = None
        self._open_positions: list[object] = []
        self._pending_symbol_list: Optional[list] = None

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

    def set_service(self, service: AppAuthServiceLike) -> None:
        if self._service and self._spot_message_handler:
            try:
                self._service.remove_message_handler(self._spot_message_handler)
            except Exception:
                pass
        self._service = service
        if self._connection_controller and self._connection_controller.service is not service:
            self._connection_controller.seed_services(service, self._oauth_service)
        if hasattr(self._service, "clear_log_history"):
            try:
                self._service.clear_log_history()
            except Exception:
                pass
        if hasattr(self._service, "set_callbacks"):
            self._service.set_callbacks(
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
        if hasattr(self._oauth_service, "clear_log_history"):
            try:
                self._oauth_service.clear_log_history()
            except Exception:
                pass
        if hasattr(self._oauth_service, "set_callbacks"):
            self._oauth_service.set_callbacks(
                on_log=self.logRequested.emit,
                on_error=lambda e: self.oauthError.emit(str(e)),
                on_oauth_success=lambda t: self.oauthSuccess.emit(t),
                on_status_changed=lambda s: self.oauthStatusChanged.emit(int(s)),
            )
        if getattr(self._oauth_service, "status", None) is not None:
            status = ConnectionStatus(self._oauth_service.status)
            self._oauth_label.setText(format_oauth_status(status))
            self._handle_oauth_status(int(status))

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
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)

        chart_panel = self._build_chart_panel()
        autotrade_panel = self._build_autotrade_panel()
        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.addWidget(autotrade_panel)
        top_splitter.addWidget(chart_panel)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 2)
        QTimer.singleShot(0, lambda: self._init_splitter_sizes(top_splitter))
        content_layout.addWidget(top_splitter, 1)

        quotes_panel = self._build_quotes_panel()
        positions_panel = self._build_positions_panel()
        bottom_splitter = QSplitter(Qt.Horizontal)
        bottom_splitter.addWidget(quotes_panel)
        bottom_splitter.addWidget(positions_panel)
        bottom_splitter.addWidget(self._log_panel)
        bottom_splitter.setStretchFactor(0, 1)
        bottom_splitter.setStretchFactor(1, 2)
        bottom_splitter.setStretchFactor(2, 1)
        QTimer.singleShot(0, lambda: self._init_bottom_splitter_sizes(bottom_splitter))

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(content)
        splitter.addWidget(bottom_splitter)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        self._setup_toolbar()
        self._setup_status_bar()

    def _build_positions_panel(self) -> QWidget:
        panel = QGroupBox("Positions")
        layout = QVBoxLayout(panel)

        account_row = QHBoxLayout()
        account_label = QLabel("Account")
        account_label.setObjectName("accountSelectorLabel")
        account_combo = QComboBox()
        account_combo.setObjectName("accountSelector")
        account_combo.setMinimumWidth(220)
        account_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        account_combo.addItem("Select account", None)
        account_combo.currentIndexChanged.connect(self._handle_account_combo_changed)
        self._account_combo = account_combo

        refresh_button = QToolButton()
        refresh_button.setObjectName("accountRefresh")
        refresh_button.setAutoRaise(True)
        refresh_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_button.setToolTip("Refresh accounts")
        refresh_button.clicked.connect(self._refresh_accounts)
        self._account_refresh_button = refresh_button

        account_row.addWidget(account_label)
        account_row.addWidget(account_combo)
        account_row.addWidget(refresh_button)
        account_row.addStretch(1)
        layout.addLayout(account_row)

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
        table.setHorizontalHeaderLabels(
            ["Symbol", "Side", "Volume", "Entry", "Current", "P/L", "SL", "TP", "Open Time", "Pos ID"]
        )
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        layout.addWidget(table)
        self._positions_table = table
        return panel

    def _build_quotes_panel(self) -> QWidget:
        panel = QGroupBox("Quotes")
        layout = QVBoxLayout(panel)

        rows = max(1, len(self._quote_symbols))
        table = QTableWidget(rows, 5)
        table.setHorizontalHeaderLabels(["Symbol", "Bid", "Ask", "Spread", "Time"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        layout.addWidget(table)
        self._quotes_table = table
        self._rebuild_quotes_table()
        return panel

    def _build_autotrade_panel(self) -> QWidget:
        panel = QGroupBox("Auto Trading")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setMovable(False)
        tabs.setUsesScrollButtons(False)
        tabs.tabBar().setExpanding(False)
        layout.addWidget(tabs)
        self._autotrade_tabs = tabs

        def _tab_form(title: str, object_name: str | None = None) -> QFormLayout:
            tab = QWidget()
            if object_name:
                tab.setObjectName(object_name)
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(12, 10, 18, 24)
            tab_layout.setSpacing(8)
            form = QFormLayout()
            form.setHorizontalSpacing(16)
            form.setVerticalSpacing(10)
            form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            form.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
            form.setRowWrapPolicy(QFormLayout.DontWrapRows)
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            tab_layout.addLayout(form)
            tab_layout.addStretch(1)
            tabs.addTab(tab, title)
            return form

        def _card(title: str) -> tuple[QFrame, QFormLayout]:
            card = QFrame()
            card.setObjectName("card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(6)
            title_label = QLabel(title)
            title_label.setObjectName("cardTitle")
            card_layout.addWidget(title_label)
            card_form = QFormLayout()
            card_form.setHorizontalSpacing(16)
            card_form.setVerticalSpacing(10)
            card_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            card_form.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
            card_form.setRowWrapPolicy(QFormLayout.DontWrapRows)
            card_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            card_layout.addLayout(card_form)
            return card, card_form

        form_model = _tab_form("Model", object_name="modelTab")
        form_trade = _tab_form("Trade", object_name="tradeTab")
        tabs.setStyleSheet(
            """
            QWidget#modelTab QLabel[section="true"],
            QWidget#tradeTab QLabel[section="true"],
            QWidget#advancedTab QLabel[section="true"] {
                color: #9aa6b2;
                font-weight: 600;
                letter-spacing: 0.5px;
                padding-top: 6px;
                padding-bottom: 2px;
            }
            QWidget#modelTab QLabel,
            QWidget#tradeTab QLabel,
            QWidget#advancedTab QLabel {
                color: #d5dde6;
                min-width: 150px;
            }
            QWidget#modelTab QLabel[spacer="true"],
            QWidget#tradeTab QLabel[spacer="true"],
            QWidget#advancedTab QLabel[spacer="true"] {
                min-height: 10px;
                min-width: 0px;
            }
            QWidget#modelTab QLabel[section="true"],
            QWidget#tradeTab QLabel[section="true"],
            QWidget#advancedTab QLabel[section="true"] {
                color: #9aa6b2;
                min-width: 0px;
            }
            QWidget#modelTab QFrame[divider="true"],
            QWidget#tradeTab QFrame[divider="true"],
            QWidget#advancedTab QFrame[divider="true"] {
                border: none;
                border-top: 1px solid rgba(255, 255, 255, 25);
                margin-top: 6px;
                margin-bottom: 6px;
            }
            QWidget#modelTab QComboBox,
            QWidget#modelTab QDoubleSpinBox,
            QWidget#modelTab QSpinBox,
            QWidget#modelTab QLineEdit,
            QWidget#tradeTab QComboBox,
            QWidget#tradeTab QDoubleSpinBox,
            QWidget#tradeTab QSpinBox,
            QWidget#tradeTab QLineEdit,
            QWidget#advancedTab QComboBox,
            QWidget#advancedTab QDoubleSpinBox,
            QWidget#advancedTab QSpinBox,
            QWidget#advancedTab QLineEdit {
                min-height: 30px;
                padding: 2px 8px;
                max-width: 360px;
            }
            QWidget#modelTab QRadioButton,
            QWidget#modelTab QCheckBox,
            QWidget#tradeTab QRadioButton,
            QWidget#tradeTab QCheckBox,
            QWidget#advancedTab QRadioButton,
            QWidget#advancedTab QCheckBox {
                spacing: 8px;
            }
            QWidget#modelTab QRadioButton::indicator,
            QWidget#modelTab QCheckBox::indicator,
            QWidget#tradeTab QRadioButton::indicator,
            QWidget#tradeTab QCheckBox::indicator,
            QWidget#advancedTab QRadioButton::indicator,
            QWidget#advancedTab QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QWidget#modelTab QFrame#card {
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 10);
                border-radius: 6px;
            }
            QWidget#modelTab QLabel#cardTitle {
                color: #c7d0db;
                font-weight: 600;
                letter-spacing: 0.2px;
                padding-bottom: 2px;
            }
            QWidget#modelTab QFrame#card QLineEdit,
            QWidget#modelTab QFrame#card QComboBox,
            QWidget#modelTab QFrame#card QDoubleSpinBox,
            QWidget#modelTab QFrame#card QSpinBox {
                background: rgba(20, 24, 30, 140);
            }
            QWidget#modelTab QFrame#card QPushButton,
            QWidget#modelTab QFrame#card QToolButton {
                min-height: 30px;
            }
            QWidget#modelTab QToolButton#modelBrowseIcon {
                background: transparent;
                border: none;
                padding: 0px;
            }
            QWidget#modelTab QToolButton#modelBrowseIcon:hover {
                background: rgba(255, 255, 255, 20);
                border-radius: 6px;
            }
            """
        )
        model_row = QWidget()
        model_layout = QVBoxLayout(model_row)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(6)
        model_field_row = QWidget()
        model_field_layout = QHBoxLayout(model_field_row)
        model_field_layout.setContentsMargins(0, 0, 0, 0)
        model_field_layout.setSpacing(6)
        self._model_path = QLineEdit("ppo-forex.zip")
        self._model_path.setPlaceholderText("ppo-forex.zip")
        self._model_path.setMinimumWidth(220)
        self._model_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._browse_model_dir_button = QToolButton()
        self._browse_model_dir_button.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        self._browse_model_dir_button.setToolTip("Select model file")
        self._browse_model_dir_button.setObjectName("modelBrowseIcon")
        self._browse_model_dir_button.setText("")
        self._browse_model_dir_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        field_height = 30
        self._field_widgets: list[QWidget] = []
        field_width = 160
        def _set_field_width(widget) -> None:
            self._field_widgets.append(widget)
            widget.setFixedWidth(field_width)
        self._model_path.setFixedHeight(field_height)
        _set_field_width(self._model_path)
        self._browse_model_dir_button.setFixedHeight(field_height)
        self._browse_model_dir_button.setMinimumWidth(36)
        self._browse_model_dir_button.clicked.connect(self._browse_model_file)
        model_field_layout.addWidget(self._model_path, 1)
        model_field_layout.addWidget(self._browse_model_dir_button)
        model_layout.addWidget(model_field_row)

        self._auto_trade_toggle = QPushButton("Start")
        self._auto_trade_toggle.setCheckable(True)
        self._auto_trade_toggle.toggled.connect(self._toggle_auto_trade)
        self._auto_trade_toggle.setFixedHeight(field_height)
        _set_field_width(self._auto_trade_toggle)

        model_card, model_card_form = _card("Model & Control")
        model_card_form.addRow("Model file", model_row)
        model_card_form.addRow("Auto Trade", self._auto_trade_toggle)
        form_model.addRow(model_card)
        self._trade_symbol = QComboBox()
        symbol_choices = self._fx_symbols or ["EURUSD", "USDJPY"]
        self._trade_symbol.addItems(symbol_choices)
        if self._symbol_name in symbol_choices:
            self._trade_symbol.setCurrentText(self._symbol_name)
        _set_field_width(self._trade_symbol)
        self._refresh_symbol_button = QToolButton()
        self._refresh_symbol_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self._refresh_symbol_button.setToolTip("Refresh symbol list")
        self._refresh_symbol_button.setFixedHeight(field_height)
        self._refresh_symbol_button.setFixedWidth(28)
        self._refresh_symbol_button.clicked.connect(self._refresh_symbol_list)
        symbol_row = QWidget()
        symbol_layout = QHBoxLayout(symbol_row)
        symbol_layout.setContentsMargins(0, 0, 0, 0)
        symbol_layout.setSpacing(6)
        symbol_layout.addWidget(self._trade_symbol)
        symbol_layout.addWidget(self._refresh_symbol_button)
        basic_card, basic_card_form = _card("Basic Settings")
        basic_card_form.addRow("Symbol", symbol_row)
        self._trade_symbol.currentTextChanged.connect(self._handle_trade_symbol_changed)

        self._trade_timeframe = QComboBox()
        self._trade_timeframe.addItems(["M1", "M5", "M15", "M30", "H1", "H4"])
        _set_field_width(self._trade_timeframe)
        basic_card_form.addRow("Timeframe", self._trade_timeframe)
        self._trade_timeframe.currentTextChanged.connect(self._handle_trade_timeframe_changed)
        form_model.addRow(basic_card)

        execution_card, execution_card_form = _card("Execution Mode")
        mode_row = QWidget()
        mode_layout = QVBoxLayout(mode_row)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(4)
        self._mode_demo = QRadioButton("Demo")
        self._mode_live = QRadioButton("Live")
        self._mode_demo.setChecked(True)
        mode_group = QButtonGroup(panel)
        mode_group.addButton(self._mode_demo)
        mode_group.addButton(self._mode_live)
        mode_layout.addWidget(self._mode_demo)
        mode_layout.addWidget(self._mode_live)
        execution_card_form.addRow("Mode", mode_row)
        form_model.addRow(execution_card)

        section_size = QLabel("POSITION SIZING")
        section_size.setProperty("section", True)
        form_trade.addRow(section_size)
        lot_row = QWidget()
        lot_layout = QVBoxLayout(lot_row)
        lot_layout.setContentsMargins(0, 0, 0, 0)
        lot_layout.setSpacing(4)
        self._lot_fixed = QRadioButton("Fixed lot")
        self._lot_risk = QRadioButton("Risk %")
        self._lot_fixed.setChecked(True)
        lot_group = QButtonGroup(panel)
        lot_group.addButton(self._lot_fixed)
        lot_group.addButton(self._lot_risk)
        lot_layout.addWidget(self._lot_fixed)
        lot_layout.addWidget(self._lot_risk)
        form_trade.addRow("Sizing", lot_row)

        self._lot_value = QDoubleSpinBox()
        self._lot_value.setDecimals(2)
        self._lot_value.setRange(0.01, 100.0)
        self._lot_value.setSingleStep(0.01)
        self._lot_value.setValue(0.1)
        self._lot_value.setSuffix(" lots")
        _set_field_width(self._lot_value)
        form_trade.addRow("Lot / Risk%", self._lot_value)
        self._lot_fixed.toggled.connect(self._sync_lot_value_style)
        self._lot_risk.toggled.connect(self._sync_lot_value_style)
        self._sync_lot_value_style()

        self._max_positions = QSpinBox()
        self._max_positions.setRange(1, 20)
        self._max_positions.setValue(1)
        _set_field_width(self._max_positions)
        form_trade.addRow("Max positions", self._max_positions)

        divider_2 = QFrame()
        divider_2.setFrameShape(QFrame.HLine)
        divider_2.setProperty("divider", True)
        form_trade.addRow(divider_2)

        section_risk = QLabel("RISK CONTROLS")
        section_risk.setProperty("section", True)
        form_trade.addRow(section_risk)
        self._stop_loss = QDoubleSpinBox()
        self._stop_loss.setDecimals(0)
        self._stop_loss.setRange(0.0, 1000000.0)
        self._stop_loss.setSingleStep(10.0)
        self._stop_loss.setValue(500.0)
        self._stop_loss.setSuffix(" pt")
        _set_field_width(self._stop_loss)
        form_trade.addRow("Stop loss (points)", self._stop_loss)

        self._take_profit = QDoubleSpinBox()
        self._take_profit.setDecimals(0)
        self._take_profit.setRange(0.0, 1000000.0)
        self._take_profit.setSingleStep(10.0)
        self._take_profit.setValue(800.0)
        self._take_profit.setSuffix(" pt")
        _set_field_width(self._take_profit)
        form_trade.addRow("Take profit (points)", self._take_profit)

        form_risk = form_trade
        self._risk_guard = QCheckBox("Enable")
        form_risk.addRow("Risk guard", self._risk_guard)

        self._max_drawdown = QDoubleSpinBox()
        self._max_drawdown.setDecimals(1)
        self._max_drawdown.setRange(0.0, 100.0)
        self._max_drawdown.setSingleStep(0.5)
        self._max_drawdown.setValue(10.0)
        self._max_drawdown.setSuffix(" %")
        _set_field_width(self._max_drawdown)
        form_risk.addRow("Max DD %", self._max_drawdown)

        self._daily_loss = QDoubleSpinBox()
        self._daily_loss.setDecimals(1)
        self._daily_loss.setRange(0.0, 100.0)
        self._daily_loss.setSingleStep(0.5)
        self._daily_loss.setValue(5.0)
        self._daily_loss.setSuffix(" %")
        _set_field_width(self._daily_loss)
        form_risk.addRow("Daily loss %", self._daily_loss)

        form_adv = _tab_form("Advanced", object_name="advancedTab")
        self._min_signal_interval = QSpinBox()
        self._min_signal_interval.setRange(0, 3600)
        self._min_signal_interval.setValue(5)
        _set_field_width(self._min_signal_interval)
        form_adv.addRow("Min interval (s)", self._min_signal_interval)

        self._slippage_bps = QDoubleSpinBox()
        self._slippage_bps.setDecimals(2)
        self._slippage_bps.setRange(0.0, 50.0)
        self._slippage_bps.setValue(0.5)
        _set_field_width(self._slippage_bps)
        form_adv.addRow("Slippage bps", self._slippage_bps)

        self._fee_bps = QDoubleSpinBox()
        self._fee_bps.setDecimals(2)
        self._fee_bps.setRange(0.0, 50.0)
        self._fee_bps.setValue(1.0)
        _set_field_width(self._fee_bps)
        form_adv.addRow("Fee bps", self._fee_bps)

        self._confidence = QDoubleSpinBox()
        self._confidence.setDecimals(2)
        self._confidence.setRange(0.0, 1.0)
        self._confidence.setSingleStep(0.05)
        self._confidence.setValue(0.0)
        _set_field_width(self._confidence)
        form_adv.addRow("Confidence", self._confidence)

        self._auto_log_panel = LogWidget(
            title="Auto Trade",
            with_timestamp=True,
            monospace=True,
            font_point_delta=1,
        )
        self._auto_log_panel.setMinimumHeight(140)
        self._auto_log_panel.setMaximumHeight(180)
        layout.addWidget(self._auto_log_panel)
        QTimer.singleShot(0, self._sync_field_widths)

        return panel

    def _init_splitter_sizes(self, splitter: QSplitter) -> None:
        total = splitter.width()
        if total <= 0:
            return
        left = max(260, int(total * 0.16))
        right = max(260, total - left)
        splitter.setSizes([left, right])

    def _sync_field_widths(self) -> None:
        if not getattr(self, "_autotrade_tabs", None):
            return
        if not getattr(self, "_field_widgets", None):
            return
        target = int(self._autotrade_tabs.width() * 0.33)
        target = max(180, min(360, target))
        for widget in self._field_widgets:
            widget.setFixedWidth(target)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_field_widths()

    def _init_bottom_splitter_sizes(self, splitter: QSplitter) -> None:
        total = splitter.width()
        if total <= 0:
            return
        quotes = max(220, int(total * 0.25))
        positions = max(420, int(total * 0.50))
        log = max(260, total - quotes - positions)
        if quotes + positions + log > total:
            log = max(200, total - quotes - positions)
        if quotes + positions + log <= total:
            splitter.setSizes([quotes, positions, log])

    def _browse_model_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select model file", self._model_path.text(), "Model (*.zip);;All files (*)"
        )
        if path:
            self._model_path.setText(path)

    def _auto_log(self, message: str) -> None:
        if self._auto_log_panel:
            self._auto_log_panel.append(message)
        self.logRequested.emit(message)

    def _toggle_auto_trade(self, enabled: bool) -> None:
        if enabled:
            if not self._load_auto_model():
                self._auto_trade_toggle.setChecked(False)
                return
            self._auto_enabled = True
            self._auto_trade_toggle.setText("Stop")
            self._auto_position = 0.0
            self._auto_position_id = None
            self._auto_last_action_ts = None
            self._auto_peak_balance = None
            self._auto_day_balance = None
            self._auto_day_key = None
            trade_symbol = self._trade_symbol.currentText()
            if trade_symbol and trade_symbol != self._symbol_name:
                self._symbol_name = trade_symbol
                self._symbol_id = self._resolve_symbol_id(trade_symbol)
                self._price_digits = self._quote_digits.get(
                    trade_symbol, self._infer_quote_digits(trade_symbol)
                )
                self._history_requested = False
                self._pending_history = False
                self._stop_live_trendbar()
                if self._oauth_service and getattr(self._oauth_service, "status", 0) >= ConnectionStatus.ACCOUNT_AUTHENTICATED:
                    self._request_recent_history()
            self._ensure_order_service()
            self._refresh_account_balance()
            self._auto_log("✅ Auto trading started")
        else:
            self._auto_enabled = False
            self._auto_trade_toggle.setText("Start")
            self._auto_log("🛑 Auto trading stopped")

    def _load_auto_model(self) -> bool:
        path = self._model_path.text().strip()
        if not path:
            self._auto_log("⚠️ Model path is empty")
            return False
        try:
            import importlib
            import sys
            import typing

            # PySide6 can inject typing.Self on Python 3.10 which breaks torch.
            if hasattr(typing, "Self"):
                delattr(typing, "Self")
            if "typing_extensions" in sys.modules:
                importlib.reload(sys.modules["typing_extensions"])
        except Exception:
            pass
        try:
            from stable_baselines3 import PPO
        except Exception as exc:
            self._auto_log(f"❌ Failed to import PPO: {exc}")
            return False
        try:
            self._auto_model = PPO.load(path)
        except Exception as exc:
            hint = ""
            if "typing.Self" in str(exc):
                hint = " (try Python>=3.10 or stable-baselines3<=2.3.x)"
            self._auto_log(f"❌ Failed to load model: {exc}{hint}")
            return False
        self._auto_log(f"✅ Model loaded: {Path(path).name}")
        return True

    def _ensure_order_service(self) -> None:
        if self._order_service or not self._service:
            return
        self._order_service = self._use_cases.create_order_service(self._service)
        self._order_service.set_callbacks(
            on_execution=self._handle_order_execution,
            on_error=lambda e: self._auto_log(f"❌ Order error: {e}"),
            on_log=self._auto_log,
        )

    def _handle_order_execution(self, payload: dict) -> None:
        position_id = payload.get("position_id")
        if position_id:
            self._auto_position_id = int(position_id)
        order = payload.get("order")
        position = payload.get("position")
        deal = payload.get("deal")
        symbol_id = (
            getattr(order, "symbolId", None)
            or getattr(position, "symbolId", None)
            or getattr(deal, "symbolId", None)
        )
        symbol_name = self._symbol_id_to_name.get(int(symbol_id)) if symbol_id else None
        volume = (
            getattr(order, "volume", None)
            or getattr(position, "volume", None)
            or getattr(deal, "volume", None)
        )
        if not volume:
            volume = payload.get("requested_volume")
        lot = None
        volume_text = None
        if volume is not None:
            try:
                volume_value = float(volume)
                lot = self._volume_to_lots(volume_value)
                volume_text = f"{int(volume_value)}"
            except (TypeError, ValueError):
                lot = None
        trade_side = getattr(order, "tradeSide", None)
        if trade_side == ProtoOATradeSide.BUY:
            side_text = "BUY"
        elif trade_side == ProtoOATradeSide.SELL:
            side_text = "SELL"
        else:
            side_text = None
        parts = []
        if side_text:
            parts.append(side_text)
        if lot is not None:
            parts.append(f"{lot:.3f} lot")
        if volume_text:
            parts.append(f"(volume {volume_text})")
        if symbol_name:
            parts.append(symbol_name)
        if position_id:
            parts.append(f"(pos {position_id})")
        if parts:
            self._auto_log(f"✅ Order executed: {' '.join(parts)}")
        self._request_positions()

    def _handle_trade_timeframe_changed(self, timeframe: str) -> None:
        self._timeframe = timeframe
        self._history_requested = False
        self._pending_history = False
        self._last_history_request_key = None
        self._last_history_success_key = None
        self._stop_live_trendbar()
        if self._oauth_service and getattr(self._oauth_service, "status", 0) >= ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._request_recent_history()

    def _refresh_symbol_list(self) -> None:
        if not self._service or not self._app_state or not self._app_state.selected_account_id:
            self._auto_log("⚠️ Account not ready; cannot refresh symbol list.")
            return
        try:
            if self._symbol_list_uc is None:
                self._symbol_list_uc = self._use_cases.create_symbol_list(self._service)
            if getattr(self._symbol_list_uc, "in_progress", False):
                return
        except Exception:
            return

        account_id = int(self._app_state.selected_account_id)

        def _on_symbols(symbols: list) -> None:
            if not symbols:
                self._queue_symbol_list_apply(symbols)
                return
            path = self._symbol_list_path()
            try:
                path.write_text(json.dumps(symbols, ensure_ascii=True, indent=2), encoding="utf-8")
            except Exception as exc:
                self.logRequested.emit(f"⚠️ Failed to write symbol list: {exc}")
            self._queue_symbol_list_apply(symbols)

        self._symbol_list_uc.set_callbacks(
            on_symbols_received=_on_symbols,
            on_error=lambda e: self._auto_log(f"❌ Symbol list error: {e}"),
            on_log=self._auto_log,
        )
        self._symbol_list_uc.fetch(account_id)

    def _queue_symbol_list_apply(self, symbols: list) -> None:
        self._pending_symbol_list = symbols
        app = QApplication.instance()
        if app is not None and QThread.currentThread() == app.thread():
            self._apply_symbol_list_update()
            return
        QMetaObject.invokeMethod(self, "_apply_symbol_list_update", Qt.QueuedConnection)

    @Slot()
    def _apply_symbol_list_update(self) -> None:
        symbols = self._pending_symbol_list or []
        if not symbols:
            return
        names = []
        mapping = {}
        for item in symbols:
            name = item.get("symbol_name") if isinstance(item, dict) else None
            symbol_id = item.get("symbol_id") if isinstance(item, dict) else None
            if not name or symbol_id is None:
                continue
            if name in mapping:
                continue
            try:
                mapping[name] = int(symbol_id)
            except (TypeError, ValueError):
                continue
            names.append(name)
        self._symbol_names = names
        self._symbol_id_map = mapping
        self._symbol_id_to_name = {symbol_id: name for name, symbol_id in mapping.items()}
        self._fx_symbols = self._filter_fx_symbols(self._symbol_names)
        current = self._trade_symbol.currentText()
        self._trade_symbol.blockSignals(True)
        self._trade_symbol.clear()
        self._trade_symbol.addItems(self._fx_symbols or ["EURUSD", "USDJPY"])
        if current and current in self._fx_symbols:
            self._trade_symbol.setCurrentText(current)
        self._trade_symbol.blockSignals(False)
        self._auto_log(f"✅ Symbol list refreshed: {len(self._fx_symbols)} symbols")
        current_symbol = self._trade_symbol.currentText() if hasattr(self, "_trade_symbol") else ""
        if not current_symbol:
            current_symbol = self._symbol_name

    def _sync_lot_value_style(self) -> None:
        if self._lot_risk.isChecked():
            self._lot_value.setSuffix(" %")
            self._lot_value.setSingleStep(0.1)
            self._lot_value.setRange(0.1, 50.0)
        else:
            self._lot_value.setSuffix(" lots")
            self._lot_value.setSingleStep(0.01)
            self._lot_value.setRange(0.01, 100.0)

    def _setup_autotrade_persistence(self) -> None:
        self._load_autotrade_settings()

        def _bind(widget, signal_name: str):
            signal = getattr(widget, signal_name, None)
            if signal is not None:
                signal.connect(self._save_autotrade_settings)

        _bind(self._model_path, "editingFinished")
        _bind(self._trade_symbol, "currentTextChanged")
        _bind(self._trade_timeframe, "currentTextChanged")
        _bind(self._lot_fixed, "toggled")
        _bind(self._lot_risk, "toggled")
        _bind(self._lot_value, "valueChanged")
        _bind(self._max_positions, "valueChanged")
        _bind(self._stop_loss, "valueChanged")
        _bind(self._take_profit, "valueChanged")
        _bind(self._risk_guard, "toggled")
        _bind(self._max_drawdown, "valueChanged")
        _bind(self._daily_loss, "valueChanged")
        _bind(self._mode_demo, "toggled")
        _bind(self._mode_live, "toggled")
        _bind(self._min_signal_interval, "valueChanged")
        _bind(self._slippage_bps, "valueChanged")
        _bind(self._fee_bps, "valueChanged")
        _bind(self._confidence, "valueChanged")

    def _save_autotrade_settings(self) -> None:
        if self._autotrade_loading:
            return
        payload = {
            "model_path": self._model_path.text().strip(),
            "symbol": self._trade_symbol.currentText(),
            "timeframe": self._trade_timeframe.currentText(),
            "sizing_mode": "risk" if self._lot_risk.isChecked() else "fixed",
            "lot_value": float(self._lot_value.value()),
            "max_positions": int(self._max_positions.value()),
            "stop_loss": float(self._stop_loss.value()),
            "take_profit": float(self._take_profit.value()),
            "risk_guard": bool(self._risk_guard.isChecked()),
            "max_drawdown": float(self._max_drawdown.value()),
            "daily_loss": float(self._daily_loss.value()),
            "mode": "live" if self._mode_live.isChecked() else "demo",
            "min_signal_interval": int(self._min_signal_interval.value()),
            "slippage_bps": float(self._slippage_bps.value()),
            "fee_bps": float(self._fee_bps.value()),
            "confidence": float(self._confidence.value()),
        }
        try:
            self._autotrade_settings_path.parent.mkdir(parents=True, exist_ok=True)
            self._autotrade_settings_path.write_text(
                json.dumps(payload, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _load_autotrade_settings(self) -> None:
        if not self._autotrade_settings_path.exists():
            return
        try:
            data = json.loads(self._autotrade_settings_path.read_text(encoding="utf-8"))
        except Exception:
            return
        self._autotrade_loading = True
        try:
            model_path = str(data.get("model_path", "")).strip()
            if model_path:
                self._model_path.setText(model_path)
            symbol = str(data.get("symbol", "")).strip()
            if symbol:
                idx = self._trade_symbol.findText(symbol)
                if idx >= 0:
                    self._trade_symbol.setCurrentIndex(idx)
            timeframe = str(data.get("timeframe", "")).strip()
            if timeframe:
                idx = self._trade_timeframe.findText(timeframe)
                if idx >= 0:
                    self._trade_timeframe.setCurrentIndex(idx)
            sizing_mode = str(data.get("sizing_mode", "fixed")).lower()
            self._lot_risk.setChecked(sizing_mode == "risk")
            self._lot_fixed.setChecked(sizing_mode != "risk")
            if "lot_value" in data:
                self._lot_value.setValue(float(data.get("lot_value", self._lot_value.value())))
            if "max_positions" in data:
                self._max_positions.setValue(int(data.get("max_positions", self._max_positions.value())))
            if "stop_loss" in data:
                self._stop_loss.setValue(float(data.get("stop_loss", self._stop_loss.value())))
            if "take_profit" in data:
                self._take_profit.setValue(float(data.get("take_profit", self._take_profit.value())))
            if "risk_guard" in data:
                self._risk_guard.setChecked(bool(data.get("risk_guard", False)))
            if "max_drawdown" in data:
                self._max_drawdown.setValue(float(data.get("max_drawdown", self._max_drawdown.value())))
            if "daily_loss" in data:
                self._daily_loss.setValue(float(data.get("daily_loss", self._daily_loss.value())))
            mode = str(data.get("mode", "demo")).lower()
            self._mode_live.setChecked(mode == "live")
            self._mode_demo.setChecked(mode != "live")
            if "min_signal_interval" in data:
                self._min_signal_interval.setValue(
                    int(data.get("min_signal_interval", self._min_signal_interval.value()))
                )
            if "slippage_bps" in data:
                self._slippage_bps.setValue(float(data.get("slippage_bps", self._slippage_bps.value())))
            if "fee_bps" in data:
                self._fee_bps.setValue(float(data.get("fee_bps", self._fee_bps.value())))
            if "confidence" in data:
                self._confidence.setValue(float(data.get("confidence", self._confidence.value())))
            self._sync_lot_value_style()
        finally:
            self._autotrade_loading = False

    def _ensure_quote_handler(self) -> None:
        if not self._service:
            return
        if self._spot_message_handler is None:
            self._spot_message_handler = self._handle_spot_message
            self._service.add_message_handler(self._spot_message_handler)

    def _ensure_positions_handler(self) -> None:
        if not self._service:
            return
        if self._positions_message_handler is None:
            self._positions_message_handler = self._handle_positions_message
            self._service.add_message_handler(self._positions_message_handler)

    def _request_positions(self) -> None:
        if self._account_switch_in_progress:
            return
        if not self._service or not self._app_state:
            return
        account_id = self._app_state.selected_account_id
        if not account_id:
            return
        self.logRequested.emit(f"➡️ Request positions (account_id={account_id})")
        try:
            client = self._service.get_client()  # type: ignore[attr-defined]
        except Exception:
            return
        self._ensure_positions_handler()
        request = ProtoOAReconcileReq()
        request.ctidTraderAccountId = int(account_id)
        client.send(request)

    def _handle_positions_message(self, _client, msg) -> bool:
        if getattr(msg, "payloadType", None) != ProtoOAPayloadType.PROTO_OA_RECONCILE_RES:
            return False
        account_id = getattr(msg, "ctidTraderAccountId", None)
        if self._app_state and self._app_state.selected_account_id:
            if int(account_id or 0) != int(self._app_state.selected_account_id):
                return False
        positions = list(getattr(msg, "position", []))
        self.positionsUpdated.emit(positions)
        return False

    @Slot(object)
    def _apply_positions_update(self, positions: object) -> None:
        try:
            pos_list = list(positions) if positions is not None else []
        except Exception:
            pos_list = []
        self._open_positions = pos_list
        self._sync_auto_position_from_positions(pos_list)
        self._schedule_positions_refresh()

    def _update_positions_table(self, positions: list[object]) -> None:
        if not self._positions_table:
            return
        table = self._positions_table
        table.setRowCount(len(positions))
        for row, position in enumerate(positions):
            trade_data = getattr(position, "tradeData", None)
            symbol_id = getattr(trade_data, "symbolId", None) if trade_data else None
            symbol_name = self._symbol_id_to_name.get(int(symbol_id)) if symbol_id else "-"
            side_value = getattr(trade_data, "tradeSide", None) if trade_data else None
            if side_value == ProtoOATradeSide.BUY:
                side_text = "BUY"
            elif side_value == ProtoOATradeSide.SELL:
                side_text = "SELL"
            else:
                side_text = "-"
            volume = getattr(trade_data, "volume", None) if trade_data else None
            if volume is not None:
                try:
                    lot_text = f"{self._volume_to_lots(float(volume)):.2f}"
                except (TypeError, ValueError):
                    lot_text = "-"
            else:
                lot_text = "-"
            entry_price = getattr(position, "price", None)
            entry_text = self._format_price(entry_price) if entry_price is not None else "-"
            current_text = self._current_price_text(symbol_id=symbol_id, side_value=side_value)
            sl_price = getattr(position, "stopLoss", None)
            tp_price = getattr(position, "takeProfit", None)
            sl_text = self._format_price(sl_price) if sl_price not in (None, 0) else "-"
            tp_text = self._format_price(tp_price) if tp_price not in (None, 0) else "-"
            open_ts = getattr(trade_data, "openTimestamp", None) if trade_data else None
            time_text = self._format_time(open_ts) if open_ts is not None else "-"
            pnl_text = self._calc_position_pnl(
                position=position,
                trade_data=trade_data,
                symbol_id=symbol_id,
                side_value=side_value,
                entry_price=entry_price,
                volume=volume,
            )

            position_id = getattr(position, "positionId", None)
            values = [
                symbol_name or "-",
                side_text,
                lot_text,
                entry_text,
                current_text,
                pnl_text,
                sl_text,
                tp_text,
                time_text,
                position_id if position_id is not None else "-",
            ]
            for col, value in enumerate(values):
                item = table.item(row, col)
                if item is None:
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row, col, item)
                else:
                    item.setText(str(value))

    def _ensure_quote_subscription(self) -> None:
        if self._account_switch_in_progress:
            return
        if not self._service or not self._app_state:
            return
        account_id = self._app_state.selected_account_id
        if not account_id:
            return
        self.logRequested.emit(f"➡️ Subscribe quotes (account_id={account_id})")
        try:
            client = self._service.get_client()  # type: ignore[attr-defined]
        except Exception:
            return
        desired_ids = set(self._quote_rows.keys())
        if desired_ids and desired_ids.issubset(self._quote_subscribed_ids | self._quote_subscribe_inflight):
            self._quote_subscribed = True
            return
        self._ensure_quote_handler()

        from utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        for symbol_id in self._quote_rows.keys():
            if symbol_id in self._quote_subscribed_ids:
                continue
            self._quote_subscribe_inflight.add(symbol_id)
        pending_ids = sorted(self._quote_subscribe_inflight)
        if pending_ids:
            reactor.callFromThread(
                send_spot_subscribe,
                client,
                account_id=account_id,
                symbol_id=pending_ids,
                log=self.logRequested.emit,
                subscribe_to_spot_timestamp=True,
            )
        self._quote_subscribed = True

    def _stop_quote_subscription(self) -> None:
        if not self._service or not self._app_state:
            return
        account_id = self._app_state.selected_account_id
        if not account_id:
            self._quote_subscribed = False
            self._quote_subscribed_ids.clear()
            return
        try:
            client = self._service.get_client()  # type: ignore[attr-defined]
        except Exception:
            self._quote_subscribed = False
            return

        from utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        unsubscribe_ids = sorted(self._quote_rows.keys())
        if unsubscribe_ids:
            reactor.callFromThread(
                send_spot_unsubscribe,
                client,
                account_id=account_id,
                symbol_id=unsubscribe_ids,
                log=self.logRequested.emit,
            )
        self._quote_subscribed = False
        self._quote_subscribed_ids.clear()
        self._quote_subscribe_inflight.clear()

    def _handle_spot_message(self, _client, msg) -> bool:
        if getattr(msg, "payloadType", None) != ProtoOAPayloadType.PROTO_OA_SPOT_EVENT:
            return False
        account_id = getattr(msg, "ctidTraderAccountId", None)
        if self._app_state and self._app_state.selected_account_id:
            if account_id is not None and int(account_id) != int(self._app_state.selected_account_id):
                return False
        symbol_id = getattr(msg, "symbolId", None)
        if symbol_id is None or symbol_id not in self._quote_rows:
            return False
        if symbol_id in self._quote_subscribe_inflight:
            self._quote_subscribe_inflight.discard(symbol_id)
            self._quote_subscribed_ids.add(symbol_id)
        bid = getattr(msg, "bid", None)
        ask = getattr(msg, "ask", None)
        has_bid = getattr(msg, "hasBid", None)
        has_ask = getattr(msg, "hasAsk", None)
        if has_bid is False:
            bid = None
        if has_ask is False:
            ask = None
        spot_ts = getattr(msg, "spotTimestamp", None)
        if spot_ts is None:
            spot_ts = getattr(msg, "timestamp", None)
        self.quoteUpdated.emit(int(symbol_id), bid, ask, spot_ts)
        return False

    @Slot(int, object, object, object)
    def _handle_quote_updated(self, symbol_id: int, bid, ask, spot_ts) -> None:
        if not self._quotes_table:
            return
        row = self._quote_rows.get(symbol_id)
        if row is None:
            return
        self._set_quote_cell(row, 1, bid)
        self._set_quote_cell(row, 2, ask)
        self._set_quote_extras(row, symbol_id, bid, ask, spot_ts)
        self._update_chart_from_quote(symbol_id, bid, ask, spot_ts)

    def _set_quote_cell(self, row: int, column: int, value) -> None:
        if not self._quotes_table:
            return
        normalized = self._normalize_price(value)
        if normalized == 0:
            text = "--"
        else:
            digits = self._quote_row_digits.get(
                next((k for k, v in self._quote_rows.items() if v == row), None),
                self._price_digits,
            )
            text = self._format_price(value, digits=digits)
        item = self._quotes_table.item(row, column)
        if item is None:
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            self._quotes_table.setItem(row, column, item)
        else:
            item.setText(text)

    def _set_quote_extras(self, row: int, symbol_id: int, bid, ask, spot_ts) -> None:
        if not self._quotes_table:
            return
        bid_val = self._normalize_price(bid)
        ask_val = self._normalize_price(ask)
        if bid_val is not None:
            self._quote_last_bid[symbol_id] = bid_val
        if ask_val is not None:
            self._quote_last_ask[symbol_id] = ask_val
        time_text = self._format_spot_time(spot_ts)
        if bid_val in (None, 0) or ask_val in (None, 0):
            self._set_quote_text(row, 3, "--")
            self._set_quote_text(row, 4, time_text)
            return
        mid = (bid_val + ask_val) / 2.0
        self._quote_last_mid[symbol_id] = mid

        digits = self._quote_row_digits.get(symbol_id, self._price_digits)
        spread = ask_val - bid_val
        spread_text = f"{spread:.{digits}f}"
        self._set_quote_text(row, 3, spread_text)
        self._set_quote_text(row, 4, time_text)
        if self._open_positions:
            self._schedule_positions_refresh()

    def _set_quote_text(self, row: int, column: int, text: str) -> None:
        if not self._quotes_table:
            return
        item = self._quotes_table.item(row, column)
        if item is None:
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            self._quotes_table.setItem(row, column, item)
        else:
            item.setText(text)

    def _schedule_positions_refresh(self) -> None:
        if self._positions_refresh_pending:
            return
        self._positions_refresh_pending = True
        self._positions_refresh_timer.start()

    def _apply_positions_refresh(self) -> None:
        self._positions_refresh_pending = False
        if self._open_positions:
            self._update_positions_table(self._open_positions)

    @staticmethod
    def _volume_to_lots(volume_value: float) -> float:
        return volume_value / 10000000.0

    def _calc_position_pnl(
        self,
        *,
        position: Optional[object],
        trade_data: Optional[object],
        symbol_id: Optional[int],
        side_value: Optional[int],
        entry_price,
        volume,
    ) -> str:
        position_id = getattr(position, "positionId", None)
        if position_id is not None:
            cached = self._position_pnl_by_id.get(int(position_id))
            if cached is not None:
                return f"{cached:,.2f}"
        for source in (position, trade_data):
            if source is None:
                continue
            money_digits = getattr(source, "moneyDigits", None) or getattr(position, "moneyDigits", None)
            for attr in ("netProfit", "netUnrealizedPnl", "unrealizedPnl", "profit", "grossProfit", "pnl"):
                value = getattr(source, attr, None)
                if value is None:
                    continue
                try:
                    if money_digits is not None and isinstance(value, int):
                        scaled = self._scale_money(value, int(money_digits))
                        return f"{scaled:,.2f}"
                    return f"{float(value):,.2f}"
                except (TypeError, ValueError):
                    pass
        if symbol_id is None or entry_price is None or volume is None:
            return "-"
        try:
            entry = float(entry_price)
            vol = float(volume)
        except (TypeError, ValueError):
            return "-"
        if vol <= 0 or entry <= 0:
            return "-"
        bid = self._quote_last_bid.get(int(symbol_id))
        ask = self._quote_last_ask.get(int(symbol_id))
        mid = self._quote_last_mid.get(int(symbol_id))
        if side_value == ProtoOATradeSide.BUY:
            current = bid if bid else mid
            if current is None:
                return "-"
            pnl = (current - entry) * vol
        elif side_value == ProtoOATradeSide.SELL:
            current = ask if ask else mid
            if current is None:
                return "-"
            pnl = (entry - current) * vol
        else:
            return "-"
        return f"{pnl:,.2f}"

    @staticmethod
    def _scale_money(value: int, digits: int) -> float:
        if digits <= 0:
            return float(value)
        return float(value) / (10**digits)

    @staticmethod
    def _format_money(value: Optional[float], digits: int) -> str:
        if value is None:
            return "-"
        if digits <= 0:
            return str(int(round(value)))
        return f"{value:.{digits}f}"

    def _update_account_summary(self, snapshot) -> None:
        if not self._account_summary_labels:
            return
        money_digits = getattr(snapshot, "money_digits", None)
        if money_digits is None:
            money_digits = 2
        balance = getattr(snapshot, "balance", None)
        equity = getattr(snapshot, "equity", None)
        free_margin = getattr(snapshot, "free_margin", None)
        used_margin = getattr(snapshot, "used_margin", None)
        margin_level = getattr(snapshot, "margin_level", None)
        currency = getattr(snapshot, "currency", None) or "-"
        net_pnl = None
        if balance is not None and equity is not None:
            net_pnl = float(equity) - float(balance)

        self._account_summary_labels["balance"].setText(self._format_money(balance, money_digits))
        self._account_summary_labels["equity"].setText(self._format_money(equity, money_digits))
        self._account_summary_labels["free_margin"].setText(self._format_money(free_margin, money_digits))
        self._account_summary_labels["used_margin"].setText(self._format_money(used_margin, money_digits))
        if margin_level is None:
            self._account_summary_labels["margin_level"].setText("-")
        else:
            self._account_summary_labels["margin_level"].setText(f"{margin_level:.1f}%")
        self._account_summary_labels["net_pnl"].setText(self._format_money(net_pnl, money_digits))
        self._account_summary_labels["currency"].setText(str(currency))

    @Slot(object)
    def _apply_account_summary_update(self, snapshot: object) -> None:
        self._update_account_summary(snapshot)

    def _current_price_text(self, *, symbol_id: Optional[int], side_value: Optional[int]) -> str:
        if symbol_id is None:
            return "-"
        bid = self._quote_last_bid.get(int(symbol_id))
        ask = self._quote_last_ask.get(int(symbol_id))
        mid = self._quote_last_mid.get(int(symbol_id))
        current = None
        if side_value == ProtoOATradeSide.BUY:
            current = bid if bid else mid
        elif side_value == ProtoOATradeSide.SELL:
            current = ask if ask else mid
        else:
            current = mid
        if current is None:
            return "-"
        digits = self._quote_row_digits.get(int(symbol_id), self._price_digits)
        return self._format_price(current, digits=digits)

    def _format_spot_time(self, spot_ts) -> str:
        if spot_ts in (None, 0, "0", "0.0"):
            return datetime.utcnow().strftime("%H:%M:%S")
        try:
            ts_val = float(spot_ts)
        except (TypeError, ValueError):
            return datetime.utcnow().strftime("%H:%M:%S")
        if ts_val > 1e12:
            ts_val = ts_val / 1000.0
        return datetime.utcfromtimestamp(ts_val).strftime("%H:%M:%S")

    def _format_time(self, timestamp) -> str:
        if timestamp in (None, 0, "0", "0.0"):
            return datetime.utcnow().strftime("%H:%M:%S")
        try:
            ts_val = float(timestamp)
        except (TypeError, ValueError):
            return datetime.utcnow().strftime("%H:%M:%S")
        if ts_val > 1e12:
            ts_val = ts_val / 1000.0
        return datetime.utcfromtimestamp(ts_val).strftime("%H:%M:%S")

    def _symbol_list_path(self) -> Path:
        return self._project_root / SYMBOL_LIST_FILE

    def _normalize_price(self, value) -> Optional[float]:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if numeric == 0:
            return 0.0
        if isinstance(value, int):
            return numeric / 100000.0
        if numeric.is_integer() and abs(numeric) >= 100000:
            return numeric / 100000.0
        return numeric

    def _format_price(self, value, *, digits: Optional[int] = None) -> str:
        normalized = self._normalize_price(value)
        if normalized is None:
            return "-"
        use_digits = self._price_digits if digits is None else digits
        return f"{normalized:.{use_digits}f}"

    def _run_auto_trade_on_close(self) -> None:
        if not self._auto_enabled or not self._auto_model:
            return
        if not self._app_state or not self._app_state.selected_account_id:
            return
        now_ts = datetime.utcnow().timestamp()
        min_interval = int(self._min_signal_interval.value()) if hasattr(self, "_min_signal_interval") else 0
        if self._auto_last_action_ts and now_ts - self._auto_last_action_ts < min_interval:
            return
        if len(self._candles) < 30:
            return

        df = pd.DataFrame(
            {
                "timestamp": [datetime.utcfromtimestamp(c[0]).strftime("%H:%M") for c in self._candles],
                "open": [c[1] for c in self._candles],
                "high": [c[2] for c in self._candles],
                "low": [c[3] for c in self._candles],
                "close": [c[4] for c in self._candles],
            }
        )
        try:
            feature_set = build_features(df)
        except Exception as exc:
            self._auto_log(f"❌ Feature build failed: {exc}")
            return
        if feature_set.features.shape[0] <= 0:
            return
        obs = np.concatenate(
            [feature_set.features[-1], np.array([self._auto_position], dtype=np.float32)]
        ).astype(np.float32)
        try:
            action, _ = self._auto_model.predict(obs, deterministic=True)
        except Exception as exc:
            self._auto_log(f"❌ Model inference failed: {exc}")
            return
        target_position = float(np.clip(action[0], -1.0, 1.0))
        self._execute_target_position(target_position)
        self._auto_last_action_ts = now_ts

    def _execute_target_position(self, target: float) -> None:
        if not self._app_state or not self._app_state.selected_account_id:
            return
        account_id = int(self._app_state.selected_account_id)
        symbol_name = self._trade_symbol.currentText() if hasattr(self, "_trade_symbol") else self._symbol_name
        symbol_id = int(self._resolve_symbol_id(symbol_name))
        self._ensure_order_service()
        if not self._order_service or getattr(self._order_service, "in_progress", False):
            return
        self._refresh_account_balance()

        threshold = 0.05
        desired = 0.0 if abs(target) < threshold else target
        desired_side = "buy" if desired > 0 else "sell"

        if desired == 0.0 and self._auto_position_id:
            volume = self._calc_volume()
            self._order_service.close_position(
                account_id=account_id,
                position_id=int(self._auto_position_id),
                volume=volume,
            )
            self._auto_position = 0.0
            self._auto_position_id = None
            return

        if desired == 0.0:
            self._auto_position = 0.0
            return

        if not self._risk_guard_allows():
            self._auto_log("⚠️ Risk guard blocked new trades.")
            return

        if self._auto_position_id and (
            (self._auto_position > 0 and desired > 0)
            or (self._auto_position < 0 and desired < 0)
        ):
            self._auto_position = desired
            return

        if self._auto_position_id:
            volume = self._calc_volume()
            self._order_service.close_position(
                account_id=account_id,
                position_id=int(self._auto_position_id),
                volume=volume,
            )
            self._auto_position_id = None

        volume = self._calc_volume()
        stop_loss_points, take_profit_points = self._calc_sl_tp_pips()
        self._order_service.place_market_order(
            account_id=account_id,
            symbol_id=symbol_id,
            trade_side=desired_side,
            volume=volume,
            relative_stop_loss=stop_loss_points,
            relative_take_profit=take_profit_points,
            label="auto-ppo",
        )
        self._auto_position = desired

    def _calc_volume(self) -> int:
        lot = float(self._lot_value.value())
        if self._lot_risk.isChecked():
            balance = self._auto_balance
            if balance:
                lot = max(0.01, (balance * (lot / 100.0)) / 100000.0)
            else:
                self._auto_log("⚠️ Balance unavailable; using fixed lot.")
        units = int(max(1, round(lot * 100000)))
        raw_volume = units * 100  # protocol volume is in 0.01 of a unit
        symbol_name = ""
        try:
            symbol_name = self._trade_symbol.currentText()
        except Exception:
            symbol_name = self._symbol_name
        self._fetch_symbol_details(symbol_name)
        min_volume, volume_step = self._get_volume_constraints(symbol_name)
        volume = max(raw_volume, min_volume)
        if volume_step > 1:
            volume = (volume // volume_step) * volume_step
            if volume < min_volume:
                volume = min_volume
        if volume != raw_volume:
            self._auto_log(
                f"⚠️ Volume adjusted {raw_volume} → {volume} (min {min_volume}, step {volume_step})."
            )
        return volume

    def _get_volume_constraints(self, symbol_name: str) -> tuple[int, int]:
        if not self._symbol_volume_loaded:
            self._load_symbol_volume_constraints()
        if symbol_name in self._symbol_volume_constraints:
            return self._symbol_volume_constraints[symbol_name]
        if not self._symbol_overrides_loaded:
            self._load_symbol_overrides()
        if symbol_name in self._symbol_overrides:
            override = self._symbol_overrides[symbol_name]
            min_volume = override.get("min_volume")
            volume_step = override.get("volume_step")
            try:
                min_volume_int = int(min_volume) if min_volume is not None else None
            except (TypeError, ValueError):
                min_volume_int = None
            try:
                volume_step_int = int(volume_step) if volume_step is not None else None
            except (TypeError, ValueError):
                volume_step_int = None
            if min_volume_int is not None or volume_step_int is not None:
                if min_volume_int is None:
                    min_volume_int = max(1, volume_step_int or 1)
                if volume_step_int is None:
                    volume_step_int = min_volume_int
                if min_volume_int > 0 and volume_step_int > 0:
                    self._symbol_volume_constraints[symbol_name] = (
                        min_volume_int,
                        volume_step_int,
                    )
                    return min_volume_int, volume_step_int
        symbol_id = self._symbol_id_map.get(symbol_name)
        if symbol_id is not None:
            detail = self._symbol_details_by_id.get(int(symbol_id))
            if isinstance(detail, dict):
                min_volume = detail.get("min_volume")
                volume_step = detail.get("volume_step")
                try:
                    min_volume_int = int(min_volume) if min_volume is not None else None
                except (TypeError, ValueError):
                    min_volume_int = None
                try:
                    volume_step_int = int(volume_step) if volume_step is not None else None
                except (TypeError, ValueError):
                    volume_step_int = None
                if min_volume_int is not None or volume_step_int is not None:
                    if min_volume_int is None:
                        min_volume_int = max(1, volume_step_int or 1)
                    if volume_step_int is None:
                        volume_step_int = min_volume_int
                    if min_volume_int > 0 and volume_step_int > 0:
                        self._symbol_volume_constraints[symbol_name] = (
                            min_volume_int,
                            volume_step_int,
                        )
                        return min_volume_int, volume_step_int
        return 100000, 100000

    def _load_symbol_overrides(self) -> None:
        self._symbol_overrides_loaded = True
        path = self._project_root / "symbol_overrides.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(data, dict):
            self._symbol_overrides = {
                str(k): v for k, v in data.items() if isinstance(v, dict)
            }

    def _load_symbol_volume_constraints(self) -> None:
        self._symbol_volume_loaded = True
        path = self._symbol_list_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        for item in data:
            name = item.get("symbol_name")
            if not isinstance(name, str) or not name:
                continue
            min_volume = item.get("min_volume", item.get("minVolume"))
            volume_step = item.get("volume_step", item.get("volumeStep"))
            digits = item.get("digits")
            try:
                min_volume_int = int(min_volume) if min_volume is not None else None
            except (TypeError, ValueError):
                min_volume_int = None
            try:
                volume_step_int = int(volume_step) if volume_step is not None else None
            except (TypeError, ValueError):
                volume_step_int = None
            try:
                digits_int = int(digits) if digits is not None else None
            except (TypeError, ValueError):
                digits_int = None
            if min_volume_int is None and volume_step_int is None:
                if digits_int is None:
                    continue
            if min_volume_int is None:
                min_volume_int = max(1, volume_step_int or 1)
            if volume_step_int is None:
                volume_step_int = min_volume_int
            if min_volume_int <= 0 or volume_step_int <= 0:
                min_volume_int = None
                volume_step_int = None
            if min_volume_int is not None and volume_step_int is not None:
                self._symbol_volume_constraints[name] = (min_volume_int, volume_step_int)
            if digits_int is not None and digits_int > 0:
                self._symbol_digits_by_name[name] = digits_int
                self._quote_digits[name] = digits_int

    def _calc_sl_tp_pips(self) -> tuple[Optional[int], Optional[int]]:
        sl_points = float(self._stop_loss.value())
        tp_points = float(self._take_profit.value())
        stop_loss = None
        take_profit = None
        if sl_points > 0:
            stop_loss = int(round(sl_points))
        if tp_points > 0:
            take_profit = int(round(tp_points))
        return stop_loss, take_profit

    def _sync_auto_position_from_positions(self, positions: list[object]) -> None:
        if not self._auto_enabled:
            return
        symbol_name = ""
        try:
            symbol_name = self._trade_symbol.currentText()
        except Exception:
            symbol_name = self._symbol_name
        symbol_id = self._resolve_symbol_id(symbol_name) if symbol_name else None
        matched = []
        for position in positions:
            trade_data = getattr(position, "tradeData", None)
            pos_symbol_id = getattr(trade_data, "symbolId", None) if trade_data else None
            if symbol_id is not None and pos_symbol_id is not None and int(pos_symbol_id) != int(symbol_id):
                continue
            matched.append(position)
        if not matched:
            self._auto_position_id = None
            self._auto_position = 0.0
            return
        primary = matched[0]
        trade_data = getattr(primary, "tradeData", None)
        side_value = getattr(trade_data, "tradeSide", None) if trade_data else None
        position_id = getattr(primary, "positionId", None)
        if position_id:
            self._auto_position_id = int(position_id)
        if side_value == ProtoOATradeSide.BUY:
            self._auto_position = 1.0
        elif side_value == ProtoOATradeSide.SELL:
            self._auto_position = -1.0

    def _risk_guard_allows(self) -> bool:
        if not self._risk_guard.isChecked():
            return True
        if self._auto_balance is None or self._auto_peak_balance is None or self._auto_day_balance is None:
            return True
        max_dd = float(self._max_drawdown.value()) / 100.0
        daily_loss = float(self._daily_loss.value()) / 100.0
        if self._auto_peak_balance > 0:
            drawdown = (self._auto_peak_balance - self._auto_balance) / self._auto_peak_balance
            if drawdown >= max_dd > 0:
                return False
        if self._auto_day_balance > 0:
            day_loss = (self._auto_day_balance - self._auto_balance) / self._auto_day_balance
            if day_loss >= daily_loss > 0:
                return False
        return True

    def _refresh_account_balance(self) -> None:
        if self._account_switch_in_progress:
            return
        if not self._service or not self._app_state or not self._app_state.selected_account_id:
            return
        now = time.time()
        if now - self._last_funds_fetch_ts < 4.5:
            return
        account_id = int(self._app_state.selected_account_id)
        try:
            if getattr(self, "_account_funds_uc", None) is None:
                self._account_funds_uc = self._use_cases.create_account_funds(self._service)
            funds_uc = self._account_funds_uc
            if getattr(funds_uc, "in_progress", False):
                return
        except Exception:
            return
        self._last_funds_fetch_ts = now

        def _on_funds(snapshot) -> None:
            balance = getattr(snapshot, "balance", None)
            if balance is not None:
                self._auto_balance = float(balance)
                if self._auto_peak_balance is None or self._auto_balance > self._auto_peak_balance:
                    self._auto_peak_balance = self._auto_balance
                day_key = datetime.utcnow().strftime("%Y-%m-%d")
                if self._auto_day_key != day_key:
                    self._auto_day_key = day_key
                    self._auto_day_balance = self._auto_balance
            self.logRequested.emit("✅ Funds received")
            self.accountSummaryUpdated.emit(snapshot)

        def _on_position_pnl(pnl_map: dict[int, float]) -> None:
            if pnl_map:
                self._position_pnl_by_id.update(pnl_map)
                if self._open_positions:
                    self.positionsUpdated.emit(self._open_positions)

        funds_uc.set_callbacks(
            on_funds_received=_on_funds,
            on_position_pnl=_on_position_pnl,
            on_log=self.logRequested.emit,
        )
        funds_uc.fetch(account_id)

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
        layout.addWidget(plot)

        self._candlestick_item = CandlestickItem([])
        plot.addItem(self._candlestick_item)
        self._last_price_line = pg.InfiniteLine(
            angle=0,
            pen=pg.mkPen("#9ca3af", width=1, style=Qt.DashLine),
            movable=False,
        )
        plot.addItem(self._last_price_line)
        self._last_price_label = pg.TextItem(color="#e5e7eb", anchor=(0, 0.5))
        self._last_price_label.setZValue(10)
        plot.addItem(self._last_price_label)
        self._chart_plot = plot

        return panel

    def set_candles(self, candles: list[tuple[float, float, float, float, float]]) -> None:
        self._pending_candles = candles

    def _flush_chart_update(self) -> None:
        if self._pending_candles is None:
            return
        candles = self._pending_candles
        self._pending_candles = None
        if not self._candlestick_item or not self._chart_plot:
            return
        if self._chart_frozen:
            return
        if not candles:
            if self._chart_ready:
                self._candlestick_item.setData([])
                if self._last_price_line:
                    self._last_price_line.hide()
                if self._last_price_label:
                    self._last_price_label.hide()
            return
        if not self._chart_ready:
            self._chart_ready = True
        self._candlestick_item.setData(candles)
        self._chart_plot.enableAutoRange(False, False)
        step_seconds = self._timeframe_minutes() * 60
        extra_space = step_seconds * 5 if step_seconds > 0 else 0
        self._chart_plot.setXRange(
            candles[0][0],
            candles[-1][0] + extra_space,
            padding=0.0,
        )
        lows = [candle[3] for candle in candles]
        highs = [candle[2] for candle in candles]
        min_price = min(lows)
        max_price = max(highs)
        if min_price == max_price:
            pad = max(0.0001, min_price * 0.0001)
            self._chart_plot.setYRange(min_price - pad, max_price + pad, padding=0.0)
        else:
            self._chart_plot.setYRange(min_price, max_price, padding=0.1)
        last_close = candles[-1][4]
        if self._last_price_line:
            self._last_price_line.setValue(last_close)
            self._last_price_line.show()
        if self._last_price_label:
            label = f"{last_close:.{self._price_digits}f}"
            self._last_price_label.setText(label)
            step_seconds = self._timeframe_minutes() * 60
            x_offset = step_seconds if step_seconds > 0 else 0
            y_offset = (max(highs) - min(lows)) * 0.015 if highs and lows else 0
            self._last_price_label.setPos(candles[-1][0] + x_offset, last_close + y_offset)
            self._last_price_label.show()

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
        self.oauthError.connect(self._handle_oauth_error)
        self.oauthSuccess.connect(self._handle_oauth_success)
        self.appStateChanged.connect(self._handle_app_state_changed)
        self.positionsUpdated.connect(self._apply_positions_update)
        self.accountSummaryUpdated.connect(self._apply_account_summary_update)
        self.historyReceived.connect(self._handle_history_received)
        self.trendbarReceived.connect(self._handle_trendbar_received)
        self.quoteUpdated.connect(self._handle_quote_updated)

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
        self.logRequested.emit(f"ℹ️ OAuth status -> {ConnectionStatus(status).name}")
        if status >= ConnectionStatus.ACCOUNT_AUTHENTICATED:
            last_auth_id = getattr(self._oauth_service, "last_authenticated_account_id", None)
            if last_auth_id is not None:
                self._last_authorized_account_id = int(last_auth_id)
            self._pending_full_reconnect = False
            if not self._accounts:
                self._refresh_accounts()
            if self._account_switch_in_progress and self._app_state and self._app_state.selected_account_id:
                token_account = getattr(getattr(self._oauth_service, "tokens", None), "account_id", None)
                if token_account and int(token_account) == int(self._app_state.selected_account_id):
                    self._account_switch_in_progress = False
            if self._app_state and self._app_state.selected_account_id:
                if last_auth_id is not None and int(self._app_state.selected_account_id) != int(last_auth_id):
                    self._account_switch_in_progress = True
                    self.logRequested.emit(
                        "⏳ Waiting for account authorization (account switch pending)"
                    )
                    self._schedule_full_reconnect()
                    return
            self._request_recent_history()
            self._ensure_quote_subscription()
            self._request_positions()
            self._refresh_account_balance()
            if not self._funds_timer.isActive():
                self._funds_timer.start()
        else:
            self._auto_enabled = False
            self._auto_trade_toggle.setChecked(False)
            self._chart_frozen = True
            self._pending_candles = None
            self._history_requested = False
            self._pending_history = False
            self._account_switch_in_progress = True
            self._stop_live_trendbar()
            self._stop_quote_subscription()
            if self._funds_timer.isActive():
                self._funds_timer.stop()

    def _handle_oauth_success(self, tokens: OAuthTokens) -> None:
        if tokens and tokens.account_id:
            self._last_authorized_account_id = int(tokens.account_id)
            self.logRequested.emit(f"✅ OAuth authorized account: {tokens.account_id}")

    def _handle_oauth_error(self, error: str) -> None:
        message = str(error)
        self.logRequested.emit(message)
        if "Trading account is not authorized" not in message:
            return
        token_account = getattr(getattr(self._oauth_service, "tokens", None), "account_id", None)
        if token_account:
            try:
                self._unauthorized_accounts.add(int(token_account))
            except Exception:
                pass
        self._account_switch_in_progress = False
        self.logRequested.emit("⚠️ Selected account is not authorized for Open API.")
        if self._last_authorized_account_id and token_account and int(token_account) != int(self._last_authorized_account_id):
            self.logRequested.emit("ℹ️ 帳戶未授權，請切回可用帳戶並手動重新連線")

    def _load_tokens_for_accounts(self) -> Optional[OAuthTokens]:
        try:
            return OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self.logRequested.emit(f"⚠️ 無法讀取 token 檔案: {exc}")
            return None

    def _refresh_accounts(self) -> None:
        if not self._use_cases:
            self.logRequested.emit(format_connection_message("missing_use_cases"))
            return
        if not self._service:
            self.logRequested.emit("⚠️ App auth service unavailable. Cannot fetch accounts.")
            return
        if self._use_cases.account_list_in_progress():
            self.logRequested.emit("⏳ 正在取得帳戶列表，請稍候")
            return

        tokens = self._load_tokens_for_accounts()
        access_token = "" if tokens is None else str(tokens.access_token or "").strip()
        if not access_token:
            self.logRequested.emit("⚠️ 缺少 Access Token，請先完成 OAuth 授權")
            return

        from utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        reactor.callFromThread(
            self._use_cases.fetch_accounts,
            self._service,
            access_token,
            self._handle_accounts_received,
            self._handle_accounts_error,
            self.logRequested.emit,
        )

    def _handle_accounts_received(self, accounts: list[object]) -> None:
        self._accounts = list(accounts or [])
        if self._accounts:
            try:
                raw_items = []
                for item in self._accounts:
                    if isinstance(item, dict):
                        raw_items.append(item)
                    else:
                        raw_items.append(
                            {
                                "account_id": getattr(item, "account_id", None),
                                "is_live": getattr(item, "is_live", None),
                                "trader_login": getattr(item, "trader_login", None),
                            }
                        )
                self.logRequested.emit(f"✅ Accounts received: {raw_items}")
            except Exception as exc:
                self.logRequested.emit(f"⚠️ Failed to format accounts: {exc}")
        if not self._account_combo:
            return

        preferred_id = None
        if self._app_state and self._app_state.selected_account_id:
            preferred_id = int(self._app_state.selected_account_id)
        else:
            tokens = self._load_tokens_for_accounts()
            if tokens and tokens.account_id:
                try:
                    preferred_id = int(tokens.account_id)
                except Exception:
                    preferred_id = None

        self._account_combo.blockSignals(True)
        self._account_combo.clear()
        self._account_combo.addItem("Select account", None)

        def account_label(account: object) -> str:
            account_id = getattr(account, "account_id", None)
            is_live = getattr(account, "is_live", None)
            trader_login = getattr(account, "trader_login", None)
            if isinstance(account, dict):
                account_id = account.get("account_id")
                is_live = account.get("is_live")
                trader_login = account.get("trader_login")
            kind = "Live" if is_live is True else ("Demo" if is_live is False else "Account")
            label = f"{kind} {account_id}"
            if trader_login:
                label += f" · {trader_login}"
            return label

        selected_index = 0
        for idx, account in enumerate(self._accounts, start=1):
            account_id = getattr(account, "account_id", None)
            if isinstance(account, dict):
                account_id = account.get("account_id")
            if not account_id:
                continue
            self._account_combo.addItem(account_label(account), int(account_id))
            if preferred_id is not None and int(account_id) == int(preferred_id):
                selected_index = idx

        self._account_combo.setCurrentIndex(selected_index)
        self._account_combo.blockSignals(False)

        selected_id = self._account_combo.currentData()
        if selected_id is not None:
            self._apply_selected_account(
                int(selected_id),
                save_token=False,
                log=False,
                user_initiated=False,
            )

    def _handle_accounts_error(self, error: str) -> None:
        self.logRequested.emit(f"❌ Account list error: {error}")

    def _handle_account_combo_changed(self, index: int) -> None:
        if not self._account_combo:
            return
        account_id = self._account_combo.itemData(index)
        if account_id is None:
            return
        if int(account_id) in self._unauthorized_accounts:
            self.logRequested.emit(f"⚠️ Account {account_id} is not authorized for Open API.")
            if self._last_authorized_account_id:
                self._sync_account_combo(int(self._last_authorized_account_id))
            return
        self._apply_selected_account(int(account_id), save_token=True, log=True, user_initiated=True)

    def _apply_selected_account(
        self,
        account_id: int,
        *,
        save_token: bool,
        log: bool,
        user_initiated: bool,
    ) -> None:
        if not self._app_state:
            return
        current = self._app_state.selected_account_id
        if current is not None and int(current) == int(account_id):
            return
        self._app_state.update_selected_account(int(account_id))
        if save_token:
            tokens = self._load_tokens_for_accounts()
            if tokens:
                tokens.account_id = int(account_id)
                try:
                    tokens.save(TOKEN_FILE)
                except Exception as exc:
                    self.logRequested.emit(f"⚠️ 無法寫入 token 檔案: {exc}")
        if log:
            self.logRequested.emit(f"✅ 已選擇帳戶: {account_id}")
        if user_initiated:
            self._account_switch_in_progress = True
            self.logRequested.emit("🔁 帳戶已切換，正在重新連線以完成授權")
            self._schedule_full_reconnect()

    def _sync_account_combo(self, account_id: Optional[int]) -> None:
        if not self._account_combo or account_id is None:
            return
        idx = self._account_combo.findData(int(account_id))
        if idx >= 0 and idx != self._account_combo.currentIndex():
            self._account_combo.blockSignals(True)
            self._account_combo.setCurrentIndex(idx)
            self._account_combo.blockSignals(False)

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
            if not self._connection_controller:
                return
            self.logRequested.emit("🔁 Reconnecting to apply account switch")
            self._connection_controller.toggle_connection()
            QTimer.singleShot(900, lambda: self._connection_controller.toggle_connection())

        QTimer.singleShot(500, _do_reconnect)

    def _handle_app_state_changed(self, state: AppState) -> None:
        oauth_status = int(getattr(self._oauth_service, "status", 0) or 0)
        if oauth_status < ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._account_switch_in_progress = True
            self.logRequested.emit("⏳ AppState change ignored: OAuth not authenticated yet")
            return
        if state.selected_account_id and self._oauth_service:
            last_auth_id = getattr(self._oauth_service, "last_authenticated_account_id", None)
            if last_auth_id is not None and int(last_auth_id) != int(state.selected_account_id):
                self._account_switch_in_progress = True
                self.logRequested.emit("⏳ Account changed; reconnecting to reauthorize")
                self._schedule_full_reconnect()
                return
        self._account_switch_in_progress = False
        self._sync_account_combo(state.selected_account_id)
        if state.selected_account_id:
            self._request_recent_history()
            self._ensure_quote_subscription()
            self._request_positions()
            self._refresh_account_balance()
            if not self._funds_timer.isActive():
                self._funds_timer.start()

    def _request_recent_history(self) -> None:
        if self._account_switch_in_progress:
            return
        if self._history_requested:
            return
        if not self._service:
            self.logRequested.emit("⚠️ App auth service unavailable. Cannot fetch candles.")
            return
        account_id = None if not self._app_state else self._app_state.selected_account_id
        if not account_id:
            self._pending_history = True
            self.logRequested.emit("⏳ Waiting for account selection to fetch candle history")
            return
        self.logRequested.emit(f"➡️ Request history (account_id={account_id}, symbol_id={self._symbol_id})")
        self._pending_history = False
        now = time.time()
        symbol_id = int(self._symbol_id)
        key = (int(account_id), symbol_id, self._timeframe, 50)
        if self._last_history_request_key == key and now - self._last_history_request_ts < 10.0:
            return
        if self._last_history_success_key == key and now - self._last_history_success_ts < 60.0:
            return

        if self._history_service is None:
            self._history_service = self._use_cases.create_trendbar_history(self._service)

        def handle_history(rows: list[dict]) -> None:
            self.historyReceived.emit(rows)

        self._history_service.clear_log_history()
        def handle_error(error: str) -> None:
            self._history_requested = False
            self.logRequested.emit(f"❌ History error: {error}")

        self._history_service.set_callbacks(
            on_history_received=handle_history,
            on_error=handle_error,
            on_log=self.logRequested.emit,
        )

        from utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        self._history_requested = True
        self._last_history_request_key = key
        self._last_history_request_ts = now
        reactor.callFromThread(
            self._history_service.fetch,
            account_id=account_id,
            symbol_id=symbol_id,
            count=50,
            timeframe=self._timeframe,
        )

    def _handle_history_received(self, rows: list[dict]) -> None:
        if not rows:
            self.logRequested.emit("⚠️ No candle data received")
            self._history_requested = False
            return
        digits = self._price_digits
        rows_sorted = sorted(rows, key=lambda r: r.get("utc_timestamp_minutes", 0))
        candles: list[tuple[float, float, float, float, float]] = []
        for row in rows_sorted:
            ts_minutes = float(row.get("utc_timestamp_minutes", 0))
            ts = ts_minutes * 60
            open_price = self._normalize_price(row.get("open", 0))
            high_price = self._normalize_price(row.get("high", 0))
            low_price = self._normalize_price(row.get("low", 0))
            close_price = self._normalize_price(row.get("close", 0))
            if None in (open_price, high_price, low_price, close_price):
                continue
            open_price = round(float(open_price), digits)
            high_price = round(float(high_price), digits)
            low_price = round(float(low_price), digits)
            close_price = round(float(close_price), digits)
            candles.append(
                (
                    ts,
                    float(open_price),
                    float(high_price),
                    float(low_price),
                    float(close_price),
                )
            )
        self._candles = candles
        self._chart_frozen = False
        self.set_candles(self._candles)
        self._flush_chart_update()
        self.logRequested.emit(f"✅ Loaded {len(candles)} candles")
        self._history_requested = False
        if self._app_state and self._app_state.selected_account_id:
            key = (
                int(self._app_state.selected_account_id),
                int(self._symbol_id),
                self._timeframe,
                50,
            )
            self._last_history_success_key = key
            self._last_history_success_ts = time.time()
        self._start_live_trendbar()

    def _start_live_trendbar(self) -> None:
        if self._trendbar_active:
            return
        if not self._service:
            return
        account_id = None if not self._app_state else self._app_state.selected_account_id
        if not account_id:
            return
        if self._trendbar_service is None:
            self._trendbar_service = self._use_cases.create_trendbar(self._service)

        def handle_trendbar(data: dict) -> None:
            self.trendbarReceived.emit(data)

        self._trendbar_service.clear_log_history()
        self._trendbar_service.set_callbacks(
            on_trendbar=handle_trendbar,
            on_error=lambda e: self._handle_trendbar_error(e),
            on_log=self.logRequested.emit,
        )

        from utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        self._trendbar_active = True
        reactor.callFromThread(
            self._trendbar_service.subscribe,
            account_id=account_id,
            symbol_id=self._symbol_id,
            timeframe=self._timeframe,
        )

    def _stop_live_trendbar(self) -> None:
        if not self._trendbar_service or not self._trendbar_active:
            return
        from utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        reactor.callFromThread(self._trendbar_service.unsubscribe)
        self._trendbar_active = False

    def _handle_trendbar_received(self, data: dict) -> None:
        if not data:
            return
        if not getattr(self, "_logged_first_trendbar", False):
            self._logged_first_trendbar = True
        symbol_id = data.get("symbol_id")
        if symbol_id is not None:
            digits = self._quote_row_digits.get(int(symbol_id), self._price_digits)
        else:
            digits = self._price_digits
        ts_minutes = float(data.get("utc_timestamp_minutes", 0))
        ts = ts_minutes * 60
        open_price = self._normalize_price(data.get("open", 0))
        high_price = self._normalize_price(data.get("high", 0))
        low_price = self._normalize_price(data.get("low", 0))
        close_price = self._normalize_price(data.get("close", 0))
        if None in (open_price, high_price, low_price, close_price):
            return
        open_price = round(float(open_price), digits)
        high_price = round(float(high_price), digits)
        low_price = round(float(low_price), digits)
        close_price = round(float(close_price), digits)
        candle = (
            ts,
            float(open_price),
            float(high_price),
            float(low_price),
            float(close_price),
        )
        appended = False
        if not self._candles:
            self._candles = [candle]
            appended = True
        elif self._candles[-1][0] == candle[0]:
            self._candles[-1] = candle
        elif self._candles[-1][0] < candle[0]:
            self._fill_missing_candles(candle)
            self._candles.append(candle)
            appended = True
        else:
            return
        if len(self._candles) > 50:
            self._candles = self._candles[-50:]
        self.set_candles(self._candles)
        if appended:
            self._run_auto_trade_on_close()

    def _update_chart_from_quote(self, symbol_id: int, bid, ask, spot_ts) -> None:
        if self._chart_frozen:
            return
        if int(symbol_id) != int(self._symbol_id):
            return
        bid_val = self._normalize_price(bid)
        ask_val = self._normalize_price(ask)
        price = None
        if bid_val and ask_val:
            price = (bid_val + ask_val) / 2.0
        elif bid_val:
            price = bid_val
        elif ask_val:
            price = ask_val
        if price is None:
            return
        ts_val = spot_ts
        if ts_val is None or ts_val == 0:
            ts_seconds = int(time.time())
        else:
            try:
                ts_seconds = int(float(ts_val))
            except (TypeError, ValueError):
                ts_seconds = int(time.time())
            if ts_seconds > 10**12:
                ts_seconds = ts_seconds // 1000
        step_seconds = self._timeframe_minutes() * 60
        if step_seconds <= 0:
            step_seconds = 60
        bucket = (ts_seconds // step_seconds) * step_seconds
        digits = self._quote_row_digits.get(int(symbol_id), self._price_digits)
        price = round(float(price), digits)
        candle = (bucket, price, price, price, price)
        if not self._candles:
            self._candles = [candle]
            self.set_candles(self._candles)
            self._flush_chart_update()
            return
        last_time = self._candles[-1][0]
        if bucket == last_time:
            open_price, high_price, low_price, _ = self._candles[-1][1:5]
            high_price = max(high_price, price)
            low_price = min(low_price, price)
            self._candles[-1] = (bucket, open_price, high_price, low_price, price)
        elif bucket > last_time:
            self._fill_missing_candles(candle)
            self._candles.append(candle)
            if len(self._candles) > 50:
                self._candles = self._candles[-50:]
        else:
            return
        self.set_candles(self._candles)
        self._flush_chart_update()

    def _handle_trendbar_error(self, error: str) -> None:
        self._trendbar_active = False
        self.logRequested.emit(f"❌ Live candle error: {error}")

    def _fill_missing_candles(self, next_candle: tuple[float, float, float, float, float]) -> None:
        if not self._candles:
            return
        step_seconds = self._timeframe_minutes() * 60
        last_time = self._candles[-1][0]
        next_time = next_candle[0]
        if step_seconds <= 0 or next_time <= last_time + step_seconds:
            return
        fill_price = self._candles[-1][4]
        t = last_time + step_seconds
        while t < next_time:
            self._candles.append((t, fill_price, fill_price, fill_price, fill_price))
            t += step_seconds

    def _timeframe_minutes(self) -> int:
        mapping = {
            "M1": 1,
            "M2": 2,
            "M3": 3,
            "M4": 4,
            "M5": 5,
            "M10": 10,
            "M15": 15,
            "M30": 30,
            "H1": 60,
            "H4": 240,
            "H12": 720,
            "D1": 1440,
            "W1": 10080,
            "MN1": 43200,
        }
        return mapping.get(self._timeframe, 1)

    def _resolve_symbol_id(self, symbol_name: str) -> int:
        if symbol_name in self._symbol_id_map:
            return self._symbol_id_map[symbol_name]
        path = self._symbol_list_path()
        if not path.exists():
            return 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return 1
        for item in data:
            if item.get("symbol_name") == symbol_name:
                try:
                    return int(item.get("symbol_id", 1))
                except (TypeError, ValueError):
                    return 1
        return 1

    def _handle_trade_symbol_changed(self, symbol: str) -> None:
        if not symbol:
            return
        if self._account_switch_in_progress:
            return
        self._sync_quote_symbols(symbol)
        if symbol != self._symbol_name:
            self._symbol_name = symbol
            self._symbol_id = self._resolve_symbol_id(symbol)
        self._history_requested = False
        self._pending_history = False
        self._last_history_request_key = None
        self._last_history_success_key = None
        if self._oauth_service and getattr(self._oauth_service, "status", 0) >= ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._request_recent_history()

    def _fetch_symbol_details(self, symbol_name: str) -> None:
        if self._account_switch_in_progress:
            return
        if not self._service or not self._app_state or not self._app_state.selected_account_id:
            return
        symbol_id = int(self._resolve_symbol_id(symbol_name))
        if symbol_id <= 0:
            return
        if symbol_id in self._symbol_details_by_id:
            return
        if symbol_id in self._symbol_details_unavailable:
            return
        if self._symbol_by_id_uc is None:
            try:
                self._symbol_by_id_uc = self._use_cases.create_symbol_by_id(self._service)
            except Exception:
                return
        if getattr(self._symbol_by_id_uc, "in_progress", False):
            return

        account_id = int(self._app_state.selected_account_id)
        self.logRequested.emit(f"➡️ Request symbol details (account_id={account_id}, symbol_id={symbol_id})")

        def _on_symbols(symbols: list) -> None:
            if not symbols:
                return
            merged = self._merge_symbol_details(symbols)
            if not merged:
                self._symbol_details_unavailable.add(symbol_id)

        self._symbol_by_id_uc.set_callbacks(
            on_symbols_received=_on_symbols,
            on_error=lambda e: self._auto_log(f"❌ Symbol detail error: {e}"),
            on_log=self._auto_log,
        )
        self._symbol_by_id_uc.fetch(
            account_id=account_id,
            symbol_ids=[symbol_id],
            include_archived=False,
        )

    def _merge_symbol_details(self, symbols: list[dict]) -> bool:
        path = self._symbol_list_path()
        existing: list[dict] = []
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        by_id: dict[int, dict] = {}
        by_name: dict[str, dict] = {}
        for item in existing:
            if not isinstance(item, dict):
                continue
            sid = item.get("symbol_id")
            name = item.get("symbol_name")
            if isinstance(sid, int):
                by_id[sid] = item
            if isinstance(name, str) and name:
                by_name[name] = item

        updated = False
        merged_any = False
        for detail in symbols:
            if not isinstance(detail, dict):
                continue
            extra_keys = set(detail.keys()) - {"symbol_id", "symbol_name"}
            if not extra_keys:
                continue
            sid = detail.get("symbol_id")
            name = detail.get("symbol_name")
            if not isinstance(name, str) or not name.strip():
                if isinstance(sid, int):
                    self._symbol_details_by_id[sid] = detail
                continue
            target = None
            if isinstance(sid, int):
                target = by_id.get(sid)
            if target is None and isinstance(name, str) and name:
                target = by_name.get(name)
            if target is None:
                if not existing:
                    if isinstance(sid, int):
                        self._symbol_details_by_id[sid] = detail
                    continue
                target = {"symbol_id": sid, "symbol_name": name}
                existing.append(target)
                if isinstance(sid, int):
                    by_id[sid] = target
                by_name[name] = target
            for key, value in detail.items():
                if value is None:
                    continue
                if target.get(key) != value:
                    target[key] = value
                    updated = True
            merged_any = True
            if isinstance(sid, int):
                self._symbol_details_by_id[sid] = detail
            if isinstance(name, str) and name:
                min_volume = detail.get("min_volume")
                volume_step = detail.get("volume_step")
                try:
                    min_volume_int = int(min_volume) if min_volume is not None else None
                except (TypeError, ValueError):
                    min_volume_int = None
                try:
                    volume_step_int = int(volume_step) if volume_step is not None else None
                except (TypeError, ValueError):
                    volume_step_int = None
                if min_volume_int is not None or volume_step_int is not None:
                    if min_volume_int is None:
                        min_volume_int = max(1, volume_step_int or 1)
                    if volume_step_int is None:
                        volume_step_int = min_volume_int
                    if min_volume_int > 0 and volume_step_int > 0:
                        self._symbol_volume_constraints[name] = (min_volume_int, volume_step_int)
                        self._symbol_volume_loaded = True
                digits = detail.get("digits")
                if isinstance(digits, int) and digits > 0:
                    self._symbol_digits_by_name[name] = digits
                    self._quote_digits[name] = digits
                    current_symbol = self._trade_symbol.currentText() if hasattr(self, "_trade_symbol") else ""
                    if not current_symbol:
                        current_symbol = self._symbol_name
                    if name == current_symbol:
                        self._price_digits = digits
                    if isinstance(sid, int):
                        self._quote_row_digits[sid] = digits

        if updated:
            try:
                path.write_text(json.dumps(existing, ensure_ascii=True, indent=2), encoding="utf-8")
            except Exception:
                pass
        return merged_any

    def _load_symbol_catalog(self) -> tuple[list[str], dict[str, int]]:
        path = self._symbol_list_path()
        if not path.exists():
            return [], {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return [], {}
        names: list[str] = []
        mapping: dict[str, int] = {}
        for item in data:
            name = item.get("symbol_name")
            if not isinstance(name, str) or not name:
                continue
            if name in mapping:
                continue
            try:
                symbol_id = int(item.get("symbol_id", 1))
            except (TypeError, ValueError):
                symbol_id = 1
            mapping[name] = symbol_id
            names.append(name)
        return names, mapping

    def _filter_fx_symbols(self, names: list[str]) -> list[str]:
        return [name for name in names if len(name) == 6 and name.isalpha() and name.isupper()]

    def _default_quote_symbols(self) -> list[str]:
        defaults = [name for name in ("EURUSD", "USDJPY") if name in self._symbol_id_map]
        if defaults:
            return defaults[: self._max_quote_rows]
        if self._fx_symbols:
            return self._fx_symbols[: self._max_quote_rows]
        return ["EURUSD", "USDJPY"][: self._max_quote_rows]

    def _infer_quote_digits(self, symbol: str) -> int:
        if symbol.endswith("JPY"):
            return 3
        return 5

    def _sync_quote_symbols(self, symbol: str) -> None:
        next_symbols = [symbol] + [item for item in self._quote_symbols if item != symbol]
        self._set_quote_symbols(next_symbols[: self._max_quote_rows])

    def _set_quote_symbols(self, symbols: list[str]) -> None:
        unique: list[str] = []
        for symbol in symbols:
            if symbol and symbol not in unique:
                unique.append(symbol)
        if not unique:
            return
        if unique == self._quote_symbols:
            return
        was_subscribed = self._quote_subscribed
        if was_subscribed:
            self._stop_quote_subscription()
        self._quote_symbols = unique
        self._quote_symbol_ids = {name: self._resolve_symbol_id(name) for name in self._quote_symbols}
        self._quote_rows.clear()
        self._quote_row_digits.clear()
        self._quote_last_mid.clear()
        self._quote_subscribed_ids.clear()
        if self._quotes_table:
            self._rebuild_quotes_table()
        if was_subscribed:
            self._ensure_quote_subscription()

    def _rebuild_quotes_table(self) -> None:
        if not self._quotes_table:
            return
        table = self._quotes_table
        rows = max(1, len(self._quote_symbols))
        table.setRowCount(rows)
        for row in range(rows):
            for col in range(5):
                item = table.item(row, col)
                if item is None:
                    item = QTableWidgetItem("-")
                    item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row, col, item)

        for row, symbol in enumerate(self._quote_symbols):
            symbol_item = table.item(row, 0)
            if symbol_item is None:
                symbol_item = QTableWidgetItem(symbol)
                symbol_item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, 0, symbol_item)
            else:
                symbol_item.setText(symbol)
            for col in (1, 2, 3, 4):
                cell = table.item(row, col)
                if cell is None:
                    cell = QTableWidgetItem("-")
                    cell.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row, col, cell)
                else:
                    cell.setText("-")
            symbol_id = self._quote_symbol_ids.get(symbol)
            if symbol_id is not None:
                self._quote_rows[symbol_id] = row
                self._quote_row_digits[symbol_id] = self._quote_digits.get(
                    symbol, self._infer_quote_digits(symbol)
                )


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
                painter.end()
                return
            width = self._infer_half_width()
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
            if self._picture.isNull():
                return QtCore.QRectF(0, 0, 1, 1)
            return QtCore.QRectF(self._picture.boundingRect())
