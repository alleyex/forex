from __future__ import annotations

import types
import numpy as np
import pytest
import torch

from forex.ml.rl.envs.trading_env import TradingConfig
from forex.tools.rl import train_ppo
from forex.tools.rl.train_ppo import (
    ImitationRolloutCallback,
    _build_warm_start_dataset,
    _profile_policy_activity,
)


class _StubModel:
    def __init__(self, actions: list[float]) -> None:
        self._actions = actions
        self._idx = 0

    def predict(self, _obs, deterministic: bool = True):
        action = self._actions[min(self._idx, len(self._actions) - 1)]
        self._idx += 1
        return np.array([action], dtype=np.float32), None


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
        action_scale=1.0,
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
        action_scale=1.0,
        long_weight=1.0,
        short_weight=1.25,
        flat_weight=0.5,
    )

    assert summary["samples"] > 0.0
    assert summary["long_ratio"] > 0.0
    assert summary["short_ratio"] > 0.0
    assert float(weights.max()) >= 1.25


def test_build_warm_start_dataset_supports_continuous_breakout_teacher() -> None:
    closes = np.asarray(
        [
            100.0,
            100.1,
            100.3,
            100.6,
            100.9,
            101.2,
            101.5,
            101.1,
            100.7,
            100.2,
            99.8,
            99.4,
            99.1,
            98.8,
            99.0,
            99.4,
            99.9,
            100.5,
            101.0,
            101.4,
        ],
        dtype=np.float32,
    )
    features = np.tile(closes.reshape(-1, 1), (1, 2))
    config = TradingConfig(max_position=1.0, position_step=0.1, window_size=3)

    _, actions, _, summary = _build_warm_start_dataset(
        features,
        closes,
        config,
        labeler="breakout_cont",
        sample_limit=0,
        lookback_short=2,
        lookback_long=5,
        threshold=0.001,
        action_scale=1.0,
        long_weight=1.0,
        short_weight=1.25,
        flat_weight=0.5,
    )

    unique_actions = np.unique(np.round(actions.reshape(-1), 4))
    assert summary["samples"] > 0.0
    assert summary["avg_abs_action"] > 0.1
    assert summary["max_abs_action"] <= 1.0
    assert summary["long_ratio"] > 0.0
    assert summary["short_ratio"] > 0.0
    assert len(unique_actions) > 3
    assert np.any((actions > 0.1) & (actions < 0.95))
    assert np.any((actions < -0.1) & (actions > -0.95))


def test_warm_start_action_scale_increases_continuous_teacher_magnitude() -> None:
    closes = np.asarray(
        [
            100.0,
            100.1,
            100.3,
            100.6,
            100.9,
            101.2,
            101.5,
            101.1,
            100.7,
            100.2,
            99.8,
            99.4,
            99.1,
            98.8,
            99.0,
            99.4,
            99.9,
            100.5,
            101.0,
            101.4,
        ],
        dtype=np.float32,
    )
    features = np.tile(closes.reshape(-1, 1), (1, 2))
    config = TradingConfig(max_position=1.0, position_step=0.1, window_size=3)

    _, actions_base, _, summary_base = _build_warm_start_dataset(
        features,
        closes,
        config,
        labeler="breakout_cont",
        sample_limit=0,
        lookback_short=2,
        lookback_long=5,
        threshold=0.001,
        action_scale=1.0,
        long_weight=1.0,
        short_weight=1.25,
        flat_weight=0.5,
    )
    _, actions_scaled, _, summary_scaled = _build_warm_start_dataset(
        features,
        closes,
        config,
        labeler="breakout_cont",
        sample_limit=0,
        lookback_short=2,
        lookback_long=5,
        threshold=0.001,
        action_scale=2.0,
        long_weight=1.0,
        short_weight=1.25,
        flat_weight=0.5,
    )

    assert summary_scaled["avg_abs_action"] > summary_base["avg_abs_action"]
    assert float(np.mean(np.abs(actions_scaled))) > float(np.mean(np.abs(actions_base)))


def test_continuous_supervision_is_disabled_for_native_discrete_actions() -> None:
    config = TradingConfig(
        discretize_actions=True,
        native_discrete_actions=True,
        discrete_positions=(-1.0, 0.0, 1.0),
    )

    assert train_ppo._continuous_supervision_supported(config) is False


