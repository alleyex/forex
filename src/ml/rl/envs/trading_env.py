from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:  # pragma: no cover - optional dependency
    gym = None
    spaces = None


@dataclass
class TradingConfig:
    transaction_cost_bps: float = 1.0
    slippage_bps: float = 0.5
    holding_cost_bps: float = 0.0
    episode_length: int | None = 2048
    random_start: bool = True
    min_position_change: float = 0.0
    discretize_actions: bool = False
    discrete_positions: tuple[float, ...] = (-1.0, 0.0, 1.0)
    max_position: float = 1.0
    position_step: float = 0.0
    reward_scale: float = 1.0
    reward_clip: float = 0.0
    risk_aversion: float = 0.0


class TradingEnv(gym.Env if gym else object):
    metadata = {"render_modes": []}

    def __init__(self, features: np.ndarray, closes: np.ndarray, config: TradingConfig | None = None) -> None:
        if gym is None or spaces is None:
            raise ImportError("gymnasium is required for TradingEnv")
        self._features = features
        self._closes = closes
        self._config = config or TradingConfig()
        self._cost_rate = (self._config.transaction_cost_bps + self._config.slippage_bps) / 10000.0
        self._holding_cost_rate = self._config.holding_cost_bps / 10000.0

        obs_dim = features.shape[1] + 1
        # Keep action space consistent with max_position so the policy can reach it.
        max_position = max(1.0, float(self._config.max_position))
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32)
        self.action_space = spaces.Box(low=-max_position, high=max_position, shape=(1,), dtype=np.float32)

        self._idx = 0
        self._max_idx = len(self._closes) - 1
        self._end = self._max_idx
        self._position = 0.0
        self._equity = 1.0

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        # Base reset bounds on full dataset, not on prior episode end.
        max_start = self._max_idx - 1
        if self._config.episode_length:
            max_start = max(0, self._max_idx - self._config.episode_length)
        if self._config.random_start and max_start > 0:
            self._idx = int(self.np_random.integers(0, max_start))
        else:
            self._idx = 0
        if self._config.episode_length:
            self._end = min(self._idx + self._config.episode_length, self._max_idx)
        else:
            self._end = self._max_idx
        self._position = 0.0
        self._equity = 1.0
        return self._get_obs(), {}

    def step(self, action: np.ndarray):
        target_position = self._apply_action(action)
        delta = target_position - self._position
        cost = abs(delta) * self._cost_rate
        holding_cost = abs(self._position) * self._holding_cost_rate

        # Guard against zero/invalid prices to avoid NaNs.
        base_price = float(self._closes[self._idx])
        if base_price <= 0.0:
            price_return = 0.0
        else:
            price_return = (float(self._closes[self._idx + 1]) - base_price) / base_price
        step_pnl = self._position * float(price_return)
        reward = step_pnl - cost - holding_cost
        if self._config.risk_aversion > 0.0:
            reward -= self._config.risk_aversion * (step_pnl ** 2)
        if self._config.reward_scale != 1.0:
            reward *= self._config.reward_scale
        if self._config.reward_clip > 0.0:
            reward = float(np.clip(reward, -self._config.reward_clip, self._config.reward_clip))

        self._equity *= 1.0 + reward
        self._position = target_position
        self._idx += 1

        terminated = self._idx >= self._end
        info = {
            "equity": self._equity,
            "position": self._position,
            "cost": cost,
            "holding_cost": holding_cost,
        }
        return self._get_obs(), reward, terminated, False, info

    def _apply_action(self, action: np.ndarray) -> float:
        target = float(np.clip(action[0], -1.0, 1.0))
        if self._config.discretize_actions and self._config.discrete_positions:
            target = min(self._config.discrete_positions, key=lambda val: abs(val - target))
        if self._config.position_step > 0.0:
            target = round(target / self._config.position_step) * self._config.position_step
        if self._config.max_position > 0.0:
            target = float(np.clip(target, -self._config.max_position, self._config.max_position))
        if abs(target - self._position) < self._config.min_position_change:
            target = self._position
        return float(target)

    def _get_obs(self) -> np.ndarray:
        obs = self._features[self._idx]
        return np.concatenate([obs, np.array([self._position], dtype=np.float32)]).astype(np.float32)
