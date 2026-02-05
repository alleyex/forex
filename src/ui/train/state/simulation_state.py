from PySide6.QtCore import Signal

from ui.train.state.base import StateBase


class SimulationState(StateBase):
    log_message = Signal(str)
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
