from __future__ import annotations

import numpy as np
import pytest

from forex.ml.rl.envs.trading_env import (
    TradingConfig,
    TradingEnv,
    compute_drawdown_governor_scale,
    simulate_step_transition,
)


def _make_env(config: TradingConfig, timestamps: list[str] | None = None) -> TradingEnv:
    features = np.zeros((10, 3), dtype=np.float32)
    closes = np.linspace(1.0, 1.1, num=10, dtype=np.float64)
    return TradingEnv(features, closes, config, timestamps=timestamps)


def test_action_space_matches_max_position() -> None:
    pytest.importorskip("gymnasium")
    config = TradingConfig(max_position=2.5)
    env = _make_env(config)
    assert float(env.action_space.high[0]) == pytest.approx(2.5)
    assert float(env.action_space.low[0]) == pytest.approx(-2.5)


def test_native_discrete_action_space_uses_position_count() -> None:
    gym = pytest.importorskip("gymnasium")
    config = TradingConfig(
        discretize_actions=True,
        native_discrete_actions=True,
        discrete_positions=(-1.0, -0.5, 0.0, 0.5, 1.0),
    )
    env = _make_env(config)
    assert isinstance(env.action_space, gym.spaces.Discrete)
    assert env.action_space.n == 5


def test_native_discrete_apply_action_maps_index_to_position() -> None:
    pytest.importorskip("gymnasium")
    env = _make_env(
        TradingConfig(
            discretize_actions=True,
            native_discrete_actions=True,
            discrete_positions=(-1.0, 0.0, 1.0),
            random_start=False,
            min_position_change=0.0,
            position_step=0.0,
        )
    )
    env.reset()
    target, _ = env._apply_action(np.array(2, dtype=np.int64))
    assert target == pytest.approx(1.0)


def test_apply_action_respects_max_position_above_one() -> None:
    pytest.importorskip("gymnasium")
    env = _make_env(TradingConfig(max_position=2.5))
    env.reset()
    target, _ = env._apply_action(np.array([2.0], dtype=np.float32))
    assert target == pytest.approx(2.0)


def test_action_constraints_with_one_step_and_one_min_change_form_three_state_policy() -> None:
    pytest.importorskip("gymnasium")
    env = _make_env(
        TradingConfig(
            min_position_change=1.0,
            max_position=1.0,
            position_step=1.0,
            random_start=False,
        )
    )
    env.reset()
    env._position = 0.0
    assert env._apply_action(np.array([0.8], dtype=np.float32))[0] == pytest.approx(1.0)
    assert env._apply_action(np.array([-0.8], dtype=np.float32))[0] == pytest.approx(-1.0)
    assert env._apply_action(np.array([0.4], dtype=np.float32))[0] == pytest.approx(0.0)


def test_min_position_change_uses_strictly_less_than_threshold() -> None:
    pytest.importorskip("gymnasium")
    env = _make_env(
        TradingConfig(
            min_position_change=1.0,
            max_position=1.0,
            position_step=1.0,
            random_start=False,
        )
    )
    env.reset()
    env._position = 1.0
    assert env._apply_action(np.array([0.9], dtype=np.float32))[0] == pytest.approx(1.0)
    assert env._apply_action(np.array([0.1], dtype=np.float32))[0] == pytest.approx(0.0)
    env._position = 0.0
    assert env._apply_action(np.array([0.49], dtype=np.float32))[0] == pytest.approx(0.0)


def test_reset_uses_full_data_range() -> None:
    pytest.importorskip("gymnasium")
    config = TradingConfig(episode_length=4, random_start=False)
    env = _make_env(config)
    obs, _ = env.reset()
    assert obs.shape[0] == 4
    assert env._end == 4


def test_window_size_expands_observation_with_edge_padding() -> None:
    pytest.importorskip("gymnasium")
    features = np.array(
        [
            [1.0, 10.0],
            [2.0, 20.0],
            [3.0, 30.0],
        ],
        dtype=np.float32,
    )
    closes = np.array([1.0, 1.01, 1.02], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(random_start=False, episode_length=2, window_size=3),
    )
    obs, _ = env.reset()
    assert obs.shape[0] == 7
    np.testing.assert_allclose(obs[:-1], np.array([1.0, 10.0, 1.0, 10.0, 1.0, 10.0], dtype=np.float32))


