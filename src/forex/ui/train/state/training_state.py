from PySide6.QtCore import Signal

from forex.ui.train.state.base import StateBase


class TrainingState(StateBase):
    log_message = Signal(str)
    metric_point = Signal(str, float, float)
    optuna_point = Signal(str, float, float)
    optuna_status = Signal(str)
    optuna_reset = Signal()
    optuna_trial_summary = Signal(str)
    optuna_best_params = Signal(dict)
    best_params_found = Signal(dict)
