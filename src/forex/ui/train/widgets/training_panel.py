from __future__ import annotations

import csv
import json
import math
from datetime import datetime
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
    QComboBox,
    QLineEdit,
    QFileDialog,
    QSizePolicy,
    QGroupBox,
    QTabWidget,
    QStackedWidget,
    QInputDialog,
    QMessageBox,
    QRadioButton,
    QSplitter,
    QDialog,
    QPlainTextEdit,
    QScrollArea,
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
from forex.ui.shared.widgets.log_widget import LogWidget
from forex.ui.shared.utils.path_utils import latest_file_in_dir
from forex.ui.shared.styles.tokens import FORM_LABEL_WIDTH_COMPACT, PRIMARY, TRAINING_PARAMS
from forex.config.paths import DATA_DIR, RAW_HISTORY_DIR
from forex.ml.rl.features.feature_builder import (
    ALPHA_FEATURE_COLUMNS,
    RESIDUAL_CONTEXT_COLUMNS,
    build_feature_frame,
    load_csv,
)
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


if pg is not None:
    class IntegerAxisItem(pg.AxisItem):
        def tickStrings(self, values, scale, spacing):  # pragma: no cover - UI formatting
            labels = []
            for value in values:
                rounded = int(round(value))
                if abs(value - rounded) < 1e-6:
                    labels.append(str(rounded))
                else:
                    labels.append("")
            return labels