def test_window_size_rolls_forward_across_steps() -> None:
    pytest.importorskip("gymnasium")
    features = np.array(
        [
            [1.0, 10.0],
            [2.0, 20.0],
            [3.0, 30.0],
        ],
        dtype=np.float32,
    )
    closes = np.array([1.0, 1.01, 1.02], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(random_start=False, episode_length=2, window_size=2),
    )
    env.reset()
    obs, _, _, _, _ = env.step(np.array([0.0], dtype=np.float32))
    np.testing.assert_allclose(obs[:-1], np.array([1.0, 10.0, 2.0, 20.0], dtype=np.float32))
    # A second reset should not shrink max range.
    obs, _ = env.reset()
    assert obs.shape[0] == 5
    assert env._end == 2


def test_reset_reserves_history_for_window_size() -> None:
    pytest.importorskip("gymnasium")
    features = np.arange(20, dtype=np.float32).reshape(10, 2)
    closes = np.linspace(1.0, 1.1, num=10, dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(random_start=False, episode_length=4, window_size=3),
    )
    obs, _ = env.reset()
    assert env._idx == 2
    np.testing.assert_allclose(obs[:-1], features[:3].reshape(-1))


def test_zero_price_return_is_safe() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((3, 2), dtype=np.float32)
    closes = np.array([0.0, 1.0, 1.0], dtype=np.float64)
    env = TradingEnv(features, closes, TradingConfig(random_start=False, episode_length=2))
    env.reset()
    _, reward, _, _, info = env.step(np.array([0.0], dtype=np.float32))
    assert np.isfinite(reward)
    assert np.isfinite(info["equity"])


def test_transaction_cost_bps_converts_to_fractional_cost() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((3, 2), dtype=np.float32)
    closes = np.array([100.0, 100.0, 100.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            transaction_cost_bps=0.225,
            slippage_bps=0.03,
            random_start=False,
            episode_length=2,
        ),
    )
    env.reset()
    _, reward, _, _, info = env.step(np.array([1.0], dtype=np.float32))
    expected_cost_rate = (0.225 + 0.03) / 10000.0
    assert env._cost_rate == pytest.approx(expected_cost_rate)
    assert info["delta"] == pytest.approx(1.0)
    assert info["cost"] == pytest.approx(expected_cost_rate)
    assert reward == pytest.approx(-expected_cost_rate)


def test_holding_cost_bps_applies_to_existing_position_each_step() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((4, 2), dtype=np.float32)
    closes = np.array([100.0, 100.0, 100.0, 100.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            holding_cost_bps=0.05,
            random_start=False,
            episode_length=3,
        ),
    )
    env.reset()
    _, reward_one, _, _, info_one = env.step(np.array([1.0], dtype=np.float32))
    _, reward_two, _, _, info_two = env.step(np.array([1.0], dtype=np.float32))
    expected_holding_cost_rate = 0.05 / 10000.0
    assert info_one["holding_cost"] == pytest.approx(0.0)
    assert reward_one == pytest.approx(0.0)
    assert info_two["holding_cost"] == pytest.approx(expected_holding_cost_rate)
    assert reward_two == pytest.approx(-expected_holding_cost_rate)


def test_drawdown_governor_scales_effective_max_position() -> None:
    pytest.importorskip("gymnasium")
    env = _make_env(
        TradingConfig(
            random_start=False,
            max_position=1.0,
            drawdown_governor_slope=2.0,
            drawdown_governor_floor=0.3,
        )
    )
    env.reset()
    env._equity = 0.8
    env._peak_equity = 1.0
    assert compute_drawdown_governor_scale(equity=env._equity, peak_equity=env._peak_equity, slope=2.0, floor=0.3) == pytest.approx(0.6)
    target, info = env._apply_action(np.array([1.0], dtype=np.float32))
    assert target == pytest.approx(0.6)
    assert info["risk_scale"] == pytest.approx(0.6)


