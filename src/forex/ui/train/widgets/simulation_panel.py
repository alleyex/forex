from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - optional dependency
    pg = None

from PySide6.QtCore import Qt, Signal, QElapsedTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QFileDialog,
    QSizePolicy,
    QGroupBox,
    QSplitter,
    QTabWidget,
    QFrame,
)

from forex.ui.shared.widgets.log_widget import LogWidget
from forex.ui.shared.widgets.layout_helpers import (
    apply_form_label_width,
    align_form_fields,
    build_browse_row,
    configure_form_layout,
)
from forex.ui.shared.utils.path_utils import latest_file_in_dir
from forex.ui.shared.utils.formatters import (
    format_action_distribution,
    format_holding_stats,
    format_playback_range,
    format_streak_stats,
    format_trade_stats,
)
from forex.ui.shared.styles.tokens import (
    FORM_LABEL_WIDTH_COMPACT,
    PRIMARY,
    SIMULATION_PARAMS,
    STAT_LABEL,
    STAT_VALUE,
)
from forex.config.paths import DEFAULT_MODEL_PATH, MODEL_DIR, RAW_HISTORY_DIR
from forex.ui.train.services import UIParamsStore


def _apply_card_tabs_style(tabs: QTabWidget) -> None:
    tabs.setStyleSheet(
        """
        QTabWidget::pane {
            border: none;
            top: 0px;
        }
        QTabWidget::tab-bar {
            left: 0px;
        }
        QTabBar::base {
            border: none;
            background: transparent;
        }
        QTabBar::tab {
            margin: 0px;
            background: #2a323c;
            color: #b8c1cc;
            padding: 6px 14px;
            border: 1px solid #343c46;
            border-bottom: none;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            min-width: 72px;
        }
        QTabBar::tab:selected {
            background: #1f252d;
            color: #f5f7fb;
            font-weight: 600;
        }
        QTabBar::tab:!selected {
            margin-top: 0px;
        }
        QWidget#modelTab QGroupBox#card,
        QWidget#tradeTab QGroupBox#card,
        QWidget#advancedTab QGroupBox#card {
            background: #262d36;
            border: 1px solid #343c46;
            border-radius: 10px;
            margin-top: 6px;
        }
        QWidget#modelTab QGroupBox#card::title,
        QWidget#tradeTab QGroupBox#card::title,
        QWidget#advancedTab QGroupBox#card::title {
            color: #cdd6e1;
            font-weight: 500;
            letter-spacing: 0.2px;
            padding: 0px 8px;
            background: #262d36;
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
        }
        QWidget#modelTab QGroupBox#card[titleTone="line"]::title,
        QWidget#tradeTab QGroupBox#card[titleTone="line"]::title,
        QWidget#advancedTab QGroupBox#card[titleTone="line"]::title {
            color: #3a4452;
            font-weight: 300;
            font-size: 10px;
            background: #262d36;
            subcontrol-origin: margin;
            subcontrol-position: top right;
            left: -20px;
        }
        """
    )


