from __future__ import annotations

import sys
from typing import Callable, Optional

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment


class PPOTrainingController(QObject):
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
        self._process: Optional[QProcess] = None

    def start(self, params: dict, data_path: str) -> None:
        if self._process and self._process.state() != QProcess.NotRunning:
            self._log("ℹ️ PPO 訓練仍在進行中")
            return

        self._process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", ".")
        self._process.setProcessEnvironment(env)

        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished_internal)

        self._log("▶️ 開始 PPO 訓練")
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
        ]
        if params.get("resume"):
            args.append("--resume")
        self._process.start(sys.executable, args)

    def _on_stdout(self) -> None:
        if not self._process:
            return
        output = bytes(self._process.readAllStandardOutput()).decode(errors="replace")
        for line in output.splitlines():
            if line.strip():
                self._log(line)
                self._ingest_log(line)

    def _on_stderr(self) -> None:
        if not self._process:
            return
        output = bytes(self._process.readAllStandardError()).decode(errors="replace")
        for line in output.splitlines():
            if line.strip():
                self._log(f"⚠️ {line}")

    def _on_finished_internal(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        status = "完成" if exit_status == QProcess.NormalExit else "異常結束"
        self._log(f"⏹️ PPO 訓練{status} (exit={exit_code})")
        self._process = None
        if self._on_finished:
            self._on_finished(exit_code, exit_status)
