from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

import ast

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from ui.controllers.process_runner import ProcessRunner


class PPOTrainingController(QObject):
    best_params_found = Signal(dict)

    def __init__(
        self,
        *,
        parent: QObject,
        log: Callable[[str], None],
        ingest_log: Callable[[str], None],
        on_finished: Optional[Callable[[int, QProcess.ExitStatus], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._log = log
        self._ingest_log = ingest_log
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

    def start(self, params: dict, data_path: str) -> None:
        if self._runner.is_running():
            self._log("ℹ️ PPO 訓練仍在進行中")
            return

        optuna_only = bool(params.get("optuna_only"))
        if optuna_only and params.get("optuna_trials", 0) <= 0:
            self._log("⚠️ Optuna 試驗次數需大於 0")
            return

        self._log("▶️ 開始 PPO 訓練")
        self._start_metrics_log_tailer()
        self._use_metrics_log = True
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
            self._log("⚠️ PPO 訓練尚在執行")
            self._stop_metrics_log_tailer()

    def _on_stdout_line(self, line: str) -> None:
        if self._use_metrics_log:
            if self._should_log_summary(line):
                self._log(line)
            if "ep_rew_mean" not in line:
                self._ingest_log(line)
        else:
            self._log(line)
            self._ingest_log(line)
        if line.startswith("Optuna best params:"):
            payload = line.split(":", 1)[1].strip()
            try:
                params = ast.literal_eval(payload)
            except (ValueError, SyntaxError):
                return
            if isinstance(params, dict):
                self.best_params_found.emit(params)

    def _on_stderr_line(self, line: str) -> None:
        self._log(f"⚠️ {line}")

    def _on_finished_internal(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        status = "完成" if exit_status == QProcess.NormalExit else "異常結束"
        self._log(f"⏹️ PPO 訓練{status} (exit={exit_code})")
        self._tail_metrics_log()
        self._stop_metrics_log_tailer()
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

    @staticmethod
    def _should_log_summary(line: str) -> bool:
        return line.startswith("Training setup:") or line.startswith("Optuna best")