class SimulationParamsPanel(QWidget):
    start_requested = Signal(dict)
    stop_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._loading_params = False
        self._params_store = UIParamsStore("simulation")
        self._setup_ui()
        self._bind_persistence()
        self._load_params()

    def _setup_ui(self) -> None:
        self.setProperty("class", SIMULATION_PARAMS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        file_group = QGroupBox("Files")
        file_group.setObjectName("card")
        file_group.setProperty("titleTone", "line")
        file_layout = QFormLayout(file_group)
        configure_form_layout(
            file_layout,
            label_alignment=Qt.AlignLeft | Qt.AlignVCenter,
            field_growth_policy=QFormLayout.FieldsStayAtSizeHint,
        )
        apply_form_label_width(file_layout, FORM_LABEL_WIDTH_COMPACT)
        align_form_fields(file_layout, Qt.AlignLeft | Qt.AlignVCenter)

        field_width = 240
        spin_width = 140

        default_data = latest_file_in_dir(
            RAW_HISTORY_DIR,
            (".csv",),
            "data/raw_history/history.csv",
        )
        self._data_path = QLineEdit(default_data)
        self._data_path.setFixedWidth(field_width)
        self._data_path.setToolTip(default_data)
        data_row = build_browse_row(self._data_path, self._browse_data)
        data_row.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        file_layout.addRow("Data File", data_row)

        default_model = latest_file_in_dir(
            MODEL_DIR,
            (".zip",),
            DEFAULT_MODEL_PATH,
        )
        self._model_path = QLineEdit(default_model)
        self._model_path.setFixedWidth(field_width)
        self._model_path.setToolTip(default_model)
        model_row = build_browse_row(self._model_path, self._browse_model)
        model_row.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        file_layout.addRow("Model File", model_row)

        params_group = QGroupBox("Simulation Params")
        params_group.setObjectName("card")
        params_group.setProperty("titleTone", "line")
        params_layout = QFormLayout(params_group)
        configure_form_layout(
            params_layout,
            label_alignment=Qt.AlignLeft | Qt.AlignVCenter,
            field_growth_policy=QFormLayout.FieldsStayAtSizeHint,
        )
        apply_form_label_width(params_layout, FORM_LABEL_WIDTH_COMPACT)
        align_form_fields(params_layout, Qt.AlignLeft | Qt.AlignVCenter)

        self._log_every = QSpinBox()
        self._log_every.setRange(1, 100_000)
        self._log_every.setValue(1000)
        self._log_every.setFixedWidth(spin_width)
        params_layout.addRow("Log Every", self._log_every)

        self._max_steps = QSpinBox()
        self._max_steps.setRange(0, 10_000_000)
        self._max_steps.setValue(0)
        self._max_steps.setFixedWidth(spin_width)
        params_layout.addRow("Max Steps", self._max_steps)

        self._transaction_cost = QDoubleSpinBox()
        self._transaction_cost.setRange(0.0, 100.0)
        self._transaction_cost.setDecimals(3)
        self._transaction_cost.setValue(1.0)
        self._transaction_cost.setFixedWidth(spin_width)
        params_layout.addRow("Transaction Cost (bps)", self._transaction_cost)

        self._slippage = QDoubleSpinBox()
        self._slippage.setRange(0.0, 100.0)
        self._slippage.setDecimals(3)
        self._slippage.setValue(0.5)
        self._slippage.setFixedWidth(spin_width)
        params_layout.addRow("Slippage (bps)", self._slippage)

        layout.addWidget(file_group)
        layout.addWidget(params_group)

        layout.addStretch(1)

        controls = QGridLayout()
        controls.setHorizontalSpacing(10)
        controls.setContentsMargins(0, 0, 0, 0)

        self._start_button = QPushButton("Start Playback")
        self._start_button.setProperty("class", PRIMARY)
        self._start_button.clicked.connect(self._emit_start)
        controls.addWidget(self._start_button, 0, 0)

        self._stop_button = QPushButton("Stop Playback")
        self._stop_button.clicked.connect(self.stop_requested.emit)
        controls.addWidget(self._stop_button, 0, 1)

        layout.addLayout(controls)

    def _browse_data(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Data File", "", "CSV (*.csv)")
        if path:
            self._data_path.setText(path)
            self._data_path.setToolTip(path)

    def _browse_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Model File", "", "ZIP (*.zip)")
        if path:
            self._model_path.setText(path)
            self._model_path.setToolTip(path)

    def set_model_path(self, path: str) -> None:
        text = str(path or "").strip()
        if not text:
            return
        self._model_path.setText(text)
        self._model_path.setToolTip(text)

    def _emit_start(self) -> None:
        self._apply_path_normalization()
        self._save_params()
        self.start_requested.emit(self.get_params())

    def get_params(self) -> dict:
        return {
            "data": self._data_path.text().strip(),
            "model": self._model_path.text().strip(),
            "log_every": int(self._log_every.value()),
            "max_steps": int(self._max_steps.value()),
            "transaction_cost_bps": float(self._transaction_cost.value()),
            "slippage_bps": float(self._slippage.value()),
        }

    def _bind_persistence(self) -> None:
        self._data_path.textChanged.connect(self._on_data_path_changed)
        self._model_path.textChanged.connect(self._on_model_path_changed)
        self._log_every.valueChanged.connect(lambda _v: self._save_params())
        self._max_steps.valueChanged.connect(lambda _v: self._save_params())
        self._transaction_cost.valueChanged.connect(lambda _v: self._save_params())
        self._slippage.valueChanged.connect(lambda _v: self._save_params())

    def _on_data_path_changed(self, text: str) -> None:
        self._data_path.setToolTip(text)
        self._save_params()

    def _on_model_path_changed(self, text: str) -> None:
        self._model_path.setToolTip(text)
        self._save_params()

    @staticmethod
    def _normalize_path_text(raw: str) -> str:
        text = str(raw).strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
            text = text[1:-1].strip()
        if not text:
            return ""
        return str(Path(text).expanduser().resolve())

    def _apply_path_normalization(self) -> None:
        data_text = self._normalize_path_text(self._data_path.text())
        model_text = self._normalize_path_text(self._model_path.text())
        if data_text and data_text != self._data_path.text():
            self._data_path.setText(data_text)
        if model_text and model_text != self._model_path.text():
            self._model_path.setText(model_text)

    def _save_params(self) -> None:
        if self._loading_params:
            return
        self._params_store.save(self.get_params())

    def _load_params(self) -> None:
        data = self._params_store.load()
        if not isinstance(data, dict):
            return

        self._loading_params = True
        try:
            if "data" in data:
                self._data_path.setText(str(data["data"]))
            if "model" in data:
                self._model_path.setText(str(data["model"]))
            if "log_every" in data:
                self._log_every.setValue(int(data["log_every"]))
            if "max_steps" in data:
                self._max_steps.setValue(int(data["max_steps"]))
            if "transaction_cost_bps" in data:
                self._transaction_cost.setValue(float(data["transaction_cost_bps"]))
            if "slippage_bps" in data:
                self._slippage.setValue(float(data["slippage_bps"]))
        finally:
            self._loading_params = False
        self._apply_path_normalization()


class PlaybackDetailsPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._summary_state = {
            "total_return": None,
            "max_drawdown": None,
            "sharpe": None,
            "trades": None,
            "equity": None,
            "trade_rate_1k": None,
            "quality_gate": None,
        }
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setMovable(False)
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setDrawBase(False)
        _apply_card_tabs_style(tabs)
        self._tabs = tabs

        self._embedded_log = LogWidget(
            title="",
            with_timestamp=True,
            monospace=True,
            font_point_delta=2,
        )

        overview_tab = QWidget()
        overview_tab.setObjectName("modelTab")
        overview_tab_layout = QVBoxLayout(overview_tab)
        overview_tab_layout.setContentsMargins(0, 0, 0, 0)
        overview_tab_layout.setSpacing(10)

        overview_group = QGroupBox("Playback Overview")
        overview_group.setObjectName("card")
        overview_group.setProperty("titleTone", "line")
        summary_layout = QVBoxLayout(overview_group)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(12)

        self._summary_fields = {}
        hero_rows = [
            ("Total Return", "total_return"),
            ("Max Drawdown", "max_drawdown"),
            ("Sharpe Ratio", "sharpe"),
        ]
        summary_rows = [
            ("Trades", "trades"),
            ("Trade Rate/1k", "trade_rate_1k"),
            ("Final Equity", "equity"),
            ("Quality Gate", "quality_gate"),
        ]

        summary_cards = QGridLayout()
        summary_cards.setContentsMargins(0, 0, 0, 0)
        summary_cards.setHorizontalSpacing(18)
        summary_cards.setVerticalSpacing(8)
        summary_cards.setColumnStretch(0, 1)
        summary_cards.setColumnStretch(1, 1)
        summary_cards.setColumnStretch(2, 1)

        def _build_summary_metric(label_text: str, key: str) -> QWidget:
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 6, 12, 6)
            card_layout.setSpacing(4)
            label = QLabel(label_text)
            label.setProperty("class", STAT_LABEL)
            card_layout.addWidget(label)
            value = QLabel("-")
            value.setProperty("class", "result_value")
            value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value.setWordWrap(True)
            card_layout.addWidget(value)
            self._summary_fields[key] = value
            return card

        for idx, (label_text, key) in enumerate(hero_rows):
            summary_cards.addWidget(_build_summary_metric(label_text, key), idx // 3, idx % 3)
        summary_layout.addLayout(summary_cards)

        summary_table = QGridLayout()
        summary_table.setContentsMargins(0, 2, 0, 0)
        summary_table.setHorizontalSpacing(14)
        summary_table.setVerticalSpacing(8)
        summary_table.setColumnStretch(1, 1)
        summary_table.setColumnStretch(3, 1)

        for row, (label_text, key) in enumerate(summary_rows):
            label = QLabel(label_text)
            label.setProperty("class", STAT_LABEL)
            value = QLabel("-")
            value.setProperty("class", STAT_VALUE)
            value.setWordWrap(True)
            self._summary_fields[key] = value
            if row < 2:
                summary_table.addWidget(label, row, 0)
                summary_table.addWidget(value, row, 1)
            else:
                summary_table.addWidget(label, row - 2, 2)
                summary_table.addWidget(value, row - 2, 3)
        summary_layout.addLayout(summary_table)

        behavior_divider = QFrame()
        behavior_divider.setFrameShape(QFrame.HLine)
        behavior_divider.setFrameShadow(QFrame.Plain)
        behavior_divider.setStyleSheet("color: rgba(184, 193, 204, 0.18);")
        summary_layout.addWidget(behavior_divider)

        self._trade_stats = QLabel("-")
        self._trade_stats.setProperty("class", STAT_VALUE)
        self._trade_stats.setWordWrap(True)
        self._trade_stats.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._trade_stats.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._streak_stats = QLabel("-")
        self._streak_stats.setProperty("class", STAT_VALUE)
        self._streak_stats.setWordWrap(True)
        self._streak_stats.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._streak_stats.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._holding_stats = QLabel("-")
        self._holding_stats.setProperty("class", STAT_VALUE)
        self._holding_stats.setWordWrap(True)
        self._holding_stats.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._holding_stats.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._action_dist = QLabel("-")
        self._action_dist.setProperty("class", STAT_VALUE)
        self._action_dist.setWordWrap(True)
        self._action_dist.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._action_dist.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        trade_layout = QGridLayout()
        trade_layout.setContentsMargins(0, 0, 0, 0)
        trade_layout.setHorizontalSpacing(14)
        trade_layout.setVerticalSpacing(10)
        trade_layout.setColumnStretch(1, 1)
        trade_layout.setColumnStretch(3, 1)
        trade_layout.setAlignment(Qt.AlignTop)

        detail_rows = [
            ("Trade Stats", self._trade_stats),
            ("Win/Loss Streak", self._streak_stats),
            ("Holding Duration", self._holding_stats),
            ("Action Distribution", self._action_dist),
        ]
        for idx, (label_text, value) in enumerate(detail_rows):
            row = idx // 2
            col = 0 if idx % 2 == 0 else 2
            label = QLabel(label_text)
            label.setProperty("class", STAT_LABEL)
            label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            trade_layout.addWidget(label, row, col, Qt.AlignTop)
            trade_layout.addWidget(value, row, col + 1, Qt.AlignTop)
        summary_layout.addLayout(trade_layout)
        overview_tab_layout.addWidget(overview_group)
        overview_tab_layout.addStretch(1)
        tabs.addTab(overview_tab, "Overview")

        range_tab = QWidget()
        range_tab.setObjectName("modelTab")
        range_tab_layout = QVBoxLayout(range_tab)
        range_tab_layout.setContentsMargins(0, 0, 0, 0)
        range_tab_layout.setSpacing(0)

        playback_group = QGroupBox("Playback Range")
        playback_group.setObjectName("card")
        playback_group.setProperty("titleTone", "line")
        playback_layout = QGridLayout(playback_group)
        playback_layout.setColumnStretch(0, 0)
        playback_layout.setColumnStretch(1, 1)
        playback_layout.setHorizontalSpacing(10)
        playback_layout.setVerticalSpacing(6)

        playback_label = QLabel("Time Range")
        playback_label.setProperty("class", STAT_LABEL)
        self._playback_range = QLabel("-")
        self._playback_range.setProperty("class", STAT_VALUE)
        self._playback_range.setWordWrap(True)
        playback_layout.addWidget(playback_label, 0, 0)
        playback_layout.addWidget(self._playback_range, 0, 1)

        range_tab_layout.addWidget(playback_group)
        tabs.addTab(range_tab, "Playback Range")
        log_tab = QWidget()
        log_tab.setObjectName("modelTab")
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)
        log_layout.addWidget(self._embedded_log)
        tabs.addTab(log_tab, "Log")

        details_panel = QGroupBox("")
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(10, 10, 10, 10)
        details_layout.setSpacing(0)
        details_layout.addWidget(tabs)

        layout.addWidget(details_panel)

    def append(self, message: str) -> None:
        self._embedded_log.append(message)

    def clear_logs(self) -> None:
        self._embedded_log.clear_logs()

    def reset_summary(self) -> None:
        self._summary_state = {
            "total_return": None,
            "max_drawdown": None,
            "sharpe": None,
            "trades": None,
            "equity": None,
            "trade_rate_1k": None,
            "quality_gate": None,
        }
        for key in self._summary_fields:
            self._summary_fields[key].setText("-")
        self._trade_stats.setText("-")
        self._streak_stats.setText("-")
        self._holding_stats.setText("-")
        self._action_dist.setText("-")
        self._playback_range.setText("-")

    def update_summary(
        self,
        total_return: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        sharpe: Optional[float] = None,
        trades: Optional[int] = None,
        equity: Optional[float] = None,
        trade_rate_1k: Optional[float] = None,
        quality_gate: Optional[str] = None,
    ) -> None:
        if total_return is not None:
            self._summary_state["total_return"] = total_return
        if max_drawdown is not None:
            self._summary_state["max_drawdown"] = max_drawdown
        if sharpe is not None:
            self._summary_state["sharpe"] = sharpe
        if trades is not None:
            self._summary_state["trades"] = trades
        if equity is not None:
            self._summary_state["equity"] = equity
        if trade_rate_1k is not None:
            self._summary_state["trade_rate_1k"] = trade_rate_1k
        if quality_gate is not None:
            self._summary_state["quality_gate"] = quality_gate

        total_return = self._summary_state["total_return"]
        max_drawdown = self._summary_state["max_drawdown"]
        sharpe = self._summary_state["sharpe"]
        trades = self._summary_state["trades"]
        equity = self._summary_state["equity"]
        trade_rate_1k = self._summary_state["trade_rate_1k"]
        quality_gate = self._summary_state["quality_gate"]

        self._summary_fields["total_return"].setText(
            "-" if total_return is None else f"{total_return:.6f}"
        )
        self._summary_fields["max_drawdown"].setText(
            "-" if max_drawdown is None else f"{max_drawdown:.6f}"
        )
        self._summary_fields["sharpe"].setText("-" if sharpe is None else f"{sharpe:.6f}")
        self._summary_fields["trades"].setText("-" if trades is None else str(trades))
        self._summary_fields["trade_rate_1k"].setText(
            "-" if trade_rate_1k is None else f"{trade_rate_1k:.2f}"
        )
        self._summary_fields["equity"].setText("-" if equity is None else f"{equity:.6f}")
        self._summary_fields["quality_gate"].setText(
            "-" if quality_gate is None else str(quality_gate)
        )

    def update_trade_stats(self, text: str) -> None:
        self._trade_stats.setText(format_trade_stats(text))

    def update_streak_stats(self, text: str) -> None:
        self._streak_stats.setText(format_streak_stats(text))

    def update_holding_stats(self, text: str) -> None:
        self._holding_stats.setText(format_holding_stats(text))

    def update_action_distribution(self, text: str) -> None:
        self._action_dist.setText(format_action_distribution(text))

    def update_playback_range(self, text: str) -> None:
        self._playback_range.setText(format_playback_range(text))


class SimulationPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._charts_available = pg is not None
        self._steps: list[int] = []
        self._equity: list[float] = []
        self._plot_timer = QElapsedTimer()
        self._plot_interval_ms = 400
        self._max_points = 2000
        self._last_point: Optional[tuple[int, float]] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        details_panel = PlaybackDetailsPanel()
        self._details_panel = details_panel

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        if self._charts_available:
            plot = pg.PlotWidget()
            plot.setTitle("Playback Equity Curve")
            plot.setLabel("bottom", "timesteps")
            plot.setLabel("left", "equity")
            plot.showGrid(x=True, y=True, alpha=0.3)
            self._plot = plot
            self._curve = plot.plot(pen=pg.mkPen("#F58518", width=2), name="equity")
            splitter.addWidget(plot)
        else:
            notice = QLabel("PyQtGraph is not installed. Install pyqtgraph to show charts.")
            notice.setWordWrap(True)
            splitter.addWidget(notice)

        splitter.addWidget(details_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        self._details_splitter = splitter
        layout.addWidget(splitter, stretch=1)

    def reset_plot(self) -> None:
        self._steps.clear()
        self._equity.clear()
        self._last_point = None
        self._plot_timer.restart()
        if self._charts_available:
            self._curve.setData([], [])

    def append_equity_point(self, step: int, equity: float) -> None:
        self.ingest_equity(step, equity)

    def ingest_equity(self, step: int, equity: float) -> None:
        self._last_point = (step, equity)
        self._steps.append(step)
        self._equity.append(equity)
        if len(self._steps) > self._max_points:
            self._steps = self._steps[-self._max_points :]
            self._equity = self._equity[-self._max_points :]
        if not self._charts_available:
            return
        if not self._plot_timer.isValid():
            self._plot_timer.start()
        if self._plot_timer.elapsed() < self._plot_interval_ms:
            return
        self._curve.setData(self._steps, self._equity)
        self._plot_timer.restart()

    def flush_plot(self) -> None:
        if not self._charts_available:
            return
        if self._last_point:
            last_step, last_equity = self._last_point
            if not self._steps or self._steps[-1] != last_step:
                self._steps.append(last_step)
                self._equity.append(last_equity)
                if len(self._steps) > self._max_points:
                    self._steps = self._steps[-self._max_points :]
                    self._equity = self._equity[-self._max_points :]
        self._curve.setData(self._steps, self._equity)

    def append_log(self, message: str) -> None:
        self._details_panel.append(message)

    def reset_summary(self) -> None:
        self._details_panel.reset_summary()

    def update_summary(self, **data) -> None:
        self._details_panel.update_summary(**data)

    def update_trade_stats(self, text: str) -> None:
        self._details_panel.update_trade_stats(text)

    def update_streak_stats(self, text: str) -> None:
        self._details_panel.update_streak_stats(text)

    def update_holding_stats(self, text: str) -> None:
        self._details_panel.update_holding_stats(text)

    def update_action_distribution(self, text: str) -> None:
        self._details_panel.update_action_distribution(text)

    def update_playback_range(self, text: str) -> None:
        self._details_panel.update_playback_range(text)
