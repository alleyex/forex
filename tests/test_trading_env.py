from __future__ import annotations

import numpy as np
import pytest

from forex.ml.rl.envs.trading_env import TradingConfig, TradingEnv


def _make_env(config: TradingConfig) -> TradingEnv:
    features = np.zeros((10, 3), dtype=np.float32)
    closes = np.linspace(1.0, 1.1, num=10, dtype=np.float64)
    return TradingEnv(features, closes, config)


def test_action_space_matches_max_position() -> None:
    pytest.importorskip("gymnasium")
    config = TradingConfig(max_position=2.5)
    env = _make_env(config)
    assert float(env.action_space.high[0]) == pytest.approx(2.5)
    assert float(env.action_space.low[0]) == pytest.approx(-2.5)


def test_reset_uses_full_data_range() -> None:
    pytest.importorskip("gymnasium")
    config = TradingConfig(episode_length=4, random_start=False)
    env = _make_env(config)
    obs, _ = env.reset()
    assert obs.shape[0] == 4
    assert env._end == 4
    # A second reset should not shrink max range.
    obs, _ = env.reset()
    assert obs.shape[0] == 4
    assert env._end == 4


def test_zero_price_return_is_safe() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((3, 2), dtype=np.float32)
    closes = np.array([0.0, 1.0, 1.0], dtype=np.float64)
    env = TradingEnv(features, closes, TradingConfig(random_start=False, episode_length=2))
    env.reset()
    _, reward, _, _, info = env.step(np.array([0.0], dtype=np.float32))
    assert np.isfinite(reward)
    assert np.isfinite(info["equity"])
