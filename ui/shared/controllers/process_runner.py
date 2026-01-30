from __future__ import annotations

import sys
from typing import Callable, Optional

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer


class ProcessRunner(QObject):
    def __init__(
        self,
        *,
        parent: QObject,
        on_stdout_line: Optional[Callable[[str], None]] = None,
        on_stderr_line: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[int, QProcess.ExitStatus], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._on_stdout_line = on_stdout_line
        self._on_stderr_line = on_stderr_line
        self._on_finished = on_finished
        self._stopping = False

    def is_running(self) -> bool:
        return bool(self._process and self._process.state() != QProcess.NotRunning)

    def start(self, program: Optional[str], args: list[str], env: Optional[dict[str, str]] = None) -> bool:
        if self.is_running():
            return False
        self._stopping = False
        self._process = QProcess(self)
        process_env = QProcessEnvironment.systemEnvironment()
        if env:
            for key, value in env.items():
                process_env.insert(key, value)
        self._process.setProcessEnvironment(process_env)
        self._process.readyReadStandardOutput.connect(self._handle_stdout)
        self._process.readyReadStandardError.connect(self._handle_stderr)
        self._process.finished.connect(self._handle_finished)
        program = program or sys.executable
        self._process.start(program, args)
        return True

    def stop(self, *, kill_after_ms: int = 1500) -> bool:
        if not self.is_running():
            return False
        self._stopping = True
        self._process.terminate()
        QTimer.singleShot(kill_after_ms, self._force_kill)
        return True

    def _handle_stdout(self) -> None:
        if not self._process:
            return
        output = bytes(self._process.readAllStandardOutput()).decode(errors="replace")
        if self._stopping:
            return
        for line in output.splitlines():
            if line.strip() and self._on_stdout_line:
                self._on_stdout_line(line)

    def _handle_stderr(self) -> None:
        if not self._process:
            return
        output = bytes(self._process.readAllStandardError()).decode(errors="replace")
        if self._stopping:
            return
        for line in output.splitlines():
            if line.strip() and self._on_stderr_line:
                self._on_stderr_line(line)

    def _handle_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._stopping = False
        self._process = None
        if self._on_finished:
            self._on_finished(exit_code, exit_status)

    def _force_kill(self) -> None:
        if not self.is_running():
            return
        self._process.kill()
