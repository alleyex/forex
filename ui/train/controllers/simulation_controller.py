from __future__ import annotations

import sys
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QProcess, QTimer
from PySide6.QtWidgets import QMessageBox, QWidget

from ui.shared.controllers.process_runner import ProcessRunner
from ui.train.state.simulation_state import SimulationState
from ui.train.presenters.simulation_presenter import SimulationPresenter
from ui.shared.utils.formatters import format_simulation_message


class SimulationController(QObject):
    def __init__(
        self,
        *,
        parent: QObject,
        state: SimulationState,
        presenter: SimulationPresenter,
        on_finished: Optional[Callable[[int, QProcess.ExitStatus], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._presenter = presenter
        self._on_finished = on_finished
        self._runner = ProcessRunner(
            parent=self,
            on_stdout_line=self._on_stdout_line,
            on_stderr_line=self._on_stderr_line,
            on_finished=self._on_finished_internal,
        )
        self._equity_log_path: Optional[str] = None
        self._equity_tail_timer = QTimer(self)
        self._equity_tail_timer.setInterval(300)
        self._equity_tail_timer.timeout.connect(self._tail_equity_log)
        self._equity_last_offset = 0

    def start(self, params: dict) -> None:
        if self._runner.is_running():
            self._state.log_message.emit(format_simulation_message("already_running"))
            return

        data_path = params.get("data", "").strip()
        model_path = params.get("model", "").strip()
        if not data_path or not Path(data_path).exists():
            self._show_error("資料檔案不存在，請選擇有效的 CSV 檔案。")
            return
        if not model_path or not Path(model_path).exists():
            self._show_error("模型檔案不存在，請選擇有效的 ZIP 檔案。")
            return

        self._state.reset_plot.emit()
        self._state.reset_summary.emit()
        self._start_equity_log_tailer()
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
            "--quiet",
            "--equity-log",
            self._equity_log_path or "",
            "--equity-log-every",
            "200",
        ]
        self._state.log_message.emit(format_simulation_message("start"))
        started = self._runner.start(sys.executable, args, env={"PYTHONPATH": "."})
        if not started:
            self._state.log_message.emit(format_simulation_message("start_failed"))
            self._stop_equity_log_tailer()

    def stop(self) -> None:
        if not self._runner.is_running():
            self._state.log_message.emit(format_simulation_message("not_running"))
            return
        self._state.log_message.emit(format_simulation_message("stop_requested"))
        self._stop_equity_log_tailer()
        if not self._runner.stop():
            self._state.log_message.emit(format_simulation_message("stop_failed"))

    def _show_error(self, message: str) -> None:
        self._state.log_message.emit(format_simulation_message("param_error", message=message))
        parent = self.parent()
        if isinstance(parent, QWidget):
            QMessageBox.warning(parent, "回放參數錯誤", message)

    def _on_stdout_line(self, line: str) -> None:
        self._state.log_message.emit(line)
        self._presenter.handle_stdout_line(line)

    def _on_stderr_line(self, line: str) -> None:
        self._state.log_message.emit(format_simulation_message("param_error", message=line))

    def _on_finished_internal(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._state.log_message.emit(
            format_simulation_message(
                "finished",
                exit_status=exit_status == QProcess.NormalExit,
                exit_code=exit_code,
            )
        )
        self._state.flush_plot.emit()
        self._stop_equity_log_tailer()
        if self._on_finished:
            self._on_finished(exit_code, exit_status)

    def _start_equity_log_tailer(self) -> None:
        tmp_dir = Path(tempfile.gettempdir())
        self._equity_log_path = str(tmp_dir / f"sim_equity_{uuid.uuid4().hex}.csv")
        self._equity_last_offset = 0
        self._equity_tail_timer.start()

    def _stop_equity_log_tailer(self) -> None:
        self._equity_tail_timer.stop()
        if self._equity_log_path:
            try:
                Path(self._equity_log_path).unlink(missing_ok=True)
            except Exception:
                pass
        self._equity_last_offset = 0
        self._equity_log_path = None

    def _tail_equity_log(self) -> None:
        if not self._equity_log_path:
            return
        path = Path(self._equity_log_path)
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as fh:
                fh.seek(self._equity_last_offset)
                data = fh.read()
                self._equity_last_offset = fh.tell()
        except Exception:
            return
        if not data:
            return
        lines = data.strip().splitlines()
        for line in lines:
            if line.startswith("step"):
                continue
            parts = line.split(",", 1)
            if len(parts) != 2:
                continue
            try:
                step = int(parts[0])
                equity = float(parts[1])
            except ValueError:
                continue
            self._presenter.handle_equity_point(step, equity)