class AdaptiveFormGrid(QWidget):
    """Responsive field grid: auto-wraps rows by available width."""

    def __init__(
        self,
        *,
        min_cell_width: int = 360,
        label_min_width: int = 0,
        max_columns: int = 2,
        split_labels: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._min_cell_width = max(220, int(min_cell_width))
        self._label_min_width = max(0, int(label_min_width))
        self._max_columns = max(1, int(max_columns))
        self._split_labels = bool(split_labels)
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
        label.setWordWrap(True)
        row.addWidget(label, 0, Qt.AlignLeft)
        row.addWidget(field, 0, Qt.AlignLeft)
        row.addStretch(1)
        self._cells.append(cell)
        self._labels.append(label)
        self._rebuild()

    def _format_label_text(self, label_text: str) -> str:
        text = str(label_text or "").strip()
        if not text or "\n" in text:
            return text
        if self._split_labels and " " in text:
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


class TrimmedDoubleSpinBox(QDoubleSpinBox):
    """Display decimals without trailing zeros while preserving numeric precision."""

    def textFromValue(self, value: float) -> str:  # pragma: no cover - Qt formatting
        text = super().textFromValue(value)
        if "." not in text:
            return text
        text = text.rstrip("0").rstrip(".")
        return text if text else "0"


class TrainingParamsPanel(QWidget):
    start_requested = Signal(dict)
    stop_requested = Signal()
    optuna_requested = Signal(dict)
    tab_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._training_running = False
        self._loading_params = False
        self._data_feature_names: list[str] = []
        self._selected_feature_names: list[str] = []
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
        self._view_features_button = QPushButton("View Features")
        self._view_features_button.setEnabled(False)
        self._view_features_button.clicked.connect(self._show_feature_list_dialog)
        file_layout.addRow("", self._view_features_button)

        params_group = QGroupBox("Training Params")
        _apply_live_card_style(params_group)
        params_group_layout = QVBoxLayout(params_group)
        params_group_layout.setContentsMargins(12, 10, 12, 12)
        params_group_layout.setSpacing(8)
        params_layout = AdaptiveFormGrid(min_cell_width=260, label_min_width=0, max_columns=2)
        params_group_layout.addWidget(params_layout)

        self._total_steps = QSpinBox()
        self._total_steps.setRange(1, 10_000_000)
        self._total_steps.setValue(300_000)
        self._total_steps.setFixedWidth(spin_width)
        params_layout.add_row("total_steps", self._total_steps)

        self._learning_rate = TrimmedDoubleSpinBox()
        self._learning_rate.setRange(1e-6, 1.0)
        self._learning_rate.setDecimals(10)
        self._learning_rate.setSingleStep(1e-4)
        self._learning_rate.setValue(1e-4)
        self._learning_rate.setFixedWidth(spin_width)
        params_layout.add_row("learning_rate", self._learning_rate)

        self._gamma = TrimmedDoubleSpinBox()
        self._gamma.setRange(0.0, 0.9999)
        self._gamma.setDecimals(10)
        self._gamma.setSingleStep(0.001)
        self._gamma.setValue(0.995)
        self._gamma.setFixedWidth(spin_width)
        params_layout.add_row("gamma", self._gamma)

        self._n_steps = QSpinBox()
        self._n_steps.setRange(1, 8192)
        self._n_steps.setValue(4096)
        self._n_steps.setFixedWidth(spin_width)
        params_layout.add_row("n_steps", self._n_steps)

        self._batch_size = QSpinBox()
        self._batch_size.setRange(1, 4096)
        self._batch_size.setValue(256)
        self._batch_size.setFixedWidth(spin_width)
        params_layout.add_row("batch_size", self._batch_size)

        self._ent_coef = TrimmedDoubleSpinBox()
        self._ent_coef.setRange(0.0, 1.0)
        # Optuna often finds very small entropy coefficients (e.g. 1e-5),
        # so keep enough visible precision to avoid displaying as 0.0000.
        self._ent_coef.setDecimals(10)
        self._ent_coef.setSingleStep(0.00001)
        self._ent_coef.setValue(5e-4)
        self._ent_coef.setFixedWidth(spin_width)
        params_layout.add_row("ent_coef", self._ent_coef)

        self._eval_split = TrimmedDoubleSpinBox()
        self._eval_split.setRange(0.05, 0.5)
        self._eval_split.setDecimals(3)
        self._eval_split.setSingleStep(0.01)
        self._eval_split.setValue(0.2)
        self._eval_split.setFixedWidth(spin_width)
        params_layout.add_row("eval_split", self._eval_split)

        self._device = QComboBox()
        self._device.addItems(["Auto", "CPU", "MPS", "CUDA"])
        self._device.setCurrentIndex(0)
        self._device.setFixedWidth(spin_width)
        self._device.setToolTip("Training device selection. Auto lets Stable-Baselines3 choose.")
        params_layout.add_row("device", self._device)

        ppo_advanced_group = QGroupBox("PPO Advanced")
        _apply_live_card_style(ppo_advanced_group)
        ppo_advanced_group_layout = QVBoxLayout(ppo_advanced_group)
        ppo_advanced_group_layout.setContentsMargins(12, 10, 12, 12)
        ppo_advanced_group_layout.setSpacing(8)
        ppo_advanced_layout = AdaptiveFormGrid(min_cell_width=260, label_min_width=0, max_columns=2)
        ppo_advanced_group_layout.addWidget(ppo_advanced_layout)

        self._gae_lambda = TrimmedDoubleSpinBox()
        self._gae_lambda.setRange(0.0, 1.0)
        self._gae_lambda.setDecimals(10)
        self._gae_lambda.setSingleStep(0.01)
        self._gae_lambda.setValue(0.98)
        self._gae_lambda.setFixedWidth(spin_width)
        ppo_advanced_layout.add_row("gae_lambda", self._gae_lambda)

        self._clip_range = TrimmedDoubleSpinBox()
        self._clip_range.setRange(0.01, 1.0)
        self._clip_range.setDecimals(10)
        self._clip_range.setSingleStep(0.01)
        self._clip_range.setValue(0.15)
        self._clip_range.setFixedWidth(spin_width)
        ppo_advanced_layout.add_row("clip_range", self._clip_range)

        self._target_kl = TrimmedDoubleSpinBox()
        self._target_kl.setRange(0.0, 1.0)
        self._target_kl.setDecimals(10)
        self._target_kl.setSingleStep(0.001)
        self._target_kl.setValue(0.02)
        self._target_kl.setFixedWidth(spin_width)
        self._target_kl.setToolTip("0 disables PPO target_kl early stopping inside each update.")
        ppo_advanced_layout.add_row("target_kl", self._target_kl)

        self._vf_coef = TrimmedDoubleSpinBox()
        self._vf_coef.setRange(0.0, 2.0)
        self._vf_coef.setDecimals(10)
        self._vf_coef.setSingleStep(0.01)
        self._vf_coef.setValue(0.7)
        self._vf_coef.setFixedWidth(spin_width)
        ppo_advanced_layout.add_row("vf_coef", self._vf_coef)

        self._n_epochs = QSpinBox()
        self._n_epochs.setRange(1, 200)
        self._n_epochs.setValue(10)
        self._n_epochs.setFixedWidth(spin_width)
        ppo_advanced_layout.add_row("n_epochs", self._n_epochs)

        options_group = QWidget()
        options_layout = QVBoxLayout(options_group)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(12)

        def _wrap_field(widget: QWidget) -> QWidget:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            layout.addWidget(widget)
            return container

        def _build_run_section(title: str, checkbox: QCheckBox, note: str) -> tuple[QGroupBox, AdaptiveFormGrid]:
            group = QGroupBox(title)
            _apply_live_card_style(group)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(12, 10, 12, 12)
            group_layout.setSpacing(8)

            header_row = QHBoxLayout()
            header_row.setContentsMargins(0, 0, 0, 0)
            header_row.setSpacing(10)
            note_label = QLabel(note)
            note_label.setProperty("class", "dialog_hint")
            note_label.setWordWrap(True)
            header_row.addWidget(note_label, 1)
            header_row.addWidget(checkbox, 0, Qt.AlignRight | Qt.AlignVCenter)
            group_layout.addLayout(header_row)

            grid = AdaptiveFormGrid(
                min_cell_width=250,
                label_min_width=0,
                max_columns=2,
                split_labels=True,
            )
            group_layout.addWidget(grid)
            return group, grid

        self._early_stop_enabled = QCheckBox("Enabled")
        self._early_stop_enabled.setChecked(True)
        self._curriculum_enabled = QCheckBox("Enabled")
        self._curriculum_enabled.setChecked(False)
        self._anti_flat_enabled = QCheckBox("Enabled")
        self._anti_flat_enabled.setChecked(True)
        self._save_best_checkpoint = QCheckBox("Enabled")
        self._save_best_checkpoint.setChecked(True)

        self._early_stop_setting_cards: list[QWidget] = []
        self._curriculum_setting_cards: list[QWidget] = []
        self._anti_flat_setting_cards: list[QWidget] = []

        checkpoint_group, checkpoint_layout = _build_run_section(
            "Checkpointing",
            self._save_best_checkpoint,
            "Promote the strongest validation checkpoint instead of whatever weights happen to be last.",
        )
        options_layout.addWidget(checkpoint_group)

        early_stop_group, early_stop_layout = _build_run_section(
            "Early Stop",
            self._early_stop_enabled,
            "End the run once validation stalls, so long tails do not overwrite a good checkpoint.",
        )
        options_layout.addWidget(early_stop_group)

        curriculum_group, curriculum_layout = _build_run_section(
            "Curriculum",
            self._curriculum_enabled,
            "Start with a smaller discrete action space, then switch back to the target config.",
        )

        anti_flat_group, anti_flat_layout = _build_run_section(
            "Anti-flat",
            self._anti_flat_enabled,
            "Profile eval activity and stop runs that collapse into no-trade or one-sided behavior.",
        )

        self._early_stop_warmup_steps = QSpinBox()
        self._early_stop_warmup_steps.setRange(0, 10_000_000)
        self._early_stop_warmup_steps.setValue(100_000)
        self._early_stop_warmup_steps.setFixedWidth(spin_width)
        early_stop_layout.add_row("Warmup steps", _wrap_field(self._early_stop_warmup_steps))
        self._early_stop_patience_evals = QSpinBox()
        self._early_stop_patience_evals.setRange(1, 100)
        self._early_stop_patience_evals.setValue(6)
        self._early_stop_patience_evals.setFixedWidth(spin_width)
        early_stop_layout.add_row("Patience evals", _wrap_field(self._early_stop_patience_evals))
        self._early_stop_min_delta = TrimmedDoubleSpinBox()
        self._early_stop_min_delta.setRange(0.0, 10.0)
        self._early_stop_min_delta.setDecimals(6)
        self._early_stop_min_delta.setSingleStep(0.0005)
        self._early_stop_min_delta.setValue(0.0005)
        self._early_stop_min_delta.setFixedWidth(spin_width)
        early_stop_layout.add_row("Min improvement", _wrap_field(self._early_stop_min_delta))
        self._early_stop_setting_cards.append(early_stop_group)

        self._seed = QSpinBox()
        self._seed.setRange(0, 2_147_483_647)
        self._seed.setValue(0)
        self._seed.setFixedWidth(spin_width)
        checkpoint_layout.add_row("Seed", _wrap_field(self._seed))

        self._curriculum_steps = QSpinBox()
        self._curriculum_steps.setRange(0, 10_000_000)
        self._curriculum_steps.setValue(25_000)
        self._curriculum_steps.setFixedWidth(spin_width)
        curriculum_layout.add_row("Curriculum steps", _wrap_field(self._curriculum_steps))

        self._curriculum_max_position = TrimmedDoubleSpinBox()
        self._curriculum_max_position.setRange(0.0, 10.0)
        self._curriculum_max_position.setDecimals(3)
        self._curriculum_max_position.setSingleStep(0.05)
        self._curriculum_max_position.setValue(0.2)
        self._curriculum_max_position.setFixedWidth(spin_width)
        curriculum_layout.add_row("Curriculum max pos", _wrap_field(self._curriculum_max_position))

        self._curriculum_position_step = TrimmedDoubleSpinBox()
        self._curriculum_position_step.setRange(0.0, 1.0)
        self._curriculum_position_step.setDecimals(3)
        self._curriculum_position_step.setSingleStep(0.01)
        self._curriculum_position_step.setValue(0.1)
        self._curriculum_position_step.setFixedWidth(spin_width)
        curriculum_layout.add_row("Curriculum step", _wrap_field(self._curriculum_position_step))

        self._curriculum_min_position_change = TrimmedDoubleSpinBox()
        self._curriculum_min_position_change.setRange(0.0, 1.0)
        self._curriculum_min_position_change.setDecimals(3)
        self._curriculum_min_position_change.setSingleStep(0.01)
        self._curriculum_min_position_change.setValue(0.05)
        self._curriculum_min_position_change.setFixedWidth(spin_width)
        curriculum_layout.add_row("Curriculum min change", _wrap_field(self._curriculum_min_position_change))
        self._curriculum_setting_cards.append(curriculum_group)

        self._anti_flat_warmup_steps = QSpinBox()
        self._anti_flat_warmup_steps.setRange(0, 10_000_000)
        self._anti_flat_warmup_steps.setValue(50_000)
        self._anti_flat_warmup_steps.setFixedWidth(spin_width)
        anti_flat_layout.add_row("Anti-flat warmup", _wrap_field(self._anti_flat_warmup_steps))

        self._anti_flat_patience_evals = QSpinBox()
        self._anti_flat_patience_evals.setRange(1, 100)
        self._anti_flat_patience_evals.setValue(3)
        self._anti_flat_patience_evals.setFixedWidth(spin_width)
        anti_flat_layout.add_row("Anti-flat patience", _wrap_field(self._anti_flat_patience_evals))

        self._anti_flat_min_trade_rate = TrimmedDoubleSpinBox()
        self._anti_flat_min_trade_rate.setRange(0.0, 100.0)
        self._anti_flat_min_trade_rate.setDecimals(3)
        self._anti_flat_min_trade_rate.setSingleStep(0.1)
        self._anti_flat_min_trade_rate.setValue(5.0)
        self._anti_flat_min_trade_rate.setFixedWidth(spin_width)
        anti_flat_layout.add_row("Min trades/1k", _wrap_field(self._anti_flat_min_trade_rate))

        self._anti_flat_max_flat_ratio = TrimmedDoubleSpinBox()
        self._anti_flat_max_flat_ratio.setRange(0.0, 1.0)
        self._anti_flat_max_flat_ratio.setDecimals(3)
        self._anti_flat_max_flat_ratio.setSingleStep(0.01)
        self._anti_flat_max_flat_ratio.setValue(0.98)
        self._anti_flat_max_flat_ratio.setFixedWidth(spin_width)
        anti_flat_layout.add_row("Max flat ratio", _wrap_field(self._anti_flat_max_flat_ratio))

        self._anti_flat_max_ls_imbalance = TrimmedDoubleSpinBox()
        self._anti_flat_max_ls_imbalance.setRange(0.0, 1.0)
        self._anti_flat_max_ls_imbalance.setDecimals(3)
        self._anti_flat_max_ls_imbalance.setSingleStep(0.01)
        self._anti_flat_max_ls_imbalance.setValue(0.2)
        self._anti_flat_max_ls_imbalance.setFixedWidth(spin_width)
        anti_flat_layout.add_row("Max L/S imbalance", _wrap_field(self._anti_flat_max_ls_imbalance))

        self._anti_flat_profile_steps = QSpinBox()
        self._anti_flat_profile_steps.setRange(0, 1_000_000)
        self._anti_flat_profile_steps.setValue(2_500)
        self._anti_flat_profile_steps.setFixedWidth(spin_width)
        anti_flat_layout.add_row("Profile steps", _wrap_field(self._anti_flat_profile_steps))
        self._anti_flat_setting_cards.append(anti_flat_group)

        self._resolved_device = QLabel("-")
        self._resolved_device.setProperty("class", "result_value")
        runtime_card = QGroupBox("")
        runtime_card.setObjectName("card")
        runtime_layout = QHBoxLayout(runtime_card)
        runtime_layout.setContentsMargins(14, 12, 14, 12)
        runtime_layout.setSpacing(12)
        runtime_title = QLabel("Resolved device")
        runtime_title.setProperty("class", "result_label")
        runtime_layout.addWidget(runtime_title)
        runtime_layout.addStretch(1)
        runtime_layout.addWidget(self._resolved_device)
        options_layout.addWidget(runtime_card)
        self._sync_early_stop_controls()
        self._sync_curriculum_controls()
        self._sync_anti_flat_controls()
        self._sync_batch_size_limit()

        cost_group = QGroupBox("Cost & Friction")
        _apply_live_card_style(cost_group)
        cost_group_layout = QVBoxLayout(cost_group)
        cost_group_layout.setContentsMargins(12, 10, 12, 12)
        cost_group_layout.setSpacing(8)
        cost_layout = AdaptiveFormGrid(min_cell_width=250, label_min_width=0, max_columns=2)
        cost_group_layout.addWidget(cost_layout)

        self._transaction_cost_bps = TrimmedDoubleSpinBox()
        self._transaction_cost_bps.setRange(0.0, 100.0)
        self._transaction_cost_bps.setDecimals(3)
        self._transaction_cost_bps.setSingleStep(0.1)
        self._transaction_cost_bps.setValue(1.0)
        self._transaction_cost_bps.setFixedWidth(spin_width)
        cost_layout.add_row(
            "Transaction cost (bps)",
            _wrap_field(self._transaction_cost_bps),
        )

        self._slippage_bps = TrimmedDoubleSpinBox()
        self._slippage_bps.setRange(0.0, 100.0)
        self._slippage_bps.setDecimals(3)
        self._slippage_bps.setSingleStep(0.1)
        self._slippage_bps.setValue(0.5)
        self._slippage_bps.setFixedWidth(spin_width)
        cost_layout.add_row(
            "Slippage (bps)",
            _wrap_field(self._slippage_bps),
        )

        self._holding_cost_bps = TrimmedDoubleSpinBox()
        self._holding_cost_bps.setRange(0.0, 100.0)
        self._holding_cost_bps.setDecimals(3)
        self._holding_cost_bps.setSingleStep(0.1)
        self._holding_cost_bps.setValue(0.1)
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

        self._min_position_change = TrimmedDoubleSpinBox()
        self._min_position_change.setRange(0.0, 1.0)
        self._min_position_change.setDecimals(3)
        self._min_position_change.setSingleStep(0.01)
        self._min_position_change.setValue(0.05)
        self._min_position_change.setFixedWidth(spin_width)
        action_layout.add_row(
            "Min position change",
            _wrap_field(self._min_position_change),
        )

        self._max_position = TrimmedDoubleSpinBox()
        self._max_position.setRange(0.0, 10.0)
        self._max_position.setDecimals(3)
        self._max_position.setSingleStep(0.1)
        self._max_position.setValue(1.0)
        self._max_position.setFixedWidth(spin_width)
        action_layout.add_row(
            "Max position",
            _wrap_field(self._max_position),
        )

        self._position_step = TrimmedDoubleSpinBox()
        self._position_step.setRange(0.0, 1.0)
        self._position_step.setDecimals(3)
        self._position_step.setSingleStep(0.01)
        self._position_step.setValue(0.1)
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
        self._episode_length.setValue(4096)
        self._episode_length.setFixedWidth(spin_width)
        episode_layout.add_row(
            "Episode length",
            _wrap_field(self._episode_length),
        )

        self._reward_horizon = QSpinBox()
        self._reward_horizon.setRange(1, 128)
        self._reward_horizon.setValue(4)
        self._reward_horizon.setFixedWidth(spin_width)
        episode_layout.add_row(
            "Reward horizon",
            _wrap_field(self._reward_horizon),
        )

        self._window_size = QSpinBox()
        self._window_size.setRange(1, 128)
        self._window_size.setValue(16)
        self._window_size.setFixedWidth(spin_width)
        episode_layout.add_row(
            "Window size",
            _wrap_field(self._window_size),
        )

        self._start_mode = QComboBox()
        self._start_mode.addItems(["Random", "First row", "Weekly open"])
        self._start_mode.setCurrentIndex(0)
        self._start_mode.setFixedWidth(spin_width)
        episode_layout.add_row(
            "Start mode",
            _wrap_field(self._start_mode),
        )

        self._feature_profile = QComboBox()
        self._feature_profile.addItems(["Raw 53 features", "Alpha layer (4)", "Alpha + context (residual)"])
        self._feature_profile.setCurrentIndex(2)
        self._feature_profile.setMinimumContentsLength(24)
        self._feature_profile.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self._feature_profile.setFixedWidth(max(spin_width, 280))
        self._feature_profile.setToolTip(
            "Choose which feature profile to feed into PPO. "
            "Residual uses alpha layer plus a small execution context."
        )
        episode_layout.add_row(
            "Feature profile",
            _wrap_field(self._feature_profile),
        )

        reward_group = QGroupBox("Reward shaping")
        _apply_live_card_style(reward_group)
        reward_group_layout = QVBoxLayout(reward_group)
        reward_group_layout.setContentsMargins(12, 10, 12, 12)
        reward_group_layout.setSpacing(8)
        reward_layout = AdaptiveFormGrid(min_cell_width=250, label_min_width=0, max_columns=2)
        reward_group_layout.addWidget(reward_layout)

        self._reward_scale = TrimmedDoubleSpinBox()
        self._reward_scale.setRange(0.0, 10000.0)
        self._reward_scale.setDecimals(3)
        self._reward_scale.setSingleStep(0.1)
        self._reward_scale.setValue(1.0)
        self._reward_scale.setFixedWidth(spin_width)
        reward_layout.add_row(
            "Reward scale",
            _wrap_field(self._reward_scale),
        )

        self._reward_clip = TrimmedDoubleSpinBox()
        self._reward_clip.setRange(0.0, 10.0)
        self._reward_clip.setDecimals(3)
        self._reward_clip.setSingleStep(0.1)
        self._reward_clip.setValue(0.02)
        self._reward_clip.setFixedWidth(spin_width)
        reward_layout.add_row(
            "Reward clip",
            _wrap_field(self._reward_clip),
        )

        self._reward_mode = QComboBox()
        self._reward_mode.addItems(["Linear PnL", "Log return", "Risk-adjusted log return"])
        self._reward_mode.setCurrentIndex(2)
        self._reward_mode.setFixedWidth(spin_width)
        self._reward_mode.setToolTip(
            "Linear PnL keeps the legacy reward. Log return uses log(1 + net return). "
            "Risk-adjusted log return adds downside-only penalty on top of log return."
        )
        reward_layout.add_row(
            "Reward mode",
            _wrap_field(self._reward_mode),
        )

        self._risk_aversion = TrimmedDoubleSpinBox()
        self._risk_aversion.setRange(0.0, 10.0)
        self._risk_aversion.setDecimals(3)
        self._risk_aversion.setSingleStep(0.1)
        self._risk_aversion.setValue(0.5)
        self._risk_aversion.setFixedWidth(spin_width)
        reward_layout.add_row(
            "Risk aversion",
            _wrap_field(self._risk_aversion),
        )

        self._drawdown_penalty = TrimmedDoubleSpinBox()
        self._drawdown_penalty.setRange(0.0, 10.0)
        self._drawdown_penalty.setDecimals(3)
        self._drawdown_penalty.setSingleStep(0.01)
        self._drawdown_penalty.setValue(2.0)
        self._drawdown_penalty.setFixedWidth(spin_width)
        self._drawdown_penalty.setToolTip(
            "Penalty applied only when drawdown worsens: drawdown_penalty * max(0, drawdown_t - drawdown_t-1)."
        )
        reward_layout.add_row(
            "Drawdown penalty",
            _wrap_field(self._drawdown_penalty),
        )

        self._downside_penalty = TrimmedDoubleSpinBox()
        self._downside_penalty.setRange(0.0, 10.0)
        self._downside_penalty.setDecimals(3)
        self._downside_penalty.setSingleStep(0.01)
        self._downside_penalty.setValue(1.0)
        self._downside_penalty.setFixedWidth(spin_width)
        self._downside_penalty.setToolTip(
            "Penalty applied only in risk-adjusted log return mode: "
            "downside_penalty * min(0, net_return)^2."
        )
        reward_layout.add_row(
            "Downside penalty",
            _wrap_field(self._downside_penalty),
        )

        self._turnover_penalty = TrimmedDoubleSpinBox()
        self._turnover_penalty.setRange(0.0, 1.0)
        self._turnover_penalty.setDecimals(6)
        self._turnover_penalty.setSingleStep(0.0001)
        self._turnover_penalty.setValue(5e-4)
        self._turnover_penalty.setFixedWidth(spin_width)
        self._turnover_penalty.setToolTip(
            "Extra penalty applied to absolute position change to discourage excess turnover."
        )
        reward_layout.add_row(
            "Turnover penalty",
            _wrap_field(self._turnover_penalty),
        )

        self._exposure_penalty = TrimmedDoubleSpinBox()
        self._exposure_penalty.setRange(0.0, 1.0)
        self._exposure_penalty.setDecimals(6)
        self._exposure_penalty.setSingleStep(0.0001)
        self._exposure_penalty.setValue(1e-4)
        self._exposure_penalty.setFixedWidth(spin_width)
        self._exposure_penalty.setToolTip(
            "Penalty applied to absolute target exposure to discourage oversized persistent positions."
        )
        reward_layout.add_row(
            "Exposure penalty",
            _wrap_field(self._exposure_penalty),
        )

        self._flat_position_penalty = TrimmedDoubleSpinBox()
        self._flat_position_penalty.setRange(0.0, 1.0)
        self._flat_position_penalty.setDecimals(6)
        self._flat_position_penalty.setSingleStep(0.0001)
        self._flat_position_penalty.setValue(0.0)
        self._flat_position_penalty.setFixedWidth(spin_width)
        self._flat_position_penalty.setToolTip(
            "Penalty applied only when the policy stays flat from one step to the next."
        )
        reward_layout.add_row(
            "Flat hold penalty",
            _wrap_field(self._flat_position_penalty),
        )

        self._flat_streak_penalty = TrimmedDoubleSpinBox()
        self._flat_streak_penalty.setRange(0.0, 1.0)
        self._flat_streak_penalty.setDecimals(6)
        self._flat_streak_penalty.setSingleStep(0.0001)
        self._flat_streak_penalty.setValue(0.0)
        self._flat_streak_penalty.setFixedWidth(spin_width)
        self._flat_streak_penalty.setToolTip(
            "Extra per-step penalty multiplied by consecutive flat-hold steps after the first."
        )
        reward_layout.add_row(
            "Flat streak penalty",
            _wrap_field(self._flat_streak_penalty),
        )

        self._flat_position_threshold = TrimmedDoubleSpinBox()
        self._flat_position_threshold.setRange(0.0, 0.1)
        self._flat_position_threshold.setDecimals(6)
        self._flat_position_threshold.setSingleStep(0.001)
        self._flat_position_threshold.setValue(1e-6)
        self._flat_position_threshold.setFixedWidth(spin_width)
        self._flat_position_threshold.setToolTip(
            "Absolute position threshold treated as flat for the flat-hold penalties."
        )
        reward_layout.add_row(
            "Flat threshold",
            _wrap_field(self._flat_position_threshold),
        )

        self._target_vol = TrimmedDoubleSpinBox()
        self._target_vol.setRange(0.0, 10.0)
        self._target_vol.setDecimals(4)
        self._target_vol.setSingleStep(0.001)
        self._target_vol.setValue(0.005)
        self._target_vol.setFixedWidth(spin_width)
        self._target_vol.setToolTip(
            "Target realized volatility used to scale raw positions. 0 disables volatility targeting."
        )
        reward_layout.add_row(
            "Target vol",
            _wrap_field(self._target_vol),
        )

        self._vol_target_lookback = QSpinBox()
        self._vol_target_lookback.setRange(2, 512)
        self._vol_target_lookback.setValue(72)
        self._vol_target_lookback.setFixedWidth(spin_width)
        self._vol_target_lookback.setToolTip("Lookback bars used to estimate realized volatility.")
        reward_layout.add_row(
            "Vol lookback",
            _wrap_field(self._vol_target_lookback),
        )

        self._vol_scale_floor = TrimmedDoubleSpinBox()
        self._vol_scale_floor.setRange(0.0, 10.0)
        self._vol_scale_floor.setDecimals(3)
        self._vol_scale_floor.setSingleStep(0.05)
        self._vol_scale_floor.setValue(0.5)
        self._vol_scale_floor.setFixedWidth(spin_width)
        self._vol_scale_floor.setToolTip("Minimum volatility targeting scale.")
        reward_layout.add_row(
            "Vol scale floor",
            _wrap_field(self._vol_scale_floor),
        )

        self._vol_scale_cap = TrimmedDoubleSpinBox()
        self._vol_scale_cap.setRange(0.0, 10.0)
        self._vol_scale_cap.setDecimals(3)
        self._vol_scale_cap.setSingleStep(0.05)
        self._vol_scale_cap.setValue(1.0)
        self._vol_scale_cap.setFixedWidth(spin_width)
        self._vol_scale_cap.setToolTip("Maximum volatility targeting scale.")
        reward_layout.add_row(
            "Vol scale cap",
            _wrap_field(self._vol_scale_cap),
        )

        self._drawdown_governor_slope = TrimmedDoubleSpinBox()
        self._drawdown_governor_slope.setRange(0.0, 20.0)
        self._drawdown_governor_slope.setDecimals(3)
        self._drawdown_governor_slope.setSingleStep(0.1)
        self._drawdown_governor_slope.setValue(4.0)
        self._drawdown_governor_slope.setFixedWidth(spin_width)
        self._drawdown_governor_slope.setToolTip(
            "Scales max position by max(floor, 1 - slope * drawdown). 0 disables governor."
        )
        reward_layout.add_row(
            "DD governor slope",
            _wrap_field(self._drawdown_governor_slope),
        )

        self._drawdown_governor_floor = TrimmedDoubleSpinBox()
        self._drawdown_governor_floor.setRange(0.0, 1.0)
        self._drawdown_governor_floor.setDecimals(3)
        self._drawdown_governor_floor.setSingleStep(0.05)
        self._drawdown_governor_floor.setValue(0.25)
        self._drawdown_governor_floor.setFixedWidth(spin_width)
        self._drawdown_governor_floor.setToolTip(
            "Minimum scaling floor for drawdown governor."
        )
        reward_layout.add_row(
            "DD governor floor",
            _wrap_field(self._drawdown_governor_floor),
        )

        optuna_group = QGroupBox("Optuna Settings")
        _apply_live_card_style(optuna_group)
        optuna_group_layout = QVBoxLayout(optuna_group)
        optuna_group_layout.setContentsMargins(12, 10, 12, 12)
        optuna_group_layout.setSpacing(8)
        optuna_fields = AdaptiveFormGrid(min_cell_width=260, label_min_width=0, max_columns=2)
        optuna_group_layout.addWidget(optuna_fields)

        self._optuna_trials = QSpinBox()
        self._optuna_trials.setRange(0, 500)
        self._optuna_trials.setValue(0)
        self._optuna_trials.setFixedWidth(spin_width)
        optuna_fields.add_row("Trials", _wrap_field(self._optuna_trials))

        self._optuna_steps = QSpinBox()
        self._optuna_steps.setRange(1, 5_000_000)
        self._optuna_steps.setValue(50_000)
        self._optuna_steps.setFixedWidth(spin_width)
        optuna_fields.add_row("Steps per trial", _wrap_field(self._optuna_steps))

        self._optuna_auto_select = QCheckBox("Auto select params")
        self._optuna_auto_select.setChecked(True)
        optuna_fields.add_row("Auto select", _wrap_field(self._optuna_auto_select))

        self._optuna_select_mode = QComboBox()
        self._optuna_select_mode.addItems(["Top K", "Top %"])
        self._optuna_select_mode.setCurrentIndex(0)
        self._optuna_select_mode.setFixedWidth(spin_width)
        optuna_fields.add_row("Selection mode", _wrap_field(self._optuna_select_mode))

        self._optuna_top_k = QSpinBox()
        self._optuna_top_k.setRange(1, 500)
        self._optuna_top_k.setValue(5)
        self._optuna_top_k.setFixedWidth(spin_width)

        self._optuna_top_percent = TrimmedDoubleSpinBox()
        self._optuna_top_percent.setRange(0.1, 100.0)
        self._optuna_top_percent.setDecimals(1)
        self._optuna_top_percent.setSingleStep(1.0)
        self._optuna_top_percent.setValue(20.0)
        self._optuna_top_percent.setFixedWidth(spin_width)

        self._optuna_threshold_stack = QStackedWidget()
        self._optuna_threshold_stack.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._optuna_threshold_stack.addWidget(_wrap_field(self._optuna_top_k))
        self._optuna_threshold_stack.addWidget(_wrap_field(self._optuna_top_percent))
        optuna_fields.add_row("Selection value", self._optuna_threshold_stack)

        self._optuna_min_candidates = QSpinBox()
        self._optuna_min_candidates.setRange(1, 500)
        self._optuna_min_candidates.setValue(3)
        self._optuna_min_candidates.setFixedWidth(spin_width)
        optuna_fields.add_row("Min candidates", _wrap_field(self._optuna_min_candidates))

        self._optuna_replay_enabled = QCheckBox("Replay top candidates")
        self._optuna_replay_enabled.setChecked(False)
        optuna_fields.add_row("Replay", _wrap_field(self._optuna_replay_enabled))

        self._optuna_replay_steps = QSpinBox()
        self._optuna_replay_steps.setRange(1, 10_000_000)
        self._optuna_replay_steps.setValue(200_000)
        self._optuna_replay_steps.setFixedWidth(spin_width)
        optuna_fields.add_row("Replay steps", _wrap_field(self._optuna_replay_steps))

        self._optuna_replay_seeds = QSpinBox()
        self._optuna_replay_seeds.setRange(1, 20)
        self._optuna_replay_seeds.setValue(3)
        self._optuna_replay_seeds.setFixedWidth(spin_width)
        optuna_fields.add_row("Seeds/candidate", _wrap_field(self._optuna_replay_seeds))

        self._optuna_replay_score_mode = QComboBox()
        self._optuna_replay_score_mode.addItems(
            ["Risk-adjusted", "Reward only", "Conservative", "Walk-forward"]
        )
        self._optuna_replay_score_mode.setCurrentIndex(3)
        self._optuna_replay_score_mode.setFixedWidth(spin_width)
        optuna_fields.add_row("Replay score", _wrap_field(self._optuna_replay_score_mode))

        self._optuna_replay_walk_forward_segments = QSpinBox()
        self._optuna_replay_walk_forward_segments.setRange(1, 20)
        self._optuna_replay_walk_forward_segments.setValue(3)
        self._optuna_replay_walk_forward_segments.setFixedWidth(spin_width)
        optuna_fields.add_row(
            "WF segments",
            _wrap_field(self._optuna_replay_walk_forward_segments),
        )

        self._optuna_replay_walk_forward_steps = QSpinBox()
        self._optuna_replay_walk_forward_steps.setRange(1, 1_000_000)
        self._optuna_replay_walk_forward_steps.setValue(2_500)
        self._optuna_replay_walk_forward_steps.setFixedWidth(spin_width)
        optuna_fields.add_row(
            "WF steps",
            _wrap_field(self._optuna_replay_walk_forward_steps),
        )

        self._optuna_replay_walk_forward_stride = QSpinBox()
        self._optuna_replay_walk_forward_stride.setRange(1, 1_000_000)
        self._optuna_replay_walk_forward_stride.setValue(2_500)
        self._optuna_replay_walk_forward_stride.setFixedWidth(spin_width)
        optuna_fields.add_row(
            "WF stride",
            _wrap_field(self._optuna_replay_walk_forward_stride),
        )

        self._optuna_replay_min_trade_rate = TrimmedDoubleSpinBox()
        self._optuna_replay_min_trade_rate.setRange(0.0, 100.0)
        self._optuna_replay_min_trade_rate.setDecimals(3)
        self._optuna_replay_min_trade_rate.setSingleStep(0.1)
        self._optuna_replay_min_trade_rate.setValue(5.0)
        self._optuna_replay_min_trade_rate.setFixedWidth(spin_width)
        optuna_fields.add_row(
            "Min trades/1k bars",
            _wrap_field(self._optuna_replay_min_trade_rate),
        )

        self._optuna_replay_max_flat_ratio = TrimmedDoubleSpinBox()
        self._optuna_replay_max_flat_ratio.setRange(0.0, 1.0)
        self._optuna_replay_max_flat_ratio.setDecimals(3)
        self._optuna_replay_max_flat_ratio.setSingleStep(0.01)
        self._optuna_replay_max_flat_ratio.setValue(0.98)
        self._optuna_replay_max_flat_ratio.setFixedWidth(spin_width)
        optuna_fields.add_row("Max flat ratio", _wrap_field(self._optuna_replay_max_flat_ratio))

        self._optuna_replay_max_ls_imbalance = TrimmedDoubleSpinBox()
        self._optuna_replay_max_ls_imbalance.setRange(0.0, 1.0)
        self._optuna_replay_max_ls_imbalance.setDecimals(3)
        self._optuna_replay_max_ls_imbalance.setSingleStep(0.01)
        self._optuna_replay_max_ls_imbalance.setValue(0.2)
        self._optuna_replay_max_ls_imbalance.setFixedWidth(spin_width)
        optuna_fields.add_row(
            "Max L/S imbalance",
            _wrap_field(self._optuna_replay_max_ls_imbalance),
        )

        self._optuna_plan_hint = QLabel("")
        self._optuna_plan_hint.setProperty("class", "dialog_hint")
        self._optuna_plan_hint.setWordWrap(True)
        optuna_group_layout.addWidget(self._optuna_plan_hint)

        self._start_button = QPushButton("Start Training")
        self._start_button.setProperty("class", PRIMARY)
        self._start_button.clicked.connect(self._emit_start)

        tabs = QTabWidget()
        self._tabs = tabs
        tabs.setDocumentMode(True)
        tabs.setMovable(False)
        tabs.setUsesScrollButtons(False)
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setDrawBase(False)

        setup_tab = QWidget()
        setup_tab.setObjectName("modelTab")
        setup_layout = QVBoxLayout(setup_tab)
        setup_layout.setContentsMargins(12, 10, 18, 24)
        setup_layout.setSpacing(8)
        setup_layout.addWidget(params_group)
        setup_layout.addWidget(ppo_advanced_group)
        setup_layout.addStretch(1)

        execution_tab = QWidget()
        execution_tab.setObjectName("tradeTab")
        execution_layout = QVBoxLayout(execution_tab)
        execution_layout.setContentsMargins(12, 10, 18, 24)
        execution_layout.setSpacing(8)
        execution_layout.addWidget(cost_group)
        execution_layout.addWidget(action_group)
        execution_layout.addStretch(1)

        run_tab = QWidget()
        run_tab.setObjectName("modelTab")
        run_layout = QVBoxLayout(run_tab)
        run_layout.setContentsMargins(12, 10, 18, 24)
        run_layout.setSpacing(8)
        run_layout.addWidget(file_group)
        run_layout.addWidget(options_group)
        run_layout.addWidget(self._start_button)
        run_layout.addStretch(1)

        guards_tab = QWidget()
        guards_tab.setObjectName("modelTab")
        guards_layout = QVBoxLayout(guards_tab)
        guards_layout.setContentsMargins(12, 10, 18, 24)
        guards_layout.setSpacing(8)
        guards_layout.addWidget(curriculum_group)
        guards_layout.addWidget(anti_flat_group)
        guards_layout.addStretch(1)

        sampling_tab = QWidget()
        sampling_tab.setObjectName("tradeTab")
        sampling_layout = QVBoxLayout(sampling_tab)
        sampling_layout.setContentsMargins(12, 10, 18, 24)
        sampling_layout.setSpacing(8)
        sampling_layout.addWidget(episode_group)
        sampling_layout.addWidget(reward_group)
        sampling_layout.addStretch(1)

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
        self._optuna_load_replay_button = QPushButton("Load Replay Params")
        self._optuna_load_replay_button.clicked.connect(self._emit_load_replay_params)
        optuna_layout_wrap.addWidget(self._optuna_load_replay_button)

        optuna_results = QGroupBox("")
        optuna_results.setObjectName("card")
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
        self._optuna_trial_summary.setStyleSheet(
            "font-family: 'Menlo', 'Monaco', 'Courier New', monospace;"
        )
        optuna_results_layout.addWidget(trial_title, 0, 0, Qt.AlignTop)
        optuna_results_layout.addWidget(self._optuna_trial_summary, 0, 1)

        best_title = QLabel("Best params")
        best_title.setProperty("class", "result_label")
        self._optuna_best_summary = QLabel(format_optuna_empty_best())
        self._optuna_best_summary.setWordWrap(True)
        self._optuna_best_summary.setProperty("class", "result_value")
        self._optuna_best_summary.setStyleSheet(
            "font-family: 'Menlo', 'Monaco', 'Courier New', monospace;"
        )
        optuna_results_layout.addWidget(best_title, 1, 0, Qt.AlignTop)
        optuna_results_layout.addWidget(self._optuna_best_summary, 1, 1)
        optuna_layout_wrap.addStretch(1)

        tabs.addTab(run_tab, "Run")
        tabs.addTab(guards_tab, "Guards")
        tabs.addTab(setup_tab, "Setup")
        tabs.addTab(execution_tab, "Execution")
        tabs.addTab(sampling_tab, "Sampling")
        self._optuna_tab_index = tabs.addTab(optuna_tab, "Optuna")
        tabs.tabBar().setTabVisible(self._optuna_tab_index, False)
        self._tab_bar = tabs.tabBar()
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
        self._update_data_metadata_preview(self._data_path.text().strip())
        self._sync_feature_selection_controls()
        self._bind_auto_save_handlers()
        self._refresh_optuna_select_controls()
        self._refresh_optuna_replay_controls()
        self._refresh_optuna_plan_hint()

    def _apply_tabs_style(self, tabs: QTabWidget) -> None:
        _apply_card_tabs_style(tabs)

    def _emit_start(self) -> None:
        if self._training_running:
            self.stop_requested.emit()
            return
        params = self.get_params()
        params["optuna_trials"] = 0
        params["optuna_only"] = False
        self._save_params(params)
        self.start_requested.emit(params)

    def set_training_running(self, running: bool) -> None:
        self._training_running = bool(running)
        self._start_button.setText("Stop Training" if running else "Start Training")

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
        if "target_kl" in params:
            self._target_kl.setValue(float(params["target_kl"]))
        if "device" in params:
            self._set_device(str(params["device"]))
        if "vf_coef" in params:
            self._vf_coef.setValue(float(params["vf_coef"]))
        if "n_epochs" in params:
            self._n_epochs.setValue(int(params["n_epochs"]))
        if "episode_length" in params:
            self._episode_length.setValue(int(params["episode_length"]))
        if "reward_horizon" in params:
            self._reward_horizon.setValue(int(params["reward_horizon"]))
        if "window_size" in params:
            self._window_size.setValue(int(params["window_size"]))
        if "reward_clip" in params:
            self._reward_clip.setValue(float(params["reward_clip"]))
        if "reward_mode" in params:
            self._set_reward_mode(str(params["reward_mode"]))
        if "feature_profile" in params:
            self._set_feature_profile(str(params["feature_profile"]))
        if "min_position_change" in params:
            self._min_position_change.setValue(float(params["min_position_change"]))
        if "position_step" in params:
            self._position_step.setValue(float(params["position_step"]))
        if "risk_aversion" in params:
            self._risk_aversion.setValue(float(params["risk_aversion"]))
        if "drawdown_penalty" in params:
            self._drawdown_penalty.setValue(float(params["drawdown_penalty"]))
        if "downside_penalty" in params:
            self._downside_penalty.setValue(float(params["downside_penalty"]))
        if "turnover_penalty" in params:
            self._turnover_penalty.setValue(float(params["turnover_penalty"]))
        if "exposure_penalty" in params:
            self._exposure_penalty.setValue(float(params["exposure_penalty"]))
        if "target_vol" in params:
            self._target_vol.setValue(float(params["target_vol"]))
        if "vol_target_lookback" in params:
            self._vol_target_lookback.setValue(int(params["vol_target_lookback"]))
        if "vol_scale_floor" in params:
            self._vol_scale_floor.setValue(float(params["vol_scale_floor"]))
        if "vol_scale_cap" in params:
            self._vol_scale_cap.setValue(float(params["vol_scale_cap"]))
        if "drawdown_governor_slope" in params:
            self._drawdown_governor_slope.setValue(float(params["drawdown_governor_slope"]))
        if "drawdown_governor_floor" in params:
            self._drawdown_governor_floor.setValue(float(params["drawdown_governor_floor"]))
        if "max_position" in params:
            self._max_position.setValue(float(params["max_position"]))

    @staticmethod
    def _set_label_text_safe(label: Optional[QLabel], text: str) -> None:
        if label is None:
            return
        try:
            label.setText(text)
        except RuntimeError:
            # The old Optuna result labels can be deleted when the UI layout
            # changes; in that case the visible Optuna summary lives elsewhere.
            return

    def reset_optuna_results(self) -> None:
        self._set_label_text_safe(
            getattr(self, "_optuna_trial_summary", None),
            format_optuna_empty_trial(),
        )
        self._set_label_text_safe(
            getattr(self, "_optuna_best_summary", None),
            format_optuna_empty_best(),
        )

    def update_optuna_trial_summary(self, text: str) -> None:
        self._set_label_text_safe(
            getattr(self, "_optuna_trial_summary", None),
            format_optuna_trial_summary(text),
        )

    def update_optuna_best_params(self, params: dict) -> None:
        if not params:
            return
        self._set_label_text_safe(
            getattr(self, "_optuna_best_summary", None),
            format_optuna_best_params(params),
        )

    def get_params(self) -> dict:
        selected_features = (
            list(self._selected_feature_names) if self._feature_profile_key() == "raw53" else []
        )
        return {
            "data_path": self._data_path.text().strip(),
            "selected_features": selected_features,
            "total_steps": int(self._total_steps.value()),
            "learning_rate": float(self._learning_rate.value()),
            "gamma": float(self._gamma.value()),
            "n_steps": int(self._n_steps.value()),
            "batch_size": int(self._batch_size.value()),
            "ent_coef": float(self._ent_coef.value()),
            "gae_lambda": float(self._gae_lambda.value()),
            "clip_range": float(self._clip_range.value()),
            "target_kl": float(self._target_kl.value()),
            "device": self._device_key(),
            "seed": int(self._seed.value()),
            "curriculum_enabled": bool(self._curriculum_enabled.isChecked()),
            "curriculum_steps": int(self._curriculum_steps.value()),
            "curriculum_max_position": float(self._curriculum_max_position.value()),
            "curriculum_position_step": float(self._curriculum_position_step.value()),
            "curriculum_min_position_change": float(self._curriculum_min_position_change.value()),
            "vf_coef": float(self._vf_coef.value()),
            "n_epochs": int(self._n_epochs.value()),
            "episode_length": int(self._episode_length.value()),
            "eval_split": float(self._eval_split.value()),
            "save_best_checkpoint": bool(self._save_best_checkpoint.isChecked()),
            "transaction_cost_bps": float(self._transaction_cost_bps.value()),
            "slippage_bps": float(self._slippage_bps.value()),
            "holding_cost_bps": float(self._holding_cost_bps.value()),
            "random_start": self._start_mode.currentIndex() == 0,
            "start_mode": self._start_mode_key(),
            "feature_profile": self._feature_profile_key(),
            "min_position_change": float(self._min_position_change.value()),
            "max_position": float(self._max_position.value()),
            "position_step": float(self._position_step.value()),
            "reward_horizon": int(self._reward_horizon.value()),
            "window_size": int(self._window_size.value()),
            "reward_scale": float(self._reward_scale.value()),
            "reward_clip": float(self._reward_clip.value()),
            "reward_mode": self._reward_mode_key(),
            "risk_aversion": float(self._risk_aversion.value()),
            "drawdown_penalty": float(self._drawdown_penalty.value()),
            "downside_penalty": float(self._downside_penalty.value()),
            "turnover_penalty": float(self._turnover_penalty.value()),
            "exposure_penalty": float(self._exposure_penalty.value()),
            "flat_position_penalty": float(self._flat_position_penalty.value()),
            "flat_streak_penalty": float(self._flat_streak_penalty.value()),
            "flat_position_threshold": float(self._flat_position_threshold.value()),
            "target_vol": float(self._target_vol.value()),
            "vol_target_lookback": int(self._vol_target_lookback.value()),
            "vol_scale_floor": float(self._vol_scale_floor.value()),
            "vol_scale_cap": float(self._vol_scale_cap.value()),
            "drawdown_governor_slope": float(self._drawdown_governor_slope.value()),
            "drawdown_governor_floor": float(self._drawdown_governor_floor.value()),
            "early_stop_enabled": bool(self._early_stop_enabled.isChecked()),
            "early_stop_warmup_steps": int(self._early_stop_warmup_steps.value()),
            "early_stop_patience_evals": int(self._early_stop_patience_evals.value()),
            "early_stop_min_delta": float(self._early_stop_min_delta.value()),
            "anti_flat_enabled": bool(self._anti_flat_enabled.isChecked()),
            "anti_flat_warmup_steps": int(self._anti_flat_warmup_steps.value()),
            "anti_flat_patience_evals": int(self._anti_flat_patience_evals.value()),
            "anti_flat_min_trade_rate": float(self._anti_flat_min_trade_rate.value()),
            "anti_flat_max_flat_ratio": float(self._anti_flat_max_flat_ratio.value()),
            "anti_flat_max_ls_imbalance": float(self._anti_flat_max_ls_imbalance.value()),
            "anti_flat_profile_steps": int(self._anti_flat_profile_steps.value()),
            "optuna_trials": int(self._optuna_trials.value()),
            "optuna_steps": int(self._optuna_steps.value()),
            "optuna_auto_select": bool(self._optuna_auto_select.isChecked()),
            "optuna_select_mode": (
                "top_percent" if self._optuna_select_mode.currentText() == "Top %" else "top_k"
            ),
            "optuna_top_k": int(self._optuna_top_k.value()),
            "optuna_top_percent": float(self._optuna_top_percent.value()),
            "optuna_min_candidates": int(self._optuna_min_candidates.value()),
            "optuna_top_out": "data/optuna/top_params.json",
            "optuna_replay_enabled": bool(self._optuna_replay_enabled.isChecked()),
            "optuna_replay_steps": int(self._optuna_replay_steps.value()),
            "optuna_replay_seeds": int(self._optuna_replay_seeds.value()),
            "optuna_replay_score_mode": self._replay_score_mode_key(),
            "optuna_replay_walk_forward_segments": int(
                self._optuna_replay_walk_forward_segments.value()
            ),
            "optuna_replay_walk_forward_steps": int(
                self._optuna_replay_walk_forward_steps.value()
            ),
            "optuna_replay_walk_forward_stride": int(
                self._optuna_replay_walk_forward_stride.value()
            ),
            "optuna_replay_min_trade_rate": float(self._optuna_replay_min_trade_rate.value()),
            "optuna_replay_max_flat_ratio": float(self._optuna_replay_max_flat_ratio.value()),
            "optuna_replay_max_ls_imbalance": float(
                self._optuna_replay_max_ls_imbalance.value()
            ),
            "optuna_replay_out": "data/optuna/replay_results.json",
            "optuna_out": "data/optuna/best_params.json",
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
        self._auto_save_params()

    def _update_data_metadata_preview(self, csv_path: str) -> None:
        self._data_feature_names = []
        self._view_features_button.setEnabled(False)
        self._refresh_view_features_button()
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
        feature_summary = None
        try:
            df = load_csv(str(path))
            features, _, _ = build_feature_frame(df)
            self._data_feature_names = list(features.columns)
            if not self._selected_feature_names:
                self._selected_feature_names = list(self._data_feature_names)
            else:
                selected = [name for name in self._selected_feature_names if name in self._data_feature_names]
                self._selected_feature_names = selected or list(self._data_feature_names)
            self._sync_feature_selection_controls()
            self._refresh_view_features_button()
            feature_summary = self._summarize_feature_names(self._data_feature_names)
        except Exception:
            feature_summary = None
        self._data_meta.setText(self._format_metadata_summary(payload, feature_summary))

    @staticmethod
    def _format_metadata_summary(payload: dict, feature_summary: str | None = None) -> str:
        if not isinstance(payload, dict):
            return "Metadata format invalid."
        details = payload.get("details", {})
        if not isinstance(details, dict):
            details = {}
        symbol = details.get("symbol_id", "unknown")
        timeframe = details.get("timeframe", "unknown")
        row_count = details.get("row_count", "unknown")
        schema_version = payload.get("schema_version", "unknown")
        summary = (
            f"symbol_id: {symbol}    timeframe: {timeframe}\n"
            f"rows: {row_count}    schema: {schema_version}"
        )
        if feature_summary:
            summary += f"\n{feature_summary}"
        return summary

    @staticmethod
    def _summarize_feature_names(feature_names: list[str]) -> str:
        if not feature_names:
            return "features: unknown"
        highlights = [
            name
            for name in (
                "vol_pct_72_252",
                "trend_flag_25",
                "range_strength_10_50_atr14",
            )
            if name in feature_names
        ]
        summary = f"features: {len(feature_names)}"
        if highlights:
            summary += f"    regime: {', '.join(highlights)}"
        return summary

    @staticmethod
    def _group_feature_names(feature_names: list[str]) -> list[tuple[str, list[str]]]:
        ordered_groups = [
            ("Returns", []),
            ("Trend & Momentum", []),
            ("Volatility", []),
            ("Breakout & Range", []),
            ("Candlestick", []),
            ("Regime & Oscillator", []),
            ("Session Context", []),
            ("Time & Session Flags", []),
            ("Other", []),
        ]
        group_map = {name: items for name, items in ordered_groups}
        session_context_names = {
            "prev_day_return",
            "prev_day_range_pct",
            "prev_day_range_position",
            "distance_to_prev_day_high",
            "distance_to_prev_day_low",
            "distance_to_day_high_so_far",
            "distance_to_day_low_so_far",
            "since_london_open_return",
            "since_ny_open_return",
            "ny_open_gap_prev_close",
            "london_to_ny_open_return",
            "ny_reversal_pressure",
        }
        time_session_names = {
            "hour_sin",
            "hour_cos",
            "weekday_sin",
            "weekday_cos",
            "minute_of_week_sin",
            "minute_of_week_cos",
            "is_monday_open_window",
            "is_london_session",
            "is_ny_session",
            "is_london_ny_overlap",
        }
        for name in feature_names:
            if name.startswith("returns_"):
                group_map["Returns"].append(name)
            elif name.startswith("sma_") or name.startswith("momentum_") or name.startswith("price_z_"):
                group_map["Trend & Momentum"].append(name)
            elif name.startswith("atr_") or name.startswith("vol_") or name.startswith("bollinger_"):
                group_map["Volatility"].append(name)
            elif name.startswith("breakout_") or name in (
                "distance_to_rolling_high_20",
                "distance_to_rolling_low_20",
            ):
                group_map["Breakout & Range"].append(name)
            elif name in ("body_size_ratio", "close_location_in_bar"):
                group_map["Candlestick"].append(name)
            elif name.startswith("rsi_") or name.startswith("adx_") or name.startswith("trend_flag_") or name.startswith(
                "range_strength_"
            ):
                group_map["Regime & Oscillator"].append(name)
            elif name in session_context_names:
                group_map["Session Context"].append(name)
            elif name in time_session_names:
                group_map["Time & Session Flags"].append(name)
            else:
                group_map["Other"].append(name)
        return [(name, items) for name, items in ordered_groups if items]

    def _show_feature_list_dialog(self) -> None:
        if self._feature_profile_key() != "raw53":
            QMessageBox.information(
                self,
                "Features Managed by Profile",
                "When feature profile is Alpha/Residual, raw feature selection is ignored.",
            )
            return
        if not self._data_feature_names:
            QMessageBox.information(self, "Features", "No feature list available for the selected data.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Features")
        dialog.resize(640, 620)
        layout = QVBoxLayout(dialog)
        summary = QLabel(
            f"{len(self._selected_feature_names) or len(self._data_feature_names)} / {len(self._data_feature_names)} selected\n"
            f"regime: {', '.join(name for name in ('vol_pct_72_252', 'trend_flag_25', 'range_strength_10_50_atr14') if name in self._data_feature_names) or '-'}"
        )
        summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(summary)
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        container = QWidget(scroll)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(10)

        selected = set(self._selected_feature_names or self._data_feature_names)
        checkboxes: dict[str, QCheckBox] = {}
        for group_name, names in self._group_feature_names(self._data_feature_names):
            group_box = QGroupBox(f"{group_name} ({len(names)})", container)
            group_grid = QGridLayout(group_box)
            group_grid.setHorizontalSpacing(18)
            group_grid.setVerticalSpacing(8)
            for idx, name in enumerate(names):
                checkbox = QCheckBox(name, group_box)
                checkbox.setChecked(name in selected)
                checkboxes[name] = checkbox
                group_grid.addWidget(checkbox, idx // 2, idx % 2)
            container_layout.addWidget(group_box)
        container_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        def update_summary() -> None:
            count = sum(1 for cb in checkboxes.values() if cb.isChecked())
            summary.setText(
                f"{count} / {len(self._data_feature_names)} selected\n"
                f"regime: {', '.join(name for name in ('vol_pct_72_252', 'trend_flag_25', 'range_strength_10_50_atr14') if name in self._data_feature_names) or '-'}"
            )

        for checkbox in checkboxes.values():
            checkbox.toggled.connect(update_summary)

        select_all_button = QPushButton("Select All", dialog)
        clear_button = QPushButton("Clear", dialog)
        cancel_button = QPushButton("Cancel", dialog)
        apply_button = QPushButton("Apply", dialog)
        apply_button.setProperty("class", PRIMARY)

        select_all_button.clicked.connect(lambda: [cb.setChecked(True) for cb in checkboxes.values()])
        clear_button.clicked.connect(lambda: [cb.setChecked(False) for cb in checkboxes.values()])
        cancel_button.clicked.connect(dialog.reject)

        def apply_selection() -> None:
            selected_names = [name for name in self._data_feature_names if checkboxes[name].isChecked()]
            if not selected_names:
                QMessageBox.information(dialog, "Features", "Select at least one feature.")
                return
            self._selected_feature_names = selected_names
            self._refresh_view_features_button()
            self._auto_save_params()
            dialog.accept()

        apply_button.clicked.connect(apply_selection)

        row = QHBoxLayout()
        row.addWidget(select_all_button)
        row.addWidget(clear_button)
        row.addStretch(1)
        row.addWidget(cancel_button)
        row.addWidget(apply_button)
        layout.addLayout(row)
        dialog.exec()

    def _refresh_view_features_button(self) -> None:
        profile = self._feature_profile_key()
        if profile != "raw53":
            if profile == "alpha4":
                self._view_features_button.setText(
                    f"Features: Alpha ({len(ALPHA_FEATURE_COLUMNS)})"
                )
            else:
                self._view_features_button.setText(
                    f"Features: Residual ({len(ALPHA_FEATURE_COLUMNS) + len(RESIDUAL_CONTEXT_COLUMNS)})"
                )
            return
        total = len(self._data_feature_names)
        selected = len(self._selected_feature_names)
        if total <= 0:
            self._view_features_button.setText("View Features")
            return
        if selected <= 0 or selected == total:
            self._view_features_button.setText(f"View Features ({total})")
            return
        self._view_features_button.setText(f"View Features ({selected}/{total})")

    def _emit_optuna(self) -> None:
        params = self.get_params()
        params["optuna_only"] = True
        self._save_params(params)
        self.optuna_requested.emit(params)
        self.reset_optuna_results()

    def _emit_load_replay_params(self) -> None:
        replay_path = Path("data/optuna/replay_results.json")
        if not replay_path.exists():
            QMessageBox.information(
                self,
                "Replay Not Found",
                "Cannot find data/optuna/replay_results.json",
            )
            return
        try:
            payload = json.loads(replay_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Replay Parse Error", f"Failed to parse replay results: {exc}")
            return
        if not isinstance(payload, dict):
            QMessageBox.warning(self, "Replay Parse Error", "Invalid replay results format.")
            return
        raw_results = payload.get("results", [])
        if not isinstance(raw_results, list) or not raw_results:
            QMessageBox.information(self, "No Replay Results", "Replay results are empty.")
            return

        candidates: list[dict] = []
        labels: list[str] = []
        for row in raw_results:
            if not isinstance(row, dict):
                continue
            params = row.get("params", {})
            if not isinstance(params, dict) or not params:
                continue
            trial = row.get("trial", "?")
            score = float(row.get("score", 0.0))
            mean_reward = float(row.get("mean_reward", 0.0))
            avg_trades = float(row.get("avg_trades", 0.0))
            label = (
                f"trial={trial} score={score:.6g} "
                f"mean={mean_reward:.6g} trades={avg_trades:.1f}"
            )
            candidates.append(row)
            labels.append(label)

        if not candidates:
            QMessageBox.information(self, "No Replay Results", "No valid replay parameter rows found.")
            return

        selected_label, ok = QInputDialog.getItem(
            self,
            "Select Replay Candidate",
            "Replay params",
            labels,
            0,
            False,
        )
        if not ok:
            return
        try:
            selected_index = labels.index(selected_label)
        except ValueError:
            return

        selected = candidates[selected_index]
        params = selected.get("params", {})
        if not isinstance(params, dict) or not params:
            return
        self.apply_optuna_params(params)
        self.update_optuna_best_params(params)
        self.update_optuna_trial_summary(
            (
                f"Replay selected: trial={selected.get('trial', '?')} "
                f"score={float(selected.get('score', 0.0)):.6g} "
                f"mean_reward={float(selected.get('mean_reward', 0.0)):.6g} "
                f"std={float(selected.get('std_reward', 0.0)):.6g}"
            )
        )
        self._auto_save_params()

    def _on_tab_changed(self, index: int) -> None:
        if hasattr(self, "_tab_bar") and hasattr(self, "_optuna_tab_index"):
            self._tab_bar.setVisible(index != self._optuna_tab_index)
        if index == getattr(self, "_optuna_tab_index", -1):
            self.tab_changed.emit("optuna")
            return
        tab_text = ""
        if hasattr(self, "_tabs"):
            tab_text = self._tabs.tabText(index).strip().lower()
        if tab_text in {"execution", "sampling"}:
            self.tab_changed.emit("environment")
            return
        self.tab_changed.emit("training")

    def show_training_mode(self) -> None:
        if hasattr(self, "_tabs"):
            if hasattr(self, "_tab_bar"):
                self._tab_bar.setVisible(True)
            self._tabs.setCurrentIndex(0)

    def show_optuna_mode(self) -> None:
        if hasattr(self, "_tabs") and hasattr(self, "_optuna_tab_index"):
            if hasattr(self, "_tab_bar"):
                self._tab_bar.setVisible(False)
            self._tabs.setCurrentIndex(self._optuna_tab_index)


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

    def _load_params(self) -> bool:
        self._loading_params = True
        data = self._params_store.load()
        if not data:
            self._loading_params = False
            return False
        if "data_path" in data:
            self._data_path.setText(str(data["data_path"]))
        if "selected_features" in data and isinstance(data["selected_features"], list):
            self._selected_feature_names = [
                str(name).strip() for name in data["selected_features"] if str(name).strip()
            ]
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
        if "target_kl" in data:
            self._target_kl.setValue(float(data["target_kl"]))
        if "device" in data:
            self._set_device(str(data["device"]))
        if "seed" in data:
            self._seed.setValue(int(data["seed"]))
        if "curriculum_enabled" in data:
            self._curriculum_enabled.setChecked(bool(data["curriculum_enabled"]))
        if "curriculum_steps" in data:
            self._curriculum_steps.setValue(int(data["curriculum_steps"]))
        if "curriculum_max_position" in data:
            self._curriculum_max_position.setValue(float(data["curriculum_max_position"]))
        if "curriculum_position_step" in data:
            self._curriculum_position_step.setValue(float(data["curriculum_position_step"]))
        if "curriculum_min_position_change" in data:
            self._curriculum_min_position_change.setValue(float(data["curriculum_min_position_change"]))
        if "vf_coef" in data:
            self._vf_coef.setValue(float(data["vf_coef"]))
        if "n_epochs" in data:
            self._n_epochs.setValue(int(data["n_epochs"]))
        if "episode_length" in data:
            self._episode_length.setValue(int(data["episode_length"]))
        if "eval_split" in data:
            self._eval_split.setValue(float(data["eval_split"]))
        if "save_best_checkpoint" in data:
            self._save_best_checkpoint.setChecked(bool(data["save_best_checkpoint"]))
        if "early_stop_enabled" in data:
            self._early_stop_enabled.setChecked(bool(data["early_stop_enabled"]))
        if "early_stop_warmup_steps" in data:
            self._early_stop_warmup_steps.setValue(int(data["early_stop_warmup_steps"]))
        if "early_stop_patience_evals" in data:
            self._early_stop_patience_evals.setValue(int(data["early_stop_patience_evals"]))
        if "early_stop_min_delta" in data:
            self._early_stop_min_delta.setValue(float(data["early_stop_min_delta"]))
        if "anti_flat_enabled" in data:
            self._anti_flat_enabled.setChecked(bool(data["anti_flat_enabled"]))
        if "anti_flat_warmup_steps" in data:
            self._anti_flat_warmup_steps.setValue(int(data["anti_flat_warmup_steps"]))
        if "anti_flat_patience_evals" in data:
            self._anti_flat_patience_evals.setValue(int(data["anti_flat_patience_evals"]))
        if "anti_flat_min_trade_rate" in data:
            self._anti_flat_min_trade_rate.setValue(float(data["anti_flat_min_trade_rate"]))
        if "anti_flat_max_flat_ratio" in data:
            self._anti_flat_max_flat_ratio.setValue(float(data["anti_flat_max_flat_ratio"]))
        if "anti_flat_max_ls_imbalance" in data:
            self._anti_flat_max_ls_imbalance.setValue(float(data["anti_flat_max_ls_imbalance"]))
        if "anti_flat_profile_steps" in data:
            self._anti_flat_profile_steps.setValue(int(data["anti_flat_profile_steps"]))
        if "transaction_cost_bps" in data:
            self._transaction_cost_bps.setValue(float(data["transaction_cost_bps"]))
        if "slippage_bps" in data:
            self._slippage_bps.setValue(float(data["slippage_bps"]))
        if "holding_cost_bps" in data:
            self._holding_cost_bps.setValue(float(data["holding_cost_bps"]))
        if "start_mode" in data:
            self._set_start_mode(str(data["start_mode"]))
        elif "random_start" in data:
            self._set_start_mode("random" if bool(data["random_start"]) else "first")
        if "feature_profile" in data:
            self._set_feature_profile(str(data["feature_profile"]))
        if "min_position_change" in data:
            self._min_position_change.setValue(float(data["min_position_change"]))
        if "max_position" in data:
            self._max_position.setValue(float(data["max_position"]))
        if "position_step" in data:
            self._position_step.setValue(float(data["position_step"]))
        if "reward_horizon" in data:
            self._reward_horizon.setValue(int(data["reward_horizon"]))
        if "window_size" in data:
            self._window_size.setValue(int(data["window_size"]))
        if "reward_scale" in data:
            self._reward_scale.setValue(float(data["reward_scale"]))
        if "reward_clip" in data:
            self._reward_clip.setValue(float(data["reward_clip"]))
        if "reward_mode" in data:
            self._set_reward_mode(str(data["reward_mode"]))
        if "risk_aversion" in data:
            self._risk_aversion.setValue(float(data["risk_aversion"]))
        if "drawdown_penalty" in data:
            self._drawdown_penalty.setValue(float(data["drawdown_penalty"]))
        if "downside_penalty" in data:
            self._downside_penalty.setValue(float(data["downside_penalty"]))
        if "turnover_penalty" in data:
            self._turnover_penalty.setValue(float(data["turnover_penalty"]))
        if "exposure_penalty" in data:
            self._exposure_penalty.setValue(float(data["exposure_penalty"]))
        if "flat_position_penalty" in data:
            self._flat_position_penalty.setValue(float(data["flat_position_penalty"]))
        if "flat_streak_penalty" in data:
            self._flat_streak_penalty.setValue(float(data["flat_streak_penalty"]))
        if "flat_position_threshold" in data:
            self._flat_position_threshold.setValue(float(data["flat_position_threshold"]))
        if "target_vol" in data:
            self._target_vol.setValue(float(data["target_vol"]))
        if "vol_target_lookback" in data:
            self._vol_target_lookback.setValue(int(data["vol_target_lookback"]))
        if "vol_scale_floor" in data:
            self._vol_scale_floor.setValue(float(data["vol_scale_floor"]))
        if "vol_scale_cap" in data:
            self._vol_scale_cap.setValue(float(data["vol_scale_cap"]))
        if "drawdown_governor_slope" in data:
            self._drawdown_governor_slope.setValue(float(data["drawdown_governor_slope"]))
        if "drawdown_governor_floor" in data:
            self._drawdown_governor_floor.setValue(float(data["drawdown_governor_floor"]))
        if "optuna_trials" in data:
            self._optuna_trials.setValue(int(data["optuna_trials"]))
        if "optuna_steps" in data:
            self._optuna_steps.setValue(int(data["optuna_steps"]))
        if "optuna_auto_select" in data:
            self._optuna_auto_select.setChecked(bool(data["optuna_auto_select"]))
        if "optuna_select_mode" in data:
            mode = str(data["optuna_select_mode"]).strip().lower()
            self._optuna_select_mode.setCurrentIndex(1 if mode == "top_percent" else 0)
        if "optuna_top_k" in data:
            self._optuna_top_k.setValue(int(data["optuna_top_k"]))
        if "optuna_top_percent" in data:
            self._optuna_top_percent.setValue(float(data["optuna_top_percent"]))
        if "optuna_min_candidates" in data:
            self._optuna_min_candidates.setValue(int(data["optuna_min_candidates"]))
        if "optuna_replay_enabled" in data:
            self._optuna_replay_enabled.setChecked(bool(data["optuna_replay_enabled"]))
        if "optuna_replay_steps" in data:
            self._optuna_replay_steps.setValue(int(data["optuna_replay_steps"]))
        if "optuna_replay_seeds" in data:
            self._optuna_replay_seeds.setValue(int(data["optuna_replay_seeds"]))
        if "optuna_replay_score_mode" in data:
            self._set_replay_score_mode(str(data["optuna_replay_score_mode"]))
        if "optuna_replay_walk_forward_segments" in data:
            self._optuna_replay_walk_forward_segments.setValue(
                int(data["optuna_replay_walk_forward_segments"])
            )
        if "optuna_replay_walk_forward_steps" in data:
            self._optuna_replay_walk_forward_steps.setValue(
                int(data["optuna_replay_walk_forward_steps"])
            )
        if "optuna_replay_walk_forward_stride" in data:
            self._optuna_replay_walk_forward_stride.setValue(
                int(data["optuna_replay_walk_forward_stride"])
            )
        if "optuna_replay_min_trade_rate" in data:
            self._optuna_replay_min_trade_rate.setValue(float(data["optuna_replay_min_trade_rate"]))
        if "optuna_replay_max_flat_ratio" in data:
            self._optuna_replay_max_flat_ratio.setValue(float(data["optuna_replay_max_flat_ratio"]))
        if "optuna_replay_max_ls_imbalance" in data:
            self._optuna_replay_max_ls_imbalance.setValue(
                float(data["optuna_replay_max_ls_imbalance"])
            )
        self._refresh_optuna_select_controls()
        self._refresh_optuna_replay_controls()
        self._sync_early_stop_controls()
        self._sync_curriculum_controls()
        self._sync_anti_flat_controls()
        self._loading_params = False
        return True

    def _auto_save_params(self, *_args) -> None:
        if self._loading_params:
            return
        self._save_params(self.get_params())

    def _bind_auto_save_handlers(self) -> None:
        # Persist environment/training edits immediately to avoid losing tweaks
        # when the app restarts.
        self._total_steps.valueChanged.connect(self._auto_save_params)
        self._learning_rate.valueChanged.connect(self._auto_save_params)
        self._gamma.valueChanged.connect(self._auto_save_params)
        self._n_steps.valueChanged.connect(self._auto_save_params)
        self._n_steps.valueChanged.connect(self._sync_batch_size_limit)
        self._batch_size.valueChanged.connect(self._auto_save_params)
        self._ent_coef.valueChanged.connect(self._auto_save_params)
        self._eval_split.valueChanged.connect(self._auto_save_params)
        self._transaction_cost_bps.valueChanged.connect(self._auto_save_params)
        self._slippage_bps.valueChanged.connect(self._auto_save_params)
        self._holding_cost_bps.valueChanged.connect(self._auto_save_params)
        self._min_position_change.valueChanged.connect(self._auto_save_params)
        self._max_position.valueChanged.connect(self._auto_save_params)
        self._position_step.valueChanged.connect(self._auto_save_params)
        self._episode_length.valueChanged.connect(self._auto_save_params)
        self._reward_horizon.valueChanged.connect(self._auto_save_params)
        self._window_size.valueChanged.connect(self._auto_save_params)
        self._start_mode.currentIndexChanged.connect(self._auto_save_params)
        self._feature_profile.currentIndexChanged.connect(self._auto_save_params)
        self._feature_profile.currentIndexChanged.connect(self._sync_feature_selection_controls)
        self._reward_scale.valueChanged.connect(self._auto_save_params)
        self._reward_clip.valueChanged.connect(self._auto_save_params)
        self._reward_mode.currentIndexChanged.connect(self._auto_save_params)
        self._risk_aversion.valueChanged.connect(self._auto_save_params)
        self._drawdown_penalty.valueChanged.connect(self._auto_save_params)
        self._downside_penalty.valueChanged.connect(self._auto_save_params)
        self._turnover_penalty.valueChanged.connect(self._auto_save_params)
        self._exposure_penalty.valueChanged.connect(self._auto_save_params)
        self._flat_position_penalty.valueChanged.connect(self._auto_save_params)
        self._flat_streak_penalty.valueChanged.connect(self._auto_save_params)
        self._flat_position_threshold.valueChanged.connect(self._auto_save_params)
        self._target_vol.valueChanged.connect(self._auto_save_params)
        self._vol_target_lookback.valueChanged.connect(self._auto_save_params)
        self._vol_scale_floor.valueChanged.connect(self._auto_save_params)
        self._vol_scale_cap.valueChanged.connect(self._auto_save_params)
        self._drawdown_governor_slope.valueChanged.connect(self._auto_save_params)
        self._drawdown_governor_floor.valueChanged.connect(self._auto_save_params)
        self._save_best_checkpoint.toggled.connect(self._auto_save_params)
        self._early_stop_enabled.toggled.connect(self._auto_save_params)
        self._early_stop_enabled.toggled.connect(self._sync_early_stop_controls)
        self._early_stop_warmup_steps.valueChanged.connect(self._auto_save_params)
        self._early_stop_patience_evals.valueChanged.connect(self._auto_save_params)
        self._early_stop_min_delta.valueChanged.connect(self._auto_save_params)
        self._anti_flat_enabled.toggled.connect(self._auto_save_params)
        self._anti_flat_enabled.toggled.connect(self._sync_anti_flat_controls)
        self._anti_flat_warmup_steps.valueChanged.connect(self._auto_save_params)
        self._anti_flat_patience_evals.valueChanged.connect(self._auto_save_params)
        self._anti_flat_min_trade_rate.valueChanged.connect(self._auto_save_params)
        self._anti_flat_max_flat_ratio.valueChanged.connect(self._auto_save_params)
        self._anti_flat_max_ls_imbalance.valueChanged.connect(self._auto_save_params)
        self._anti_flat_profile_steps.valueChanged.connect(self._auto_save_params)
        self._gae_lambda.valueChanged.connect(self._auto_save_params)
        self._clip_range.valueChanged.connect(self._auto_save_params)
        self._target_kl.valueChanged.connect(self._auto_save_params)
        self._device.currentIndexChanged.connect(self._auto_save_params)
        self._seed.valueChanged.connect(self._auto_save_params)
        self._curriculum_enabled.toggled.connect(self._auto_save_params)
        self._curriculum_enabled.toggled.connect(self._sync_curriculum_controls)
        self._curriculum_steps.valueChanged.connect(self._auto_save_params)
        self._curriculum_max_position.valueChanged.connect(self._auto_save_params)
        self._curriculum_position_step.valueChanged.connect(self._auto_save_params)
        self._curriculum_min_position_change.valueChanged.connect(self._auto_save_params)
        self._vf_coef.valueChanged.connect(self._auto_save_params)
        self._n_epochs.valueChanged.connect(self._auto_save_params)
        self._optuna_trials.valueChanged.connect(self._auto_save_params)
        self._optuna_trials.valueChanged.connect(self._refresh_optuna_plan_hint)
        self._optuna_steps.valueChanged.connect(self._auto_save_params)
        self._optuna_auto_select.toggled.connect(self._on_optuna_auto_select_toggled)
        self._optuna_select_mode.currentIndexChanged.connect(self._on_optuna_select_mode_changed)
        self._optuna_top_k.valueChanged.connect(self._auto_save_params)
        self._optuna_top_k.valueChanged.connect(self._refresh_optuna_plan_hint)
        self._optuna_top_percent.valueChanged.connect(self._auto_save_params)
        self._optuna_top_percent.valueChanged.connect(self._refresh_optuna_plan_hint)
        self._optuna_min_candidates.valueChanged.connect(self._auto_save_params)
        self._optuna_min_candidates.valueChanged.connect(self._refresh_optuna_plan_hint)
        self._optuna_replay_enabled.toggled.connect(self._on_optuna_replay_toggled)
        self._optuna_replay_steps.valueChanged.connect(self._auto_save_params)
        self._optuna_replay_seeds.valueChanged.connect(self._auto_save_params)
        self._optuna_replay_score_mode.currentIndexChanged.connect(self._on_optuna_replay_score_mode_changed)
        self._optuna_replay_walk_forward_segments.valueChanged.connect(self._auto_save_params)
        self._optuna_replay_walk_forward_steps.valueChanged.connect(self._auto_save_params)
        self._optuna_replay_walk_forward_stride.valueChanged.connect(self._auto_save_params)
        self._optuna_replay_min_trade_rate.valueChanged.connect(self._auto_save_params)
        self._optuna_replay_max_flat_ratio.valueChanged.connect(self._auto_save_params)
        self._optuna_replay_max_ls_imbalance.valueChanged.connect(self._auto_save_params)

    def _on_optuna_auto_select_toggled(self, _checked: bool) -> None:
        self._refresh_optuna_select_controls()
        self._refresh_optuna_plan_hint()
        self._auto_save_params()

    def _on_optuna_select_mode_changed(self, _index: int) -> None:
        self._refresh_optuna_select_controls()
        self._refresh_optuna_plan_hint()
        self._auto_save_params()

    def _refresh_optuna_select_controls(self) -> None:
        enabled = bool(self._optuna_auto_select.isChecked())
        self._optuna_select_mode.setEnabled(enabled)
        self._optuna_min_candidates.setEnabled(enabled)
        is_top_k = self._optuna_select_mode.currentText() == "Top K"
        self._optuna_top_k.setEnabled(enabled and is_top_k)
        self._optuna_top_percent.setEnabled(enabled and not is_top_k)
        self._optuna_threshold_stack.setCurrentIndex(0 if is_top_k else 1)
        self._optuna_threshold_stack.setEnabled(enabled)

    def _on_optuna_replay_toggled(self, _checked: bool) -> None:
        self._refresh_optuna_replay_controls()
        self._refresh_optuna_plan_hint()
        self._auto_save_params()

    def _on_optuna_replay_score_mode_changed(self, _index: int) -> None:
        self._refresh_optuna_replay_controls()
        self._auto_save_params()

    def _refresh_optuna_replay_controls(self) -> None:
        enabled = bool(self._optuna_replay_enabled.isChecked())
        walk_forward = self._replay_score_mode_key() == "walk_forward"
        self._optuna_replay_steps.setEnabled(enabled)
        self._optuna_replay_seeds.setEnabled(enabled)
        self._optuna_replay_score_mode.setEnabled(enabled)
        self._optuna_replay_walk_forward_segments.setEnabled(enabled and walk_forward)
        self._optuna_replay_walk_forward_steps.setEnabled(enabled and walk_forward)
        self._optuna_replay_walk_forward_stride.setEnabled(enabled and walk_forward)
        self._optuna_replay_min_trade_rate.setEnabled(enabled)
        self._optuna_replay_max_flat_ratio.setEnabled(enabled)
        self._optuna_replay_max_ls_imbalance.setEnabled(enabled)

    def _sync_early_stop_controls(self, *_args: object) -> None:
        enabled = bool(self._early_stop_enabled.isChecked())
        self._early_stop_warmup_steps.setEnabled(enabled)
        self._early_stop_patience_evals.setEnabled(enabled)
        self._early_stop_min_delta.setEnabled(enabled)

    def _sync_curriculum_controls(self, *_args: object) -> None:
        enabled = bool(self._curriculum_enabled.isChecked())
        self._curriculum_steps.setEnabled(enabled)
        self._curriculum_max_position.setEnabled(enabled)
        self._curriculum_position_step.setEnabled(enabled)
        self._curriculum_min_position_change.setEnabled(enabled)

    def _sync_anti_flat_controls(self, *_args: object) -> None:
        enabled = bool(self._anti_flat_enabled.isChecked())
        self._anti_flat_warmup_steps.setEnabled(enabled)
        self._anti_flat_patience_evals.setEnabled(enabled)
        self._anti_flat_min_trade_rate.setEnabled(enabled)
        self._anti_flat_max_flat_ratio.setEnabled(enabled)
        self._anti_flat_max_ls_imbalance.setEnabled(enabled)
        self._anti_flat_profile_steps.setEnabled(enabled)

    def _sync_batch_size_limit(self, *_args: object) -> None:
        max_batch = max(1, int(self._n_steps.value()))
        self._batch_size.setMaximum(max_batch)
        if int(self._batch_size.value()) > max_batch:
            self._batch_size.setValue(max_batch)

    def _refresh_optuna_plan_hint(self) -> None:
        trials = int(self._optuna_trials.value())
        if trials <= 0:
            self._optuna_plan_hint.setText("Set Trials > 0 to preview candidate selection.")
            return
        if not self._optuna_auto_select.isChecked():
            replay_count = 1 if self._optuna_replay_enabled.isChecked() else 0
            if replay_count > 0:
                self._optuna_plan_hint.setText(
                    f"Auto select is off. Replay will use best 1 candidate (replay={replay_count})."
                )
            else:
                self._optuna_plan_hint.setText("Auto select is off.")
            return
        if self._optuna_select_mode.currentText() == "Top K":
            mode_count = int(self._optuna_top_k.value())
        else:
            pct = float(self._optuna_top_percent.value())
            mode_count = int(math.ceil(trials * pct / 100.0))
        selected_count = max(mode_count, int(self._optuna_min_candidates.value()))
        selected_count = min(trials, max(1, selected_count))
        replay_count = selected_count if self._optuna_replay_enabled.isChecked() else 0
        self._optuna_plan_hint.setText(
            f"Expected selection: {selected_count}/{trials} candidates. Replay: {replay_count}."
        )

    def _replay_score_mode_key(self) -> str:
        text = self._optuna_replay_score_mode.currentText()
        if text.startswith("Reward only"):
            return "reward_only"
        if text.startswith("Conservative"):
            return "conservative"
        if text.startswith("Walk-forward"):
            return "walk_forward"
        return "risk_adjusted"

    def _set_replay_score_mode(self, mode: str) -> None:
        value = (mode or "").strip().lower()
        if value == "reward_only":
            self._optuna_replay_score_mode.setCurrentIndex(1)
            return
        if value == "conservative":
            self._optuna_replay_score_mode.setCurrentIndex(2)
            return
        if value == "walk_forward":
            self._optuna_replay_score_mode.setCurrentIndex(3)
            return
        self._optuna_replay_score_mode.setCurrentIndex(0)

    def _start_mode_key(self) -> str:
        text = self._start_mode.currentText()
        if text.startswith("First"):
            return "first"
        if text.startswith("Weekly"):
            return "weekly_open"
        return "random"

    def _set_start_mode(self, mode: str) -> None:
        value = (mode or "").strip().lower()
        if value == "first":
            self._start_mode.setCurrentIndex(1)
            return
        if value == "weekly_open":
            self._start_mode.setCurrentIndex(2)
            return
        self._start_mode.setCurrentIndex(0)

    def _reward_mode_key(self) -> str:
        text = self._reward_mode.currentText()
        if text.startswith("Risk-adjusted"):
            return "risk_adjusted"
        if text.startswith("Log"):
            return "log_return"
        return "linear"

    def _feature_profile_key(self) -> str:
        text = self._feature_profile.currentText()
        if text.startswith("Raw"):
            return "raw53"
        if text.startswith("Alpha layer"):
            return "alpha4"
        return "residual"

    def _sync_feature_selection_controls(self, *_args: object) -> None:
        raw_profile = self._feature_profile_key() == "raw53"
        can_pick = raw_profile and bool(self._data_feature_names)
        self._view_features_button.setEnabled(can_pick)
        if raw_profile:
            self._view_features_button.setToolTip("Select raw features used by training.")
        else:
            self._view_features_button.setToolTip(
                "Feature profile controls the active features. Raw feature selection is disabled."
            )
        self._refresh_view_features_button()

    def _device_key(self) -> str:
        text = self._device.currentText().strip().lower()
        if text in {"cpu", "mps", "cuda"}:
            return text
        return "auto"

    def _set_reward_mode(self, mode: str) -> None:
        value = (mode or "").strip().lower()
        if value == "risk_adjusted":
            self._reward_mode.setCurrentIndex(2)
            return
        if value == "log_return":
            self._reward_mode.setCurrentIndex(1)
            return
        self._reward_mode.setCurrentIndex(0)

    def _set_feature_profile(self, profile: str) -> None:
        value = (profile or "").strip().lower()
        if value == "raw53":
            self._feature_profile.setCurrentIndex(0)
        elif value == "alpha4":
            self._feature_profile.setCurrentIndex(1)
        else:
            self._feature_profile.setCurrentIndex(2)
        self._sync_feature_selection_controls()

    def _set_device(self, device: str) -> None:
        value = (device or "").strip().lower()
        mapping = {
            "auto": 0,
            "cpu": 1,
            "mps": 2,
            "cuda": 3,
        }
        self._device.setCurrentIndex(mapping.get(value, 0))

    def set_resolved_device(self, device: str) -> None:
        value = str(device or "").strip() or "-"
        self._resolved_device.setText(value)


class TrainingPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_step = 0
        self._charts_available = pg is not None
        self._plot_timer = QElapsedTimer()
        self._plot_interval_ms = 50
        self._max_points = 2000
        self._reward_stat_window = 200
        self._rolling_sharpe_window = 50
        self._reward_samples: deque[float] = deque(maxlen=self._reward_stat_window)
        self._rolling_sharpe_samples: deque[float] = deque(maxlen=self._rolling_sharpe_window)
        self._reward_diagnostics_path = self._resolve_training_diagnostics_path()
        self._reward_run_started_at = self._current_timestamp()
        self._metrics = [
            ("eval/mean_reward", "eval/mean_reward"),
            ("ep_rew_mean", "ep_rew_mean"),
            ("rolling_sharpe", "rolling_sharpe"),
            ("step_pnl_mean", "step_pnl_mean"),
            ("cost_mean", "cost_mean"),
            ("abs_delta_mean", "abs_delta_mean"),
            ("approx_kl", "approx_kl"),
            ("clip_fraction", "clip_fraction"),
            ("explained_variance", "explained_variance"),
        ]
        self._hidden_metric_keys = {
            "eval/trade_rate_1k",
            "eval/flat_ratio",
            "eval/max_drawdown",
            "reward_step_mean",
            "holding_cost_mean",
            "abs_price_return_mean",
            "eval/ls_imbalance",
            "early_stop_patience_left",
            "value_loss",
            "entropy_loss",
            "policy_gradient_loss",
            "loss",
            "std",
            "fps",
        }
        self._metric_data: dict[str, dict[str, deque[float]]] = {}
        self._latest_metric_values: dict[str, float] = {}
        self._curves: dict[str, object] = {}
        self._curve_colors: dict[str, str] = {}
        self._checkboxes: dict[str, QRadioButton] = {}
        self._metric_labels = {key: label for label, key in self._metrics}
        self._accepted_metric_keys = set(self._metric_labels) | set(self._hidden_metric_keys)
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
                self._curve_colors[key] = color
                self._metric_data[key] = {
                    "x": deque(maxlen=self._max_points),
                    "y": deque(maxlen=self._max_points),
                }

            self._optuna_title_base = "Optuna trials"
            optuna_plot = pg.PlotWidget(
                axisItems={"bottom": IntegerAxisItem(orientation="bottom")}
            )
            optuna_plot.setTitle(self._optuna_title_base)
            optuna_plot.setLabel("bottom", "trial")
            optuna_plot.setLabel("left", "value")
            optuna_plot.showGrid(x=True, y=True, alpha=0.3)
            self._optuna_legend = optuna_plot.addLegend()
            self._optuna_plot = optuna_plot
            optuna_colors = ["#4C78A8", "#F58518", "#E45756", "#54A24B"]
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

            optuna_results = QGroupBox("")
            optuna_results.setObjectName("card")
            optuna_results_layout = QGridLayout(optuna_results)
            optuna_results_layout.setContentsMargins(12, 10, 12, 12)
            optuna_results_layout.setHorizontalSpacing(12)
            optuna_results_layout.setVerticalSpacing(8)
            optuna_results_layout.setColumnStretch(1, 1)

            trial_title = QLabel("Latest trial", optuna_results)
            trial_title.setProperty("class", "result_label")
            self._optuna_trial_summary_panel = QLabel(format_optuna_empty_trial(), optuna_results)
            self._optuna_trial_summary_panel.setWordWrap(True)
            self._optuna_trial_summary_panel.setProperty("class", "result_value")
            self._optuna_trial_summary_panel.setStyleSheet(
                "font-family: 'Menlo', 'Monaco', 'Courier New', monospace;"
            )
            optuna_results_layout.addWidget(trial_title, 0, 0, Qt.AlignTop)
            optuna_results_layout.addWidget(self._optuna_trial_summary_panel, 0, 1)

            best_title = QLabel("Best params", optuna_results)
            best_title.setProperty("class", "result_label")
            self._optuna_best_summary_panel = QWidget(optuna_results)
            best_params_layout = QGridLayout(self._optuna_best_summary_panel)
            best_params_layout.setContentsMargins(0, 0, 0, 0)
            best_params_layout.setHorizontalSpacing(18)
            best_params_layout.setVerticalSpacing(4)
            best_params_layout.setColumnStretch(1, 1)
            best_params_layout.setColumnStretch(3, 1)
            best_params_layout.setColumnStretch(5, 1)
            self._optuna_best_summary_grid = best_params_layout
            self._optuna_best_summary_cells: list[tuple[QLabel, QLabel]] = []
            for index in range(12):
                label_widget = QLabel("", self._optuna_best_summary_panel)
                label_widget.setStyleSheet("color: #90a0b6; font-size: 12px; font-weight: 600;")
                value_widget = QLabel("", self._optuna_best_summary_panel)
                value_widget.setStyleSheet(
                    "color: #e7edf7; font-size: 13px; font-weight: 600;"
                )
                value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
                row = index // 3
                col = (index % 3) * 2
                best_params_layout.addWidget(label_widget, row, col, Qt.AlignLeft | Qt.AlignTop)
                best_params_layout.addWidget(value_widget, row, col + 1, Qt.AlignLeft | Qt.AlignTop)
                label_widget.hide()
                value_widget.hide()
                self._optuna_best_summary_cells.append((label_widget, value_widget))
            self._populate_optuna_best_params_grid({})
            optuna_results_layout.addWidget(best_title, 1, 0, Qt.AlignTop)
            optuna_results_layout.addWidget(self._optuna_best_summary_panel, 1, 1)

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
                checkbox = QRadioButton(label)
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
            reward_group = QGroupBox(
                f"Training Diagnostics (ep_rew_mean, last {self._reward_stat_window} episodes)"
            )
            reward_group.setObjectName("card")
            reward_group.setProperty("titleAlign", "left")
            reward_group.setProperty("titleTone", "line")
            reward_group_layout = QVBoxLayout(reward_group)
            reward_group_layout.setContentsMargins(12, 10, 12, 12)
            reward_group_layout.setSpacing(10)
            reward_group_layout.setAlignment(Qt.AlignTop)

            self._reward_count_value = QLabel("-")
            self._reward_mean_value = QLabel("-")
            self._reward_std_value = QLabel("-")
            self._reward_snr_value = QLabel("-")
            self._reward_quantiles_value = QLabel("-")
            self._reward_quantiles_value.setWordWrap(False)
            self._reward_quantiles_value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._reward_eval_value = QLabel("-")
            self._reward_rolling_sharpe_value = QLabel("-")
            self._reward_signal_band_value = QLabel("-")
            self._reward_update_regime_value = QLabel("-")
            self._reward_critic_regime_value = QLabel("-")
            self._reward_quality_flags_value = QLabel("-")
            self._reward_quality_flags_value.setWordWrap(True)
            self._reward_hint_value = QLabel("Waiting for ep_rew_mean samples.")
            self._reward_hint_value.setWordWrap(True)
            summary_grid = QGridLayout()
            summary_grid.setContentsMargins(0, 0, 0, 0)
            summary_grid.setHorizontalSpacing(28)
            summary_grid.setVerticalSpacing(10)
            summary_grid.setAlignment(Qt.AlignTop)
            summary_grid.setColumnStretch(1, 1)
            summary_grid.setColumnStretch(3, 1)

            def add_summary_row(row_index: int, left_label: str, left_value: QLabel, right_label: str, right_value: QLabel) -> None:
                left_title = QLabel(left_label, reward_group)
                left_title.setStyleSheet(
                    "color: #90a0b6; font-size: 12px; font-weight: 600; padding-bottom: 2px;"
                )
                left_value.setParent(reward_group)
                left_value.setWordWrap(True)
                left_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
                left_value.setMinimumHeight(left_value.sizeHint().height() + 4)
                left_value.setStyleSheet(
                    "color: #e7edf7; font-size: 13px; font-weight: 600; padding-bottom: 2px;"
                )

                right_title = QLabel(right_label, reward_group)
                right_title.setStyleSheet(
                    "color: #90a0b6; font-size: 12px; font-weight: 600; padding-bottom: 2px;"
                )
                right_value.setParent(reward_group)
                right_value.setWordWrap(True)
                right_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
                right_value.setMinimumHeight(right_value.sizeHint().height() + 4)
                right_value.setStyleSheet(
                    "color: #e7edf7; font-size: 13px; font-weight: 600; padding-bottom: 2px;"
                )

                summary_grid.addWidget(left_title, row_index, 0, Qt.AlignLeft | Qt.AlignTop)
                summary_grid.addWidget(left_value, row_index, 1, Qt.AlignLeft | Qt.AlignTop)
                summary_grid.addWidget(right_title, row_index, 2, Qt.AlignLeft | Qt.AlignTop)
                summary_grid.addWidget(right_value, row_index, 3, Qt.AlignLeft | Qt.AlignTop)

            def add_summary_full_row(row_index: int, label_text: str, value_label: QLabel) -> None:
                title = QLabel(label_text, reward_group)
                title.setStyleSheet(
                    "color: #90a0b6; font-size: 12px; font-weight: 600; padding-bottom: 2px;"
                )
                value_label.setParent(reward_group)
                value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                value_label.setMinimumHeight(value_label.sizeHint().height() + 4)
                value_label.setStyleSheet(
                    "color: #e7edf7; font-size: 13px; font-weight: 600; padding-bottom: 2px;"
                )
                summary_grid.addWidget(title, row_index, 0, Qt.AlignLeft | Qt.AlignTop)
                summary_grid.addWidget(value_label, row_index, 1, 1, 3, Qt.AlignLeft | Qt.AlignTop)

            def add_summary_single_row(row_index: int, label_text: str, value_label: QLabel) -> None:
                title = QLabel(label_text, reward_group)
                title.setStyleSheet(
                    "color: #90a0b6; font-size: 12px; font-weight: 600; padding-bottom: 2px;"
                )
                value_label.setParent(reward_group)
                value_label.setWordWrap(True)
                value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                value_label.setMinimumHeight(value_label.sizeHint().height() + 4)
                value_label.setStyleSheet(
                    "color: #e7edf7; font-size: 13px; font-weight: 600; padding-bottom: 2px;"
                )
                summary_grid.addWidget(title, row_index, 0, Qt.AlignLeft | Qt.AlignTop)
                summary_grid.addWidget(value_label, row_index, 1, Qt.AlignLeft | Qt.AlignTop)

            add_summary_row(0, "samples", self._reward_count_value, "reward mean", self._reward_mean_value)
            add_summary_row(1, "reward std", self._reward_std_value, "reward SNR", self._reward_snr_value)
            add_summary_full_row(2, "quantiles", self._reward_quantiles_value)
            add_summary_row(3, "eval mean reward", self._reward_eval_value, "rolling sharpe", self._reward_rolling_sharpe_value)
            add_summary_row(4, "signal band", self._reward_signal_band_value, "update regime", self._reward_update_regime_value)
            add_summary_single_row(5, "critic regime", self._reward_critic_regime_value)
            summary_grid.setRowStretch(6, 1)
            reward_group_layout.addLayout(summary_grid)

            narrative_layout = QGridLayout()
            narrative_layout.setContentsMargins(0, 6, 0, 0)
            narrative_layout.setHorizontalSpacing(16)
            narrative_layout.setVerticalSpacing(10)
            narrative_layout.setAlignment(Qt.AlignTop)
            narrative_layout.setColumnStretch(1, 1)
            self._reward_quality_flags_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._reward_hint_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._reward_quality_flags_value.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self._reward_hint_value.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self._reward_quality_flags_value.setWordWrap(False)
            self._reward_hint_value.setWordWrap(False)
            self._reward_quality_flags_value.setMinimumHeight(self._reward_quality_flags_value.sizeHint().height() + 4)
            self._reward_hint_value.setMinimumHeight(self._reward_hint_value.sizeHint().height() + 4)
            quality_title = QLabel("quality flags", reward_group)
            quality_title.setStyleSheet(
                "color: #90a0b6; font-size: 12px; font-weight: 600; padding-bottom: 2px;"
            )
            interpretation_title = QLabel("interpretation", reward_group)
            interpretation_title.setStyleSheet(
                "color: #90a0b6; font-size: 12px; font-weight: 600; padding-bottom: 2px;"
            )
            self._reward_quality_flags_value.setStyleSheet(
                "color: #dbe4f2; font-size: 13px; padding-bottom: 2px;"
            )
            self._reward_hint_value.setStyleSheet(
                "color: #dbe4f2; font-size: 13px; padding-bottom: 2px;"
            )
            narrative_layout.addWidget(quality_title, 0, 0, Qt.AlignLeft | Qt.AlignTop)
            narrative_layout.addWidget(self._reward_quality_flags_value, 0, 1, Qt.AlignLeft | Qt.AlignTop)
            narrative_layout.addWidget(interpretation_title, 1, 0, Qt.AlignLeft | Qt.AlignTop)
            narrative_layout.addWidget(self._reward_hint_value, 1, 1, Qt.AlignLeft | Qt.AlignTop)
            narrative_layout.setRowStretch(2, 1)
            reward_group_layout.addLayout(narrative_layout)
            reward_group_layout.addStretch(1)

            details_tabs = QTabWidget()
            details_tabs.setDocumentMode(True)
            details_tabs.setMovable(False)
            details_tabs.tabBar().setExpanding(False)
            details_tabs.tabBar().setDrawBase(False)
            _apply_card_tabs_style(details_tabs)

            reward_tab = QWidget()
            reward_tab.setObjectName("modelTab")
            reward_tab_layout = QVBoxLayout(reward_tab)
            reward_tab_layout.setContentsMargins(0, 0, 0, 0)
            reward_tab_layout.setSpacing(0)
            reward_tab_layout.setAlignment(Qt.AlignTop)
            reward_tab_layout.addWidget(reward_group)

            log_tab = QWidget()
            log_tab.setObjectName("modelTab")
            log_layout = QVBoxLayout(log_tab)
            log_layout.setContentsMargins(0, 0, 0, 0)
            log_layout.setSpacing(0)
            self._embedded_log = LogWidget(
                title="",
                with_timestamp=True,
                monospace=True,
                font_point_delta=2,
            )
            log_layout.addWidget(self._embedded_log)

            details_tabs.addTab(reward_tab, "Training Diagnostics")
            details_tabs.addTab(log_tab, "Log")

            optuna_details_tabs = QTabWidget()
            optuna_details_tabs.setDocumentMode(True)
            optuna_details_tabs.setMovable(False)
            optuna_details_tabs.tabBar().setExpanding(False)
            optuna_details_tabs.tabBar().setDrawBase(False)
            _apply_card_tabs_style(optuna_details_tabs)

            optuna_results_tab = QWidget()
            optuna_results_tab.setObjectName("modelTab")
            optuna_results_layout_wrap = QVBoxLayout(optuna_results_tab)
            optuna_results_layout_wrap.setContentsMargins(0, 0, 0, 0)
            optuna_results_layout_wrap.setSpacing(0)
            optuna_results_layout_wrap.setAlignment(Qt.AlignTop)
            optuna_results_layout_wrap.addWidget(optuna_results)

            optuna_log_tab = QWidget()
            optuna_log_tab.setObjectName("modelTab")
            optuna_log_layout = QVBoxLayout(optuna_log_tab)
            optuna_log_layout.setContentsMargins(0, 0, 0, 0)
            optuna_log_layout.setSpacing(0)
            self._optuna_embedded_log = LogWidget(
                title="",
                with_timestamp=True,
                monospace=True,
                font_point_delta=2,
            )
            optuna_log_layout.addWidget(self._optuna_embedded_log)

            optuna_details_tabs.addTab(optuna_results_tab, "Optuna Results")
            optuna_details_tabs.addTab(optuna_log_tab, "Log")

            details_stack = QStackedWidget()
            details_stack.addWidget(details_tabs)
            details_stack.addWidget(optuna_details_tabs)
            details_stack.setCurrentIndex(0)

            curve_panel = QGroupBox("")
            curve_layout = QVBoxLayout(curve_panel)
            curve_layout.setContentsMargins(10, 10, 10, 10)
            curve_layout.setSpacing(10)
            curve_layout.addWidget(self._chart_stack, stretch=1)
            curve_layout.addWidget(chooser)
            curve_layout.addWidget(optuna_selector)

            details_panel = QGroupBox("")
            details_layout = QVBoxLayout(details_panel)
            details_layout.setContentsMargins(10, 10, 10, 10)
            details_layout.setSpacing(0)
            details_layout.setAlignment(Qt.AlignTop)
            details_layout.addWidget(details_stack)

            details_splitter = QSplitter(Qt.Vertical)
            details_splitter.setChildrenCollapsible(False)
            details_splitter.addWidget(curve_panel)
            details_splitter.addWidget(details_panel)
            details_splitter.setStretchFactor(0, 1)
            details_splitter.setStretchFactor(1, 1)
            layout.addWidget(details_splitter, stretch=1)
            optuna_selector.setVisible(False)
            self._reward_group = reward_group
            self._details_stack = details_stack
            self._details_panel = details_panel
            self._details_splitter = details_splitter
            self._update_reward_diagnostics()
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
        self._reward_run_started_at = self._current_timestamp()
        self._plot_timer.restart()
        for key in self._metric_data:
            self._metric_data[key]["x"].clear()
            self._metric_data[key]["y"].clear()
            self._curves[key].setData([])
        self._latest_metric_values.clear()
        self._reward_samples.clear()
        self._rolling_sharpe_samples.clear()
        self._update_reward_diagnostics()
        self._sync_curve_visibility()
        self._refresh_training_plot_range()

    def reset_optuna_metrics(self) -> None:
        if not self._charts_available:
            return
        self.update_optuna_status("")
        self.reset_optuna_results()
        for key in self._optuna_data:
            self._optuna_data[key]["x"].clear()
            self._optuna_data[key]["y"].clear()
            self._optuna_curves[key].setData([])
        for key in self._optuna_visible:
            self._optuna_curves[key].setData([])

    def reset_optuna_results(self) -> None:
        trial_label = getattr(self, "_optuna_trial_summary_panel", None)
        if trial_label is not None:
            trial_label.setText(format_optuna_empty_trial())
        self._populate_optuna_best_params_grid({})

    def update_optuna_trial_summary(self, text: str) -> None:
        trial_label = getattr(self, "_optuna_trial_summary_panel", None)
        if trial_label is not None:
            trial_label.setText(format_optuna_trial_summary(text))

    def update_optuna_best_params(self, params: dict) -> None:
        if not params:
            return
        self._populate_optuna_best_params_grid(params)

    def _populate_optuna_best_params_grid(self, params: dict) -> None:
        cells = getattr(self, "_optuna_best_summary_cells", None)
        if not cells:
            return
        label_map = {
            "learning_rate": "LR",
            "gamma": "Gamma",
            "gae_lambda": "GAE",
            "clip_range": "Clip",
            "ent_coef": "Entropy",
            "vf_coef": "VF coef",
            "n_steps": "Steps",
            "batch_size": "Batch",
            "n_epochs": "Epochs",
            "episode_length": "Episode",
            "reward_clip": "R clip",
            "min_position_change": "Min chg",
            "position_step": "Pos step",
            "risk_aversion": "Risk",
            "turnover_penalty": "Turnover",
            "exposure_penalty": "Exposure",
            "max_position": "Max pos",
        }
        ordered_keys = [
            "learning_rate",
            "gamma",
            "gae_lambda",
            "clip_range",
            "ent_coef",
            "vf_coef",
            "n_steps",
            "batch_size",
            "n_epochs",
            "episode_length",
            "reward_clip",
            "min_position_change",
            "position_step",
            "risk_aversion",
            "turnover_penalty",
            "exposure_penalty",
            "max_position",
        ]
        rows: list[tuple[str, str]] = []
        for key in ordered_keys:
            if key not in params:
                continue
            value = params[key]
            if isinstance(value, float):
                value_text = f"{value:.6g}"
            else:
                value_text = str(value)
            rows.append((label_map.get(key, key), value_text))
        if not rows:
            rows = [("Best params", "—")]
        for index, (label_widget, value_widget) in enumerate(cells):
            if index < len(rows):
                label_text, value_text = rows[index]
                label_widget.setText(label_text)
                value_widget.setText(value_text)
                label_widget.show()
                value_widget.show()
            else:
                label_widget.hide()
                value_widget.hide()

    def update_optuna_status(self, status: str) -> None:
        if not self._charts_available:
            return
        text = str(status or "").strip()
        if not text:
            self._optuna_plot.setTitle(self._optuna_title_base)
            return
        self._optuna_plot.setTitle(f"{self._optuna_title_base} - {text}")

    def flush_plot(self) -> None:
        if not self._charts_available:
            return
        for _, key in self._metrics:
            if not self._checkboxes[key].isChecked():
                continue
            data = self._metric_data[key]
            self._set_curve_data(key, list(data["x"]), list(data["y"]))
        self._refresh_training_plot_range()

    def append_metric_point(self, key: str, step: float, value: float) -> None:
        if not self._charts_available:
            return
        if key not in self._accepted_metric_keys:
            return
        self._current_step = int(step)
        self._latest_metric_values[key] = value
        if key == "ep_rew_mean":
            self._reward_samples.append(value)
            self._update_reward_diagnostics()
        elif key == "step_pnl_mean":
            self._rolling_sharpe_samples.append(value)
            rolling_sharpe = self._compute_rolling_sharpe(self._rolling_sharpe_samples)
            if rolling_sharpe is not None:
                self._latest_metric_values["rolling_sharpe"] = rolling_sharpe
                self._append_point("rolling_sharpe", step, rolling_sharpe)
        elif key == "eval/mean_reward" and self._reward_samples:
            # Persist eval snapshots into training diagnostics immediately so the
            # CSV keeps explicit eval points instead of only piggybacking on the
            # next episode-reward update.
            self._update_reward_diagnostics()
        if key in self._metric_data:
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
        details_stack = getattr(self, "_details_stack", None)
        if details_stack is not None:
            details_stack.setCurrentIndex(0)
        details_panel = getattr(self, "_details_panel", None)
        if details_panel is not None:
            details_panel.setVisible(True)

    def show_optuna_plot(self) -> None:
        if not self._charts_available:
            return
        self._chart_stack.setCurrentWidget(self._optuna_plot)
        self._metrics_selector.setVisible(False)
        self._optuna_selector.setVisible(True)
        details_stack = getattr(self, "_details_stack", None)
        if details_stack is not None:
            details_stack.setCurrentIndex(1)
        details_panel = getattr(self, "_details_panel", None)
        if details_panel is not None:
            details_panel.setVisible(True)

    def append_log(self, message: str) -> None:
        embedded = getattr(self, "_embedded_log", None)
        if embedded is not None:
            embedded.append(message)
        optuna_embedded = getattr(self, "_optuna_embedded_log", None)
        if optuna_embedded is not None:
            optuna_embedded.append(message)

    def _append_point(self, key: str, step: float, value: float) -> None:
        data = self._metric_data[key]
        if data["x"]:
            last_step = data["x"][-1]
            if step < last_step:
                return
            if step == last_step:
                data["y"][-1] = value
                if self._checkboxes[key].isChecked():
                    self._set_curve_data(key, list(data["x"]), list(data["y"]))
                    self._refresh_training_plot_range()
                return
        data["x"].append(step)
        data["y"].append(value)
        if not self._checkboxes[key].isChecked():
            return
        should_update_now = len(data["x"]) <= 1 or key in {"eval/mean_reward", "fps"}
        if not self._plot_timer.isValid():
            self._plot_timer.start()
            should_update_now = True
        elif self._plot_timer.elapsed() >= self._plot_interval_ms:
            should_update_now = True
        if not should_update_now:
            return
        self._set_curve_data(key, list(data["x"]), list(data["y"]))
        self._refresh_training_plot_range()
        self._plot_timer.restart()

    def _append_optuna_point(self, key: str, trial: float, value: float) -> None:
        data = self._optuna_data[key]
        if data["x"]:
            last_trial = data["x"][-1]
            if trial < last_trial:
                return
            if trial == last_trial:
                data["y"][-1] = value
                if key in self._optuna_curves and key in self._optuna_visible:
                    self._optuna_curves[key].setData(list(data["x"]), list(data["y"]))
                return
        data["x"].append(trial)
        data["y"].append(value)
        if key in self._optuna_curves and key in self._optuna_visible:
            self._optuna_curves[key].setData(list(data["x"]), list(data["y"]))

    def _toggle_curve(self, key: str, visible: bool) -> None:
        data = self._metric_data[key]
        if visible:
            self._set_curve_data(key, list(data["x"]), list(data["y"]))
            if key not in self._legend_keys:
                self._legend.addItem(self._curves[key], self._metric_labels[key])
                self._legend_keys.add(key)
            if data["y"]:
                self._set_curve_data(key, list(data["x"]), list(data["y"]))
        else:
            self._curves[key].setData([], [])
            if key in self._legend_keys:
                self._legend.removeItem(self._curves[key])
                self._legend_keys.remove(key)
        self._refresh_training_plot_range()

    def _set_curve_data(self, key: str, xs: list[float], ys: list[float]) -> None:
        curve = self._curves[key]
        color = self._curve_colors.get(key, "#4C78A8")
        if len(xs) == 1:
            curve.setData(
                xs,
                ys,
                pen=pg.mkPen(color, width=2),
                symbol="o",
                symbolSize=7,
                symbolBrush=color,
                symbolPen=pg.mkPen(color, width=1),
            )
            return
        curve.setData(
            xs,
            ys,
            pen=pg.mkPen(color, width=2),
            symbol=None,
        )

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
        self._refresh_optuna_plot_range()

    def _sync_curve_visibility(self) -> None:
        for _, key in self._metrics:
            self._toggle_curve(key, self._checkboxes[key].isChecked())

    def _sync_optuna_curve_visibility(self) -> None:
        for key, _ in self._optuna_metrics:
            self._toggle_optuna_curve(key, key in self._optuna_visible)

    def _refresh_training_plot_range(self) -> None:
        if not self._charts_available:
            return
        visible_points: list[tuple[list[float], list[float]]] = []
        for _, key in self._metrics:
            checkbox = self._checkboxes.get(key)
            if checkbox is None or not checkbox.isChecked():
                continue
            data = self._metric_data[key]
            if not data["x"] or not data["y"]:
                continue
            visible_points.append((list(data["x"]), list(data["y"])))
        if not visible_points:
            self._plot.enableAutoRange(axis="x", enable=True)
            self._plot.enableAutoRange(axis="y", enable=True)
            self._plot.autoRange()
            return
        xs = [value for series, _ in visible_points for value in series]
        ys = [value for _, series in visible_points for value in series]
        x_min = min(xs)
        x_max = max(xs)
        y_min = min(ys)
        y_max = max(ys)
        if x_min == x_max:
            x_pad = max(1.0, abs(x_min) * 0.05)
            x_min -= x_pad
            x_max += x_pad
        else:
            x_pad = max((x_max - x_min) * 0.03, 1.0)
            x_min -= x_pad
            x_max += x_pad
        y_abs_max = max(abs(y_min), abs(y_max), 1e-12)
        if y_min == y_max:
            y_pad = max(y_abs_max * 0.1, 1e-6)
            y_min -= y_pad
            y_max += y_pad
        else:
            y_pad = max((y_max - y_min) * 0.08, y_abs_max * 0.05, 1e-6)
            y_min -= y_pad
            y_max += y_pad
        self._plot.enableAutoRange(axis="x", enable=False)
        self._plot.enableAutoRange(axis="y", enable=False)
        self._plot.setXRange(x_min, x_max, padding=0.0)
        self._plot.setYRange(y_min, y_max, padding=0.0)

    def _format_metric_value(self, value: float | None) -> str:
        if value is None:
            return "-"
        abs_value = abs(value)
        if abs_value >= 1000:
            return f"{value:,.2f}"
        if abs_value >= 1:
            return f"{value:.4f}"
        return f"{value:.6f}"

    def _refresh_optuna_plot_range(self) -> None:
        if not self._charts_available:
            return
        self._optuna_plot.enableAutoRange(axis="x", enable=True)
        self._optuna_plot.enableAutoRange(axis="y", enable=True)
        self._optuna_plot.autoRange()

    def _update_reward_diagnostics(self) -> None:
        if not self._charts_available:
            return
        count = len(self._reward_samples)
        if count == 0:
            self._reward_count_value.setText("0")
            self._reward_mean_value.setText("-")
            self._reward_std_value.setText("-")
            self._reward_snr_value.setText("-")
            self._reward_quantiles_value.setText("-")
            self._reward_eval_value.setText("-")
            self._reward_rolling_sharpe_value.setText("-")
            self._reward_signal_band_value.setText("-")
            self._reward_update_regime_value.setText("-")
            self._reward_critic_regime_value.setText("-")
            self._reward_quality_flags_value.setText("-")
            self._reward_hint_value.setText("Waiting for ep_rew_mean samples.")
            return
        values = list(self._reward_samples)
        mean = sum(values) / count
        variance = sum((value - mean) ** 2 for value in values) / count
        std = math.sqrt(max(variance, 0.0))
        snr = abs(mean) / std if std > 1e-12 else float("inf")
        p10 = self._quantile(values, 0.10)
        p50 = self._quantile(values, 0.50)
        p90 = self._quantile(values, 0.90)
        eval_mean_reward = self._latest_metric_values.get("eval/mean_reward")
        rolling_sharpe = self._latest_metric_values.get("rolling_sharpe")
        approx_kl = self._latest_metric_values.get("approx_kl")
        clip_fraction = self._latest_metric_values.get("clip_fraction")
        explained_variance = self._latest_metric_values.get("explained_variance")
        abs_delta_mean = self._latest_metric_values.get("abs_delta_mean")
        abs_price_return_mean = self._latest_metric_values.get("abs_price_return_mean")
        signal_band = self._classify_signal_band(snr)
        update_regime = self._classify_update_regime(approx_kl, clip_fraction)
        critic_regime = self._classify_critic_regime(explained_variance)
        quality_flags = self._build_quality_flags(
            snr=snr,
            eval_mean_reward=eval_mean_reward,
            approx_kl=approx_kl,
            clip_fraction=clip_fraction,
            explained_variance=explained_variance,
            abs_delta_mean=abs_delta_mean,
            abs_price_return_mean=abs_price_return_mean,
        )
        snr_text = "inf" if math.isinf(snr) else f"{snr:.4f}"
        self._reward_count_value.setText(str(count))
        self._reward_mean_value.setText(self._format_stat(mean))
        self._reward_std_value.setText(self._format_stat(std))
        self._reward_snr_value.setText(snr_text)
        self._reward_quantiles_value.setText(
            f"p10={self._format_stat(p10)}  p50={self._format_stat(p50)}  p90={self._format_stat(p90)}"
        )
        self._reward_eval_value.setText(
            "-" if eval_mean_reward is None else self._format_stat(float(eval_mean_reward))
        )
        self._reward_rolling_sharpe_value.setText(
            "-" if rolling_sharpe is None else self._format_stat(float(rolling_sharpe))
        )
        self._reward_signal_band_value.setText(signal_band)
        self._reward_update_regime_value.setText(update_regime)
        self._reward_critic_regime_value.setText(critic_regime)
        self._reward_quality_flags_value.setText(quality_flags or "clean")
        if std <= 1e-12:
            hint = "Reward variance is near zero in this window."
        elif snr < 0.5:
            hint = "Low-SNR window: mean reward is small relative to volatility."
        elif snr < 1.0:
            hint = "Moderate-noise window: reward signal exists but is still noisy."
        else:
            hint = "Reward signal is stronger than its recent volatility."
        if abs(p90 - p10) > max(std * 2.5, 1e-9):
            hint += " Wide percentile spread suggests a heavy-tailed or unstable reward distribution."
        self._reward_hint_value.setText(hint)
        self._append_reward_diagnostics_row(
            samples=count,
            mean=mean,
            std=std,
            snr=snr,
            p10=p10,
            p50=p50,
            p90=p90,
            interpretation=hint,
        )

    def _append_reward_diagnostics_row(
        self,
        *,
        samples: int,
        mean: float,
        std: float,
        snr: float,
        p10: float,
        p50: float,
        p90: float,
        interpretation: str,
    ) -> None:
        path = self._reward_diagnostics_path
        component_columns = [
            ("reward_step_mean", "reward_step_mean"),
            ("step_pnl_mean", "step_pnl_mean"),
            ("rolling_sharpe", "rolling_sharpe"),
            ("cost_mean", "cost_mean"),
            ("holding_cost_mean", "holding_cost_mean"),
            ("abs_delta_mean", "abs_delta_mean"),
            ("abs_price_return_mean", "abs_price_return_mean"),
            ("eval_mean_reward", "eval/mean_reward"),
            ("eval_trade_rate_1k", "eval/trade_rate_1k"),
            ("eval_flat_ratio", "eval/flat_ratio"),
            ("eval_ls_imbalance", "eval/ls_imbalance"),
            ("eval_max_drawdown", "eval/max_drawdown"),
            ("early_stop_patience_left", "early_stop_patience_left"),
            ("explained_variance", "explained_variance"),
            ("approx_kl", "approx_kl"),
            ("clip_fraction", "clip_fraction"),
            ("entropy_loss", "entropy_loss"),
            ("policy_gradient_loss", "policy_gradient_loss"),
            ("value_loss", "value_loss"),
            ("loss", "loss"),
            ("std_metric", "std"),
            ("fps", "fps"),
        ]
        component_values = {
            metric_key: self._latest_metric_values.get(metric_key)
            for _, metric_key in component_columns
        }
        reward_step_mean = component_values.get("reward_step_mean")
        step_pnl_mean = component_values.get("step_pnl_mean")
        rolling_sharpe = component_values.get("rolling_sharpe")
        cost_mean = component_values.get("cost_mean")
        holding_cost_mean = component_values.get("holding_cost_mean")
        abs_delta_mean = component_values.get("abs_delta_mean")
        abs_price_return_mean = component_values.get("abs_price_return_mean")
        eval_mean_reward = component_values.get("eval/mean_reward")
        eval_trade_rate_1k = component_values.get("eval/trade_rate_1k")
        eval_flat_ratio = component_values.get("eval/flat_ratio")
        eval_ls_imbalance = component_values.get("eval/ls_imbalance")
        eval_max_drawdown = component_values.get("eval/max_drawdown")
        early_stop_patience_left = component_values.get("early_stop_patience_left")
        explained_variance = component_values.get("explained_variance")
        approx_kl = component_values.get("approx_kl")
        clip_fraction = component_values.get("clip_fraction")
        entropy_loss = component_values.get("entropy_loss")
        policy_gradient_loss = component_values.get("policy_gradient_loss")
        value_loss = component_values.get("value_loss")
        loss_value = component_values.get("loss")
        std_metric = component_values.get("std")
        fps = component_values.get("fps")
        tail_spread = p90 - p10
        net_step_mean = self._safe_subtract(step_pnl_mean, cost_mean, holding_cost_mean)
        action_to_move_ratio = self._safe_divide(abs_delta_mean, abs_price_return_mean)
        signal_band = self._classify_signal_band(snr)
        update_regime = self._classify_update_regime(approx_kl, clip_fraction)
        critic_regime = self._classify_critic_regime(explained_variance)
        quality_flags = self._build_quality_flags(
            snr=snr,
            eval_mean_reward=eval_mean_reward,
            approx_kl=approx_kl,
            clip_fraction=clip_fraction,
            explained_variance=explained_variance,
            abs_delta_mean=abs_delta_mean,
            abs_price_return_mean=abs_price_return_mean,
        )
        fieldnames = [
            "schema_version",
            "timestamp",
            "run_started_at",
            "step",
            "samples",
            "reward_mean",
            "reward_std",
            "reward_snr",
            "reward_p10",
            "reward_p50",
            "reward_p90",
            "reward_tail_spread",
            "signal_band",
            "interpretation",
            "eval_mean_reward",
            "eval_trade_rate_1k",
            "eval_flat_ratio",
            "eval_ls_imbalance",
            "eval_max_drawdown",
            "reward_step_mean",
            "step_pnl_mean",
            "net_step_mean",
            "rolling_sharpe",
            "cost_mean",
            "holding_cost_mean",
            "abs_delta_mean",
            "abs_price_return_mean",
            "action_to_move_ratio",
            "approx_kl",
            "clip_fraction",
            "update_regime",
            "explained_variance",
            "critic_regime",
            "value_loss",
            "entropy_loss",
            "policy_gradient_loss",
            "loss",
            "std_metric",
            "fps",
            "early_stop_patience_left",
            "quality_flags",
        ]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_reward_diagnostics_schema(path, fieldnames)
            row = {
                "schema_version": "v2",
                "timestamp": self._current_timestamp(),
                "run_started_at": self._reward_run_started_at,
                "step": str(self._current_step),
                "samples": str(samples),
                "reward_mean": f"{mean:.10g}",
                "reward_std": f"{std:.10g}",
                "reward_snr": "inf" if math.isinf(snr) else f"{snr:.10g}",
                "reward_p10": f"{p10:.10g}",
                "reward_p50": f"{p50:.10g}",
                "reward_p90": f"{p90:.10g}",
                "reward_tail_spread": f"{tail_spread:.10g}",
                "signal_band": signal_band,
                "interpretation": interpretation,
                "eval_mean_reward": self._format_csv_metric_value(eval_mean_reward),
                "eval_trade_rate_1k": self._format_csv_metric_value(eval_trade_rate_1k),
                "eval_flat_ratio": self._format_csv_metric_value(eval_flat_ratio),
                "eval_ls_imbalance": self._format_csv_metric_value(eval_ls_imbalance),
                "eval_max_drawdown": self._format_csv_metric_value(eval_max_drawdown),
                "reward_step_mean": self._format_csv_metric_value(reward_step_mean),
                "step_pnl_mean": self._format_csv_metric_value(step_pnl_mean),
                "net_step_mean": self._format_csv_metric_value(net_step_mean),
                "rolling_sharpe": self._format_csv_metric_value(rolling_sharpe),
                "cost_mean": self._format_csv_metric_value(cost_mean),
                "holding_cost_mean": self._format_csv_metric_value(holding_cost_mean),
                "abs_delta_mean": self._format_csv_metric_value(abs_delta_mean),
                "abs_price_return_mean": self._format_csv_metric_value(abs_price_return_mean),
                "action_to_move_ratio": self._format_csv_metric_value(action_to_move_ratio),
                "approx_kl": self._format_csv_metric_value(approx_kl),
                "clip_fraction": self._format_csv_metric_value(clip_fraction),
                "update_regime": update_regime,
                "explained_variance": self._format_csv_metric_value(explained_variance),
                "critic_regime": critic_regime,
                "value_loss": self._format_csv_metric_value(value_loss),
                "entropy_loss": self._format_csv_metric_value(entropy_loss),
                "policy_gradient_loss": self._format_csv_metric_value(policy_gradient_loss),
                "loss": self._format_csv_metric_value(loss_value),
                "std_metric": self._format_csv_metric_value(std_metric),
                "fps": self._format_csv_metric_value(fps),
                "early_stop_patience_left": self._format_csv_metric_value(early_stop_patience_left),
                "quality_flags": quality_flags,
            }
            with path.open("a", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                if fh.tell() == 0:
                    writer.writeheader()
                writer.writerow(row)
        except OSError:
            return

    @staticmethod
    def _resolve_training_diagnostics_path() -> Path:
        training_dir = Path(DATA_DIR) / "training"
        new_path = training_dir / "training_diagnostics.csv"
        old_path = training_dir / "reward_diagnostics.csv"
        if new_path.exists() or not old_path.exists():
            return new_path
        try:
            training_dir.mkdir(parents=True, exist_ok=True)
            old_path.replace(new_path)
        except OSError:
            return old_path
        return new_path

    @staticmethod
    def _format_stat(value: float) -> str:
        return f"{value:.6g}"

    @staticmethod
    def _format_csv_metric_value(value: Optional[float]) -> str:
        if value is None:
            return ""
        if math.isinf(value):
            return "inf"
        return f"{value:.10g}"

    @staticmethod
    def _safe_subtract(base: Optional[float], *parts: Optional[float]) -> Optional[float]:
        if base is None:
            return None
        total = float(base)
        for part in parts:
            if part is not None:
                total -= float(part)
        return total

    @staticmethod
    def _safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
        if numerator is None or denominator is None or abs(float(denominator)) <= 1e-12:
            return None
        return float(numerator) / float(denominator)

    @staticmethod
    def _classify_signal_band(snr: float) -> str:
        if math.isinf(snr):
            return "flat"
        if snr < 0.5:
            return "low"
        if snr < 1.0:
            return "moderate"
        return "strong"

    @staticmethod
    def _classify_update_regime(
        approx_kl: Optional[float],
        clip_fraction: Optional[float],
    ) -> str:
        if approx_kl is None and clip_fraction is None:
            return "unknown"
        kl = 0.0 if approx_kl is None else float(approx_kl)
        clip = 0.0 if clip_fraction is None else float(clip_fraction)
        if kl < 0.001 and clip < 0.01:
            return "weak"
        if kl > 0.03 or clip > 0.08:
            return "aggressive"
        return "healthy"

    @staticmethod
    def _classify_critic_regime(explained_variance: Optional[float]) -> str:
        if explained_variance is None:
            return "unknown"
        value = float(explained_variance)
        if value < 0.0:
            return "poor"
        if value < 0.2:
            return "usable"
        return "good"

    @classmethod
    def _build_quality_flags(
        cls,
        *,
        snr: float,
        eval_mean_reward: Optional[float],
        approx_kl: Optional[float],
        clip_fraction: Optional[float],
        explained_variance: Optional[float],
        abs_delta_mean: Optional[float],
        abs_price_return_mean: Optional[float],
    ) -> str:
        flags: list[str] = []
        if not math.isinf(snr) and snr < 0.5:
            flags.append("low_signal")
        if eval_mean_reward is None:
            flags.append("no_eval")
        elif eval_mean_reward <= 0.0:
            flags.append("eval_weak")
        if cls._classify_update_regime(approx_kl, clip_fraction) == "weak":
            flags.append("weak_update")
        if cls._classify_update_regime(approx_kl, clip_fraction) == "aggressive":
            flags.append("aggressive_update")
        if cls._classify_critic_regime(explained_variance) == "poor":
            flags.append("critic_unreliable")
        action_to_move_ratio = cls._safe_divide(abs_delta_mean, abs_price_return_mean)
        if action_to_move_ratio is not None and action_to_move_ratio > 5.0:
            flags.append("high_turnover")
        return ";".join(flags)

    @staticmethod
    def _ensure_reward_diagnostics_schema(path: Path, fieldnames: list[str]) -> None:
        if not path.exists() or path.stat().st_size == 0:
            return
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            existing_fields = reader.fieldnames or []
            if existing_fields == fieldnames:
                return
            rows = list(reader)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                normalized = {field: row.get(field, "") for field in fieldnames}
                writer.writerow(normalized)

    @staticmethod
    def _quantile(values: list[float], q: float) -> float:
        ordered = sorted(values)
        if not ordered:
            return float("nan")
        if len(ordered) == 1:
            return ordered[0]
        position = max(0.0, min(1.0, q)) * (len(ordered) - 1)
        lower = int(math.floor(position))
        upper = int(math.ceil(position))
        if lower == upper:
            return ordered[lower]
        weight = position - lower
        return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

    @staticmethod
    def _compute_rolling_sharpe(values: deque[float]) -> Optional[float]:
        count = len(values)
        if count < 2:
            return None
        sample = list(values)
        mean = sum(sample) / count
        variance = sum((value - mean) ** 2 for value in sample) / count
        std = math.sqrt(max(variance, 0.0))
        if std <= 1e-12:
            return None
        return mean / std

    @staticmethod
    def _current_timestamp() -> str:
        return datetime.now().isoformat(timespec="seconds")

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