def test_drawdown_governor_respects_floor() -> None:
    pytest.importorskip("gymnasium")
    env = _make_env(
        TradingConfig(
            random_start=False,
            max_position=1.0,
            drawdown_governor_slope=2.0,
            drawdown_governor_floor=0.3,
        )
    )
    env.reset()
    env._equity = 0.4
    env._peak_equity = 1.0
    assert compute_drawdown_governor_scale(equity=env._equity, peak_equity=env._peak_equity, slope=2.0, floor=0.3) == pytest.approx(0.3)
    target, info = env._apply_action(np.array([1.0], dtype=np.float32))
    assert target == pytest.approx(0.3)
    assert info["risk_scale"] == pytest.approx(0.3)


def test_volatility_targeting_scales_position_from_realized_vol() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((6, 2), dtype=np.float32)
    closes = np.array([100.0, 110.0, 100.0, 110.0, 100.0, 110.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=4,
            max_position=1.0,
            target_vol=0.05,
            vol_target_lookback=4,
            vol_scale_floor=0.25,
            vol_scale_cap=2.0,
        ),
    )
    env.reset()
    env._idx = 4
    target, info = env._apply_action(np.array([1.0], dtype=np.float32))
    assert info["realized_vol"] > 0.0
    assert info["vol_target_scale"] < 1.0
    assert target == pytest.approx(info["vol_target_scale"])


def test_volatility_targeting_respects_scale_floor_and_cap() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((6, 2), dtype=np.float32)
    closes = np.array([100.0, 100.1, 100.2, 100.3, 100.4, 100.5], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=4,
            max_position=1.0,
            target_vol=1.0,
            vol_target_lookback=4,
            vol_scale_floor=0.5,
            vol_scale_cap=1.2,
        ),
    )
    env.reset()
    env._idx = 4
    target, info = env._apply_action(np.array([1.0], dtype=np.float32))
    assert info["vol_target_scale"] == pytest.approx(1.2)
    assert target == pytest.approx(1.0)


def test_step_info_exposes_reward_components() -> None:
    pytest.importorskip("gymnasium")
    env = _make_env(TradingConfig(random_start=False, episode_length=2))
    env.reset()
    _, reward, _, _, info = env.step(np.array([0.5], dtype=np.float32))
    assert "delta" in info
    assert "price_return" in info
    assert "step_pnl" in info
    assert "reward_return" in info
    assert "reward_step_pnl" in info
    assert "reward_net_return" in info
    assert "reward" in info
    assert "turnover_penalty" in info
    assert info["reward"] == pytest.approx(reward)


def test_simulate_step_transition_matches_env_step() -> None:
    pytest.importorskip("gymnasium")
    config = TradingConfig(
        random_start=False,
        episode_length=3,
        reward_horizon=1,
        reward_mode="log_return",
        drawdown_penalty=0.5,
        risk_aversion=0.1,
        transaction_cost_bps=0.225,
        slippage_bps=0.03,
        holding_cost_bps=0.05,
    )
    env = _make_env(config)
    env.reset()
    env._position = 0.5
    transition = simulate_step_transition(
        current_position=env._position,
        target_position=0.25,
        closes=env._closes,
        idx=env._idx,
        equity=env._equity,
        peak_equity=env._peak_equity,
        config=config,
    )
    _, reward, _, _, info = env.step(np.array([0.25], dtype=np.float32))
    assert reward == pytest.approx(transition["reward"])
    assert info["equity"] == pytest.approx(transition["equity"])
    assert info["drawdown"] == pytest.approx(transition["drawdown"])
    assert info["cost"] == pytest.approx(transition["cost"])


def test_reward_horizon_uses_future_n_step_return() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((5, 2), dtype=np.float32)
    closes = np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(random_start=False, episode_length=4, reward_horizon=2),
    )
    env.reset()
    env._position = 1.0
    _, reward, _, _, info = env.step(np.array([1.0], dtype=np.float32))
    expected_one_bar_return = (101.0 - 100.0) / 100.0
    expected_horizon_return = (102.0 - 100.0) / 100.0
    assert info["price_return"] == pytest.approx(expected_one_bar_return)
    assert info["step_pnl"] == pytest.approx(expected_one_bar_return)
    assert info["reward_return"] == pytest.approx(expected_horizon_return)
    assert info["reward_step_pnl"] == pytest.approx(expected_horizon_return)
    assert info["reward_net_return"] == pytest.approx(expected_horizon_return)
    assert reward == pytest.approx(expected_horizon_return)


