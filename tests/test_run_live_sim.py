from __future__ import annotations

import numpy as np

from forex.ml.rl.envs.trading_env import TradingConfig
from forex.tools.rl.run_live_sim import (
    PlaybackBundle,
    _classify_position_change,
    _split_transition_cost,
    run_playback,
)


class _StubModel:
    def __init__(self, actions: list[float]) -> None:
        self._actions = actions
        self._idx = 0

    def predict(self, _obs, deterministic: bool = True):
        action = self._actions[min(self._idx, len(self._actions) - 1)]
        self._idx += 1
        return np.array([action], dtype=np.float32), None


def test_split_transition_cost_handles_reversal_and_resize() -> None:
    exit_cost, entry_cost = _split_transition_cost(1.0, -1.0, 0.001)
    assert exit_cost == 0.001
    assert entry_cost == 0.001

    exit_cost, entry_cost = _split_transition_cost(1.0, 0.5, 0.001)
    assert exit_cost == 0.0005
    assert entry_cost == 0.0

    exit_cost, entry_cost = _split_transition_cost(0.5, 1.0, 0.001)
    assert exit_cost == 0.0
    assert entry_cost == 0.0005


def test_classify_position_change_distinguishes_open_close_resize_and_reversal() -> None:
    assert _classify_position_change(0.0, 1.0) == "open"
    assert _classify_position_change(1.0, 0.0) == "close"
    assert _classify_position_change(1.0, 0.5) == "resize"
    assert _classify_position_change(0.5, 1.0) == "resize"
    assert _classify_position_change(1.0, -1.0) == "reversal"


def test_run_playback_closes_last_open_trade_segment() -> None:
    bundle = PlaybackBundle(
        features=np.zeros((4, 1), dtype=np.float32),
        closes=np.array([100.0, 110.0, 120.0, 120.0], dtype=np.float32),
        timestamps=[0, 1, 2, 3],
        config=TradingConfig(
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            holding_cost_bps=0.0,
            window_size=1,
            reward_horizon=1,
            max_position=1.0,
            min_position_change=0.0,
            position_step=0.0,
        ),
        model=_StubModel([1.0, 1.0, 1.0]),
    )

    result = run_playback(bundle, start_index=0, max_steps=3, quiet=True)

    assert result.trades == 1
    assert len(result.trade_pnls) == 1
    assert len(result.trade_costs) == 1
    assert result.trade_rate_1k > 0
    assert result.trade_pnls[0] > 0.09
    assert result.drawdown_trough_step >= result.drawdown_peak_step
    assert result.drawdown_peak_equity >= result.drawdown_trough_equity


def test_run_playback_holding_duration_tracks_trade_not_resize_segments() -> None:
    bundle = PlaybackBundle(
        features=np.zeros((5, 1), dtype=np.float32),
        closes=np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=np.float32),
        timestamps=[0, 1, 2, 3, 4],
        config=TradingConfig(
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            holding_cost_bps=0.0,
            window_size=1,
            reward_horizon=1,
            max_position=1.0,
            min_position_change=0.0,
            position_step=0.0,
        ),
        model=_StubModel([1.0, 0.5, 1.0, 0.0]),
    )

    result = run_playback(bundle, start_index=0, max_steps=4, quiet=True)

    assert result.resizes == 2
    assert result.trades == 1
    assert result.holding_steps == [3]


def test_run_playback_range_ends_at_last_processed_timestamp() -> None:
    bundle = PlaybackBundle(
        features=np.zeros((4, 1), dtype=np.float32),
        closes=np.array([100.0, 101.0, 102.0, 103.0], dtype=np.float32),
        timestamps=["t0", "t1", "t2", "t3"],
        config=TradingConfig(
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            holding_cost_bps=0.0,
            window_size=1,
            reward_horizon=1,
            max_position=1.0,
            min_position_change=0.0,
            position_step=0.0,
        ),
        model=_StubModel([0.0, 0.0, 0.0]),
    )

    result = run_playback(bundle, start_index=0, max_steps=3, quiet=True)

    assert result.processed_steps == 3
    assert result.end_index == 2
    assert result.end_ts == "t2"
