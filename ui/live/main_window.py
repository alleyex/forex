from __future__ import annotations

from typing import Optional
from datetime import datetime
import json
from pathlib import Path

from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QMainWindow,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

try:
    import pyqtgraph as pg
    from pyqtgraph.Qt import QtCore, QtGui
except Exception:  # pragma: no cover - optional dependency
    pg = None
    QtCore = None
    QtGui = None

from application import AppAuthServiceLike, AppState, BrokerUseCases, EventBus, OAuthServiceLike
from config.constants import ConnectionStatus
from config.paths import SYMBOL_LIST_FILE
from infrastructure.broker.ctrader.services.spot_subscription import (
    send_spot_subscribe,
    send_spot_unsubscribe,
)
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
    historyReceived = Signal(list)
    trendbarReceived = Signal(dict)
    quoteUpdated = Signal(int, object, object)

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
        self._trendbar_service = None
        self._trendbar_active = False
        self._candles: list[tuple[float, float, float, float, float]] = []
        self._chart_plot = None
        self._candlestick_item = None
        self._last_price_line = None
        self._last_price_label = None
        self._symbol_name = "EURUSD"
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
        self._quotes_table = None
        self._quote_symbols = ["EURUSD", "USDJPY"]
        self._quote_digits = {
            "EURUSD": 5,
            "USDJPY": 3,
        }
        self._quote_symbol_ids = {name: self._resolve_symbol_id(name) for name in self._quote_symbols}
        self._quote_rows: dict[int, int] = {}
        self._quote_row_digits: dict[int, int] = {}
        self._quote_subscribed = False
        self._spot_message_handler = None

        self._setup_ui()
        self._setup_connection_controller()
        self._connect_signals()

        if self._event_bus:
            self._event_bus.subscribe("log", self._log_panel.append)

        if self._service:
            self.set_service(self._service)
        if self._oauth_service:
            self.set_oauth_service(self._oauth_service)

        if self._app_state:
            self._app_state.subscribe(self._handle_app_state_changed)

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
                on_status_changed=lambda s: self.oauthStatusChanged.emit(int(s)),
            )
        if getattr(self._oauth_service, "status", None) is not None:
            status = ConnectionStatus(self._oauth_service.status)
            self._oauth_label.setText(format_oauth_status(status))
            self._handle_oauth_status(int(status))

    def _setup_ui(self) -> None:
        self.setWindowTitle("外匯交易應用程式 - 實盤")
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

        headline = QLabel("實盤交易")
        headline.setProperty("class", "section_title")
        content_layout.addWidget(headline)

        chart_panel = self._build_chart_panel()
        content_layout.addWidget(chart_panel, 1)

        quotes_panel = self._build_quotes_panel()
        bottom_splitter = QSplitter(Qt.Horizontal)
        bottom_splitter.addWidget(quotes_panel)
        bottom_splitter.addWidget(self._log_panel)
        bottom_splitter.setStretchFactor(0, 1)
        bottom_splitter.setStretchFactor(1, 2)

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

    def _build_quotes_panel(self) -> QWidget:
        panel = QGroupBox("行情表")
        layout = QVBoxLayout(panel)

        table = QTableWidget(2, 3)
        table.setHorizontalHeaderLabels(["Symbol", "Bid", "Ask"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        symbols = list(self._quote_symbols)
        for row, symbol in enumerate(symbols):
            symbol_item = QTableWidgetItem(symbol)
            symbol_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 0, symbol_item)
            symbol_id = self._quote_symbol_ids.get(symbol)
            if symbol_id is not None:
                self._quote_rows[symbol_id] = row
                self._quote_row_digits[symbol_id] = self._quote_digits.get(
                    symbol, self._price_digits
                )
            for col in (1, 2):
                item = QTableWidgetItem("-")
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, col, item)

        layout.addWidget(table)
        self._quotes_table = table
        return panel

    def _ensure_quote_handler(self) -> None:
        if not self._service:
            return
        if self._spot_message_handler is None:
            self._spot_message_handler = self._handle_spot_message
            self._service.add_message_handler(self._spot_message_handler)

    def _ensure_quote_subscription(self) -> None:
        if self._quote_subscribed:
            return
        if not self._service or not self._app_state:
            return
        account_id = self._app_state.selected_account_id
        if not account_id:
            return
        try:
            client = self._service.get_client()  # type: ignore[attr-defined]
        except Exception:
            return
        self._ensure_quote_handler()

        from utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        for symbol_id in self._quote_rows.keys():
            reactor.callFromThread(
                send_spot_subscribe,
                client,
                account_id=account_id,
                symbol_id=symbol_id,
                log=self.logRequested.emit,
                subscribe_to_spot_timestamp=True,
            )
        self._quote_subscribed = True

    def _stop_quote_subscription(self) -> None:
        if not self._quote_subscribed:
            return
        if not self._service or not self._app_state:
            return
        account_id = self._app_state.selected_account_id
        if not account_id:
            self._quote_subscribed = False
            return
        try:
            client = self._service.get_client()  # type: ignore[attr-defined]
        except Exception:
            self._quote_subscribed = False
            return

        from utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        for symbol_id in self._quote_rows.keys():
            reactor.callFromThread(
                send_spot_unsubscribe,
                client,
                account_id=account_id,
                symbol_id=symbol_id,
                log=self.logRequested.emit,
            )
        self._quote_subscribed = False

    def _handle_spot_message(self, _client, msg) -> bool:
        if getattr(msg, "payloadType", None) != ProtoOAPayloadType.PROTO_OA_SPOT_EVENT:
            return False
        symbol_id = getattr(msg, "symbolId", None)
        if symbol_id is None or symbol_id not in self._quote_rows:
            return False
        bid = getattr(msg, "bid", None)
        ask = getattr(msg, "ask", None)
        self.quoteUpdated.emit(int(symbol_id), bid, ask)
        return False

    @Slot(int, object, object)
    def _handle_quote_updated(self, symbol_id: int, bid, ask) -> None:
        if not self._quotes_table:
            return
        row = self._quote_rows.get(symbol_id)
        if row is None:
            return
        self._set_quote_cell(row, 1, bid)
        self._set_quote_cell(row, 2, ask)

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

    def _normalize_price(self, value) -> Optional[float]:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if numeric == 0:
            return 0.0
        if abs(numeric) >= 1000:
            return numeric / (10 ** self._price_digits)
        return numeric

    def _format_price(self, value, *, digits: Optional[int] = None) -> str:
        normalized = self._normalize_price(value)
        if normalized is None:
            return "-"
        use_digits = self._price_digits if digits is None else digits
        return f"{normalized:.{use_digits}f}"

    def _build_chart_panel(self) -> QWidget:
        panel = QGroupBox("即時K線圖")
        layout = QVBoxLayout(panel)

        if pg is None:
            notice = QLabel("PyQtGraph 未安裝，無法顯示K線圖。請安裝 pyqtgraph。")
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
        self._chart_plot.setYRange(min(lows), max(highs), padding=0.1)
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

        self._action_toggle_connection = QAction("連線/斷線", self)
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
        if status >= ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._request_recent_history()
            self._ensure_quote_subscription()
        else:
            self._chart_frozen = True
            self._pending_candles = None
            self._history_requested = False
            self._pending_history = False
            self._stop_live_trendbar()
            self._stop_quote_subscription()

    def _handle_app_state_changed(self, state: AppState) -> None:
        if self._pending_history and state.selected_account_id:
            self._request_recent_history()
        if state.selected_account_id:
            self._ensure_quote_subscription()

    def _request_recent_history(self) -> None:
        if self._history_requested:
            return
        if not self._service:
            self.logRequested.emit("⚠️ 尚未取得 App 認證服務，無法抓取 K 線")
            return
        account_id = None if not self._app_state else self._app_state.selected_account_id
        if not account_id:
            self._pending_history = True
            self.logRequested.emit("⏳ 等待帳戶選擇完成後取得 K 線歷史資料")
            return
        self._pending_history = False

        if self._history_service is None:
            self._history_service = self._use_cases.create_trendbar_history(self._service)

        def handle_history(rows: list[dict]) -> None:
            self.historyReceived.emit(rows)

        self._history_service.clear_log_history()
        def handle_error(error: str) -> None:
            self._history_requested = False
            self.logRequested.emit(f"❌ 歷史資料錯誤: {error}")

        self._history_service.set_callbacks(
            on_history_received=handle_history,
            on_error=handle_error,
            on_log=self.logRequested.emit,
        )

        from utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        self._history_requested = True
        reactor.callFromThread(
            self._history_service.fetch,
            account_id=account_id,
            symbol_id=self._symbol_id,
            count=50,
            timeframe=self._timeframe,
        )

    def _handle_history_received(self, rows: list[dict]) -> None:
        if not rows:
            self.logRequested.emit("⚠️ 未收到 K 線資料")
            return
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
        self.logRequested.emit(f"✅ 已載入 {len(candles)} 筆 K 線資料")
        self._log_recent_history_rows(rows_sorted, count=5)
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
            self._log_first_trendbar(data)
        ts_minutes = float(data.get("utc_timestamp_minutes", 0))
        ts = ts_minutes * 60
        open_price = self._normalize_price(data.get("open", 0))
        high_price = self._normalize_price(data.get("high", 0))
        low_price = self._normalize_price(data.get("low", 0))
        close_price = self._normalize_price(data.get("close", 0))
        if None in (open_price, high_price, low_price, close_price):
            return
        candle = (
            ts,
            float(open_price),
            float(high_price),
            float(low_price),
            float(close_price),
        )
        if not self._candles:
            self._candles = [candle]
        elif self._candles[-1][0] == candle[0]:
            self._candles[-1] = candle
        elif self._candles[-1][0] < candle[0]:
            self._fill_missing_candles(candle)
            self._candles.append(candle)
        else:
            return
        if len(self._candles) > 50:
            self._candles = self._candles[-50:]
        self.set_candles(self._candles)

    def _handle_trendbar_error(self, error: str) -> None:
        self._trendbar_active = False
        self.logRequested.emit(f"❌ 即時 K 線錯誤: {error}")

    def _log_recent_history_rows(self, rows_sorted: list[dict], count: int = 5) -> None:
        tail = rows_sorted[-count:] if rows_sorted else []
        if not tail:
            return
        lines = ["📌 歷史最後數筆："]
        for row in tail:
            ts_minutes = row.get("utc_timestamp_minutes")
            ts_text = row.get("timestamp")
            lines.append(
                f"  - {ts_text} ({ts_minutes}) O:{row.get('open')} "
                f"H:{row.get('high')} L:{row.get('low')} C:{row.get('close')}"
            )
        self.logRequested.emit("\n".join(lines))

    def _log_first_trendbar(self, data: dict) -> None:
        self.logRequested.emit(
            "📌 第一筆即時 trendbar："
            f" {data.get('timestamp')} ({data.get('utc_timestamp_minutes')})"
            f" O:{data.get('open')} H:{data.get('high')}"
            f" L:{data.get('low')} C:{data.get('close')}"
        )

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
        path = Path(SYMBOL_LIST_FILE)
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
                painter.setPen(pg.mkPen("#4b5563", width=2))
                painter.drawLine(QtCore.QPointF(time, low), QtCore.QPointF(time, high))
                if open_price > close:
                    color = "#ef4444"
                    rect = QtCore.QRectF(time - width, close, width * 2, open_price - close)
                else:
                    color = "#10b981"
                    rect = QtCore.QRectF(time - width, open_price, width * 2, close - open_price)
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
