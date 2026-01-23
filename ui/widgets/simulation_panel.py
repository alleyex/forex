from __future__ import annotations

from typing import Optional

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - optional dependency
    pg = None

from PySide6.QtCore import Qt, Signal
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
)

from ui.widgets.form_helpers import (
    apply_form_label_width,
    align_form_fields,
    build_browse_row,
    configure_form_layout,
)
from ui.utils.path_utils import latest_file_in_dir
from ui.utils.formatters import format_kv_lines
from ui.styles.tokens import (
    FORM_LABEL_WIDTH_COMPACT,
    PRIMARY,
    SIMULATION_PARAMS,
    STAT_LABEL,
    STAT_VALUE,
)
from config.paths import RAW_HISTORY_DIR

class SimulationParamsPanel(QWidget):
    start_requested = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._summary_state = {
            "total_return": None,
            "max_drawdown": None,
            "sharpe": None,
            "trades": None,
            "equity": None,
        }
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setProperty("class", SIMULATION_PARAMS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        file_group = QGroupBox("檔案")
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
        file_layout.addRow("資料檔案", data_row)

        default_model = latest_file_in_dir(
            "ml/rl/models",
            (".zip",),
            "ml/rl/models/ppo_forex.zip",
        )
        self._model_path = QLineEdit(default_model)
        self._model_path.setFixedWidth(field_width)
        self._model_path.setToolTip(default_model)
        model_row = build_browse_row(self._model_path, self._browse_model)
        model_row.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        file_layout.addRow("模型檔案", model_row)

        params_group = QGroupBox("模擬參數")
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
        self._log_every.setValue(200)
        self._log_every.setFixedWidth(spin_width)
        params_layout.addRow("輸出間隔", self._log_every)

        self._max_steps = QSpinBox()
        self._max_steps.setRange(0, 10_000_000)
        self._max_steps.setValue(0)
        self._max_steps.setFixedWidth(spin_width)
        params_layout.addRow("最大步數", self._max_steps)

        self._transaction_cost = QDoubleSpinBox()
        self._transaction_cost.setRange(0.0, 100.0)
        self._transaction_cost.setDecimals(3)
        self._transaction_cost.setValue(1.0)
        self._transaction_cost.setFixedWidth(spin_width)
        params_layout.addRow("手續費(bps)", self._transaction_cost)

        self._slippage = QDoubleSpinBox()
        self._slippage.setRange(0.0, 100.0)
        self._slippage.setDecimals(3)
        self._slippage.setValue(0.5)
        self._slippage.setFixedWidth(spin_width)
        params_layout.addRow("滑價(bps)", self._slippage)

        summary_group = QGroupBox("績效摘要")
        summary_layout = QGridLayout(summary_group)
        summary_layout.setColumnStretch(0, 0)
        summary_layout.setColumnStretch(1, 1)
        summary_layout.setHorizontalSpacing(10)
        summary_layout.setVerticalSpacing(6)

        self._summary_fields = {}
        summary_rows = [
            ("總報酬", "total_return"),
            ("最大回撤", "max_drawdown"),
            ("夏普比率", "sharpe"),
            ("交易次數", "trades"),
            ("最終權益", "equity"),
        ]
        for row, (label_text, key) in enumerate(summary_rows):
            label = QLabel(label_text)
            label.setProperty("class", STAT_LABEL)
            value = QLabel("-")
            value.setProperty("class", STAT_VALUE)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            summary_layout.addWidget(label, row, 0)
            summary_layout.addWidget(value, row, 1)
            self._summary_fields[key] = value

        details_group = QGroupBox("交易與持倉")
        details_layout = QGridLayout(details_group)
        details_layout.setColumnStretch(0, 0)
        details_layout.setColumnStretch(1, 1)
        details_layout.setHorizontalSpacing(10)
        details_layout.setVerticalSpacing(6)

        self._trade_stats = QLabel("-")
        self._trade_stats.setProperty("class", STAT_VALUE)
        self._trade_stats.setWordWrap(True)
        self._streak_stats = QLabel("-")
        self._streak_stats.setProperty("class", STAT_VALUE)
        self._streak_stats.setWordWrap(True)
        self._holding_stats = QLabel("-")
        self._holding_stats.setProperty("class", STAT_VALUE)
        self._holding_stats.setWordWrap(True)
        self._action_dist = QLabel("-")
        self._action_dist.setProperty("class", STAT_VALUE)
        self._action_dist.setWordWrap(True)

        detail_rows = [
            ("交易統計", self._trade_stats),
            ("連勝/連敗", self._streak_stats),
            ("持倉時間", self._holding_stats),
            ("行動分布", self._action_dist),
        ]
        for row, (label_text, value) in enumerate(detail_rows):
            label = QLabel(label_text)
            label.setProperty("class", STAT_LABEL)
            details_layout.addWidget(label, row, 0)
            details_layout.addWidget(value, row, 1)

        playback_group = QGroupBox("回放區間")
        playback_layout = QGridLayout(playback_group)
        playback_layout.setColumnStretch(0, 0)
        playback_layout.setColumnStretch(1, 1)
        playback_layout.setHorizontalSpacing(10)
        playback_layout.setVerticalSpacing(6)
        playback_label = QLabel("時間範圍")
        playback_label.setProperty("class", STAT_LABEL)
        self._playback_range = QLabel("-")
        self._playback_range.setProperty("class", STAT_VALUE)
        self._playback_range.setWordWrap(True)
        playback_layout.addWidget(playback_label, 0, 0)
        playback_layout.addWidget(self._playback_range, 0, 1)

        layout.addWidget(file_group)
        layout.addWidget(params_group)
        layout.addWidget(summary_group)
        layout.addWidget(details_group)
        layout.addWidget(playback_group)

        layout.addStretch(1)

        self._start_button = QPushButton("開始回放")
        self._start_button.setProperty("class", PRIMARY)
        self._start_button.clicked.connect(self._emit_start)
        layout.addWidget(self._start_button)

    def _browse_data(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "選擇資料檔", "", "CSV (*.csv)")
        if path:
            self._data_path.setText(path)
            self._data_path.setToolTip(path)

    def _browse_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "選擇模型檔", "", "ZIP (*.zip)")
        if path:
            self._model_path.setText(path)
            self._model_path.setToolTip(path)

    def _emit_start(self) -> None:
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

    def reset_summary(self) -> None:
        self._summary_state = {
            "total_return": None,
            "max_drawdown": None,
            "sharpe": None,
            "trades": None,
            "equity": None,
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

        total_return = self._summary_state["total_return"]
        max_drawdown = self._summary_state["max_drawdown"]
        sharpe = self._summary_state["sharpe"]
        trades = self._summary_state["trades"]
        equity = self._summary_state["equity"]

        self._summary_fields["total_return"].setText(
            "-" if total_return is None else f"{total_return:.6f}"
        )
        self._summary_fields["max_drawdown"].setText(
            "-" if max_drawdown is None else f"{max_drawdown:.6f}"
        )
        self._summary_fields["sharpe"].setText("-" if sharpe is None else f"{sharpe:.6f}")
        self._summary_fields["trades"].setText("-" if trades is None else str(trades))
        self._summary_fields["equity"].setText("-" if equity is None else f"{equity:.6f}")

    def update_trade_stats(self, text: str) -> None:
        label_map = {
            "count": "交易次數",
            "wins": "獲利筆數",
            "win_rate": "勝率",
            "avg_pnl": "平均盈虧",
            "avg_cost": "平均成本",
        }
        self._trade_stats.setText(format_kv_lines(text, label_map))

    def update_streak_stats(self, text: str) -> None:
        label_map = {
            "max_win": "最大連勝",
            "max_loss": "最大連敗",
        }
        self._streak_stats.setText(format_kv_lines(text, label_map))

    def update_holding_stats(self, text: str) -> None:
        label_map = {
            "max_steps": "最長持倉",
            "avg_steps": "平均持倉",
        }
        self._holding_stats.setText(format_kv_lines(text, label_map))

    def update_action_distribution(self, text: str) -> None:
        label_map = {
            "long": "多單比例",
            "short": "空單比例",
            "flat": "空手比例",
            "avg": "平均持倉",
        }
        self._action_dist.setText(format_kv_lines(text, label_map))

    def update_playback_range(self, text: str) -> None:
        label_map = {
            "start": "開始",
            "end": "結束",
            "steps": "步數",
        }
        self._playback_range.setText(format_kv_lines(text, label_map))

class SimulationPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._charts_available = pg is not None
        self._steps: list[int] = []
        self._equity: list[float] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        if self._charts_available:
            plot = pg.PlotWidget()
            plot.setTitle("回放權益曲線")
            plot.setLabel("bottom", "timesteps")
            plot.setLabel("left", "equity")
            plot.showGrid(x=True, y=True, alpha=0.3)
            self._plot = plot
            self._curve = plot.plot(pen=pg.mkPen("#F58518", width=2), name="equity")
            layout.addWidget(plot, stretch=1)
        else:
            notice = QLabel("PyQtGraph 未安裝，無法顯示曲線圖。請安裝 pyqtgraph。")
            notice.setWordWrap(True)
            layout.addWidget(notice)

    def reset_plot(self) -> None:
        self._steps.clear()
        self._equity.clear()
        if self._charts_available:
            self._curve.setData([], [])

    def ingest_equity(self, step: int, equity: float) -> None:
        self._steps.append(step)
        self._equity.append(equity)
        if self._charts_available:
            self._curve.setData(self._steps, self._equity)