def test_log_return_reward_uses_log_growth() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((3, 2), dtype=np.float32)
    closes = np.array([100.0, 110.0, 110.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=2,
            reward_horizon=1,
            reward_mode="log_return",
        ),
    )
    env.reset()
    env._position = 1.0
    _, reward, _, _, info = env.step(np.array([1.0], dtype=np.float32))
    assert reward == pytest.approx(np.log(1.1))
    assert info["reward_mode"] == "log_return"
    assert info["net_return"] == pytest.approx(0.1)
    assert info["equity"] == pytest.approx(1.1)


def test_log_return_reward_ignores_risk_and_execution_penalties() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((3, 2), dtype=np.float32)
    closes = np.array([100.0, 110.0, 110.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=2,
            reward_horizon=1,
            reward_mode="log_return",
            risk_aversion=0.5,
            drawdown_penalty=1.0,
            turnover_penalty=0.25,
            exposure_penalty=0.1,
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            holding_cost_bps=0.0,
        ),
    )
    env.reset()
    env._position = 1.0
    _, reward, _, _, info = env.step(np.array([0.5], dtype=np.float32))
    assert info["reward_mode"] == "log_return"
    assert info["turnover_penalty"] == pytest.approx(0.0)
    assert info["exposure_penalty"] == pytest.approx(0.0)
    assert info["drawdown_penalty"] == pytest.approx(0.0)
    assert reward == pytest.approx(np.log(1.1))


def test_linear_reward_ignores_risk_and_execution_penalties() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((3, 2), dtype=np.float32)
    closes = np.array([100.0, 110.0, 110.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=2,
            reward_horizon=1,
            reward_mode="linear",
            risk_aversion=0.5,
            drawdown_penalty=1.0,
            turnover_penalty=0.25,
            exposure_penalty=0.1,
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            holding_cost_bps=0.0,
        ),
    )
    env.reset()
    env._position = 1.0
    _, reward, _, _, info = env.step(np.array([0.5], dtype=np.float32))
    assert info["reward_mode"] == "linear"
    assert info["turnover_penalty"] == pytest.approx(0.0)
    assert info["exposure_penalty"] == pytest.approx(0.0)
    assert info["drawdown_penalty"] == pytest.approx(0.0)
    assert reward == pytest.approx(0.1)


def test_drawdown_penalty_uses_drawdown_delta_only() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((4, 2), dtype=np.float32)
    closes = np.array([100.0, 90.0, 90.0, 90.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=3,
            reward_horizon=1,
            reward_mode="risk_adjusted",
            drawdown_penalty=1.0,
        ),
    )
    env.reset()
    env._position = 1.0
    _, reward_one, _, _, info_one = env.step(np.array([1.0], dtype=np.float32))
    _, reward_two, _, _, info_two = env.step(np.array([1.0], dtype=np.float32))
    assert info_one["drawdown"] == pytest.approx(0.1)
    assert info_one["drawdown_delta"] == pytest.approx(0.1)
    assert reward_one == pytest.approx(np.log(0.9) - 0.1)
    assert info_two["drawdown"] == pytest.approx(0.1)
    assert info_two["drawdown_delta"] == pytest.approx(0.0)
    assert reward_two == pytest.approx(0.0)


def test_risk_adjusted_reward_uses_log_return_and_downside_only_penalty() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((3, 2), dtype=np.float32)
    closes = np.array([100.0, 90.0, 90.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=2,
            reward_horizon=1,
            reward_mode="risk_adjusted",
            downside_penalty=2.0,
            drawdown_penalty=0.5,
        ),
    )
    env.reset()
    env._position = 1.0
    _, reward, _, _, info = env.step(np.array([1.0], dtype=np.float32))
    expected_log_return = np.log(0.9)
    expected_downside_penalty = 2.0 * (0.1**2)
    expected_drawdown_penalty = 0.5 * 0.1
    assert info["reward_mode"] == "risk_adjusted"
    assert info["net_return"] == pytest.approx(-0.1)
    assert info["downside_penalty"] == pytest.approx(expected_downside_penalty)
    assert info["drawdown_penalty"] == pytest.approx(expected_drawdown_penalty)
    assert reward == pytest.approx(
        expected_log_return - expected_downside_penalty - expected_drawdown_penalty
    )


