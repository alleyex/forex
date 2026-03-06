from __future__ import annotations

import numpy as np

from forex.ml.rl.envs.trading_env import TradingConfig
from forex.tools.rl.train_ppo import _build_warm_start_dataset


def test_build_warm_start_dataset_balances_directional_and_caps_flat() -> None:
    closes = np.asarray(
        [
            100.0,
            101.0,
            102.0,
            103.0,
            104.0,
            103.0,
            102.0,
            101.0,
            100.0,
            101.0,
            102.0,
            103.0,
            102.0,
            101.0,
            100.0,
            100.0,
            100.0,
            100.0,
            101.0,
            102.0,
        ],
        dtype=np.float32,
    )
    features = np.tile(closes.reshape(-1, 1), (1, 3))
    config = TradingConfig(max_position=1.0, position_step=0.1, window_size=4)

    observations, actions, weights, summary = _build_warm_start_dataset(
        features,
        closes,
        config,
        labeler="momentum",
        sample_limit=0,
        lookback_short=2,
        lookback_long=4,
        threshold=0.005,
        long_weight=1.0,
        short_weight=1.25,
        flat_weight=0.5,
    )

    assert len(observations) == len(actions)
    assert len(weights) == len(actions)
    assert summary["samples"] > 0.0
    assert summary["raw_samples"] >= summary["samples"]
    assert summary["flat_ratio"] <= summary["long_ratio"] + 1e-9
    assert abs(summary["long_ratio"] - summary["short_ratio"]) < 1e-9
    assert float(weights.min()) >= 0.5
    assert float(weights.max()) <= 1.25


def test_build_warm_start_dataset_supports_symmetric_breakout_labeler() -> None:
    closes = np.asarray(
        [
            100.0,
            100.2,
            100.1,
            100.3,
            100.5,
            100.8,
            101.2,
            100.9,
            100.6,
            100.2,
            99.8,
            99.4,
            99.1,
            99.5,
            99.9,
            100.4,
        ],
        dtype=np.float32,
    )
    features = np.tile(closes.reshape(-1, 1), (1, 2))
    config = TradingConfig(max_position=1.0, position_step=0.1, window_size=3)

    _, _, weights, summary = _build_warm_start_dataset(
        features,
        closes,
        config,
        labeler="breakout_sym",
        sample_limit=0,
        lookback_short=2,
        lookback_long=4,
        threshold=0.001,
        long_weight=1.0,
        short_weight=1.25,
        flat_weight=0.5,
    )

    assert summary["samples"] > 0.0
    assert summary["long_ratio"] > 0.0
    assert summary["short_ratio"] > 0.0
    assert float(weights.max()) >= 1.25
