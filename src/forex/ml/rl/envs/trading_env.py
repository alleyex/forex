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


def compute_drawdown(equity: float, peak_equity: float) -> float:
    peak = max(float(peak_equity), 1e-12)
    current = max(float(equity), 1e-12)
    return max(0.0, (peak - current) / peak)


def compute_drawdown_governor_scale(
    *,
    equity: float,
    peak_equity: float,
    slope: float,
    floor: float,
) -> float:
    slope = max(0.0, float(slope))
    floor = min(1.0, max(0.0, float(floor)))
    if slope <= 0.0:
        return 1.0
    drawdown = compute_drawdown(equity, peak_equity)
    return max(floor, 1.0 - slope * drawdown)


def compute_realized_vol(closes: np.ndarray, idx: int, lookback: int) -> float:
    lookback = max(2, int(lookback))
    end = max(0, int(idx)) + 1
    start = max(0, end - lookback)
    window = closes[start:end]
    if len(window) < 2:
        return 0.0
    prev = window[:-1].astype(np.float64)
    curr = window[1:].astype(np.float64)
    valid = prev > 0.0
    if not np.any(valid):
        return 0.0
    returns = (curr[valid] - prev[valid]) / prev[valid]
    if len(returns) == 0:
        return 0.0
    return float(np.std(returns))


def compute_horizon_return(closes: np.ndarray, idx: int, reward_horizon: int) -> float:
    base_idx = max(0, int(idx))
    if base_idx >= len(closes):
        return 0.0
    base_price = float(closes[base_idx])
    if base_price <= 0.0:
        return 0.0
    horizon = max(1, int(reward_horizon))
    horizon_idx = min(base_idx + horizon, len(closes) - 1)
    return (float(closes[horizon_idx]) - base_price) / base_price


def compute_vol_target_scale(
    closes: np.ndarray,
    idx: int,
    *,
    target_vol: float,
    lookback: int,
    floor: float,
    cap: float,
) -> tuple[float, float]:
    target_vol = max(0.0, float(target_vol))
    floor = max(0.0, float(floor))
    cap = max(floor, float(cap))
    if target_vol <= 0.0:
        return 1.0, 0.0
    realized_vol = compute_realized_vol(closes, idx, lookback)
    if realized_vol <= 0.0:
        return 1.0, realized_vol
    scale = target_vol / realized_vol
    return float(np.clip(scale, floor, cap)), realized_vol


def simulate_step_transition(
    *,
    current_position: float,
    target_position: float,
    closes: np.ndarray,
    idx: int,
    equity: float,
    peak_equity: float,
    config: "TradingConfig",
) -> dict[str, float]:
    cost_rate = (float(config.transaction_cost_bps) + float(config.slippage_bps)) / 10000.0
    holding_cost_rate = float(config.holding_cost_bps) / 10000.0
    delta = float(target_position) - float(current_position)
    cost = abs(delta) * cost_rate
    holding_cost = abs(float(current_position)) * holding_cost_rate
    price_return = compute_horizon_return(closes, idx, int(getattr(config, "reward_horizon", 1)))
    step_pnl = float(current_position) * float(price_return)
    net_return = step_pnl - cost - holding_cost
    reward = net_return
    if float(config.risk_aversion) > 0.0:
        reward -= float(config.risk_aversion) * (step_pnl ** 2)

    prev_equity = max(float(equity), 1e-12)
    prev_peak_equity = max(float(peak_equity), prev_equity, 1e-12)
    prev_drawdown = compute_drawdown(prev_equity, prev_peak_equity)
    growth_factor = max(1e-12, 1.0 + net_return)
    next_equity = prev_equity * growth_factor
    next_peak_equity = max(prev_peak_equity, next_equity)
    drawdown = compute_drawdown(next_equity, next_peak_equity)
    drawdown_delta = max(0.0, drawdown - prev_drawdown)

    reward_mode = str(getattr(config, "reward_mode", "linear") or "linear").strip().lower()
    if reward_mode == "log_return":
        reward = float(np.log(growth_factor))
    elif reward_mode == "risk_adjusted":
        reward = float(np.log(growth_factor))

    downside_penalty = 0.0
    if reward_mode == "risk_adjusted" and float(config.downside_penalty) > 0.0:
        downside_penalty = float(config.downside_penalty) * (min(0.0, net_return) ** 2)
        reward -= downside_penalty

    drawdown_penalty = 0.0
    if float(config.drawdown_penalty) > 0.0:
        drawdown_penalty = float(config.drawdown_penalty) * drawdown_delta
        reward -= drawdown_penalty
    if float(config.reward_scale) != 1.0:
        reward *= float(config.reward_scale)
    if float(config.reward_clip) > 0.0:
        reward = float(np.clip(reward, -float(config.reward_clip), float(config.reward_clip)))

    return {
        "delta": float(delta),
        "cost": float(cost),
        "holding_cost": float(holding_cost),
        "net_return": float(net_return),
        "price_return": float(price_return),
        "step_pnl": float(step_pnl),
        "reward": float(reward),
        "reward_mode": reward_mode,
        "downside_penalty": float(downside_penalty),
        "drawdown": float(drawdown),
        "drawdown_delta": float(drawdown_delta),
        "drawdown_penalty": float(drawdown_penalty),
        "equity": float(next_equity),
        "peak_equity": float(next_peak_equity),
    }


