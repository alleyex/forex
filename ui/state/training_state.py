from __future__ import annotations

from PySide6.QtCore import Signal

from ui.state.base import StateBase


class TrainingState(StateBase):
    log_message = Signal(str)
    metric_point = Signal(str, float, float)
    optuna_point = Signal(str, float, float)
    optuna_reset = Signal()
    optuna_trial_summary = Signal(str)
    optuna_best_params = Signal(dict)
    best_params_found = Signal(dict)
