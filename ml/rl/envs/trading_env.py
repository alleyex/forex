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
    episode_length: int | None = 2048
    random_start: bool = True


class TradingEnv(gym.Env if gym else object):
    metadata = {"render_modes": []}

    def __init__(self, features: np.ndarray, closes: np.ndarray, config: TradingConfig | None = None) -> None:
        if gym is None or spaces is None:
            raise ImportError("gymnasium is required for TradingEnv")
        self._features = features
        self._closes = closes
        self._config = config or TradingConfig()
        self._cost_rate = (self._config.transaction_cost_bps + self._config.slippage_bps) / 10000.0

        obs_dim = features.shape[1] + 1
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)

        self._idx = 0
        self._end = len(self._closes) - 1
        self._position = 0.0
        self._equity = 1.0

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        max_start = self._end - 1
        if self._config.episode_length:
            max_start = max(0, self._end - self._config.episode_length)
        if self._config.random_start and max_start > 0:
            self._idx = int(self.np_random.integers(0, max_start))
        else:
            self._idx = 0
        if self._config.episode_length:
            self._end = min(self._idx + self._config.episode_length, len(self._closes) - 1)
        else:
            self._end = len(self._closes) - 1
        self._position = 0.0
        self._equity = 1.0
        return self._get_obs(), {}

    def step(self, action: np.ndarray):
        target_position = float(np.clip(action[0], -1.0, 1.0))
        delta = target_position - self._position
        cost = abs(delta) * self._cost_rate

        price_return = (self._closes[self._idx + 1] - self._closes[self._idx]) / self._closes[self._idx]
        reward = self._position * float(price_return) - cost

        self._equity *= 1.0 + reward
        self._position = target_position
        self._idx += 1

        terminated = self._idx >= self._end
        info = {
            "equity": self._equity,
            "position": self._position,
            "cost": cost,
        }
        return self._get_obs(), reward, terminated, False, info

    def _get_obs(self) -> np.ndarray:
        obs = self._features[self._idx]
        return np.concatenate([obs, np.array([self._position], dtype=np.float32)]).astype(np.float32)
