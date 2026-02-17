from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - optional dependency
    pg = None
from collections import deque
from PySide6.QtCore import Qt, Signal, QElapsedTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
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
    QStackedWidget,
)

from forex.ui.shared.utils.formatters import (
    format_optuna_best_params,
    format_optuna_empty_best,
    format_optuna_empty_trial,
    format_optuna_trial_summary,
)
from forex.ui.shared.widgets.layout_helpers import (
    apply_form_label_width,
    align_form_fields,
    build_browse_row,
    configure_form_layout,
)
from forex.ui.shared.utils.path_utils import latest_file_in_dir
from forex.ui.shared.styles.tokens import FORM_LABEL_WIDTH_COMPACT, PRIMARY, TRAINING_PARAMS
from forex.config.paths import RAW_HISTORY_DIR
from forex.ui.train.services import UIParamsStore


class AdaptiveFormGrid(QWidget):
    """Responsive field grid: auto-wraps rows by available width."""

    def __init__(
        self,
        *,
        min_cell_width: int = 360,
        label_min_width: int = 0,
        max_columns: int = 2,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._min_cell_width = max(220, int(min_cell_width))
        self._label_min_width = max(0, int(label_min_width))
        self._max_columns = max(1, int(max_columns))
        self._cells: list[QWidget] = []
        self._labels: list[QLabel] = []
        self._last_columns = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(48)
        self._grid.setVerticalSpacing(10)

    def add_row(self, label_text: str, field: QWidget) -> None:
        cell = QWidget(self)
        row = QHBoxLayout(cell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        label = QLabel(self._format_label_text(label_text), cell)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        row.addWidget(label, 0, Qt.AlignLeft)
        row.addWidget(field, 0, Qt.AlignLeft)
        row.addStretch(1)
        self._cells.append(cell)
        self._labels.append(label)
        self._rebuild()

    @staticmethod
    def _format_label_text(label_text: str) -> str:
        text = str(label_text or "").strip()
        if not text or "\n" in text:
            return text
        if " " in text:
            left, right = text.split(" ", 1)
            return f"{left}\n{right}"
        return text

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rebuild()

    def _compute_columns(self) -> int:
        width = max(1, self.width())
        columns = max(1, width // self._min_cell_width)
        return min(self._max_columns, columns)

    def _rebuild(self) -> None:
        cols = self._compute_columns()
        if cols == self._last_columns and self._grid.count() == len(self._cells):
            return
        self._last_columns = cols
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self)
        for idx, cell in enumerate(self._cells):
            row = idx // cols
            col = idx % cols
            self._grid.addWidget(cell, row, col, Qt.AlignLeft | Qt.AlignTop)

        # Align fields per visual column: label width = longest label in the column + small gap.
        cjk_gap = max(1, self.fontMetrics().horizontalAdvance("中"))
        for col_idx in range(cols):
            col_labels = [self._labels[idx] for idx in range(col_idx, len(self._labels), cols)]
            if not col_labels:
                continue
            col_max = max(label.sizeHint().width() for label in col_labels)
            width = max(self._label_min_width, col_max + cjk_gap)
            for label in col_labels:
                label.setFixedWidth(width)

        for col in range(cols + 1):
            self._grid.setColumnStretch(col, 0)
        self._grid.setColumnStretch(cols, 1)


class TrainingParamsPanel(QWidget):
    start_requested = Signal(dict)
    optuna_requested = Signal(dict)
    tab_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._loading_params = False
        self._params_store = UIParamsStore("training")
        self._optuna_metrics = [
            ("trial_value", "trial value"),
            ("best_value", "best so far"),
            ("duration_sec", "duration (s)"),
        ]
        self._optuna_checkboxes: dict[str, QCheckBox] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setProperty("class", TRAINING_PARAMS)
        left_layout = QVBoxLayout(self)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(14)

        def _apply_live_card_style(group: QGroupBox, *, line_title: bool = True) -> None:
            group.setObjectName("card")
            group.setProperty("titleAlign", "left")
            group.setProperty("titleTone", "line" if line_title else "default")

        file_group = QGroupBox("Files")
        _apply_live_card_style(file_group)
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
        self._data_path.textChanged.connect(self._on_data_path_changed)
        data_row = build_browse_row(self._data_path, self._browse_data)
        data_row.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        file_layout.addRow("data_path", data_row)
        self._data_meta = QLabel("")
        self._data_meta.setWordWrap(True)
        self._data_meta.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._data_meta.setProperty("class", "result_value")
        self._data_meta.setMinimumWidth(field_width)
        self._data_meta.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._data_meta_label = QLabel("Metadata")
        self._data_meta_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        file_layout.addRow(self._data_meta_label, self._data_meta)

        params_group = QGroupBox("Training Params")
        _apply_live_card_style(params_group)
        params_group_layout = QVBoxLayout(params_group)
        params_group_layout.setContentsMargins(12, 10, 12, 12)
        params_group_layout.setSpacing(8)
        params_layout = AdaptiveFormGrid(min_cell_width=260, label_min_width=0, max_columns=2)
        params_group_layout.addWidget(params_layout)

        self._total_steps = QSpinBox()
        self._total_steps.setRange(1, 10_000_000)
        self._total_steps.setValue(200_000)
        self._total_steps.setFixedWidth(spin_width)
        params_layout.add_row("total_steps", self._total_steps)

        self._learning_rate = QDoubleSpinBox()
        self._learning_rate.setRange(1e-6, 1.0)
        self._learning_rate.setDecimals(6)
        self._learning_rate.setSingleStep(1e-4)
        self._learning_rate.setValue(3e-4)
        self._learning_rate.setFixedWidth(spin_width)
        params_layout.add_row("learning_rate", self._learning_rate)

        self._gamma = QDoubleSpinBox()
        self._gamma.setRange(0.0, 0.9999)
        self._gamma.setDecimals(4)
        self._gamma.setSingleStep(0.001)
        self._gamma.setValue(0.99)
        self._gamma.setFixedWidth(spin_width)
        params_layout.add_row("gamma", self._gamma)

        self._n_steps = QSpinBox()
        self._n_steps.setRange(1, 8192)
        self._n_steps.setValue(2048)
        self._n_steps.setFixedWidth(spin_width)
        params_layout.add_row("n_steps", self._n_steps)

        self._batch_size = QSpinBox()
        self._batch_size.setRange(1, 4096)
        self._batch_size.setValue(64)
        self._batch_size.setFixedWidth(spin_width)
        params_layout.add_row("batch_size", self._batch_size)

        self._ent_coef = QDoubleSpinBox()
        self._ent_coef.setRange(0.0, 1.0)
        # Optuna often finds very small entropy coefficients (e.g. 1e-5),
        # so keep enough visible precision to avoid displaying as 0.0000.
        self._ent_coef.setDecimals(8)
        self._ent_coef.setSingleStep(0.00001)
        self._ent_coef.setValue(0.0)
        self._ent_coef.setFixedWidth(spin_width)
        params_layout.add_row("ent_coef", self._ent_coef)

        self._eval_split = QDoubleSpinBox()
        self._eval_split.setRange(0.05, 0.5)
        self._eval_split.setDecimals(3)
        self._eval_split.setSingleStep(0.01)
        self._eval_split.setValue(0.2)
        self._eval_split.setFixedWidth(spin_width)
        params_layout.add_row("eval_split", self._eval_split)

        ppo_advanced_group = QGroupBox("PPO Advanced")
        _apply_live_card_style(ppo_advanced_group)
        ppo_advanced_group_layout = QVBoxLayout(ppo_advanced_group)
        ppo_advanced_group_layout.setContentsMargins(12, 10, 12, 12)
        ppo_advanced_group_layout.setSpacing(8)
        ppo_advanced_layout = AdaptiveFormGrid(min_cell_width=260, label_min_width=0, max_columns=2)
        ppo_advanced_group_layout.addWidget(ppo_advanced_layout)

        self._gae_lambda = QDoubleSpinBox()
        self._gae_lambda.setRange(0.0, 1.0)
        self._gae_lambda.setDecimals(3)
        self._gae_lambda.setSingleStep(0.01)
        self._gae_lambda.setValue(0.95)
        self._gae_lambda.setFixedWidth(spin_width)
        ppo_advanced_layout.add_row("gae_lambda", self._gae_lambda)

        self._clip_range = QDoubleSpinBox()
        self._clip_range.setRange(0.01, 1.0)
        self._clip_range.setDecimals(3)
        self._clip_range.setSingleStep(0.01)
        self._clip_range.setValue(0.2)
        self._clip_range.setFixedWidth(spin_width)
        ppo_advanced_layout.add_row("clip_range", self._clip_range)

        self._vf_coef = QDoubleSpinBox()
        self._vf_coef.setRange(0.0, 2.0)
        self._vf_coef.setDecimals(3)
        self._vf_coef.setSingleStep(0.01)
        self._vf_coef.setValue(0.5)
        self._vf_coef.setFixedWidth(spin_width)
        ppo_advanced_layout.add_row("vf_coef", self._vf_coef)

        self._n_epochs = QSpinBox()
        self._n_epochs.setRange(1, 200)
        self._n_epochs.setValue(10)
        self._n_epochs.setFixedWidth(spin_width)
        ppo_advanced_layout.add_row("n_epochs", self._n_epochs)

        options_group = QGroupBox("Options")
        _apply_live_card_style(options_group)
        options_layout = QVBoxLayout(options_group)
        self._resume_training = QCheckBox("Resume training")
        self._resume_training.setChecked(False)
        options_layout.addWidget(self._resume_training)
        self._optuna_train_best = QCheckBox("Train best model")
        self._optuna_train_best.setChecked(True)
        options_layout.addWidget(self._optuna_train_best)

        def _wrap_field(widget: QWidget) -> QWidget:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            layout.addWidget(widget)
            return container

        env_label_width = 180

        cost_group = QGroupBox("Cost & Friction")
        _apply_live_card_style(cost_group)
        cost_group_layout = QVBoxLayout(cost_group)
        cost_group_layout.setContentsMargins(12, 10, 12, 12)
        cost_group_layout.setSpacing(8)
        cost_layout = AdaptiveFormGrid(min_cell_width=250, label_min_width=0, max_columns=2)
        cost_group_layout.addWidget(cost_layout)

        self._transaction_cost_bps = QDoubleSpinBox()
        self._transaction_cost_bps.setRange(0.0, 100.0)
        self._transaction_cost_bps.setDecimals(3)
        self._transaction_cost_bps.setSingleStep(0.1)
        self._transaction_cost_bps.setValue(1.0)
        self._transaction_cost_bps.setFixedWidth(spin_width)
        cost_layout.add_row(
            "Transaction cost (bps)",
            _wrap_field(self._transaction_cost_bps),
        )

        self._slippage_bps = QDoubleSpinBox()
        self._slippage_bps.setRange(0.0, 100.0)
        self._slippage_bps.setDecimals(3)
        self._slippage_bps.setSingleStep(0.1)
        self._slippage_bps.setValue(0.5)
        self._slippage_bps.setFixedWidth(spin_width)
        cost_layout.add_row(
            "Slippage (bps)",
            _wrap_field(self._slippage_bps),
        )

        self._holding_cost_bps = QDoubleSpinBox()
        self._holding_cost_bps.setRange(0.0, 100.0)
        self._holding_cost_bps.setDecimals(3)
        self._holding_cost_bps.setSingleStep(0.1)
        self._holding_cost_bps.setValue(0.0)
        self._holding_cost_bps.setFixedWidth(spin_width)
        cost_layout.add_row(
            "Holding cost (bps)",
            _wrap_field(self._holding_cost_bps),
        )

        action_group = QGroupBox("Action & Position")
        _apply_live_card_style(action_group)
        action_group_layout = QVBoxLayout(action_group)
        action_group_layout.setContentsMargins(12, 10, 12, 12)
        action_group_layout.setSpacing(8)
        action_layout = AdaptiveFormGrid(min_cell_width=250, label_min_width=0, max_columns=2)
        action_group_layout.addWidget(action_layout)

        self._min_position_change = QDoubleSpinBox()
        self._min_position_change.setRange(0.0, 1.0)
        self._min_position_change.setDecimals(3)
        self._min_position_change.setSingleStep(0.01)
        self._min_position_change.setValue(0.0)
        self._min_position_change.setFixedWidth(spin_width)
        action_layout.add_row(
            "Min position change",
            _wrap_field(self._min_position_change),
        )

        self._max_position = QDoubleSpinBox()
        self._max_position.setRange(0.0, 10.0)
        self._max_position.setDecimals(3)
        self._max_position.setSingleStep(0.1)
        self._max_position.setValue(1.0)
        self._max_position.setFixedWidth(spin_width)
        action_layout.add_row(
            "Max position",
            _wrap_field(self._max_position),
        )

        self._position_step = QDoubleSpinBox()
        self._position_step.setRange(0.0, 1.0)
        self._position_step.setDecimals(3)
        self._position_step.setSingleStep(0.01)
        self._position_step.setValue(0.0)
        self._position_step.setFixedWidth(spin_width)
        action_layout.add_row(
            "Position step",
            _wrap_field(self._position_step),
        )

        episode_group = QGroupBox("Episode & Sampling")
        _apply_live_card_style(episode_group)
        episode_group_layout = QVBoxLayout(episode_group)
        episode_group_layout.setContentsMargins(12, 10, 12, 12)
        episode_group_layout.setSpacing(8)
        episode_layout = AdaptiveFormGrid(min_cell_width=250, label_min_width=0, max_columns=2)
        episode_group_layout.addWidget(episode_layout)

        self._episode_length = QSpinBox()
        self._episode_length.setRange(1, 20_000)
        self._episode_length.setValue(2048)
        self._episode_length.setFixedWidth(spin_width)
        episode_layout.add_row(
            "Episode length",
            _wrap_field(self._episode_length),
        )

        self._random_start = QCheckBox()
        self._random_start.setChecked(True)
        episode_layout.add_row(
            "Random start",
            _wrap_field(self._random_start),
        )

        reward_group = QGroupBox("Reward shaping")
        _apply_live_card_style(reward_group)
        reward_group_layout = QVBoxLayout(reward_group)
        reward_group_layout.setContentsMargins(12, 10, 12, 12)
        reward_group_layout.setSpacing(8)
        reward_layout = AdaptiveFormGrid(min_cell_width=250, label_min_width=0, max_columns=2)
        reward_group_layout.addWidget(reward_layout)

        self._reward_scale = QDoubleSpinBox()
        self._reward_scale.setRange(0.0, 100.0)
        self._reward_scale.setDecimals(3)
        self._reward_scale.setSingleStep(0.1)
        self._reward_scale.setValue(1.0)
        self._reward_scale.setFixedWidth(spin_width)
        reward_layout.add_row(
            "Reward scale",
            _wrap_field(self._reward_scale),
        )

        self._reward_clip = QDoubleSpinBox()
        self._reward_clip.setRange(0.0, 10.0)
        self._reward_clip.setDecimals(3)
        self._reward_clip.setSingleStep(0.1)
        self._reward_clip.setValue(0.0)
        self._reward_clip.setFixedWidth(spin_width)
        reward_layout.add_row(
            "Reward clip",
            _wrap_field(self._reward_clip),
        )

        self._risk_aversion = QDoubleSpinBox()
        self._risk_aversion.setRange(0.0, 10.0)
        self._risk_aversion.setDecimals(3)
        self._risk_aversion.setSingleStep(0.1)
        self._risk_aversion.setValue(0.0)
        self._risk_aversion.setFixedWidth(spin_width)
        reward_layout.add_row(
            "Risk aversion",
            _wrap_field(self._risk_aversion),
        )

        optuna_group = QGroupBox("Optuna Settings")
        _apply_live_card_style(optuna_group)
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

        self._start_button = QPushButton("Start Training")
        self._start_button.setProperty("class", PRIMARY)
        self._start_button.clicked.connect(self._emit_start)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setMovable(False)
        tabs.setUsesScrollButtons(False)
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setDrawBase(False)

        training_tab = QWidget()
        training_tab.setObjectName("modelTab")
        training_layout = QVBoxLayout(training_tab)
        training_layout.setContentsMargins(12, 10, 18, 24)
        training_layout.setSpacing(8)
        training_layout.addWidget(file_group)
        training_layout.addWidget(params_group)
        training_layout.addWidget(ppo_advanced_group)
        training_layout.addWidget(options_group)
        training_layout.addWidget(self._start_button)
        training_layout.addStretch(1)

        env_tab = QWidget()
        env_tab.setObjectName("tradeTab")
        env_layout_wrap = QVBoxLayout(env_tab)
        env_layout_wrap.setContentsMargins(12, 10, 18, 24)
        env_layout_wrap.setSpacing(8)
        env_layout_wrap.addWidget(cost_group)
        env_layout_wrap.addWidget(action_group)
        env_layout_wrap.addWidget(episode_group)
        env_layout_wrap.addWidget(reward_group)
        env_layout_wrap.addStretch(1)

        optuna_tab = QWidget()
        optuna_tab.setObjectName("advancedTab")
        optuna_layout_wrap = QVBoxLayout(optuna_tab)
        optuna_layout_wrap.setContentsMargins(12, 10, 18, 24)
        optuna_layout_wrap.setSpacing(8)
        optuna_hint = QLabel("Run a short search to find better PPO hyperparameters.")
        optuna_hint.setProperty("class", "dialog_hint")
        optuna_layout_wrap.addWidget(optuna_hint)
        optuna_layout_wrap.addWidget(optuna_group)

        self._optuna_search_button = QPushButton("Search Best Params")
        self._optuna_search_button.setProperty("class", PRIMARY)
        self._optuna_search_button.clicked.connect(self._emit_optuna)
        optuna_layout_wrap.addWidget(self._optuna_search_button)

        optuna_results = QGroupBox("Optuna Results")
        _apply_live_card_style(optuna_results)
        optuna_results_layout = QGridLayout(optuna_results)
        optuna_results_layout.setContentsMargins(12, 10, 12, 12)
        optuna_results_layout.setHorizontalSpacing(12)
        optuna_results_layout.setVerticalSpacing(8)
        optuna_results_layout.setColumnStretch(1, 1)

        trial_title = QLabel("Latest trial")
        trial_title.setProperty("class", "result_label")
        self._optuna_trial_summary = QLabel(format_optuna_empty_trial())
        self._optuna_trial_summary.setWordWrap(True)
        self._optuna_trial_summary.setProperty("class", "result_value")
        optuna_results_layout.addWidget(trial_title, 0, 0, Qt.AlignTop)
        optuna_results_layout.addWidget(self._optuna_trial_summary, 0, 1)

        best_title = QLabel("Best params")
        best_title.setProperty("class", "result_label")
        self._optuna_best_summary = QLabel(format_optuna_empty_best())
        self._optuna_best_summary.setWordWrap(True)
        self._optuna_best_summary.setProperty("class", "result_value")
        optuna_results_layout.addWidget(best_title, 1, 0, Qt.AlignTop)
        optuna_results_layout.addWidget(self._optuna_best_summary, 1, 1)
        optuna_layout_wrap.addWidget(optuna_results)

        optuna_layout_wrap.addStretch(1)

        tabs.addTab(training_tab, "Training")
        tabs.addTab(env_tab, "Environment")
        tabs.addTab(optuna_tab, "Optuna")
        self._apply_tabs_style(tabs)
        tabs.currentChanged.connect(self._on_tab_changed)
        outer_container = QGroupBox("")
        outer_container.setObjectName("card")
        outer_layout = QVBoxLayout(outer_container)
        outer_layout.setContentsMargins(12, 8, 12, 12)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(tabs)
        left_layout.addWidget(outer_container)

        self._load_params()
        self._load_optuna_defaults()
        self._update_data_metadata_preview(self._data_path.text().strip())
        self._bind_auto_save_handlers()

    def _apply_tabs_style(self, tabs: QTabWidget) -> None:
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
            QWidget#modelTab QGroupBox#card QLineEdit,
            QWidget#modelTab QGroupBox#card QComboBox,
            QWidget#modelTab QGroupBox#card QDoubleSpinBox,
            QWidget#modelTab QGroupBox#card QSpinBox,
            QWidget#tradeTab QGroupBox#card QLineEdit,
            QWidget#tradeTab QGroupBox#card QComboBox,
            QWidget#tradeTab QGroupBox#card QDoubleSpinBox,
            QWidget#tradeTab QGroupBox#card QSpinBox,
            QWidget#advancedTab QGroupBox#card QLineEdit,
            QWidget#advancedTab QGroupBox#card QComboBox,
            QWidget#advancedTab QGroupBox#card QDoubleSpinBox,
            QWidget#advancedTab QGroupBox#card QSpinBox {
                background: #1f252d;
                border: 1px solid #343c46;
                border-radius: 8px;
                min-height: 30px;
                padding: 2px 8px;
            }
            QWidget#modelTab QGroupBox#card QPushButton,
            QWidget#modelTab QGroupBox#card QToolButton {
                min-height: 30px;
            }
            """
        )

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
        if "gae_lambda" in params:
            self._gae_lambda.setValue(float(params["gae_lambda"]))
        if "clip_range" in params:
            self._clip_range.setValue(float(params["clip_range"]))
        if "vf_coef" in params:
            self._vf_coef.setValue(float(params["vf_coef"]))
        if "n_epochs" in params:
            self._n_epochs.setValue(int(params["n_epochs"]))
        if "episode_length" in params:
            self._episode_length.setValue(int(params["episode_length"]))
        if "reward_clip" in params:
            self._reward_clip.setValue(float(params["reward_clip"]))
        if "min_position_change" in params:
            self._min_position_change.setValue(float(params["min_position_change"]))
        if "position_step" in params:
            self._position_step.setValue(float(params["position_step"]))
        if "risk_aversion" in params:
            self._risk_aversion.setValue(float(params["risk_aversion"]))
        if "max_position" in params:
            self._max_position.setValue(float(params["max_position"]))

    def reset_optuna_results(self) -> None:
        self._optuna_trial_summary.setText(format_optuna_empty_trial())
        self._optuna_best_summary.setText(format_optuna_empty_best())

    def update_optuna_trial_summary(self, text: str) -> None:
        self._optuna_trial_summary.setText(format_optuna_trial_summary(text))

    def update_optuna_best_params(self, params: dict) -> None:
        if not params:
            return
        self._optuna_best_summary.setText(format_optuna_best_params(params))

    def get_params(self) -> dict:
        return {
            "data_path": self._data_path.text().strip(),
            "total_steps": int(self._total_steps.value()),
            "learning_rate": float(self._learning_rate.value()),
            "gamma": float(self._gamma.value()),
            "n_steps": int(self._n_steps.value()),
            "batch_size": int(self._batch_size.value()),
            "ent_coef": float(self._ent_coef.value()),
            "gae_lambda": float(self._gae_lambda.value()),
            "clip_range": float(self._clip_range.value()),
            "vf_coef": float(self._vf_coef.value()),
            "n_epochs": int(self._n_epochs.value()),
            "episode_length": int(self._episode_length.value()),
            "eval_split": float(self._eval_split.value()),
            "resume": bool(self._resume_training.isChecked()),
            "transaction_cost_bps": float(self._transaction_cost_bps.value()),
            "slippage_bps": float(self._slippage_bps.value()),
            "holding_cost_bps": float(self._holding_cost_bps.value()),
            "random_start": bool(self._random_start.isChecked()),
            "min_position_change": float(self._min_position_change.value()),
            "max_position": float(self._max_position.value()),
            "position_step": float(self._position_step.value()),
            "reward_scale": float(self._reward_scale.value()),
            "reward_clip": float(self._reward_clip.value()),
            "risk_aversion": float(self._risk_aversion.value()),
            "optuna_trials": int(self._optuna_trials.value()),
            "optuna_steps": int(self._optuna_steps.value()),
            "optuna_train_best": bool(self._optuna_train_best.isChecked()),
            "optuna_out": self._optuna_out.text().strip(),
            "optuna_only": False,
        }

    def _browse_data(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Training Data", self._data_path.text(), "CSV (*.csv)"
        )
        if path:
            self._data_path.setText(path)

    def _on_data_path_changed(self, text: str) -> None:
        cleaned = str(text).strip()
        self._data_path.setToolTip(cleaned)
        self._update_data_metadata_preview(cleaned)

    def _update_data_metadata_preview(self, csv_path: str) -> None:
        if not csv_path:
            self._data_meta.setText("No data file selected.")
            return
        path = Path(csv_path).expanduser()
        if not path.exists():
            self._data_meta.setText("CSV file not found.")
            return
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        if not meta_path.exists():
            self._data_meta.setText("Metadata not found (.meta.json).")
            return
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._data_meta.setText(f"Metadata parse failed: {exc}")
            return
        self._data_meta.setText(self._format_metadata_summary(payload))

    @staticmethod
    def _format_metadata_summary(payload: dict) -> str:
        if not isinstance(payload, dict):
            return "Metadata format invalid."
        details = payload.get("details", {})
        if not isinstance(details, dict):
            details = {}
        symbol = details.get("symbol_id", "unknown")
        timeframe = details.get("timeframe", "unknown")
        row_count = details.get("row_count", "unknown")
        schema_version = payload.get("schema_version", "unknown")
        return (
            f"symbol_id: {symbol}    timeframe: {timeframe}\n"
            f"rows: {row_count}    schema: {schema_version}"
        )

    def _browse_optuna_out(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Optuna Params", self._optuna_out.text(), "JSON (*.json)"
        )
        if path:
            self._optuna_out.setText(path)

    def _emit_optuna(self) -> None:
        params = self.get_params()
        params["optuna_only"] = True
        params["optuna_train_best"] = False
        self._save_params(params)
        self.optuna_requested.emit(params)
        self.reset_optuna_results()

    def _on_tab_changed(self, index: int) -> None:
        if index == 0:
            self.tab_changed.emit("training")
        elif index == 1:
            self.tab_changed.emit("environment")
        else:
            self.tab_changed.emit("optuna")


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

    def _save_params(self, params: dict) -> None:
        payload = dict(params)
        payload.pop("optuna_only", None)
        self._params_store.save(payload)

    def _load_params(self) -> None:
        self._loading_params = True
        data = self._params_store.load()
        if not data:
            self._loading_params = False
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
        if "gae_lambda" in data:
            self._gae_lambda.setValue(float(data["gae_lambda"]))
        if "clip_range" in data:
            self._clip_range.setValue(float(data["clip_range"]))
        if "vf_coef" in data:
            self._vf_coef.setValue(float(data["vf_coef"]))
        if "n_epochs" in data:
            self._n_epochs.setValue(int(data["n_epochs"]))
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
        if "holding_cost_bps" in data:
            self._holding_cost_bps.setValue(float(data["holding_cost_bps"]))
        if "random_start" in data:
            self._random_start.setChecked(bool(data["random_start"]))
        if "min_position_change" in data:
            self._min_position_change.setValue(float(data["min_position_change"]))
        if "max_position" in data:
            self._max_position.setValue(float(data["max_position"]))
        if "position_step" in data:
            self._position_step.setValue(float(data["position_step"]))
        if "reward_scale" in data:
            self._reward_scale.setValue(float(data["reward_scale"]))
        if "reward_clip" in data:
            self._reward_clip.setValue(float(data["reward_clip"]))
        if "risk_aversion" in data:
            self._risk_aversion.setValue(float(data["risk_aversion"]))
        if "optuna_trials" in data:
            self._optuna_trials.setValue(int(data["optuna_trials"]))
        if "optuna_steps" in data:
            self._optuna_steps.setValue(int(data["optuna_steps"]))
        if "optuna_train_best" in data:
            self._optuna_train_best.setChecked(bool(data["optuna_train_best"]))
        if "optuna_out" in data:
            self._optuna_out.setText(str(data["optuna_out"]))
        self._loading_params = False

    def _auto_save_params(self, *_args) -> None:
        if self._loading_params:
            return
        self._save_params(self.get_params())

    def _bind_auto_save_handlers(self) -> None:
        # Persist environment/training edits immediately to avoid losing tweaks
        # when the app restarts.
        self._transaction_cost_bps.valueChanged.connect(self._auto_save_params)
        self._slippage_bps.valueChanged.connect(self._auto_save_params)
        self._holding_cost_bps.valueChanged.connect(self._auto_save_params)
        self._min_position_change.valueChanged.connect(self._auto_save_params)
        self._max_position.valueChanged.connect(self._auto_save_params)
        self._position_step.valueChanged.connect(self._auto_save_params)
        self._episode_length.valueChanged.connect(self._auto_save_params)
        self._random_start.toggled.connect(self._auto_save_params)
        self._reward_scale.valueChanged.connect(self._auto_save_params)
        self._reward_clip.valueChanged.connect(self._auto_save_params)
        self._risk_aversion.valueChanged.connect(self._auto_save_params)
        self._gae_lambda.valueChanged.connect(self._auto_save_params)
        self._clip_range.valueChanged.connect(self._auto_save_params)
        self._vf_coef.valueChanged.connect(self._auto_save_params)
        self._n_epochs.valueChanged.connect(self._auto_save_params)


class TrainingPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_step = 0
        self._charts_available = pg is not None
        self._plot_timer = QElapsedTimer()
        self._plot_interval_ms = 50
        self._max_points = 2000
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
        self._metric_data: dict[str, dict[str, deque[float]]] = {}
        self._curves: dict[str, object] = {}
        self._checkboxes: dict[str, QCheckBox] = {}
        self._metric_labels = {key: label for label, key in self._metrics}
        self._legend_keys: set[str] = set()
        self._optuna_metrics = [
            ("trial_value", "trial value"),
            ("best_value", "best so far"),
            ("duration_sec", "duration (s)"),
        ]
        self._optuna_data: dict[str, dict[str, deque[float]]] = {}
        self._optuna_curves: dict[str, object] = {}
        self._optuna_legend_keys: set[str] = set()
        self._optuna_checkboxes: dict[str, QCheckBox] = {}
        self._optuna_visible: set[str] = set()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        if self._charts_available:
            plot = pg.PlotWidget()
            plot.setTitle("PPO Training Curve")
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
                self._metric_data[key] = {
                    "x": deque(maxlen=self._max_points),
                    "y": deque(maxlen=self._max_points),
                }

            optuna_plot = pg.PlotWidget()
            optuna_plot.setTitle("Optuna trials")
            optuna_plot.setLabel("bottom", "trial")
            optuna_plot.setLabel("left", "value")
            optuna_plot.showGrid(x=True, y=True, alpha=0.3)
            self._optuna_legend = optuna_plot.addLegend()
            self._optuna_plot = optuna_plot
            optuna_colors = ["#4C78A8", "#F58518", "#54A24B"]
            for index, (key, _) in enumerate(self._optuna_metrics):
                curve = optuna_plot.plot(
                    pen=pg.mkPen(optuna_colors[index % len(optuna_colors)], width=2)
                )
                self._optuna_curves[key] = curve
                self._optuna_data[key] = {
                    "x": deque(maxlen=self._max_points),
                    "y": deque(maxlen=self._max_points),
                }
                if key in {"trial_value", "best_value"}:
                    self._optuna_visible.add(key)
                else:
                    self._optuna_curves[key].setData([], [])

            optuna_selector = QWidget()
            optuna_selector_layout = QGridLayout(optuna_selector)
            optuna_selector_layout.setContentsMargins(0, 0, 0, 0)
            optuna_selector_layout.setHorizontalSpacing(10)
            optuna_selector_layout.setVerticalSpacing(4)
            for idx, (key, label) in enumerate(self._optuna_metrics):
                checkbox = QCheckBox(label)
                checked = key in {"trial_value", "best_value"}
                checkbox.setChecked(checked)
                checkbox.toggled.connect(
                    lambda checked_state, k=key: self._toggle_optuna_curve(k, checked_state)
                )
                self._optuna_checkboxes[key] = checkbox
                optuna_selector_layout.addWidget(checkbox, idx // 3, idx % 3)

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

            self._chart_stack = QStackedWidget()
            self._chart_stack.addWidget(plot)
            self._chart_stack.addWidget(optuna_plot)
            self._chart_stack.setCurrentWidget(plot)
            self._metrics_selector = chooser
            self._optuna_selector = optuna_selector
            layout.addWidget(self._chart_stack, stretch=1)
            layout.addWidget(chooser)
            layout.addWidget(optuna_selector)
            optuna_selector.setVisible(False)
            self._sync_curve_visibility()
            self._sync_optuna_curve_visibility()
        else:
            notice = QLabel("PyQtGraph is not installed. Install pyqtgraph to show charts.")
            notice.setWordWrap(True)
            layout.addWidget(notice)

    def reset_metrics(self) -> None:
        if not self._charts_available:
            return
        self._current_step = 0
        self._plot_timer.restart()
        for key in self._metric_data:
            self._metric_data[key]["x"].clear()
            self._metric_data[key]["y"].clear()
            self._curves[key].setData([])
        self._sync_curve_visibility()

    def reset_optuna_metrics(self) -> None:
        if not self._charts_available:
            return
        for key in self._optuna_data:
            self._optuna_data[key]["x"].clear()
            self._optuna_data[key]["y"].clear()
            self._optuna_curves[key].setData([])
        for key in self._optuna_visible:
            self._optuna_curves[key].setData([])

    def flush_plot(self) -> None:
        if not self._charts_available:
            return
        for _, key in self._metrics:
            if not self._checkboxes[key].isChecked():
                continue
            data = self._metric_data[key]
            self._curves[key].setData(list(data["x"]), list(data["y"]))

    def append_metric_point(self, key: str, step: float, value: float) -> None:
        if not self._charts_available:
            return
        if key not in self._metric_labels:
            return
        self._append_point(key, step, value)

    def append_optuna_point(self, key: str, trial: float, value: float) -> None:
        if not self._charts_available:
            return
        if key not in self._optuna_data:
            return
        self._append_optuna_point(key, trial, value)

    def show_training_plot(self) -> None:
        if not self._charts_available:
            return
        self._chart_stack.setCurrentWidget(self._plot)
        self._metrics_selector.setVisible(True)
        self._optuna_selector.setVisible(False)

    def show_optuna_plot(self) -> None:
        if not self._charts_available:
            return
        self._chart_stack.setCurrentWidget(self._optuna_plot)
        self._metrics_selector.setVisible(False)
        self._optuna_selector.setVisible(True)

    def _append_point(self, key: str, step: float, value: float) -> None:
        data = self._metric_data[key]
        data["x"].append(step)
        data["y"].append(value)
        if self._checkboxes[key].isChecked():
            if not self._plot_timer.isValid():
                self._plot_timer.start()
            if self._plot_timer.elapsed() < self._plot_interval_ms:
                return
            self._curves[key].setData(list(data["x"]), list(data["y"]))
            self._plot_timer.restart()

    def _append_optuna_point(self, key: str, trial: float, value: float) -> None:
        data = self._optuna_data[key]
        data["x"].append(trial)
        data["y"].append(value)
        if key in self._optuna_curves and key in self._optuna_visible:
            self._optuna_curves[key].setData(list(data["x"]), list(data["y"]))

    def _toggle_curve(self, key: str, visible: bool) -> None:
        data = self._metric_data[key]
        if visible:
            self._curves[key].setData(list(data["x"]), list(data["y"]))
            if key not in self._legend_keys:
                self._legend.addItem(self._curves[key], self._metric_labels[key])
                self._legend_keys.add(key)
            if data["y"]:
                self._curves[key].setData(list(data["x"]), list(data["y"]))
        else:
            self._curves[key].setData([], [])
            if key in self._legend_keys:
                self._legend.removeItem(self._curves[key])
                self._legend_keys.remove(key)

    def _toggle_optuna_curve(self, key: str, visible: bool) -> None:
        data = self._optuna_data[key]
        if visible:
            self._optuna_visible.add(key)
            self._optuna_curves[key].setData(list(data["x"]), list(data["y"]))
            if key not in self._optuna_legend_keys:
                label = dict(self._optuna_metrics)[key]
                self._optuna_legend.addItem(self._optuna_curves[key], label)
                self._optuna_legend_keys.add(key)
        else:
            self._optuna_visible.discard(key)
            self._optuna_curves[key].setData([], [])
            if key in self._optuna_legend_keys:
                self._optuna_legend.removeItem(self._optuna_curves[key])
                self._optuna_legend_keys.remove(key)

    def _sync_curve_visibility(self) -> None:
        for _, key in self._metrics:
            self._toggle_curve(key, self._checkboxes[key].isChecked())

    def _sync_optuna_curve_visibility(self) -> None:
        for key, _ in self._optuna_metrics:
            self._toggle_optuna_curve(key, key in self._optuna_visible)

    @staticmethod
    def _parse_kv_line(line: str) -> Optional[tuple[str, float]]:
        parts = [part.strip() for part in line.split("|") if part.strip()]
        if len(parts) < 2:
            return None
        try:
            return parts[0], float(parts[1])
        except ValueError:
            return None

    @staticmethod
    def _parse_csv_line(line: str) -> Optional[tuple[int, str, float]]:
        if "," not in line:
            return None
        parts = line.strip().split(",", 2)
        if len(parts) != 3:
            return None
        try:
            step = int(parts[0])
            metric = parts[1]
            value = float(parts[2])
        except ValueError:
            return None
        return step, metric, value

    @staticmethod
    def _parse_optuna_csv_line(line: str) -> Optional[tuple[float, float, float, float]]:
        if "," not in line:
            return None
        parts = line.strip().split(",", 3)
        if len(parts) != 4:
            return None
        if parts[0] == "trial":
            return None
        try:
            trial = float(parts[0])
            trial_value = float(parts[1])
            best_value = float(parts[2])
            duration = float(parts[3])
        except ValueError:
            return None
        return trial, trial_value, best_value, duration

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

    @staticmethod
    def _parse_int(key: str, line: str) -> Optional[int]:
        value = TrainingPanel._parse_float(key, line)
        if value is None:
            return None
        return int(value)