def test_risk_adjusted_reward_also_applies_risk_aversion_penalty() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((3, 2), dtype=np.float32)
    closes = np.array([100.0, 110.0, 110.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=2,
            reward_horizon=1,
            reward_mode="risk_adjusted",
            risk_aversion=0.5,
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            holding_cost_bps=0.0,
            downside_penalty=0.0,
            drawdown_penalty=0.0,
        ),
    )
    env.reset()
    env._position = 1.0
    _, reward, _, _, info = env.step(np.array([1.0], dtype=np.float32))
    step_pnl = 0.1
    expected = np.log(1.1) - 0.5 * (step_pnl**2)
    assert info["reward_mode"] == "risk_adjusted"
    assert reward == pytest.approx(expected)


def test_reward_clip_applies_in_env_step_not_transition() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((3, 2), dtype=np.float32)
    closes = np.array([100.0, 120.0, 120.0], dtype=np.float64)
    config = TradingConfig(
        random_start=False,
        episode_length=2,
        reward_horizon=1,
        reward_mode="linear",
        reward_clip=0.01,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
        holding_cost_bps=0.0,
    )
    env = TradingEnv(features, closes, config)
    env.reset()
    env._position = 1.0
    transition = simulate_step_transition(
        current_position=env._position,
        target_position=1.0,
        closes=env._closes,
        idx=env._idx,
        equity=env._equity,
        peak_equity=env._peak_equity,
        config=config,
    )
    assert transition["reward"] == pytest.approx(0.2)
    _, reward, _, _, info = env.step(np.array([1.0], dtype=np.float32))
    assert reward == pytest.approx(0.01)
    assert info["reward"] == pytest.approx(0.01)


def test_turnover_penalty_applies_additional_penalty_to_position_change() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((3, 2), dtype=np.float32)
    closes = np.array([100.0, 100.0, 100.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=2,
            reward_horizon=1,
            reward_mode="risk_adjusted",
            turnover_penalty=0.001,
        ),
    )
    env.reset()
    _, reward, _, _, info = env.step(np.array([1.0], dtype=np.float32))
    assert info["turnover_penalty"] == pytest.approx(0.001)
    assert reward == pytest.approx(np.log(1.0 - info["cost"]) - 0.001)


def test_exposure_penalty_applies_to_absolute_target_position() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((3, 2), dtype=np.float32)
    closes = np.array([100.0, 100.0, 100.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=2,
            reward_horizon=1,
            reward_mode="risk_adjusted",
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            holding_cost_bps=0.0,
            exposure_penalty=0.01,
        ),
    )
    env.reset()
    _, reward, _, _, info = env.step(np.array([0.5], dtype=np.float32))
    assert info["exposure_penalty"] == pytest.approx(0.005)
    assert reward == pytest.approx(-0.005)


def test_flat_position_penalty_applies_only_when_staying_flat() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((4, 2), dtype=np.float32)
    closes = np.array([100.0, 100.0, 100.0, 100.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=3,
            reward_horizon=1,
            flat_position_penalty=0.001,
            flat_streak_penalty=0.0005,
        ),
    )
    env.reset()
    _, reward_one, _, _, info_one = env.step(np.array([0.0], dtype=np.float32))
    _, reward_two, _, _, info_two = env.step(np.array([0.0], dtype=np.float32))
    assert info_one["flat_position_penalty"] == pytest.approx(0.001)
    assert info_one["flat_streak_penalty"] == pytest.approx(0.0)
    assert info_one["flat_steps"] == 1
    assert reward_one == pytest.approx(-0.001)
    assert info_two["flat_position_penalty"] == pytest.approx(0.001)
    assert info_two["flat_streak_penalty"] == pytest.approx(0.0005)
    assert info_two["flat_steps"] == 2
    assert reward_two == pytest.approx(-0.0015)


