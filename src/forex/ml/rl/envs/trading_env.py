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


def build_window_observation(
    features: np.ndarray,
    idx: int,
    *,
    position: float,
    max_position: float,
    window_size: int,
) -> np.ndarray:
    window_size = max(1, int(window_size))
    width = features.shape[1]
    start = max(0, idx - window_size + 1)
    window = features[start : idx + 1]
    if len(window) < window_size:
        if len(window) > 0:
            first_row = window[:1]
        else:
            first_row = np.zeros((1, width), dtype=np.float32)
        pad = np.repeat(first_row.astype(np.float32), window_size - len(window), axis=0)
        window = np.vstack([pad, window])
    denom = float(max_position) if max_position else 1.0
    if denom <= 0.0:
        denom = 1.0
    position_norm = position / denom
    return np.concatenate([window.reshape(-1), np.array([position_norm], dtype=np.float32)]).astype(
        np.float32
    )


@dataclass
class TradingConfig:
    transaction_cost_bps: float = 1.0
    slippage_bps: float = 0.5
    holding_cost_bps: float = 0.0
    episode_length: int | None = 2048
    random_start: bool = True
    start_mode: str = ""
    min_position_change: float = 0.0
    discretize_actions: bool = False
    discrete_positions: tuple[float, ...] = (-1.0, 0.0, 1.0)
    max_position: float = 1.0
    position_step: float = 0.0
    reward_horizon: int = 1
    window_size: int = 1
    reward_scale: float = 1.0
    reward_clip: float = 0.0
    reward_mode: str = "linear"
    risk_aversion: float = 0.0
    drawdown_penalty: float = 0.0
    drawdown_governor_slope: float = 0.0
    drawdown_governor_floor: float = 0.3


