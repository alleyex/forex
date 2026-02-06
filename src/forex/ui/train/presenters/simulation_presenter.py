from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject

from forex.ui.train.presenters.base import PresenterBase
from forex.ui.train.state.simulation_state import SimulationState


class SimulationPresenter(PresenterBase):
    def __init__(self, *, parent: QObject, state: SimulationState) -> None:
        super().__init__(parent=parent, state=state)

    def handle_stdout_line(self, line: str) -> None:
        self._maybe_emit_equity(line)
        if line.startswith("Done."):
            summary = self._parse_done_summary(line)
            if summary:
                self._state.summary_update.emit(summary)
            return
        if line.startswith("Max drawdown:"):
            value = self._parse_float_line(line)
            if value is not None:
                self._state.summary_update.emit({"max_drawdown": value})
            return
        if line.startswith("Sharpe:"):
            value = self._parse_float_line(line)
            if value is not None:
                self._state.summary_update.emit({"sharpe": value})
            return
        if line.startswith("Trade stats:"):
            self._state.trade_stats.emit(line.replace("Trade stats:", "").strip())
            return
        if line.startswith("Streak stats:"):
            self._state.streak_stats.emit(line.replace("Streak stats:", "").strip())
            return
        if line.startswith("Holding stats:"):
            self._state.holding_stats.emit(line.replace("Holding stats:", "").strip())
            return
        if line.startswith("Action distribution:"):
            self._state.action_distribution.emit(line.replace("Action distribution:", "").strip())
            return
        if line.startswith("Playback range:"):
            self._state.playback_range.emit(line.replace("Playback range:", "").strip())

    def handle_equity_point(self, step: int, equity: float) -> None:
        self._state.equity_point.emit(step, equity)

    def _maybe_emit_equity(self, line: str) -> None:
        if "step=" not in line or "equity=" not in line:
            return
        step = None
        equity = None
        for part in line.split():
            if part.startswith("step="):
                try:
                    step = int(part.split("=")[1])
                except ValueError:
                    step = None
            elif part.startswith("equity="):
                try:
                    equity = float(part.split("=")[1])
                except ValueError:
                    equity = None
        if step is not None and equity is not None:
            self.handle_equity_point(step, equity)

    @staticmethod
    def _parse_done_summary(line: str) -> Optional[dict]:
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
            return None
        return {
            "total_return": total_return,
            "trades": trades,
            "equity": equity,
        }

    @staticmethod
    def _parse_float_line(line: str) -> Optional[float]:
        try:
            return float(line.split(":", 1)[1].strip())
        except (ValueError, IndexError):
            return None
