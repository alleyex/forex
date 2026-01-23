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
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QFileDialog,
    QSizePolicy,
)

from ui.widgets.form_helpers import build_browse_row, configure_form_layout
from ui.utils.path_utils import latest_file_in_dir
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        form = QFormLayout()
        configure_form_layout(
            form,
            label_alignment=Qt.AlignLeft | Qt.AlignVCenter,
            field_growth_policy=QFormLayout.FieldsStayAtSizeHint,
        )

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
        form.addRow("data", data_row)

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
        form.addRow("model", model_row)

        self._log_every = QSpinBox()
        self._log_every.setRange(1, 100_000)
        self._log_every.setValue(200)
        self._log_every.setFixedWidth(spin_width)
        form.addRow("log_every", self._log_every)

        self._max_steps = QSpinBox()
        self._max_steps.setRange(0, 10_000_000)
        self._max_steps.setValue(0)
        self._max_steps.setFixedWidth(spin_width)
        form.addRow("max_steps", self._max_steps)

        self._transaction_cost = QDoubleSpinBox()
        self._transaction_cost.setRange(0.0, 100.0)
        self._transaction_cost.setDecimals(3)
        self._transaction_cost.setValue(1.0)
        self._transaction_cost.setFixedWidth(spin_width)
        form.addRow("transaction_cost_bps", self._transaction_cost)

        self._slippage = QDoubleSpinBox()
        self._slippage.setRange(0.0, 100.0)
        self._slippage.setDecimals(3)
        self._slippage.setValue(0.5)
        self._slippage.setFixedWidth(spin_width)
        form.addRow("slippage_bps", self._slippage)

        layout.addLayout(form)

        self._summary = QLabel("總報酬: -\n最大回撤: -\n夏普比率: -\n交易次數: -\n最終權益: -")
        self._summary.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self._summary)

        self._trade_stats = QLabel("交易統計: -")
        self._trade_stats.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self._trade_stats)

        self._streak_stats = QLabel("連勝/連敗: -")
        self._streak_stats.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self._streak_stats)

        self._holding_stats = QLabel("持倉時間: -")
        self._holding_stats.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self._holding_stats)

        self._action_dist = QLabel("行動分布: -")
        self._action_dist.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self._action_dist)

        self._playback_range = QLabel("回放區間: -")
        self._playback_range.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self._playback_range)

        layout.addStretch(1)

        self._start_button = QPushButton("開始回放")
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
        self._summary.setText("總報酬: -\n最大回撤: -\n夏普比率: -\n交易次數: -\n最終權益: -")
        self._trade_stats.setText("交易統計: -")
        self._streak_stats.setText("連勝/連敗: -")
        self._holding_stats.setText("持倉時間: -")
        self._action_dist.setText("行動分布: -")
        self._playback_range.setText("回放區間: -")

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

        total_text = "-" if total_return is None else f"{total_return:.6f}"
        dd_text = "-" if max_drawdown is None else f"{max_drawdown:.6f}"
        sharpe_text = "-" if sharpe is None else f"{sharpe:.6f}"
        trades_text = "-" if trades is None else str(trades)
        equity_text = "-" if equity is None else f"{equity:.6f}"
        self._summary.setText(
            f"總報酬: {total_text}\n最大回撤: {dd_text}\n夏普比率: {sharpe_text}\n交易次數: {trades_text}\n最終權益: {equity_text}"
        )

    def update_trade_stats(self, text: str) -> None:
        self._trade_stats.setText(f"交易統計: {text}")

    def update_streak_stats(self, text: str) -> None:
        self._streak_stats.setText(f"連勝/連敗: {text}")

    def update_holding_stats(self, text: str) -> None:
        self._holding_stats.setText(f"持倉時間: {text}")

    def update_action_distribution(self, text: str) -> None:
        self._action_dist.setText(f"行動分布: {text}")

    def update_playback_range(self, text: str) -> None:
        self._playback_range.setText(f"回放區間: {text}")


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
