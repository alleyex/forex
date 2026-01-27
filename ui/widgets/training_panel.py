from __future__ import annotations

import json
from pathlib import Path
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
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QCheckBox,
    QLineEdit,
    QFileDialog,
    QSizePolicy,
    QGroupBox,
    QTabWidget,
)

from ui.widgets.form_helpers import (
    apply_form_label_width,
    align_form_fields,
    build_browse_row,
    configure_form_layout,
)
from ui.utils.path_utils import latest_file_in_dir
from ui.styles.tokens import FORM_LABEL_WIDTH_COMPACT, PRIMARY, TRAINING_PARAMS
from config.paths import RAW_HISTORY_DIR


class TrainingParamsPanel(QWidget):
    start_requested = Signal(dict)
    optuna_requested = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setProperty("class", TRAINING_PARAMS)
        left_layout = QVBoxLayout(self)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(14)

        file_group = QGroupBox("Files")
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
        file_layout.addRow("data_path", data_row)

        params_group = QGroupBox("Training Params")
        params_layout = QFormLayout(params_group)
        configure_form_layout(
            params_layout,
            label_alignment=Qt.AlignLeft | Qt.AlignVCenter,
            field_growth_policy=QFormLayout.FieldsStayAtSizeHint,
        )
        apply_form_label_width(params_layout, FORM_LABEL_WIDTH_COMPACT)
        align_form_fields(params_layout, Qt.AlignLeft | Qt.AlignVCenter)

        self._total_steps = QSpinBox()
        self._total_steps.setRange(1, 10_000_000)
        self._total_steps.setValue(200_000)
        self._total_steps.setFixedWidth(spin_width)
        params_layout.addRow("total_steps", self._total_steps)

        self._learning_rate = QDoubleSpinBox()
        self._learning_rate.setRange(1e-6, 1.0)
        self._learning_rate.setDecimals(6)
        self._learning_rate.setSingleStep(1e-4)
        self._learning_rate.setValue(3e-4)
        self._learning_rate.setFixedWidth(spin_width)
        params_layout.addRow("learning_rate", self._learning_rate)

        self._gamma = QDoubleSpinBox()
        self._gamma.setRange(0.0, 0.9999)
        self._gamma.setDecimals(4)
        self._gamma.setSingleStep(0.001)
        self._gamma.setValue(0.99)
        self._gamma.setFixedWidth(spin_width)
        params_layout.addRow("gamma", self._gamma)

        self._n_steps = QSpinBox()
        self._n_steps.setRange(1, 8192)
        self._n_steps.setValue(2048)
        self._n_steps.setFixedWidth(spin_width)
        params_layout.addRow("n_steps", self._n_steps)

        self._batch_size = QSpinBox()
        self._batch_size.setRange(1, 4096)
        self._batch_size.setValue(64)
        self._batch_size.setFixedWidth(spin_width)
        params_layout.addRow("batch_size", self._batch_size)

        self._ent_coef = QDoubleSpinBox()
        self._ent_coef.setRange(0.0, 1.0)
        self._ent_coef.setDecimals(4)
        self._ent_coef.setSingleStep(0.001)
        self._ent_coef.setValue(0.0)
        self._ent_coef.setFixedWidth(spin_width)
        params_layout.addRow("ent_coef", self._ent_coef)

        self._eval_split = QDoubleSpinBox()
        self._eval_split.setRange(0.05, 0.5)
        self._eval_split.setDecimals(3)
        self._eval_split.setSingleStep(0.01)
        self._eval_split.setValue(0.2)
        self._eval_split.setFixedWidth(spin_width)
        params_layout.addRow("eval_split", self._eval_split)

        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        self._resume_training = QCheckBox("Resume training")
        self._resume_training.setChecked(False)
        options_layout.addWidget(self._resume_training)
        self._optuna_train_best = QCheckBox("Train best model")
        self._optuna_train_best.setChecked(True)
        options_layout.addWidget(self._optuna_train_best)

        env_group = QGroupBox("Environment")
        env_layout = QFormLayout(env_group)
        configure_form_layout(
            env_layout,
            label_alignment=Qt.AlignLeft | Qt.AlignVCenter,
            field_growth_policy=QFormLayout.FieldsStayAtSizeHint,
        )
        apply_form_label_width(env_layout, FORM_LABEL_WIDTH_COMPACT)
        align_form_fields(env_layout, Qt.AlignLeft | Qt.AlignVCenter)

        self._episode_length = QSpinBox()
        self._episode_length.setRange(1, 20_000)
        self._episode_length.setValue(2048)
        self._episode_length.setFixedWidth(spin_width)
        env_layout.addRow("episode_length", self._episode_length)

        self._transaction_cost_bps = QDoubleSpinBox()
        self._transaction_cost_bps.setRange(0.0, 100.0)
        self._transaction_cost_bps.setDecimals(3)
        self._transaction_cost_bps.setSingleStep(0.1)
        self._transaction_cost_bps.setValue(1.0)
        self._transaction_cost_bps.setFixedWidth(spin_width)
        env_layout.addRow("transaction_cost_bps", self._transaction_cost_bps)

        self._slippage_bps = QDoubleSpinBox()
        self._slippage_bps.setRange(0.0, 100.0)
        self._slippage_bps.setDecimals(3)
        self._slippage_bps.setSingleStep(0.1)
        self._slippage_bps.setValue(0.5)
        self._slippage_bps.setFixedWidth(spin_width)
        env_layout.addRow("slippage_bps", self._slippage_bps)

        self._random_start = QCheckBox()
        self._random_start.setChecked(True)
        env_layout.addRow("random_start", self._random_start)

        optuna_group = QGroupBox("Optuna Settings")
        optuna_layout = QFormLayout(optuna_group)
        configure_form_layout(
            optuna_layout,
            label_alignment=Qt.AlignLeft | Qt.AlignVCenter,
            field_growth_policy=QFormLayout.FieldsStayAtSizeHint,
        )
        apply_form_label_width(optuna_layout, FORM_LABEL_WIDTH_COMPACT)
        align_form_fields(optuna_layout, Qt.AlignLeft | Qt.AlignVCenter)

        self._optuna_trials = QSpinBox()
        self._optuna_trials.setRange(0, 500)
        self._optuna_trials.setValue(0)
        self._optuna_trials.setFixedWidth(spin_width)
        optuna_layout.addRow("Trials", self._optuna_trials)

        self._optuna_steps = QSpinBox()
        self._optuna_steps.setRange(1, 5_000_000)
        self._optuna_steps.setValue(50_000)
        self._optuna_steps.setFixedWidth(spin_width)
        optuna_layout.addRow("Steps per trial", self._optuna_steps)

        self._optuna_out = QLineEdit("data/optuna/best_params.json")
        self._optuna_out.setFixedWidth(field_width)
        self._optuna_out.setPlaceholderText("data/optuna/best_params.json")
        optuna_out_row = build_browse_row(self._optuna_out, self._browse_optuna_out)
        optuna_out_row.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        optuna_layout.addRow("Output JSON", optuna_out_row)

        self._start_button = QPushButton("開始訓練")
        self._start_button.setProperty("class", PRIMARY)
        self._start_button.clicked.connect(self._emit_start)

        tabs = QTabWidget()
        training_tab = QWidget()
        training_layout = QVBoxLayout(training_tab)
        training_layout.setContentsMargins(0, 0, 0, 0)
        training_layout.setSpacing(12)
        training_layout.addWidget(file_group)
        training_layout.addWidget(params_group)
        training_layout.addWidget(options_group)
        training_layout.addWidget(self._start_button)
        training_layout.addStretch(1)

        env_tab = QWidget()
        env_layout_wrap = QVBoxLayout(env_tab)
        env_layout_wrap.setContentsMargins(0, 0, 0, 0)
        env_layout_wrap.setSpacing(12)
        env_layout_wrap.addWidget(env_group)
        env_layout_wrap.addStretch(1)

        optuna_tab = QWidget()
        optuna_layout_wrap = QVBoxLayout(optuna_tab)
        optuna_layout_wrap.setContentsMargins(0, 0, 0, 0)
        optuna_layout_wrap.setSpacing(12)
        optuna_hint = QLabel("Run a short search to find better PPO hyperparameters.")
        optuna_hint.setProperty("class", "dialog_hint")
        optuna_layout_wrap.addWidget(optuna_hint)
        optuna_layout_wrap.addWidget(optuna_group)

        self._optuna_search_button = QPushButton("搜尋最佳參數")
        self._optuna_search_button.setProperty("class", PRIMARY)
        self._optuna_search_button.clicked.connect(self._emit_optuna)
        optuna_layout_wrap.addWidget(self._optuna_search_button)

        optuna_layout_wrap.addStretch(1)

        tabs.addTab(training_tab, "Training")
        tabs.addTab(env_tab, "Environment")
        tabs.addTab(optuna_tab, "Optuna")
        left_layout.addWidget(tabs)

        self._load_params()
        self._load_optuna_defaults()

    def _emit_start(self) -> None:
        params = self.get_params()
        params["optuna_trials"] = 0
        params["optuna_train_best"] = False
        params["optuna_only"] = False
        self._save_params(params)
        self.start_requested.emit(params)

    def should_apply_optuna(self) -> bool:
        return bool(self._optuna_train_best.isChecked())

    def apply_optuna_params(self, params: dict) -> None:
        if "learning_rate" in params:
            self._learning_rate.setValue(float(params["learning_rate"]))
        if "gamma" in params:
            self._gamma.setValue(float(params["gamma"]))
        if "n_steps" in params:
            self._n_steps.setValue(int(params["n_steps"]))
        if "batch_size" in params:
            self._batch_size.setValue(int(params["batch_size"]))
        if "ent_coef" in params:
            self._ent_coef.setValue(float(params["ent_coef"]))

    def get_params(self) -> dict:
        return {
            "data_path": self._data_path.text().strip(),
            "total_steps": int(self._total_steps.value()),
            "learning_rate": float(self._learning_rate.value()),
            "gamma": float(self._gamma.value()),
            "n_steps": int(self._n_steps.value()),
            "batch_size": int(self._batch_size.value()),
            "ent_coef": float(self._ent_coef.value()),
            "episode_length": int(self._episode_length.value()),
            "eval_split": float(self._eval_split.value()),
            "resume": bool(self._resume_training.isChecked()),
            "transaction_cost_bps": float(self._transaction_cost_bps.value()),
            "slippage_bps": float(self._slippage_bps.value()),
            "random_start": bool(self._random_start.isChecked()),
            "optuna_trials": int(self._optuna_trials.value()),
            "optuna_steps": int(self._optuna_steps.value()),
            "optuna_train_best": bool(self._optuna_train_best.isChecked()),
            "optuna_out": self._optuna_out.text().strip(),
            "optuna_only": False,
        }

    def _browse_data(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇訓練資料", self._data_path.text(), "CSV (*.csv)"
        )
        if path:
            self._data_path.setText(path)
            self._data_path.setToolTip(path)

    def _browse_optuna_out(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Optuna 參數", self._optuna_out.text(), "JSON (*.json)"
        )
        if path:
            self._optuna_out.setText(path)

    def _emit_optuna(self) -> None:
        params = self.get_params()
        params["optuna_only"] = True
        params["optuna_train_best"] = False
        self._save_params(params)
        self.optuna_requested.emit(params)

    def _load_optuna_defaults(self) -> None:
        path = Path("data/optuna/best_params.json")
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(data, dict):
            self.apply_optuna_params(data)

    def _params_path(self) -> Path:
        return Path("data/optuna/training_params.json")

    def _save_params(self, params: dict) -> None:
        path = self._params_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(params)
        payload.pop("optuna_only", None)
        try:
            path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        except OSError:
            return

    def _load_params(self) -> None:
        path = self._params_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        if "data_path" in data:
            self._data_path.setText(str(data["data_path"]))
        if "total_steps" in data:
            self._total_steps.setValue(int(data["total_steps"]))
        if "learning_rate" in data:
            self._learning_rate.setValue(float(data["learning_rate"]))
        if "gamma" in data:
            self._gamma.setValue(float(data["gamma"]))
        if "n_steps" in data:
            self._n_steps.setValue(int(data["n_steps"]))
        if "batch_size" in data:
            self._batch_size.setValue(int(data["batch_size"]))
        if "ent_coef" in data:
            self._ent_coef.setValue(float(data["ent_coef"]))
        if "episode_length" in data:
            self._episode_length.setValue(int(data["episode_length"]))
        if "eval_split" in data:
            self._eval_split.setValue(float(data["eval_split"]))
        if "resume" in data:
            self._resume_training.setChecked(bool(data["resume"]))
        if "transaction_cost_bps" in data:
            self._transaction_cost_bps.setValue(float(data["transaction_cost_bps"]))
        if "slippage_bps" in data:
            self._slippage_bps.setValue(float(data["slippage_bps"]))
        if "random_start" in data:
            self._random_start.setChecked(bool(data["random_start"]))
        if "optuna_trials" in data:
            self._optuna_trials.setValue(int(data["optuna_trials"]))
        if "optuna_steps" in data:
            self._optuna_steps.setValue(int(data["optuna_steps"]))
        if "optuna_train_best" in data:
            self._optuna_train_best.setChecked(bool(data["optuna_train_best"]))
        if "optuna_out" in data:
            self._optuna_out.setText(str(data["optuna_out"]))


class TrainingPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_step = 0
        self._charts_available = pg is not None
        self._metrics = [
            ("ep_rew_mean", "ep_rew_mean"),
            ("eval/mean_reward", "mean_reward"),
            ("value_loss", "value_loss"),
            ("explained_variance", "explained_variance"),
            ("approx_kl", "approx_kl"),
            ("clip_fraction", "clip_fraction"),
            ("entropy_loss", "entropy_loss"),
            ("policy_gradient_loss", "policy_gradient_loss"),
            ("loss", "loss"),
            ("std", "std"),
            ("fps", "fps"),
        ]
        self._metric_data: dict[str, dict[str, list[float]]] = {}
        self._curves: dict[str, object] = {}
        self._checkboxes: dict[str, QCheckBox] = {}
        self._metric_labels = {key: label for label, key in self._metrics}
        self._legend_keys: set[str] = set()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        if self._charts_available:
            plot = pg.PlotWidget()
            plot.setTitle("PPO 訓練曲線")
            plot.setLabel("bottom", "timesteps")
            plot.setLabel("left", "metric")
            plot.showGrid(x=True, y=True, alpha=0.3)
            self._legend = plot.addLegend()
            self._plot = plot

            colors = [
                "#4C78A8",
                "#F58518",
                "#54A24B",
                "#B279A2",
                "#E45756",
                "#72B7B2",
                "#FF9DA6",
                "#9D755D",
                "#BAB0AC",
                "#59A14F",
                "#EDC948",
            ]
            for index, (label, key) in enumerate(self._metrics):
                color = colors[index % len(colors)]
                curve = plot.plot(pen=pg.mkPen(color, width=2))
                self._curves[key] = curve
                self._metric_data[key] = {"x": [], "y": []}

            chooser = QWidget()
            chooser_layout = QGridLayout(chooser)
            chooser_layout.setContentsMargins(0, 0, 0, 0)
            chooser_layout.setHorizontalSpacing(10)
            chooser_layout.setVerticalSpacing(4)
            for idx, (label, key) in enumerate(self._metrics):
                checkbox = QCheckBox(label)
                checked = label == "eval/mean_reward"
                checkbox.setChecked(checked)
                checkbox.toggled.connect(lambda checked_state, k=key: self._toggle_curve(k, checked_state))
                self._checkboxes[key] = checkbox
                row = idx // 4
                col = idx % 4
                chooser_layout.addWidget(checkbox, row, col)

            layout.addWidget(plot, stretch=1)
            layout.addWidget(chooser)
            self._sync_curve_visibility()
        else:
            notice = QLabel("PyQtGraph 未安裝，無法顯示曲線圖。請安裝 pyqtgraph。")
            notice.setWordWrap(True)
            layout.addWidget(notice)

    def reset_metrics(self) -> None:
        if not self._charts_available:
            return
        self._current_step = 0
        for key in self._metric_data:
            self._metric_data[key]["x"].clear()
            self._metric_data[key]["y"].clear()
            self._curves[key].setData([])
        self._sync_curve_visibility()

    def ingest_log_line(self, line: str) -> None:
        if not self._charts_available:
            return
        step = self._parse_int("total_timesteps", line)
        if step is None:
            step = self._parse_int("num_timesteps", line)
        if step is not None:
            self._current_step = step

        for label, key in self._metrics:
            value = self._parse_float(key, line)
            if value is None:
                continue
            self._append_point(key, float(self._current_step), value)

    def _append_point(self, key: str, step: float, value: float) -> None:
        data = self._metric_data[key]
        data["x"].append(step)
        data["y"].append(value)
        if self._checkboxes[key].isChecked():
            self._curves[key].setData(data["x"], data["y"])

    def _toggle_curve(self, key: str, visible: bool) -> None:
        data = self._metric_data[key]
        if visible:
            self._curves[key].setData(data["x"], data["y"])
            if key not in self._legend_keys:
                self._legend.addItem(self._curves[key], self._metric_labels[key])
                self._legend_keys.add(key)
            if data["y"]:
                self._curves[key].setData(data["x"], data["y"])
        else:
            self._curves[key].setData([], [])
            if key in self._legend_keys:
                self._legend.removeItem(self._curves[key])
                self._legend_keys.remove(key)

    def _sync_curve_visibility(self) -> None:
        for _, key in self._metrics:
            self._toggle_curve(key, self._checkboxes[key].isChecked())



    @staticmethod
    def _parse_float(key: str, line: str) -> Optional[float]:
        parts = [part.strip() for part in line.split("|") if part.strip()]
        if len(parts) < 2:
            return None
        if parts[0] != key:
            return None
        try:
            return float(parts[1])
        except ValueError:
            return None
        return None

    @staticmethod
    def _parse_int(key: str, line: str) -> Optional[int]:
        value = TrainingPanel._parse_float(key, line)
        if value is None:
            return None
        return int(value)