class TradingEnv(gym.Env if gym else object):
    metadata = {"render_modes": []}

    def __init__(
        self,
        features: np.ndarray,
        closes: np.ndarray,
        config: TradingConfig | None = None,
        timestamps: list[str] | None = None,
    ) -> None:
        if gym is None or spaces is None:
            raise ImportError("gymnasium is required for TradingEnv")
        self._features = features
        self._closes = closes
        self._config = config or TradingConfig()
        self._cost_rate = (self._config.transaction_cost_bps + self._config.slippage_bps) / 10000.0
        self._holding_cost_rate = self._config.holding_cost_bps / 10000.0
        self._timestamps = timestamps or []
        self._start_candidates: list[int] | None = None
        self._window_size = max(1, int(self._config.window_size))

        obs_dim = features.shape[1] * self._window_size + 1
        # Keep action space consistent with max_position so the policy can reach it.
        max_position = max(1.0, float(self._config.max_position))
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32)
        self.action_space = spaces.Box(low=-max_position, high=max_position, shape=(1,), dtype=np.float32)

        self._idx = 0
        self._max_idx = len(self._closes) - 1
        self._end = self._max_idx
        self._position = 0.0
        self._equity = 1.0
        self._peak_equity = 1.0

    def _current_drawdown(self) -> float:
        peak = max(float(self._peak_equity), 1e-12)
        equity = max(float(self._equity), 1e-12)
        return max(0.0, (peak - equity) / peak)

    def _drawdown_governor_scale(self) -> float:
        slope = max(0.0, float(getattr(self._config, "drawdown_governor_slope", 0.0)))
        floor = float(getattr(self._config, "drawdown_governor_floor", 0.3))
        floor = min(1.0, max(0.0, floor))
        if slope <= 0.0:
            return 1.0
        drawdown = self._current_drawdown()
        return max(floor, 1.0 - slope * drawdown)

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        _ = options
        # Base reset bounds on full dataset, not on prior episode end.
        max_start = self._max_idx - 1
        if self._config.episode_length:
            max_start = max(0, self._max_idx - self._config.episode_length)
        min_start = min(max_start, max(0, self._window_size - 1))
        self._idx = self._pick_start_index(max_start, min_start)
        if self._config.episode_length:
            self._end = min(self._idx + self._config.episode_length, self._max_idx)
        else:
            self._end = self._max_idx
        self._position = 0.0
        self._equity = 1.0
        self._peak_equity = 1.0
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
            horizon = max(1, int(self._config.reward_horizon))
            horizon_idx = min(self._idx + horizon, self._max_idx)
            price_return = (float(self._closes[horizon_idx]) - base_price) / base_price
        step_pnl = self._position * float(price_return)
        net_return = step_pnl - cost - holding_cost
        reward = net_return
        if self._config.risk_aversion > 0.0:
            reward -= self._config.risk_aversion * (step_pnl ** 2)

        prev_equity = max(float(self._equity), 1e-12)
        prev_peak_equity = max(float(self._peak_equity), prev_equity, 1e-12)
        prev_drawdown = max(0.0, (prev_peak_equity - prev_equity) / prev_peak_equity)
        growth_factor = max(1e-12, 1.0 + net_return)
        next_equity = prev_equity * growth_factor
        next_peak_equity = max(prev_peak_equity, next_equity)
        drawdown = max(0.0, (next_peak_equity - next_equity) / next_peak_equity)
        drawdown_delta = max(0.0, drawdown - prev_drawdown)

        reward_mode = str(getattr(self._config, "reward_mode", "linear") or "linear").strip().lower()
        if reward_mode == "log_return":
            reward = float(np.log(growth_factor))

        drawdown_penalty = 0.0
        if self._config.drawdown_penalty > 0.0:
            drawdown_penalty = self._config.drawdown_penalty * drawdown_delta
            reward -= drawdown_penalty
        if self._config.reward_scale != 1.0:
            reward *= self._config.reward_scale
        if self._config.reward_clip > 0.0:
            reward = float(np.clip(reward, -self._config.reward_clip, self._config.reward_clip))

        self._equity = next_equity
        self._peak_equity = next_peak_equity
        self._position = target_position
        self._idx += 1

        terminated = self._idx >= self._end
        info = {
            "equity": self._equity,
            "position": self._position,
            "delta": delta,
            "cost": cost,
            "holding_cost": holding_cost,
            "net_return": net_return,
            "drawdown": drawdown,
            "drawdown_delta": drawdown_delta,
            "drawdown_penalty": drawdown_penalty,
            "drawdown_governor_scale": self._drawdown_governor_scale(),
            "price_return": price_return,
            "step_pnl": step_pnl,
            "reward": reward,
            "reward_mode": reward_mode,
        }
        return self._get_obs(), reward, terminated, False, info

    def _apply_action(self, action: np.ndarray) -> float:
        max_position = max(0.0, float(self._config.max_position))
        governor_scale = self._drawdown_governor_scale()
        effective_max_position = max_position * governor_scale
        clip_limit = max(1.0, max_position)
        target = float(np.clip(action[0], -clip_limit, clip_limit))
        if self._config.discretize_actions and self._config.discrete_positions:
            target = min(self._config.discrete_positions, key=lambda val: abs(val - target))
        if self._config.position_step > 0.0:
            target = round(target / self._config.position_step) * self._config.position_step
        if effective_max_position > 0.0:
            target = float(np.clip(target, -effective_max_position, effective_max_position))
        else:
            target = 0.0
        if abs(target - self._position) < self._config.min_position_change:
            target = self._position
        return float(target)

    def _get_obs(self) -> np.ndarray:
        return build_window_observation(
            self._features,
            self._idx,
            position=self._position,
            max_position=float(self._config.max_position),
            window_size=self._window_size,
        )

    def _windowed_features(self, idx: int) -> np.ndarray:
        obs = build_window_observation(
            self._features,
            idx,
            position=0.0,
            max_position=1.0,
            window_size=self._window_size,
        )
        return obs[:-1]

    def _pick_start_index(self, max_start: int, min_start: int) -> int:
        mode = str(getattr(self._config, "start_mode", "") or "").strip().lower()
        if not mode:
            mode = "random" if self._config.random_start else "first"
        if mode == "first" or max_start <= min_start:
            return int(min_start)
        if mode == "weekly_open":
            candidates = [idx for idx in self._weekly_open_indices() if min_start <= idx <= max_start]
            if candidates:
                return int(candidates[int(self.np_random.integers(0, len(candidates)))])
            return int(min_start)
        if max_start > min_start:
            return int(self.np_random.integers(min_start, max_start + 1))
        return int(min_start)

    def _weekly_open_indices(self) -> list[int]:
        if self._start_candidates is not None:
            return self._start_candidates
        if not self._timestamps:
            self._start_candidates = []
            return self._start_candidates
        candidates: list[int] = []
        prev_stamp = None
        for idx, raw in enumerate(self._timestamps):
            stamp = np.datetime64(raw)
            if np.isnat(stamp):
                prev_stamp = None
                continue
            weekday = int(((stamp.astype("datetime64[D]").astype(int) + 3) % 7))
            if weekday != 0:
                prev_stamp = stamp
                continue
            if prev_stamp is None:
                candidates.append(idx)
                prev_stamp = stamp
                continue
            prev_day = prev_stamp.astype("datetime64[D]")
            curr_day = stamp.astype("datetime64[D]")
            if curr_day != prev_day:
                candidates.append(idx)
            prev_stamp = stamp
        self._start_candidates = candidates
        return self._start_candidates
