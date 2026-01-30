from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

import ast
import re

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from ui.controllers.process_runner import ProcessRunner
from ui.state.training_state import TrainingState
from ui.utils.formatters import format_training_message


class PPOTrainingController(QObject):
    best_params_found = Signal(dict)
    optuna_trial_logged = Signal(str)
    optuna_best_params_logged = Signal(dict)

    def __init__(
        self,
        *,
        parent: QObject,
        state: TrainingState,
        ingest_log: Callable[[str], None],
        ingest_optuna_log: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[int, QProcess.ExitStatus], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._ingest_log = ingest_log
        self._ingest_optuna_log = ingest_optuna_log
        self._on_finished = on_finished
        self._runner = ProcessRunner(
            parent=self,
            on_stdout_line=self._on_stdout_line,
            on_stderr_line=self._on_stderr_line,
            on_finished=self._on_finished_internal,
        )
        self._metrics_log_path: Optional[str] = None
        self._metrics_tail_timer = QTimer(self)
        self._metrics_tail_timer.setInterval(50)
        self._metrics_tail_timer.timeout.connect(self._tail_metrics_log)
        self._metrics_last_offset = 0
        self._use_metrics_log = False
        self._optuna_log_path: Optional[str] = None
        self._optuna_tail_timer = QTimer(self)
        self._optuna_tail_timer.setInterval(200)
        self._optuna_tail_timer.timeout.connect(self._tail_optuna_log)
        self._optuna_last_offset = 0

    def start(self, params: dict, data_path: str) -> None:
        if self._runner.is_running():
            self._state.log_message.emit(format_training_message("already_running"))
            return

        optuna_only = bool(params.get("optuna_only"))
        if optuna_only and params.get("optuna_trials", 0) <= 0:
            self._state.log_message.emit(format_training_message("optuna_trials_required"))
            return

        self._state.log_message.emit(format_training_message("start"))
        self._start_metrics_log_tailer()
        self._use_metrics_log = True
        if params.get("optuna_trials", 0) > 0:
            self._start_optuna_log_tailer()
        discrete_positions = str(params.get("discrete_positions", "")).strip()
        if not discrete_positions:
            discrete_positions = "-1,0,1"
        args = [
            "ml/rl/train/train_ppo.py",
            "--data",
            data_path,
            "--total-steps",
            str(params["total_steps"]),
            "--learning-rate",
            str(params["learning_rate"]),
            "--gamma",
            str(params["gamma"]),
            "--n-steps",
            str(params["n_steps"]),
            "--batch-size",
            str(params["batch_size"]),
            "--ent-coef",
            str(params["ent_coef"]),
            "--episode-length",
            str(params["episode_length"]),
            "--eval-split",
            str(params["eval_split"]),
            "--transaction-cost-bps",
            str(params["transaction_cost_bps"]),
            "--slippage-bps",
            str(params["slippage_bps"]),
            "--holding-cost-bps",
            str(params["holding_cost_bps"]),
            "--min-position-change",
            str(params["min_position_change"]),
            "--max-position",
            str(params["max_position"]),
            "--position-step",
            str(params["position_step"]),
            "--reward-scale",
            str(params["reward_scale"]),
            "--reward-clip",
            str(params["reward_clip"]),
            "--risk-aversion",
            str(params["risk_aversion"]),
        ]
        if discrete_positions:
            args.append(f"--discrete-positions={discrete_positions}")
        args.extend(["--metrics-log", self._metrics_log_path or ""])
        if not params.get("random_start", True):
            args.append("--no-random-start")
        if params.get("discretize_actions"):
            args.append("--discretize-actions")
        if params.get("optuna_trials", 0) > 0:
            args.extend(
                [
                    "--optuna-trials",
                    str(params["optuna_trials"]),
                    "--optuna-steps",
                    str(params["optuna_steps"]),
                ]
            )
            if self._optuna_log_path:
                args.extend(["--optuna-log", self._optuna_log_path])
            if params.get("optuna_train_best") and not optuna_only:
                args.append("--optuna-train-best")
            optuna_out = params.get("optuna_out", "").strip()
            if optuna_out:
                args.extend(["--optuna-out", optuna_out])
            if optuna_only:
                args.extend(["--verbose", "0"])
        if params.get("resume"):
            args.append("--resume")
        started = self._runner.start(sys.executable, args, env={"PYTHONPATH": "."})
        if not started:
            self._state.log_message.emit(format_training_message("start_failed"))
            self._stop_metrics_log_tailer()
            self._stop_optuna_log_tailer()

    def _on_stdout_line(self, line: str) -> None:
        if self._use_metrics_log:
            if self._should_log_summary(line):
                self._state.log_message.emit(line)
            if "ep_rew_mean" not in line:
                self._ingest_log(line)
        else:
            self._state.log_message.emit(line)
            self._ingest_log(line)
        self._handle_optuna_line(line)
        if line.startswith("Optuna best params:"):
            payload = line.split(":", 1)[1].strip()
            try:
                params = ast.literal_eval(payload)
            except (ValueError, SyntaxError):
                return
            if isinstance(params, dict):
                self.best_params_found.emit(params)

    def _on_stderr_line(self, line: str) -> None:
        self._state.log_message.emit(format_training_message("stderr", line=line))
        self._handle_optuna_line(line)

    def _on_finished_internal(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._state.log_message.emit(
            format_training_message(
                "finished",
                exit_status=exit_status == QProcess.NormalExit,
                exit_code=exit_code,
            )
        )
        self._tail_metrics_log()
        self._tail_optuna_log()
        self._stop_metrics_log_tailer()
        self._stop_optuna_log_tailer()
        if self._on_finished:
            self._on_finished(exit_code, exit_status)

    def _start_metrics_log_tailer(self) -> None:
        tmp_dir = Path(tempfile.gettempdir())
        self._metrics_log_path = str(tmp_dir / f"ppo_metrics_{id(self)}.csv")
        self._metrics_last_offset = 0
        self._metrics_tail_timer.start()

    def _stop_metrics_log_tailer(self) -> None:
        self._metrics_tail_timer.stop()
        if self._metrics_log_path:
            try:
                Path(self._metrics_log_path).unlink(missing_ok=True)
            except Exception:
                pass
        self._metrics_log_path = None
        self._metrics_last_offset = 0
        self._use_metrics_log = False

    def _tail_metrics_log(self) -> None:
        if not self._metrics_log_path:
            return
        path = Path(self._metrics_log_path)
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as fh:
                fh.seek(self._metrics_last_offset)
                data = fh.read()
                self._metrics_last_offset = fh.tell()
        except Exception:
            return
        if not data:
            return
        for line in data.strip().splitlines():
            if line.startswith("step"):
                continue
            self._ingest_log(line)

    def _start_optuna_log_tailer(self) -> None:
        if self._ingest_optuna_log is None:
            return
        tmp_dir = Path(tempfile.gettempdir())
        self._optuna_log_path = str(tmp_dir / f"ppo_optuna_{id(self)}.csv")
        self._optuna_last_offset = 0
        self._optuna_tail_timer.start()

    def _stop_optuna_log_tailer(self) -> None:
        self._optuna_tail_timer.stop()
        if self._optuna_log_path:
            try:
                Path(self._optuna_log_path).unlink(missing_ok=True)
            except Exception:
                pass
        self._optuna_log_path = None
        self._optuna_last_offset = 0

    def _tail_optuna_log(self) -> None:
        if not self._optuna_log_path or self._ingest_optuna_log is None:
            return
        path = Path(self._optuna_log_path)
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as fh:
                fh.seek(self._optuna_last_offset)
                data = fh.read()
                self._optuna_last_offset = fh.tell()
        except Exception:
            return
        if not data:
            return
        for line in data.strip().splitlines():
            if line.startswith("trial"):
                continue
            self._ingest_optuna_log(line)

    @staticmethod
    def _should_log_summary(line: str) -> bool:
        return line.startswith("Training setup:") or line.startswith("Optuna best")

    def _handle_optuna_line(self, line: str) -> None:
        summary, best_params = self._parse_optuna_trial_details(line)
        if summary:
            self.optuna_trial_logged.emit(summary)
        if best_params:
            self.optuna_best_params_logged.emit(best_params)

    @staticmethod
    def _parse_optuna_trial_details(line: str) -> tuple[Optional[str], Optional[dict]]:
        match = re.search(
            r"Trial\s+(?P<trial>\d+)\s+finished with value:\s+(?P<value>[-+0-9.eE]+)",
            line,
        )
        best_match = re.search(
            r"Best is trial\s+(?P<best_trial>\d+)\s+with value:\s+(?P<best_value>[-+0-9.eE]+)",
            line,
        )
        if not match or not best_match:
            return None, None
        trial = match.group("trial")
        value = match.group("value")
        best_trial = best_match.group("best_trial")
        best_value = best_match.group("best_value")
        summary = f"Trial {trial}: value={value} | best={best_value} (trial {best_trial})"
        best_params = None
        if trial == best_trial:
            params_match = re.search(
                r"parameters:\s+(\{.*?\})(?:\.\s+Best is trial|$)",
                line,
            )
            if params_match:
                params_text = params_match.group(1)
                try:
                    parsed = ast.literal_eval(params_text)
                except (ValueError, SyntaxError):
                    parsed = None
                if isinstance(parsed, dict):
                    best_params = parsed
        return summary, best_params