def test_warm_start_policy_emits_epoch_metrics() -> None:
    class _TinyPolicy(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.linear = torch.nn.Linear(2, 1, bias=False)
            self.optimizer = torch.optim.SGD(self.parameters(), lr=0.05)

        def get_distribution(self, obs):
            mean = self.linear(obs)
            return types.SimpleNamespace(distribution=types.SimpleNamespace(mean=mean))

    class _TinyModel:
        def __init__(self) -> None:
            self.device = torch.device("cpu")
            self.policy = _TinyPolicy()

    metrics: list[tuple[int, str, float]] = []
    model = _TinyModel()
    observations = np.ones((4, 2), dtype=np.float32)
    actions = np.full((4, 1), 0.5, dtype=np.float32)
    weights = np.ones((4, 1), dtype=np.float32)

    loss = train_ppo._warm_start_policy(
        model,
        observations,
        actions,
        weights,
        epochs=2,
        batch_size=2,
        loss_scale=1.0,
        metric_writer=lambda step, metric, value: metrics.append((step, metric, value)),
        metric_step=0,
        metric_prefix="warm_start_test",
    )

    assert loss >= 0.0
    assert metrics[0][1] == "warm_start_test/epoch"
    assert metrics[1][1] == "warm_start_test/epoch_loss"
    assert metrics[2][1] == "warm_start_test/epoch"
    assert metrics[3][1] == "warm_start_test/epoch_loss"
    assert metrics[-1][1] == "warm_start_test/loss"


def test_train_model_passes_policy_log_std_init(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _StubPPO:
        def __init__(self, policy, env, *, verbose, policy_kwargs, **kwargs) -> None:
            captured["policy"] = policy
            captured["env"] = env
            captured["verbose"] = verbose
            captured["policy_kwargs"] = policy_kwargs
            captured["kwargs"] = kwargs
            self.device = "cpu"

    monkeypatch.setattr(train_ppo, "PPO", _StubPPO)

    model = train_ppo._train_model(
        env=object(),
        learning_rate=3e-5,
        n_steps=128,
        batch_size=64,
        gamma=0.99,
        ent_coef=1e-4,
        gae_lambda=0.95,
        clip_range=0.2,
        target_kl=0.02,
        vf_coef=0.5,
        n_epochs=4,
        total_steps=1000,
        window_size=32,
        feature_dim=8,
        device="cpu",
        policy_log_std_init=-2.0,
        verbose=0,
    )

    assert model.device == "cpu"
    assert captured["policy"] == "MlpPolicy"
    assert captured["policy_kwargs"]["log_std_init"] == pytest.approx(-2.0)


def test_profile_policy_activity_reports_raw_deterministic_action_stats() -> None:
    features = np.zeros((5, 2), dtype=np.float32)
    closes = np.asarray([100.0, 101.0, 102.0, 101.0, 100.0], dtype=np.float32)
    config = TradingConfig(
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
        holding_cost_bps=0.0,
        window_size=1,
        reward_horizon=1,
        max_position=1.0,
        min_position_change=0.0,
        position_step=0.0,
    )

    profile = _profile_policy_activity(
        _StubModel([0.0, 0.30, -0.40, 0.10]),
        features,
        closes,
        timestamps=[0, 1, 2, 3, 4],
        config=config,
        max_steps=4,
        replay_policy={
            "action_gate_specs": [],
            "action_gate_mode": "entry_only",
            "threshold_bump_specs": [],
            "long_threshold": 0.25,
            "short_threshold": -0.25,
            "long_exit_threshold": 0.25,
            "short_exit_threshold": -0.25,
        },
    )

    assert profile["raw_action_abs_mean"] == pytest.approx(np.mean(np.abs([0.0, 0.30, -0.40, 0.10])))
    assert profile["raw_action_flatish_ratio"] == pytest.approx(0.25)
    assert profile["raw_action_over_005_ratio"] == pytest.approx(0.75)
    assert profile["raw_action_over_010_ratio"] == pytest.approx(0.75)
    assert profile["raw_action_over_025_ratio"] == pytest.approx(0.50)
    assert profile["raw_entry_hit_ratio"] == pytest.approx(0.50)
    assert profile["raw_long_entry_hit_ratio"] == pytest.approx(0.25)
    assert profile["raw_short_entry_hit_ratio"] == pytest.approx(0.25)


def test_imitation_rollout_callback_applies_supervised_update_while_active(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, int]] = []
    metrics: list[tuple[int, str, float]] = []

    def _fake_warm_start_policy(model, observations, actions, sample_weights, *, epochs: int, batch_size: int, loss_scale: float) -> float:
        calls.append((epochs, batch_size, loss_scale))
        assert observations.shape == (3, 4)
        assert actions.shape == (3, 1)
        assert sample_weights.shape == (3, 1)
        return 0.123

    monkeypatch.setattr(train_ppo, "_warm_start_policy", _fake_warm_start_policy)
    callback = ImitationRolloutCallback(
        write_metric=lambda step, metric, value: metrics.append((step, metric, value)),
        observations=np.ones((3, 4), dtype=np.float32),
        actions=np.ones((3, 1), dtype=np.float32),
        sample_weights=np.ones((3, 1), dtype=np.float32),
        max_steps=5_000,
        epochs_per_rollout=2,
        batch_size=64,
        loss_scale=3.0,
    )
    callback.model = object()
    callback.num_timesteps = 4_096

    callback._on_rollout_end()

    assert calls == [(2, 64, 3.0)]
    assert metrics == [
        (4096, "imitation/loss", 0.123),
        (4096, "imitation/active", 1.0),
    ]


def test_imitation_rollout_callback_stops_after_max_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def _fake_warm_start_policy(*args, **kwargs) -> float:
        nonlocal calls
        calls += 1
        return 0.0

    monkeypatch.setattr(train_ppo, "_warm_start_policy", _fake_warm_start_policy)
    callback = ImitationRolloutCallback(
        write_metric=lambda *_args: None,
        observations=np.ones((3, 4), dtype=np.float32),
        actions=np.ones((3, 1), dtype=np.float32),
        sample_weights=np.ones((3, 1), dtype=np.float32),
        max_steps=5_000,
        epochs_per_rollout=1,
        batch_size=32,
        loss_scale=1.0,
    )
    callback.model = object()
    callback.num_timesteps = 5_001

    callback._on_rollout_end()

    assert calls == 0
