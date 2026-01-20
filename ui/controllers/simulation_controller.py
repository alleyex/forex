from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment
from PySide6.QtWidgets import QMessageBox, QWidget


class SimulationController(QObject):
    def __init__(
        self,
        *,
        parent: QObject,
        log: Callable[[str], None],
        reset_plot: Callable[[], None],
        ingest_equity: Callable[[int, float], None],
        update_summary: Callable[..., None],
        update_trade_stats: Callable[[str], None],
        update_streak_stats: Callable[[str], None],
        update_holding_stats: Callable[[str], None],
        update_action_distribution: Callable[[str], None],
        update_playback_range: Callable[[str], None],
        on_finished: Optional[Callable[[int, QProcess.ExitStatus], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._log = log
        self._reset_plot = reset_plot
        self._ingest_equity = ingest_equity
        self._update_summary = update_summary
        self._update_trade_stats = update_trade_stats
        self._update_streak_stats = update_streak_stats
        self._update_holding_stats = update_holding_stats
        self._update_action_distribution = update_action_distribution
        self._update_playback_range = update_playback_range
        self._on_finished = on_finished
        self._process: Optional[QProcess] = None

    def start(self, params: dict) -> None:
        if self._process and self._process.state() != QProcess.NotRunning:
            self._log("ℹ️ 回放模擬仍在進行中")
            return

        data_path = params.get("data", "").strip()
        model_path = params.get("model", "").strip()
        if not data_path or not Path(data_path).exists():
            self._show_error("資料檔案不存在，請選擇有效的 CSV 檔案。")
            return
        if not model_path or not Path(model_path).exists():
            self._show_error("模型檔案不存在，請選擇有效的 ZIP 檔案。")
            return

        self._reset_plot()
        self._process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", ".")
        self._process.setProcessEnvironment(env)

        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished_internal)

        args = [
            "ml/rl/sim/run_live_sim.py",
            "--data",
            data_path,
            "--model",
            model_path,
            "--log-every",
            str(params["log_every"]),
            "--max-steps",
            str(params["max_steps"]),
            "--transaction-cost-bps",
            str(params["transaction_cost_bps"]),
            "--slippage-bps",
            str(params["slippage_bps"]),
        ]
        self._log("▶️ 開始回放模擬")
        self._process.start(sys.executable, args)

    def _show_error(self, message: str) -> None:
        self._log(f"⚠️ {message}")
        parent = self.parent()
        if isinstance(parent, QWidget):
            QMessageBox.warning(parent, "回放參數錯誤", message)

    def _on_stdout(self) -> None:
        if not self._process:
            return
        output = bytes(self._process.readAllStandardOutput()).decode(errors="replace")
        for line in output.splitlines():
            if line.strip():
                self._log(line)
                self._maybe_update_plot(line)

    def _on_stderr(self) -> None:
        if not self._process:
            return
        output = bytes(self._process.readAllStandardError()).decode(errors="replace")
        for line in output.splitlines():
            if line.strip():
                self._log(f"⚠️ {line}")

    def _on_finished_internal(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        status = "完成" if exit_status == QProcess.NormalExit else "異常結束"
        self._log(f"⏹️ 回放模擬{status} (exit={exit_code})")
        self._process = None
        if self._on_finished:
            self._on_finished(exit_code, exit_status)

    def _maybe_update_plot(self, line: str) -> None:
        if "step=" in line and "equity=" in line:
            parts = line.split()
            step = None
            equity = None
            for part in parts:
                if part.startswith("step="):
                    try:
                        step = int(part.split("=")[1])
                    except ValueError:
                        pass
                if part.startswith("equity="):
                    try:
                        equity = float(part.split("=")[1])
                    except ValueError:
                        pass
            if step is not None and equity is not None:
                self._ingest_equity(step, equity)
                return
        if line.startswith("Done."):
            tokens = line.replace("Done.", "").split()
            data = {}
            for token in tokens:
                if "=" in token:
                    key, value = token.split("=", 1)
                    data[key] = value
            try:
                trades = int(data.get("trades", "0"))
                equity = float(data.get("equity", "0"))
                total_return = float(data.get("return", "0"))
            except ValueError:
                return
            self._update_summary(
                total_return=total_return,
                trades=trades,
                equity=equity,
            )
        if line.startswith("Max drawdown:"):
            try:
                max_dd = float(line.split(":", 1)[1].strip())
            except ValueError:
                return
            self._update_summary(max_drawdown=max_dd)
        if line.startswith("Sharpe:"):
            try:
                sharpe = float(line.split(":", 1)[1].strip())
            except ValueError:
                return
            self._update_summary(sharpe=sharpe)
        if line.startswith("Trade stats:"):
            self._update_trade_stats(line.replace("Trade stats:", "").strip())
        if line.startswith("Streak stats:"):
            self._update_streak_stats(line.replace("Streak stats:", "").strip())
        if line.startswith("Holding stats:"):
            self._update_holding_stats(line.replace("Holding stats:", "").strip())
        if line.startswith("Action distribution:"):
            self._update_action_distribution(line.replace("Action distribution:", "").strip())
        if line.startswith("Playback range:"):
            self._update_playback_range(line.replace("Playback range:", "").strip())