def test_flat_penalty_does_not_apply_when_closing_position_to_flat() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((4, 2), dtype=np.float32)
    closes = np.array([100.0, 100.0, 100.0, 100.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=3,
            reward_horizon=1,
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            flat_position_penalty=0.001,
            flat_streak_penalty=0.0005,
        ),
    )
    env.reset()
    env._position = 1.0
    _, reward, _, _, info = env.step(np.array([0.0], dtype=np.float32))
    assert info["flat_position_penalty"] == pytest.approx(0.0)
    assert info["flat_streak_penalty"] == pytest.approx(0.0)
    assert info["flat_steps"] == 0
    assert reward == pytest.approx(0.0)


def test_position_bias_penalty_accumulates_for_persistent_one_sided_exposure() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((5, 2), dtype=np.float32)
    closes = np.array([100.0, 100.0, 100.0, 100.0, 100.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=4,
            reward_horizon=1,
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            holding_cost_bps=0.0,
            position_bias_penalty=0.1,
            position_bias_threshold=0.2,
            position_bias_ema_alpha=0.5,
        ),
    )
    env.reset()
    _, reward_one, _, _, info_one = env.step(np.array([1.0], dtype=np.float32))
    _, reward_two, _, _, info_two = env.step(np.array([1.0], dtype=np.float32))
    assert info_one["position_bias_ema"] == pytest.approx(0.5)
    assert info_one["position_bias_penalty"] == pytest.approx(0.03)
    assert reward_one == pytest.approx(-0.03)
    assert info_two["position_bias_ema"] == pytest.approx(0.75)
    assert info_two["position_bias_penalty"] == pytest.approx(0.055)
    assert reward_two == pytest.approx(-0.055)


def test_position_bias_penalty_relaxes_when_exposure_rebalances() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((5, 2), dtype=np.float32)
    closes = np.array([100.0, 100.0, 100.0, 100.0, 100.0], dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            episode_length=4,
            reward_horizon=1,
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            holding_cost_bps=0.0,
            position_bias_penalty=0.1,
            position_bias_threshold=0.2,
            position_bias_ema_alpha=0.5,
        ),
    )
    env.reset()
    env.step(np.array([1.0], dtype=np.float32))
    _, reward, _, _, info = env.step(np.array([-1.0], dtype=np.float32))
    assert info["position_bias_ema"] == pytest.approx(-0.25)
    assert info["position_bias_penalty"] == pytest.approx(0.005)
    assert reward == pytest.approx(-0.005)


def test_weekly_open_start_mode_uses_monday_anchor() -> None:
    pytest.importorskip("gymnasium")
    timestamps = [
        "2021-02-26 23:45",
        "2021-03-01 00:00",
        "2021-03-01 00:15",
        "2021-03-01 00:30",
        "2021-03-02 00:00",
        "2021-03-05 23:45",
        "2021-03-08 00:00",
        "2021-03-08 00:15",
        "2021-03-08 00:30",
        "2021-03-09 00:00",
    ]
    env = _make_env(
        TradingConfig(start_mode="weekly_open", episode_length=3, random_start=True),
        timestamps=timestamps,
    )
    env.reset(seed=7)
    assert env._idx in {1, 6}


def test_large_window_and_horizon_config_keep_expected_obs_shape_and_horizon_cap() -> None:
    pytest.importorskip("gymnasium")
    features = np.zeros((100, 12), dtype=np.float32)
    closes = np.linspace(100.0, 101.0, num=100, dtype=np.float64)
    env = TradingEnv(
        features,
        closes,
        TradingConfig(
            random_start=False,
            start_mode="random",
            episode_length=8192,
            window_size=72,
            reward_horizon=96,
        ),
    )
    obs, _ = env.reset(seed=1)
    assert obs.shape[0] == 12 * 72 + 1
    assert env._end == len(closes) - 1
    env._position = 1.0
    _, _, _, _, info = env.step(np.array([1.0], dtype=np.float32))
    expected_one_bar_return = (closes[1] - closes[0]) / closes[0]
    expected_horizon_return = (closes[96] - closes[0]) / closes[0]
    assert info["price_return"] == pytest.approx(expected_one_bar_return)
    assert info["reward_return"] == pytest.approx(expected_horizon_return)
