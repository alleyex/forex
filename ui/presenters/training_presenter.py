from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject

from ui.presenters.base import PresenterBase
from ui.state.training_state import TrainingState


class TrainingPresenter(PresenterBase):
    def __init__(self, *, parent: QObject, state: TrainingState) -> None:
        super().__init__(parent=parent, state=state)
        self._current_step = 0

    def handle_log_line(self, line: str) -> None:
        parsed = self._parse_csv_line(line)
        if parsed:
            step, key, value = parsed
            self._current_step = step
            self._state.metric_point.emit(key, float(step), value)
            return

        step = self._parse_int("total_timesteps", line)
        if step is None:
            step = self._parse_int("num_timesteps", line)
        if step is not None:
            self._current_step = step

        parsed = self._parse_kv_line(line)
        if not parsed:
            return
        key, value = parsed
        self._state.metric_point.emit(key, float(self._current_step), value)

    def handle_optuna_log_line(self, line: str) -> None:
        parsed = self._parse_optuna_csv_line(line)
        if not parsed:
            return
        trial, trial_value, best_value, duration = parsed
        display_trial = trial + 1
        self._state.optuna_point.emit("trial_value", display_trial, trial_value)
        self._state.optuna_point.emit("best_value", display_trial, best_value)
        self._state.optuna_point.emit("duration_sec", display_trial, duration)

    def handle_optuna_trial_summary(self, summary: str) -> None:
        if summary:
            self._state.optuna_trial_summary.emit(summary)

    def handle_optuna_best_params(self, params: dict) -> None:
        if params:
            self._state.optuna_best_params.emit(params)

    def handle_best_params_found(self, params: dict) -> None:
        if params:
            self._state.best_params_found.emit(params)

    def reset_optuna_results(self) -> None:
        self._state.optuna_reset.emit()

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
        return None

    @staticmethod
    def _parse_int(key: str, line: str) -> Optional[int]:
        value = TrainingPresenter._parse_float(key, line)
        if value is None:
            return None
        return int(value)
