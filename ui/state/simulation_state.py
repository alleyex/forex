from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class SimulationState(QObject):
    reset_plot = Signal()
    flush_plot = Signal()
    reset_summary = Signal()
    equity_point = Signal(int, float)
    summary_update = Signal(dict)
    trade_stats = Signal(str)
    streak_stats = Signal(str)
    holding_stats = Signal(str)
    action_distribution = Signal(str)
    playback_range = Signal(str)