def apply_risk_engine(
    target: float,
    *,
    current_position: float,
    config: "TradingConfig",
    closes: np.ndarray,
    idx: int,
    equity: float,
    peak_equity: float,
) -> tuple[float, dict[str, float]]:
    max_position = max(0.0, float(config.max_position))
    clip_limit = max(1.0, max_position)
    value = float(np.clip(target, -clip_limit, clip_limit))
    vol_scale, realized_vol = compute_vol_target_scale(
        closes,
        idx,
        target_vol=float(getattr(config, "target_vol", 0.0)),
        lookback=int(getattr(config, "vol_target_lookback", 72)),
        floor=float(getattr(config, "vol_scale_floor", 0.5)),
        cap=float(getattr(config, "vol_scale_cap", 1.5)),
    )
    dd_scale = compute_drawdown_governor_scale(
        equity=equity,
        peak_equity=peak_equity,
        slope=float(getattr(config, "drawdown_governor_slope", 0.0)),
        floor=float(getattr(config, "drawdown_governor_floor", 0.3)),
    )
    combined_scale = vol_scale * dd_scale
    value *= combined_scale
    if config.discretize_actions and config.discrete_positions:
        value = min(config.discrete_positions, key=lambda candidate: abs(float(candidate) - value))
    if config.position_step > 0.0:
        value = round(value / config.position_step) * config.position_step
    effective_max_position = max_position * dd_scale
    if effective_max_position > 0.0:
        value = float(np.clip(value, -effective_max_position, effective_max_position))
    else:
        value = 0.0
    if abs(value - current_position) < config.min_position_change:
        value = float(current_position)
    return float(value), {
        "vol_target_scale": float(vol_scale),
        "realized_vol": float(realized_vol),
        "drawdown_governor_scale": float(dd_scale),
        "risk_scale": float(combined_scale),
    }


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
    downside_penalty: float = 0.0
    drawdown_penalty: float = 0.0
    target_vol: float = 0.0
    vol_target_lookback: int = 72
    vol_scale_floor: float = 0.5
    vol_scale_cap: float = 1.5
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
        target_position, risk_info = self._apply_action(action)
        transition = simulate_step_transition(
            current_position=self._position,
            target_position=target_position,
            closes=self._closes,
            idx=self._idx,
            equity=self._equity,
            peak_equity=self._peak_equity,
            config=self._config,
        )
        self._equity = transition["equity"]
        self._peak_equity = transition["peak_equity"]
        self._position = target_position
        self._idx += 1

        terminated = self._idx >= self._end
        info = {
            "equity": self._equity,
            "position": self._position,
            "delta": transition["delta"],
            "cost": transition["cost"],
            "holding_cost": transition["holding_cost"],
            "net_return": transition["net_return"],
            "drawdown": transition["drawdown"],
            "drawdown_delta": transition["drawdown_delta"],
            "downside_penalty": transition["downside_penalty"],
            "drawdown_penalty": transition["drawdown_penalty"],
            "drawdown_governor_scale": risk_info["drawdown_governor_scale"],
            "vol_target_scale": risk_info["vol_target_scale"],
            "realized_vol": risk_info["realized_vol"],
            "risk_scale": risk_info["risk_scale"],
            "price_return": transition["price_return"],
            "step_pnl": transition["step_pnl"],
            "reward": transition["reward"],
            "reward_mode": transition["reward_mode"],
        }
        return self._get_obs(), transition["reward"], terminated, False, info

    def _apply_action(self, action: np.ndarray) -> tuple[float, dict[str, float]]:
        return apply_risk_engine(
            float(action[0]),
            current_position=self._position,
            config=self._config,
            closes=self._closes,
            idx=self._idx,
            equity=self._equity,
            peak_equity=self._peak_equity,
        )

    def _get_obs(self) -> np.ndarray:
        return build_window_observation(
            self._features,
            self._idx,
            position=self._position,
            max_position=float(self._config.max_position),
            window_size=self._window_size,
        )

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
