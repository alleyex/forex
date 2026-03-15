from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, EvalCallback
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, sync_envs_normalization

from forex.config.paths import DEFAULT_MODEL_PATH
from forex.ml.rl.envs.trading_config_io import save_trading_config
from forex.ml.rl.envs.trading_env import (
    TradingConfig,
    TradingEnv,
    apply_risk_engine,
    build_window_observation,
    decode_policy_action,
    simulate_step_transition,
    uses_native_discrete_actions,
)
from forex.ml.rl.features.feature_builder import (
    apply_feature_profile,
    apply_scaler,
    build_feature_frame,
    filter_feature_rows_by_session,
    fit_scaler,
    load_csv,
    required_raw_columns_for_profile,
    save_scaler,
    select_feature_columns,
)
from forex.ml.rl.models import WindowCnnExtractor
from forex.tools.rl.run_live_sim import (
    PlaybackBundle,
    PlaybackResult,
    _apply_policy_envelope,
    _build_gate_mask,
    _build_threshold_bump_array,
    _parse_gate_specs,
    _parse_threshold_bump_specs,
    _policy_enabled,
    run_playback,
)


def _save_training_args_snapshot(
    out_path: str,
    args: argparse.Namespace,
    *,
    feature_profile: str,
    requested_feature_names: list[str] | None,
    scaler_path: str,
    env_config_path: str,
) -> None:
    target = str(out_path).strip()
    if not target:
        return
    path = Path(target).expanduser()
    payload = dict(vars(args))
    payload["feature_profile"] = feature_profile
    payload["requested_feature_names"] = requested_feature_names
    payload["feature_scaler_out_resolved"] = scaler_path
    payload["env_config_out_resolved"] = env_config_path
    payload["model_out_resolved"] = str(Path(args.model_out).expanduser())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _save_training_status(
    out_path: str,
    *,
    status: str,
    stop_reason: str = "",
    exit_code: int | None = None,
    stopped_early: bool | None = None,
    total_steps_target: int | None = None,
    last_step: int | None = None,
) -> None:
    target = str(out_path).strip()
    if not target:
        return
    path = Path(target).expanduser()
    payload = {
        "status": status,
        "stop_reason": stop_reason,
        "exit_code": exit_code,
        "stopped_early": stopped_early,
        "total_steps_target": total_steps_target,
        "last_step": last_step,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _save_checkpoint_selection(out_path: str, payload: dict) -> None:
    target = str(out_path).strip()
    if not target:
        return
    path = Path(target).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _handle_termination_signal(signum, _frame) -> None:
    signal_name = (
        signal.Signals(signum).name
        if signum in signal.Signals._value2member_map_
        else str(signum)
    )
    print(f"Received {signal_name}; saving current checkpoint before exit.")
    raise KeyboardInterrupt


def _build_env(features, closes, config: TradingConfig, timestamps=None) -> DummyVecEnv:
    return DummyVecEnv(
        [lambda: Monitor(TradingEnv(features, closes, config, timestamps=timestamps))]
    )


def _build_curriculum_positions(max_position: float, position_step: float) -> tuple[float, ...]:
    max_position = max(0.0, float(max_position))
    position_step = max(0.0, float(position_step))
    if max_position <= 0.0 or position_step <= 0.0:
        return (0.0,)
    count = max(1, int(round(max_position / position_step)))
    positions = [round(idx * position_step, 10) for idx in range(-count, count + 1)]
    clipped = sorted(
        {float(np.clip(value, -max_position, max_position)) for value in positions}
    )
    if 0.0 not in clipped:
        clipped.append(0.0)
    return tuple(sorted(clipped))


def _heuristic_action_label(
    closes: np.ndarray,
    idx: int,
    *,
    labeler: str,
    max_position: float,
    position_step: float,
    lookback_short: int,
    lookback_long: int,
    threshold: float,
    action_scale: float,
) -> float:
    lookback_short = max(2, int(lookback_short))
    lookback_long = max(lookback_short + 1, int(lookback_long))
    if idx < lookback_long:
        return 0.0
    base_short = float(closes[idx - lookback_short])
    base_long = float(closes[idx - lookback_long])
    current = float(closes[idx])
    if base_short <= 0.0 or base_long <= 0.0 or current <= 0.0:
        return 0.0
    action_scale = max(float(action_scale), 0.0)
    action_level = min(max_position, max(2.0 * max(position_step, 0.0), 0.2))
    labeler = str(labeler).strip().lower()
    if labeler == "breakout_sym":
        short_window = closes[idx - lookback_short : idx]
        long_window = closes[idx - lookback_long : idx]
        if len(short_window) == 0 or len(long_window) == 0:
            return 0.0
        short_high = float(np.max(short_window))
        short_low = float(np.min(short_window))
        long_high = float(np.max(long_window))
        long_low = float(np.min(long_window))
        if short_low <= 0.0 or long_low <= 0.0:
            return 0.0
        long_break = min(
            (current - short_high) / max(short_high, 1e-12),
            (current - long_high) / max(long_high, 1e-12),
        )
        short_break = min(
            (short_low - current) / max(short_low, 1e-12),
            (long_low - current) / max(long_low, 1e-12),
        )
        if long_break > threshold:
            return float(action_level)
        if short_break > threshold:
            return float(-action_level)
        return 0.0
    if labeler == "breakout_cont":
        short_window = closes[idx - lookback_short : idx]
        long_window = closes[idx - lookback_long : idx]
        if len(short_window) == 0 or len(long_window) == 0:
            return 0.0
        short_high = float(np.max(short_window))
        short_low = float(np.min(short_window))
        long_high = float(np.max(long_window))
        long_low = float(np.min(long_window))
        short_range = max(short_high - short_low, 1e-12)
        long_range = max(long_high - long_low, 1e-12)
        breakout_up = max(
            (current - short_high) / max(short_high, 1e-12),
            (current - long_high) / max(long_high, 1e-12),
            0.0,
        )
        breakout_down = max(
            (short_low - current) / max(short_low, 1e-12),
            (long_low - current) / max(long_low, 1e-12),
            0.0,
        )
        market_pos_short = ((current - ((short_high + short_low) * 0.5)) / short_range) * 2.0
        market_pos_long = ((current - ((long_high + long_low) * 0.5)) / long_range) * 2.0
        ret_short = (current - base_short) / base_short
        ret_long = (current - base_long) / base_long
        signal = (
            0.45 * (breakout_up - breakout_down)
            + 0.30 * (0.5 * (market_pos_short + market_pos_long))
            + 0.25 * (0.5 * (ret_short + ret_long) / max(threshold, 1e-6))
        )
        action = max_position * math.tanh(signal * action_scale)
        neutral_floor = max(max_position * 0.05, max(position_step, 0.0))
        if abs(action) < neutral_floor:
            return 0.0
        return float(np.clip(action, -max_position, max_position))

    ret_short = (current - base_short) / base_short
    ret_long = (current - base_long) / base_long
    if labeler == "momentum_cont":
        signal = 0.5 * (ret_short + ret_long) / max(threshold, 1e-6)
        signal *= action_scale
        action = max_position * math.tanh(signal)
        neutral_floor = max(max_position * 0.05, max(position_step, 0.0))
        if abs(action) < neutral_floor:
            return 0.0
        return float(np.clip(action, -max_position, max_position))
    discrete_action_level = min(max_position, action_level * max(action_scale, 1.0))
    if ret_short > threshold and ret_long > threshold:
        return float(discrete_action_level)
    if ret_short < -threshold and ret_long < -threshold:
        return float(-discrete_action_level)
    return 0.0


def _warm_start_direction_bucket(
    action: float,
    *,
    max_position: float,
    position_step: float,
) -> int:
    directional_floor = max(max(position_step, 0.0), max_position * 0.05, 1e-6)
    if action > directional_floor:
        return 1
    if action < -directional_floor:
        return -1
    return 0


def _sample_balanced_indices(indices: np.ndarray, target_count: int) -> np.ndarray:
    if target_count <= 0 or len(indices) == 0:
        return np.zeros(0, dtype=np.int32)
    if len(indices) <= target_count:
        return np.asarray(indices, dtype=np.int32)
    take = np.linspace(0, len(indices) - 1, num=target_count, dtype=np.int32)
    return np.asarray(indices, dtype=np.int32)[take]


def _build_warm_start_dataset(
    features: np.ndarray,
    closes: np.ndarray,
    config: TradingConfig,
    *,
    labeler: str,
    sample_limit: int,
    lookback_short: int,
    lookback_long: int,
    threshold: float,
    action_scale: float,
    long_weight: float,
    short_weight: float,
    flat_weight: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, float]]:
    max_position = max(0.0, float(config.max_position))
    if max_position <= 0.0:
        return (
            np.zeros(
                (0, features.shape[1] * max(1, int(config.window_size)) + 1),
                dtype=np.float32,
            ),
            np.zeros((0, 1), dtype=np.float32),
            np.zeros((0, 1), dtype=np.float32),
            {"samples": 0.0},
        )
    start_idx = max(max(1, int(config.window_size)) - 1, int(lookback_long))
    indices = np.arange(start_idx, len(closes) - 1, dtype=np.int32)
    if sample_limit > 0 and len(indices) > sample_limit:
        take = np.linspace(0, len(indices) - 1, num=sample_limit, dtype=np.int32)
        indices = indices[take]
    flat_indices: list[int] = []
    long_indices: list[int] = []
    short_indices: list[int] = []
    for idx in indices:
        action = _heuristic_action_label(
            closes,
            int(idx),
            labeler=labeler,
            max_position=max_position,
            position_step=float(config.position_step),
            lookback_short=lookback_short,
            lookback_long=lookback_long,
            threshold=threshold,
            action_scale=action_scale,
        )
        bucket = _warm_start_direction_bucket(
            action,
            max_position=max_position,
            position_step=float(config.position_step),
        )
        if bucket > 0:
            long_indices.append(int(idx))
        elif bucket < 0:
            short_indices.append(int(idx))
        else:
            flat_indices.append(int(idx))

    raw_long_count = len(long_indices)
    raw_short_count = len(short_indices)
    raw_flat_count = len(flat_indices)
    directional_target = min(raw_long_count, raw_short_count)
    if directional_target > 0:
        long_indices = _sample_balanced_indices(
            np.asarray(long_indices, dtype=np.int32),
            directional_target,
        ).tolist()
        short_indices = _sample_balanced_indices(
            np.asarray(short_indices, dtype=np.int32),
            directional_target,
        ).tolist()
        flat_target = min(raw_flat_count, max(directional_target, 1))
        flat_indices = _sample_balanced_indices(
            np.asarray(flat_indices, dtype=np.int32),
            flat_target,
        ).tolist()
        balanced_indices = np.asarray(
            sorted(long_indices + short_indices + flat_indices),
            dtype=np.int32,
        )
    else:
        balanced_indices = np.asarray(indices, dtype=np.int32)

    observations: list[np.ndarray] = []
    actions: list[list[float]] = []
    weights: list[list[float]] = []
    long_count = 0
    short_count = 0
    flat_count = 0
    abs_action_sum = 0.0
    for idx in balanced_indices:
        action = _heuristic_action_label(
            closes,
            int(idx),
            labeler=labeler,
            max_position=max_position,
            position_step=float(config.position_step),
            lookback_short=lookback_short,
            lookback_long=lookback_long,
            threshold=threshold,
            action_scale=action_scale,
        )
        bucket = _warm_start_direction_bucket(
            action,
            max_position=max_position,
            position_step=float(config.position_step),
        )
        if bucket > 0:
            long_count += 1
        elif bucket < 0:
            short_count += 1
        else:
            flat_count += 1
        abs_action_sum += abs(float(action))
        if action < 0.0:
            sample_weight = max(float(short_weight), 0.0)
        elif action > 0.0:
            sample_weight = max(float(long_weight), 0.0)
        else:
            sample_weight = max(float(flat_weight), 0.0)
        observations.append(
            build_window_observation(
                features,
                int(idx),
                position=0.0,
                max_position=max_position,
                window_size=int(config.window_size),
            )
        )
        actions.append([float(action)])
        weights.append([float(sample_weight)])
    obs_array = np.asarray(observations, dtype=np.float32)
    action_array = np.asarray(actions, dtype=np.float32)
    weight_array = np.asarray(weights, dtype=np.float32)
    summary = {
        "samples": float(len(action_array)),
        "long_ratio": float(long_count / len(action_array)) if len(action_array) else 0.0,
        "short_ratio": float(short_count / len(action_array)) if len(action_array) else 0.0,
        "flat_ratio": float(flat_count / len(action_array)) if len(action_array) else 1.0,
        "raw_samples": float(len(indices)),
        "raw_long_ratio": float(raw_long_count / len(indices)) if len(indices) else 0.0,
        "raw_short_ratio": float(raw_short_count / len(indices)) if len(indices) else 0.0,
        "raw_flat_ratio": float(raw_flat_count / len(indices)) if len(indices) else 1.0,
        "long_weight": max(float(long_weight), 0.0),
        "short_weight": max(float(short_weight), 0.0),
        "flat_weight": max(float(flat_weight), 0.0),
        "avg_abs_action": abs_action_sum / len(action_array) if len(action_array) else 0.0,
        "max_abs_action": float(np.max(np.abs(action_array))) if len(action_array) else 0.0,
        "action_scale": max(float(action_scale), 0.0),
    }
    return obs_array, action_array, weight_array, summary


def _warm_start_policy(
    model: PPO,
    observations: np.ndarray,
    actions: np.ndarray,
    sample_weights: np.ndarray,
    *,
    epochs: int,
    batch_size: int,
    loss_scale: float = 1.0,
    metric_writer=None,
    metric_step: int | None = None,
    metric_prefix: str = "warm_start",
) -> float:
    if len(observations) == 0 or len(actions) == 0 or epochs <= 0:
        return 0.0
    device = model.device
    obs_tensor = torch.as_tensor(observations, dtype=torch.float32, device=device)
    action_tensor = torch.as_tensor(actions, dtype=torch.float32, device=device)
    weight_tensor = torch.as_tensor(sample_weights, dtype=torch.float32, device=device)
    optimizer = model.policy.optimizer
    batch_size = max(1, int(batch_size))
    epochs = max(1, int(epochs))
    loss_scale = max(float(loss_scale), 0.0)
    epoch_losses: list[float] = []
    for epoch in range(epochs):
        permutation = torch.randperm(obs_tensor.shape[0], device=device)
        epoch_loss = 0.0
        batch_count = 0
        for start in range(0, obs_tensor.shape[0], batch_size):
            idx = permutation[start : start + batch_size]
            batch_obs = obs_tensor[idx]
            batch_actions = action_tensor[idx]
            batch_weights = weight_tensor[idx]
            distribution = model.policy.get_distribution(batch_obs)
            if not hasattr(distribution.distribution, "mean"):
                raise ValueError("Warm-start requires a continuous-action policy distribution.")
            predicted_actions = distribution.distribution.mean
            squared_error = torch.square(predicted_actions - batch_actions)
            base_loss = torch.mean(batch_weights * squared_error)
            loss = base_loss * loss_scale
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.detach().cpu().item())
            batch_count += 1
        mean_loss = epoch_loss / max(1, batch_count)
        epoch_losses.append(float(mean_loss))
        if metric_writer is not None and metric_step is not None:
            metric_writer(metric_step, f"{metric_prefix}/epoch", float(epoch + 1))
            metric_writer(metric_step, f"{metric_prefix}/epoch_loss", float(mean_loss))
        print(
            "Warm-start epoch:",
            f"{epoch + 1}/{epochs}",
            f"loss={mean_loss:.6g}",
        )
    final_loss = float(np.mean(epoch_losses)) if epoch_losses else 0.0
    if metric_writer is not None and metric_step is not None:
        metric_writer(metric_step, f"{metric_prefix}/loss", final_loss)
    return final_loss


class ImitationRolloutCallback(BaseCallback):
    def __init__(
        self,
        *,
        write_metric,
        observations: np.ndarray,
        actions: np.ndarray,
        sample_weights: np.ndarray,
        max_steps: int,
        epochs_per_rollout: int,
        batch_size: int,
        loss_scale: float,
        verbose: int = 0,
    ) -> None:
        super().__init__(verbose=verbose)
        self._write_metric = write_metric
        self._observations = observations
        self._actions = actions
        self._sample_weights = sample_weights
        self._max_steps = max(0, int(max_steps))
        self._epochs_per_rollout = max(1, int(epochs_per_rollout))
        self._batch_size = max(1, int(batch_size))
        self._loss_scale = max(float(loss_scale), 0.0)

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        if self._max_steps <= 0 or len(self._observations) == 0:
            return
        step = int(self.num_timesteps)
        if step > self._max_steps:
            return
        loss = _warm_start_policy(
            self.model,
            self._observations,
            self._actions,
            self._sample_weights,
            epochs=self._epochs_per_rollout,
            batch_size=self._batch_size,
            loss_scale=self._loss_scale,
        )
        self._write_metric(step, "imitation/loss", float(loss))
        self._write_metric(step, "imitation/active", 1.0)


class MetricsLogCallback(BaseCallback):
    def __init__(self, write_metric, verbose: int = 0) -> None:
        super().__init__(verbose=verbose)
        self._write_metric = write_metric
        self._started_at = time.perf_counter()
        self._rollout_sums = {
            "reward_step_mean": 0.0,
            "step_pnl_mean": 0.0,
            "cost_mean": 0.0,
            "holding_cost_mean": 0.0,
            "abs_delta_mean": 0.0,
            "abs_price_return_mean": 0.0,
        }
        self._rollout_count = 0

    def _on_step(self) -> bool:
        step = int(self.num_timesteps)
        for info in self.locals.get("infos", []):
            self._rollout_sums["reward_step_mean"] += float(info.get("reward", 0.0))
            self._rollout_sums["step_pnl_mean"] += float(info.get("step_pnl", 0.0))
            self._rollout_sums["cost_mean"] += float(info.get("cost", 0.0))
            self._rollout_sums["holding_cost_mean"] += float(info.get("holding_cost", 0.0))
            self._rollout_sums["abs_delta_mean"] += abs(float(info.get("delta", 0.0)))
            self._rollout_sums["abs_price_return_mean"] += abs(float(info.get("price_return", 0.0)))
            self._rollout_count += 1
            metrics = info.get("episode")
            if not metrics:
                continue
            if "r" in metrics:
                self._write_metric(step, "ep_rew_mean", float(metrics["r"]))
        return True

    def _on_rollout_end(self) -> None:
        step = int(self.num_timesteps)
        if self._rollout_count > 0:
            for metric, total in self._rollout_sums.items():
                self._write_metric(step, metric, total / self._rollout_count)
        mean_reward = self.logger.name_to_value.get("rollout/ep_rew_mean")
        if mean_reward is not None:
            self._write_metric(step, "ep_rew_mean", float(mean_reward))
        logger_metric_map = {
            "train/value_loss": "value_loss",
            "train/explained_variance": "explained_variance",
            "train/approx_kl": "approx_kl",
            "train/clip_fraction": "clip_fraction",
            "train/entropy_loss": "entropy_loss",
            "train/policy_gradient_loss": "policy_gradient_loss",
            "train/loss": "loss",
            "train/std": "std",
            "time/fps": "fps",
        }
        for logger_key, metric_key in logger_metric_map.items():
            metric_value = self.logger.name_to_value.get(logger_key)
            if metric_value is None:
                continue
            self._write_metric(step, metric_key, float(metric_value))
        if self.logger.name_to_value.get("time/fps") is None:
            elapsed = max(time.perf_counter() - self._started_at, 1e-9)
            self._write_metric(step, "fps", float(step) / elapsed)
        for metric in self._rollout_sums:
            self._rollout_sums[metric] = 0.0
        self._rollout_count = 0


def _continuous_supervision_supported(config: TradingConfig) -> bool:
    return not uses_native_discrete_actions(config)


class PlateauEvalCallback(EvalCallback):
    def __init__(
        self,
        *args,
        write_metric,
        early_stop_enabled: bool,
        early_stop_warmup_steps: int,
        early_stop_patience_evals: int,
        early_stop_min_delta: float,
        activity_profiler=None,
        anti_flat_enabled: bool,
        anti_flat_warmup_steps: int,
        anti_flat_patience_evals: int,
        anti_flat_min_trade_rate: float,
        anti_flat_max_flat_ratio: float,
        anti_flat_max_ls_imbalance: float,
        checkpoint_min_trade_rate: float,
        checkpoint_max_trade_rate: float,
        checkpoint_max_flat_ratio: float,
        checkpoint_max_ls_imbalance: float,
        checkpoint_max_drawdown: float,
        playback_candidate_dir: str = "",
        playback_top_n: int = 0,
        collect_playback_candidates: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._write_metric = write_metric
        self._early_stop_enabled = bool(early_stop_enabled)
        self._early_stop_warmup_steps = max(0, int(early_stop_warmup_steps))
        self._early_stop_patience_evals = max(1, int(early_stop_patience_evals))
        self._early_stop_min_delta = max(0.0, float(early_stop_min_delta))
        self._best_eval_reward = float("-inf")
        self._no_improvement_evals = 0
        self._activity_profiler = activity_profiler
        self._anti_flat_enabled = bool(anti_flat_enabled)
        self._anti_flat_warmup_steps = max(0, int(anti_flat_warmup_steps))
        self._anti_flat_patience_evals = max(1, int(anti_flat_patience_evals))
        self._anti_flat_min_trade_rate = max(0.0, float(anti_flat_min_trade_rate))
        self._anti_flat_max_flat_ratio = float(anti_flat_max_flat_ratio)
        self._anti_flat_max_ls_imbalance = float(anti_flat_max_ls_imbalance)
        self._checkpoint_min_trade_rate = max(0.0, float(checkpoint_min_trade_rate))
        self._checkpoint_max_trade_rate = max(0.0, float(checkpoint_max_trade_rate))
        self._checkpoint_max_flat_ratio = float(checkpoint_max_flat_ratio)
        self._checkpoint_max_ls_imbalance = float(checkpoint_max_ls_imbalance)
        self._checkpoint_max_drawdown = float(checkpoint_max_drawdown)
        self._anti_flat_violation_evals = 0
        self._playback_candidate_dir = (
            Path(playback_candidate_dir).expanduser()
            if str(playback_candidate_dir).strip()
            else None
        )
        self._playback_top_n = max(0, int(playback_top_n))
        self._collect_playback_candidates = bool(collect_playback_candidates)
        self._playback_candidates: list[dict[str, object]] = []
        self.stopped_early = False
        self.stop_reason = ""

    def _maybe_record_playback_candidate(
        self,
        *,
        step: int,
        mean_reward: float,
        checkpoint_gate: str,
        trade_rate_1k: float | None,
        flat_ratio: float | None,
        ls_imbalance: float | None,
        max_drawdown: float | None,
    ) -> None:
        if (
            not self._collect_playback_candidates
            or self._playback_candidate_dir is None
            or self._playback_top_n <= 0
        ):
            return
        current = {
            "step": int(step),
            "eval_mean_reward": float(mean_reward),
            "checkpoint_gate": str(checkpoint_gate),
            "eval_trade_rate_1k": None if trade_rate_1k is None else float(trade_rate_1k),
            "eval_flat_ratio": None if flat_ratio is None else float(flat_ratio),
            "eval_ls_imbalance": None if ls_imbalance is None else float(ls_imbalance),
            "eval_max_drawdown": None if max_drawdown is None else float(max_drawdown),
        }
        existing = next(
            (
                row
                for row in self._playback_candidates
                if int(row.get("step", -1)) == int(step)
            ),
            None,
        )
        if existing is not None:
            existing.update(current)
            return
        should_add = len(self._playback_candidates) < self._playback_top_n
        if not should_add:
            worst = min(
                self._playback_candidates,
                key=lambda row: float(row.get("eval_mean_reward", float("-inf"))),
            )
            should_add = float(mean_reward) > float(worst.get("eval_mean_reward", float("-inf")))
            if should_add:
                old_path = str(worst.get("path") or "").strip()
                if old_path:
                    Path(old_path).unlink(missing_ok=True)
                self._playback_candidates.remove(worst)
        if not should_add:
            return
        self._playback_candidate_dir.mkdir(parents=True, exist_ok=True)
        candidate_path = self._playback_candidate_dir / f"candidate_step_{int(step):08d}.zip"
        self.model.save(str(candidate_path))
        current["path"] = str(candidate_path)
        self._playback_candidates.append(current)
        self._playback_candidates.sort(
            key=lambda row: (
                float(row.get("eval_mean_reward", float("-inf"))),
                -int(row.get("step", 0)),
            ),
            reverse=True,
        )
        while len(self._playback_candidates) > self._playback_top_n:
            dropped = self._playback_candidates.pop()
            dropped_path = str(dropped.get("path") or "").strip()
            if dropped_path:
                Path(dropped_path).unlink(missing_ok=True)

    def get_playback_candidates(self) -> list[dict[str, object]]:
        return [dict(row) for row in self._playback_candidates]

    def _on_step(self) -> bool:
        continue_training = True

        if self.eval_freq <= 0 or self.n_calls % self.eval_freq != 0:
            return True

        if self.model.get_vec_normalize_env() is not None:
            try:
                sync_envs_normalization(self.training_env, self.eval_env)
            except AttributeError as e:
                raise AssertionError(
                    "Training and eval env are not wrapped the same way, "
                    "see "
                    "https://stable-baselines3.readthedocs.io/en/master/guide/"
                    "callbacks.html#evalcallback "
                    "and warning above."
                ) from e

        self._is_success_buffer = []

        episode_rewards, episode_lengths = evaluate_policy(
            self.model,
            self.eval_env,
            n_eval_episodes=self.n_eval_episodes,
            render=self.render,
            deterministic=self.deterministic,
            return_episode_rewards=True,
            warn=self.warn,
            callback=self._log_success_callback,
        )

        if self.log_path is not None:
            assert isinstance(episode_rewards, list)
            assert isinstance(episode_lengths, list)
            self.evaluations_timesteps.append(self.num_timesteps)
            self.evaluations_results.append(episode_rewards)
            self.evaluations_length.append(episode_lengths)

            kwargs = {}
            if len(self._is_success_buffer) > 0:
                self.evaluations_successes.append(self._is_success_buffer)
                kwargs = dict(successes=self.evaluations_successes)

            np.savez(
                self.log_path,
                timesteps=self.evaluations_timesteps,
                results=self.evaluations_results,
                ep_lengths=self.evaluations_length,
                **kwargs,
            )

        step = int(self.num_timesteps)
        mean_reward = float(np.mean(episode_rewards))
        std_reward = float(np.std(episode_rewards))
        mean_ep_length = float(np.mean(episode_lengths))
        self.last_mean_reward = mean_reward

        if self.verbose >= 1:
            print(
                f"Eval num_timesteps={self.num_timesteps}, "
                f"episode_reward={mean_reward:.2f} +/- {std_reward:.2f}"
            )
            print(
                f"Episode length: {mean_ep_length:.2f} "
                f"+/- {float(np.std(episode_lengths)):.2f}"
            )

        self.logger.record("eval/mean_reward", mean_reward)
        self.logger.record("eval/mean_ep_length", mean_ep_length)

        if len(self._is_success_buffer) > 0:
            success_rate = float(np.mean(self._is_success_buffer))
            if self.verbose >= 1:
                print(f"Success rate: {100 * success_rate:.2f}%")
            self.logger.record("eval/success_rate", success_rate)

        self.logger.record("time/total_timesteps", self.num_timesteps, exclude="tensorboard")
        self.logger.dump(self.num_timesteps)

        self._write_metric(step, "eval/mean_reward", mean_reward)
        allow_checkpoint_updates = True
        anti_flat_violation = False
        anti_flat_reason = ""
        checkpoint_reasons: list[str] = []
        if self._activity_profiler is not None:
            profile = self._activity_profiler(self.model)
            trade_rate_1k = float(profile.get("trade_rate_1k", 0.0))
            flat_ratio = float(profile.get("flat_ratio", 1.0))
            ls_imbalance = float(profile.get("ls_imbalance", 0.0))
            max_drawdown = float(profile.get("max_drawdown", 0.0))
            raw_action_abs_mean = float(profile.get("raw_action_abs_mean", 0.0))
            raw_action_flatish_ratio = float(
                profile.get("raw_action_flatish_ratio", 1.0)
            )
            raw_action_over_005_ratio = float(
                profile.get("raw_action_over_005_ratio", 0.0)
            )
            raw_action_over_010_ratio = float(
                profile.get("raw_action_over_010_ratio", 0.0)
            )
            raw_action_over_025_ratio = float(
                profile.get("raw_action_over_025_ratio", 0.0)
            )
            raw_entry_hit_ratio = float(profile.get("raw_entry_hit_ratio", 0.0))
            self._write_metric(step, "eval/trade_rate_1k", trade_rate_1k)
            self._write_metric(step, "eval/flat_ratio", flat_ratio)
            self._write_metric(step, "eval/ls_imbalance", ls_imbalance)
            self._write_metric(step, "eval/max_drawdown", max_drawdown)
            self._write_metric(step, "eval/raw_action_abs_mean", raw_action_abs_mean)
            self._write_metric(
                step,
                "eval/raw_action_flatish_ratio",
                raw_action_flatish_ratio,
            )
            self._write_metric(
                step,
                "eval/raw_action_over_005_ratio",
                raw_action_over_005_ratio,
            )
            self._write_metric(
                step,
                "eval/raw_action_over_010_ratio",
                raw_action_over_010_ratio,
            )
            self._write_metric(
                step,
                "eval/raw_action_over_025_ratio",
                raw_action_over_025_ratio,
            )
            self._write_metric(step, "eval/raw_entry_hit_ratio", raw_entry_hit_ratio)
            if trade_rate_1k < self._checkpoint_min_trade_rate:
                checkpoint_reasons.append(
                    f"trade_rate({trade_rate_1k:.3f}<{self._checkpoint_min_trade_rate:.3f})"
                )
            if (
                self._checkpoint_max_trade_rate > 0.0
                and trade_rate_1k > self._checkpoint_max_trade_rate
            ):
                checkpoint_reasons.append(
                    f"trade_rate({trade_rate_1k:.3f}>{self._checkpoint_max_trade_rate:.3f})"
                )
            if flat_ratio > self._checkpoint_max_flat_ratio:
                checkpoint_reasons.append(
                    f"flat_ratio({flat_ratio:.3f}>{self._checkpoint_max_flat_ratio:.3f})"
                )
            if ls_imbalance > self._checkpoint_max_ls_imbalance:
                checkpoint_reasons.append(
                    f"ls_imbalance({ls_imbalance:.3f}>{self._checkpoint_max_ls_imbalance:.3f})"
                )
            if max_drawdown > self._checkpoint_max_drawdown:
                checkpoint_reasons.append(
                    f"max_dd({max_drawdown:.3f}>{self._checkpoint_max_drawdown:.3f})"
                )
            if self._anti_flat_enabled and step >= self._anti_flat_warmup_steps:
                reasons = []
                if trade_rate_1k < self._anti_flat_min_trade_rate:
                    reasons.append(
                        f"trade_rate({trade_rate_1k:.3f}<{self._anti_flat_min_trade_rate:.3f})"
                    )
                if flat_ratio > self._anti_flat_max_flat_ratio:
                    reasons.append(
                        f"flat_ratio({flat_ratio:.3f}>{self._anti_flat_max_flat_ratio:.3f})"
                    )
                if ls_imbalance > self._anti_flat_max_ls_imbalance:
                    reasons.append(
                        f"ls_imbalance({ls_imbalance:.3f}>{self._anti_flat_max_ls_imbalance:.3f})"
                    )
                anti_flat_violation = bool(reasons)
                anti_flat_reason = " ".join(reasons)
                if anti_flat_violation:
                    self._anti_flat_violation_evals += 1
                else:
                    self._anti_flat_violation_evals = 0
        allow_checkpoint_updates = not checkpoint_reasons
        if not allow_checkpoint_updates and self.verbose >= 1:
            print(
                "Best checkpoint skipped:",
                f"step={step}",
                " ".join(checkpoint_reasons),
            )
        checkpoint_gate = (
            "pass"
            if allow_checkpoint_updates
            else f"fail: {', '.join(checkpoint_reasons)}"
        )
        if allow_checkpoint_updates and not anti_flat_violation:
            self._maybe_record_playback_candidate(
                step=step,
                mean_reward=mean_reward,
                checkpoint_gate=checkpoint_gate,
                trade_rate_1k=(
                    trade_rate_1k if self._activity_profiler is not None else None
                ),
                flat_ratio=flat_ratio if self._activity_profiler is not None else None,
                ls_imbalance=(
                    ls_imbalance if self._activity_profiler is not None else None
                ),
                max_drawdown=(
                    max_drawdown if self._activity_profiler is not None else None
                ),
            )
        if (
            allow_checkpoint_updates
            and (not anti_flat_violation)
            and mean_reward > self.best_mean_reward
        ):
            if self.verbose >= 1:
                print("New best mean reward!")
            if self.best_model_save_path is not None:
                self.model.save(os.path.join(self.best_model_save_path, "best_model"))
            self.best_mean_reward = mean_reward
            if self.callback_on_new_best is not None:
                continue_training = self.callback_on_new_best.on_step()

        if self.callback is not None:
            continue_training = continue_training and self._on_event()

        if not continue_training:
            return False
        if (
            self._anti_flat_enabled
            and step >= self._anti_flat_warmup_steps
            and self._anti_flat_violation_evals >= self._anti_flat_patience_evals
        ):
            self.stopped_early = True
            self.stop_reason = anti_flat_reason or "activity constraints violated"
            print(
                "Anti-flat stop:",
                f"step={step}",
                f"violations={self._anti_flat_violation_evals}",
                self.stop_reason,
            )
            return False
        if not self._early_stop_enabled or step < self._early_stop_warmup_steps:
            return True
        if not allow_checkpoint_updates or anti_flat_violation:
            return True
        if self._best_eval_reward == float("-inf"):
            self._best_eval_reward = mean_reward
            self._no_improvement_evals = 1
            remaining = max(0, self._early_stop_patience_evals - self._no_improvement_evals)
            self._write_metric(step, "early_stop_patience_left", float(remaining))
            if self.verbose >= 1:
                print(
                    "Early stop baseline established:",
                    f"step={step}",
                    f"eval_mean_reward={mean_reward:.6g}",
                    f"patience_left={remaining}",
                )
            return True
        if mean_reward > self._best_eval_reward + self._early_stop_min_delta:
            self._best_eval_reward = mean_reward
            self._no_improvement_evals = 0
        else:
            self._no_improvement_evals += 1
        remaining = max(0, self._early_stop_patience_evals - self._no_improvement_evals)
        self._write_metric(step, "early_stop_patience_left", float(remaining))
        if self._no_improvement_evals >= self._early_stop_patience_evals:
            self.stopped_early = True
            self.stop_reason = "eval reward plateau"
            print(
                "Early stop:",
                f"step={step}",
                f"eval_mean_reward={mean_reward:.6g}",
                f"best_eval_reward={self._best_eval_reward:.6g}",
                f"patience={self._early_stop_patience_evals}",
            )
            return False
        return True


def _train_model(
    *,
    env: DummyVecEnv,
    learning_rate: float,
    n_steps: int,
    batch_size: int,
    gamma: float,
    ent_coef: float,
    gae_lambda: float,
    clip_range: float,
    target_kl: float | None,
    vf_coef: float,
    n_epochs: int,
    total_steps: int,
    window_size: int,
    feature_dim: int,
    device: str,
    policy_log_std_init: float,
    verbose: int = 1,
) -> PPO:
    policy_kwargs = {
        "features_extractor_class": WindowCnnExtractor,
        "features_extractor_kwargs": {
            "window_size": window_size,
            "feature_dim": feature_dim,
        },
        "log_std_init": float(policy_log_std_init),
    }
    model = PPO(
        "MlpPolicy",
        env,
        verbose=verbose,
        policy_kwargs=policy_kwargs,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
        gamma=gamma,
        ent_coef=ent_coef,
        gae_lambda=gae_lambda,
        clip_range=clip_range,
        target_kl=target_kl,
        vf_coef=vf_coef,
        n_epochs=n_epochs,
        device=device,
    )
    print(f"Resolved device: {model.device}")
    return model


def _clone_config(config: TradingConfig, **overrides) -> TradingConfig:
    payload = dict(config.__dict__)
    payload.update(overrides)
    return TradingConfig(**payload)


def _extract_data_context(csv_path: str | Path) -> dict[str, int | str]:
    path = Path(csv_path).expanduser()
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    if not meta_path.exists():
        return {}
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    details = payload.get("details", {})
    if not isinstance(details, dict):
        return {}
    out: dict[str, int | str] = {}
    symbol = details.get("symbol_id")
    timeframe = details.get("timeframe")
    if symbol is not None:
        try:
            out["symbol_id"] = int(symbol)
        except (TypeError, ValueError):
            pass
    if timeframe is not None:
        out["timeframe"] = str(timeframe).strip().upper()
    return out


def _resolve_replay_policy(
    *,
    frame,
    action_gate_specs: list[dict[str, float | str | None]],
    threshold_bump_specs: list[dict[str, float | str | None]],
    action_gate_mode: str,
    action_scale: float,
    long_threshold: float | None,
    short_threshold: float | None,
    long_exit_threshold: float | None,
    short_exit_threshold: float | None,
) -> dict[str, object]:
    if frame is None or len(frame) <= 0:
        return {
            "action_gate_mask": np.ones(0, dtype=bool),
            "threshold_bumps": np.zeros(0, dtype=np.float32),
            "action_gate_mode": str(action_gate_mode),
            "action_scale": max(float(action_scale), 0.0),
            "long_threshold": long_threshold,
            "short_threshold": short_threshold,
            "long_exit_threshold": long_exit_threshold,
            "short_exit_threshold": short_exit_threshold,
            "enabled": False,
        }
    action_gate_mask = (
        _build_gate_mask(frame, action_gate_specs) if action_gate_specs else np.ones(len(frame), dtype=bool)
    )
    threshold_bumps = (
        _build_threshold_bump_array(frame, threshold_bump_specs)
        if threshold_bump_specs
        else np.zeros(len(frame), dtype=np.float32)
    )
    enabled = long_threshold is not None and short_threshold is not None
    return {
        "action_gate_mask": action_gate_mask.astype(bool, copy=False),
        "threshold_bumps": threshold_bumps.astype(np.float32, copy=False),
        "action_gate_mode": str(action_gate_mode),
        "action_scale": max(float(action_scale), 0.0),
        "long_threshold": long_threshold,
        "short_threshold": short_threshold,
        "long_exit_threshold": long_exit_threshold,
        "short_exit_threshold": short_exit_threshold,
        "enabled": enabled,
    }


def _build_playback_bundle(
    *,
    model: PPO,
    features: np.ndarray,
    closes: np.ndarray,
    timestamps,
    config: TradingConfig,
    replay_policy: dict[str, object] | None = None,
) -> PlaybackBundle:
    replay_policy = replay_policy or {}
    return PlaybackBundle(
        features=features,
        closes=closes,
        timestamps=list(timestamps),
        config=config,
        model=model,
        action_gate_mask=replay_policy.get("action_gate_mask"),
        threshold_bumps=replay_policy.get("threshold_bumps"),
        action_gate_mode=str(replay_policy.get("action_gate_mode", "force_flat")),
        action_scale=float(replay_policy.get("action_scale", 1.0)),
        long_threshold=replay_policy.get("long_threshold"),
        short_threshold=replay_policy.get("short_threshold"),
        long_exit_threshold=replay_policy.get("long_exit_threshold"),
        short_exit_threshold=replay_policy.get("short_exit_threshold"),
    )


def _aggregate_playback_results(results: list[PlaybackResult]) -> dict[str, float]:
    if not results:
        return {
            "segments": 0.0,
            "pass_count": 0.0,
            "pass_rate": 0.0,
            "avg_return": 0.0,
            "avg_sharpe": 0.0,
            "avg_max_drawdown": 0.0,
            "worst_max_drawdown": 0.0,
            "avg_trade_rate_1k": 0.0,
        }

    returns = np.asarray([result.total_return for result in results], dtype=np.float64)
    sharpes = np.asarray([result.sharpe for result in results], dtype=np.float64)
    drawdowns = np.asarray([result.max_drawdown for result in results], dtype=np.float64)
    trade_rates = np.asarray([result.trade_rate_1k for result in results], dtype=np.float64)
    pass_count = sum(1 for result in results if not result.gate_reasons)
    return {
        "segments": float(len(results)),
        "pass_count": float(pass_count),
        "pass_rate": float(pass_count / len(results)),
        "avg_return": float(np.mean(returns)),
        "avg_sharpe": float(np.mean(sharpes)),
        "avg_max_drawdown": float(np.mean(drawdowns)),
        "worst_max_drawdown": float(np.max(drawdowns)),
        "avg_trade_rate_1k": float(np.mean(trade_rates)),
    }


def _playback_result_to_dict(result: PlaybackResult) -> dict[str, object]:
    return {
        "processed_steps": int(result.processed_steps),
        "trades": int(result.trades),
        "total_return": float(result.total_return),
        "sharpe": float(result.sharpe),
        "max_drawdown": float(result.max_drawdown),
        "trade_rate_1k": float(result.trade_rate_1k),
        "flat_ratio": float(result.flat_ratio),
        "ls_imbalance": float(result.ls_imbalance),
        "gate_pass": not bool(result.gate_reasons),
        "gate_reasons": list(result.gate_reasons),
    }


def _rank_playback_candidate(entry: dict[str, object]) -> tuple:
    playback = entry.get("playback", {})
    if not isinstance(playback, dict):
        playback = {}
    gate_pass = bool(playback.get("gate_pass", False))
    total_return = float(playback.get("total_return", float("-inf")))
    sharpe = float(playback.get("sharpe", float("-inf")))
    max_drawdown = float(playback.get("max_drawdown", float("inf")))
    eval_mean_reward = float(entry.get("eval_mean_reward", float("-inf")))
    return (1 if gate_pass else 0, total_return, sharpe, -max_drawdown, eval_mean_reward)


def _evaluate_playback_candidates(
    candidates: list[dict[str, object]],
    *,
    features: np.ndarray,
    closes: np.ndarray,
    timestamps,
    config: TradingConfig,
    device: str,
    replay_policy: dict[str, object] | None = None,
) -> dict[str, object]:
    evaluated: list[dict[str, object]] = []
    for candidate in candidates:
        model_path = str(candidate.get("path") or "").strip()
        if not model_path:
            continue
        try:
            model = PPO.load(model_path, device=device)
            bundle = _build_playback_bundle(
                model=model,
                features=features,
                closes=closes,
                timestamps=timestamps,
                config=config,
                replay_policy=replay_policy,
            )
            playback = run_playback(
                bundle,
                start_index=0,
                max_steps=0,
                quiet=True,
            )
            row = dict(candidate)
            row["playback"] = _playback_result_to_dict(playback)
            evaluated.append(row)
        except Exception as exc:
            row = dict(candidate)
            row["playback_error"] = str(exc)
            evaluated.append(row)
    selected = max(evaluated, key=_rank_playback_candidate) if evaluated else None
    return {
        "candidate_count": int(len(evaluated)),
        "candidates": evaluated,
        "selected": selected,
    }


def _profile_policy_activity(
    model: PPO,
    features: np.ndarray,
    closes: np.ndarray,
    timestamps,
    config: TradingConfig,
    *,
    max_steps: int = 0,
    replay_policy: dict[str, object] | None = None,
) -> dict[str, float]:
    bundle = _build_playback_bundle(
        model=model,
        features=features,
        closes=closes,
        timestamps=timestamps,
        config=config,
        replay_policy=replay_policy,
    )
    step_limit = len(bundle.features) - 1
    if max_steps > 0:
        step_limit = min(step_limit, int(max_steps))
    raw_actions: list[float] = []
    raw_entry_hits = 0
    raw_long_entry_hits = 0
    raw_short_entry_hits = 0
    state = {"position": 0.0, "equity": 1.0, "peak_equity": 1.0}
    for idx in range(max(0, int(step_limit))):
        obs = build_window_observation(
            bundle.features,
            idx,
            position=float(state["position"]),
            max_position=bundle.config.max_position,
            window_size=getattr(bundle.config, "window_size", 1),
        )
        action, _ = bundle.model.predict(obs, deterministic=True)
        raw_action = decode_policy_action(action, config=bundle.config)
        raw_action *= max(float(bundle.action_scale), 0.0)
        raw_actions.append(raw_action)
        threshold_bump = (
            float(bundle.threshold_bumps[idx])
            if bundle.threshold_bumps is not None and len(bundle.threshold_bumps) > idx
            else 0.0
        )
        long_threshold = (
            float(bundle.long_threshold) + threshold_bump if bundle.long_threshold is not None else None
        )
        short_threshold = (
            float(bundle.short_threshold) - threshold_bump if bundle.short_threshold is not None else None
        )
        if long_threshold is not None and raw_action >= long_threshold:
            raw_entry_hits += 1
            raw_long_entry_hits += 1
        elif short_threshold is not None and raw_action <= short_threshold:
            raw_entry_hits += 1
            raw_short_entry_hits += 1

        gate_enabled = (
            bool(bundle.action_gate_mask[idx])
            if bundle.action_gate_mask is not None and len(bundle.action_gate_mask) > idx
            else True
        )
        target_raw = raw_action
        if _policy_enabled(bundle):
            target_raw = _apply_policy_envelope(
                raw_action,
                current_position=float(state["position"]),
                gate_enabled=gate_enabled,
                action_gate_mode=str(bundle.action_gate_mode),
                long_threshold=float(bundle.long_threshold) + threshold_bump,
                short_threshold=float(bundle.short_threshold) - threshold_bump,
                long_exit_threshold=float(bundle.long_exit_threshold),
                short_exit_threshold=float(bundle.short_exit_threshold),
            )
        target_position, _ = apply_risk_engine(
            target_raw,
            current_position=float(state["position"]),
            config=bundle.config,
            closes=bundle.closes,
            idx=idx,
            equity=float(state["equity"]),
            peak_equity=float(state["peak_equity"]),
        )
        transition = simulate_step_transition(
            current_position=float(state["position"]),
            target_position=target_position,
            closes=bundle.closes,
            idx=idx,
            equity=float(state["equity"]),
            peak_equity=float(state["peak_equity"]),
            config=bundle.config,
        )
        state["position"] = float(target_position)
        state["equity"] = float(transition["equity"])
        state["peak_equity"] = float(transition["peak_equity"])

    raw_action_array = np.asarray(raw_actions, dtype=np.float64)
    result = run_playback(
        bundle,
        start_index=0,
        max_steps=max_steps,
        quiet=True,
    )
    metrics = {
        "trades": float(result.trades),
        "trade_rate_1k": float(result.trade_rate_1k),
        "flat_ratio": float(result.flat_ratio),
        "long_ratio": float(result.long_ratio),
        "short_ratio": float(result.short_ratio),
        "ls_imbalance": float(result.ls_imbalance),
        "max_drawdown": float(result.max_drawdown),
        "sharpe": float(result.sharpe),
        "total_return": float(result.total_return),
    }
    if len(raw_action_array) == 0:
        metrics.update(
            {
                "raw_action_abs_mean": 0.0,
                "raw_action_flatish_ratio": 1.0,
                "raw_action_over_005_ratio": 0.0,
                "raw_action_over_010_ratio": 0.0,
                "raw_action_over_025_ratio": 0.0,
                "raw_entry_hit_ratio": 0.0,
                "raw_long_entry_hit_ratio": 0.0,
                "raw_short_entry_hit_ratio": 0.0,
            }
        )
        return metrics
    raw_abs = np.abs(raw_action_array)
    metrics.update(
        {
            "raw_action_abs_mean": float(np.mean(raw_abs)),
            "raw_action_flatish_ratio": float(np.mean(raw_abs <= 0.05)),
            "raw_action_over_005_ratio": float(np.mean(raw_abs >= 0.05)),
            "raw_action_over_010_ratio": float(np.mean(raw_abs >= 0.10)),
            "raw_action_over_025_ratio": float(np.mean(raw_abs >= 0.25)),
            "raw_entry_hit_ratio": float(raw_entry_hits / len(raw_action_array)),
            "raw_long_entry_hit_ratio": float(raw_long_entry_hits / len(raw_action_array)),
            "raw_short_entry_hit_ratio": float(raw_short_entry_hits / len(raw_action_array)),
        }
    )
    return metrics


def _profile_walk_forward(
    model: PPO,
    features: np.ndarray,
    closes: np.ndarray,
    timestamps,
    config: TradingConfig,
    *,
    segment_steps: int,
    segments: int,
    stride: int,
    replay_policy: dict[str, object] | None = None,
) -> dict[str, float]:
    if segment_steps <= 0 or segments <= 0 or stride <= 0:
        return _aggregate_playback_results([])

    bundle = _build_playback_bundle(
        model=model,
        features=features,
        closes=closes,
        timestamps=timestamps,
        config=config,
        replay_policy=replay_policy,
    )
    results: list[PlaybackResult] = []
    for segment_idx in range(segments):
        start_index = segment_idx * stride
        try:
            result = run_playback(
                bundle,
                start_index=start_index,
                max_steps=segment_steps,
                quiet=True,
            )
        except ValueError:
            break
        results.append(result)
    return _aggregate_playback_results(results)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        # Ensure progress logs are flushed promptly when running under QProcess pipes.
        sys.stdout.reconfigure(line_buffering=True)
    signal.signal(signal.SIGTERM, _handle_termination_signal)
    parser = argparse.ArgumentParser(description="Train PPO on forex history with an MLP policy.")
    parser.add_argument("--data", required=True, help="Path to raw history CSV.")
    parser.add_argument(
        "--feature-subset-json",
        default="",
        help="Optional JSON file containing a list of feature names to keep for training.",
    )
    parser.add_argument("--total-steps", type=int, default=300_000, help="Total PPO timesteps.")
    parser.add_argument("--learning-rate", type=float, default=1e-4, help="PPO learning rate.")
    parser.add_argument("--gamma", type=float, default=0.995, help="PPO discount factor.")
    parser.add_argument("--n-steps", type=int, default=4096, help="PPO rollout steps per update.")
    parser.add_argument("--batch-size", type=int, default=256, help="PPO minibatch size.")
    parser.add_argument("--ent-coef", type=float, default=5e-4, help="Entropy coefficient.")
    parser.add_argument("--gae-lambda", type=float, default=0.98, help="PPO GAE lambda.")
    parser.add_argument("--clip-range", type=float, default=0.15, help="PPO clip range.")
    parser.add_argument(
        "--target-kl",
        type=float,
        default=0.02,
        help="Target KL for PPO inner-update early stopping (0 disables).",
    )
    parser.add_argument(
        "--policy-log-std-init",
        type=float,
        default=0.0,
        help="Initial log std for the PPO Gaussian action distribution.",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "mps", "cuda"],
        default="auto",
        help="Training device selection for Stable-Baselines3.",
    )
    parser.add_argument("--seed", type=int, default=0, help="Random seed for reproducible training runs.")
    parser.add_argument(
        "--curriculum-enabled",
        action="store_true",
        help="Run an initial constrained action-space stage before switching to the target config.",
    )
    parser.add_argument(
        "--curriculum-steps",
        type=int,
        default=25_000,
        help="Timesteps allocated to the initial curriculum stage.",
    )
    parser.add_argument(
        "--curriculum-max-position",
        type=float,
        default=0.2,
        help="Max position used during the curriculum stage.",
    )
    parser.add_argument(
        "--curriculum-position-step",
        type=float,
        default=0.1,
        help="Discrete position step used during the curriculum stage.",
    )
    parser.add_argument(
        "--curriculum-min-position-change",
        type=float,
        default=0.05,
        help="Minimum position change used during the curriculum stage.",
    )
    parser.add_argument(
        "--warm-start-enabled",
        action="store_true",
        help="Pretrain the actor with heuristic action labels before PPO learning starts.",
    )
    parser.add_argument(
        "--warm-start-labeler",
        choices=("momentum", "momentum_cont", "breakout_sym", "breakout_cont"),
        default="momentum",
        help="Heuristic labeler used to generate supervised warm-start actions.",
    )
    parser.add_argument(
        "--warm-start-epochs",
        type=int,
        default=5,
        help="Supervised epochs used for heuristic actor warm-start.",
    )
    parser.add_argument(
        "--warm-start-batch-size",
        type=int,
        default=512,
        help="Batch size used during heuristic actor warm-start.",
    )
    parser.add_argument(
        "--warm-start-samples",
        type=int,
        default=20_000,
        help="Maximum number of heuristic warm-start samples.",
    )
    parser.add_argument(
        "--warm-start-lookback-short",
        type=int,
        default=12,
        help="Short lookback used by the heuristic warm-start labeler.",
    )
    parser.add_argument(
        "--warm-start-lookback-long",
        type=int,
        default=48,
        help="Long lookback used by the heuristic warm-start labeler.",
    )
    parser.add_argument(
        "--warm-start-threshold",
        type=float,
        default=0.0005,
        help="Momentum threshold used by the heuristic warm-start labeler.",
    )
    parser.add_argument(
        "--warm-start-action-scale",
        type=float,
        default=1.0,
        help="Multiplier applied to heuristic warm-start action intensity.",
    )
    parser.add_argument(
        "--warm-start-loss-scale",
        type=float,
        default=1.0,
        help="Multiplier applied to the supervised warm-start loss.",
    )
    parser.add_argument(
        "--warm-start-long-weight",
        type=float,
        default=1.0,
        help="Supervised loss weight applied to long warm-start labels.",
    )
    parser.add_argument(
        "--warm-start-short-weight",
        type=float,
        default=1.25,
        help="Supervised loss weight applied to short warm-start labels.",
    )
    parser.add_argument(
        "--warm-start-flat-weight",
        type=float,
        default=0.5,
        help="Supervised loss weight applied to flat warm-start labels.",
    )
    parser.add_argument(
        "--imitation-enabled",
        action="store_true",
        help=(
            "Continue applying warm-start imitation loss during the first "
            "training updates."
        ),
    )
    parser.add_argument(
        "--imitation-steps",
        type=int,
        default=20_000,
        help=(
            "Maximum PPO timesteps that receive additional imitation "
            "updates after each rollout."
        ),
    )
    parser.add_argument(
        "--imitation-epochs-per-rollout",
        type=int,
        default=1,
        help=(
            "Supervised epochs to run after each rollout while imitation "
            "is active."
        ),
    )
    parser.add_argument(
        "--imitation-batch-size",
        type=int,
        default=512,
        help="Batch size used by the rollout-time imitation updates.",
    )
    parser.add_argument(
        "--imitation-loss-scale",
        type=float,
        default=1.0,
        help="Multiplier applied to the rollout-time imitation loss.",
    )
    parser.add_argument(
        "--vf-coef",
        type=float,
        default=0.7,
        help="PPO value function coefficient.",
    )
    parser.add_argument(
        "--n-epochs",
        type=int,
        default=10,
        help="PPO epochs per update.",
    )
    parser.add_argument(
        "--episode-length",
        type=int,
        default=4096,
        help="Episode length in bars.",
    )
    parser.add_argument(
        "--eval-split",
        type=float,
        default=0.2,
        help="Eval split (fraction from tail).",
    )
    parser.add_argument(
        "--eval-freq",
        type=int,
        default=10_000,
        help="Eval frequency in timesteps.",
    )
    parser.add_argument(
        "--eval-episodes",
        type=int,
        default=8,
        help="Eval episodes per evaluation.",
    )
    parser.add_argument(
        "--transaction-cost-bps",
        type=float,
        default=1.0,
        help="Transaction cost in bps.",
    )
    parser.add_argument(
        "--slippage-bps",
        type=float,
        default=0.5,
        help="Slippage in bps.",
    )
    parser.add_argument(
        "--holding-cost-bps",
        type=float,
        default=0.1,
        help="Holding cost in bps per step.",
    )
    parser.add_argument(
        "--no-random-start",
        action="store_true",
        help="Disable random episode starts.",
    )
    parser.add_argument(
        "--start-mode",
        choices=["random", "first", "weekly_open"],
        default="",
        help="Episode reset mode. Empty keeps backward-compatible random_start behavior.",
    )
    parser.add_argument("--min-position-change", type=float, default=0.2, help="Minimum position change.")
    parser.add_argument(
        "--discretize-actions",
        action="store_true",
        help="Snap actions to discrete positions.",
    )
    parser.add_argument(
        "--native-discrete-actions",
        action="store_true",
        help="Use a true Discrete action space instead of continuous actions snapped post-hoc.",
    )
    parser.add_argument(
        "--discrete-positions",
        default="-1,0,1",
        help="Comma-separated discrete positions (e.g. -1,0,1).",
    )
    parser.add_argument(
        "--max-position",
        type=float,
        default=1.0,
        help="Maximum absolute position size.",
    )
    parser.add_argument(
        "--position-step",
        type=float,
        default=0.1,
        help="Position step size (0 disables).",
    )
    parser.add_argument(
        "--reward-horizon",
        type=int,
        default=4,
        help="Reward uses return over the next N bars.",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=16,
        help=(
            "Observation window size. Uses the latest N bars of features "
            "flattened into one vector."
        ),
    )
    parser.add_argument(
        "--reward-scale",
        type=float,
        default=1.0,
        help="Scale reward by this factor.",
    )
    parser.add_argument(
        "--reward-clip",
        type=float,
        default=0.02,
        help="Clip reward to +/- value (0 disables).",
    )
    parser.add_argument(
        "--reward-mode",
        choices=(
            "linear",
            "log_return",
            "risk_adjusted",
            "terminal_horizon",
            "path_penalty",
            "tp_sl_proxy",
        ),
        default="tp_sl_proxy",
        help=(
            "Reward definition: raw net return, log return, "
            "risk-adjusted log return, fixed-horizon terminal reward, "
            "path-penalty reward, or take-profit/stop-loss proxy reward."
        ),
    )
    parser.add_argument("--risk-aversion", type=float, default=0.5, help="Penalty for variance of PnL.")
    parser.add_argument(
        "--drawdown-penalty",
        type=float,
        default=2.0,
        help="Penalty applied when drawdown worsens: drawdown_penalty * drawdown_delta.",
    )
    parser.add_argument(
        "--downside-penalty",
        type=float,
        default=1.0,
        help="Penalty applied only in risk_adjusted mode: downside_penalty * min(0, net_return)^2.",
    )
    parser.add_argument(
        "--turnover-penalty",
        type=float,
        default=1e-4,
        help="Extra penalty applied to absolute position change to discourage excess turnover.",
    )
    parser.add_argument(
        "--exposure-penalty",
        type=float,
        default=1e-4,
        help="Penalty applied to absolute target exposure to discourage oversized persistent positions.",
    )
    parser.add_argument(
        "--flat-position-penalty",
        type=float,
        default=0.0,
        help="Penalty applied when the policy stays flat from one step to the next.",
    )
    parser.add_argument(
        "--flat-streak-penalty",
        type=float,
        default=0.0,
        help="Additional per-step penalty multiplied by consecutive flat-hold steps after the first.",
    )
    parser.add_argument(
        "--flat-position-threshold",
        type=float,
        default=1e-6,
        help="Absolute position threshold treated as flat for anti-flat reward shaping.",
    )
    parser.add_argument(
        "--path-vol-penalty",
        type=float,
        default=0.25,
        help="Path-penalty mode only: weight applied to path standard deviation.",
    )
    parser.add_argument(
        "--path-downside-penalty",
        type=float,
        default=0.25,
        help="Path-penalty mode only: weight applied to path downside semivariance.",
    )
    parser.add_argument(
        "--position-bias-penalty",
        type=float,
        default=0.0,
        help=(
            "Penalty applied to persistent long/short imbalance measured "
            "from an EMA of normalized position."
        ),
    )
    parser.add_argument(
        "--position-bias-threshold",
        type=float,
        default=0.2,
        help="EMA imbalance threshold tolerated before position-bias penalty starts applying.",
    )
    parser.add_argument(
        "--position-bias-ema-alpha",
        type=float,
        default=0.05,
        help="EMA smoothing factor used by the position-bias penalty.",
    )
    parser.add_argument(
        "--drawdown-governor-slope",
        type=float,
        default=4.0,
        help="Scales max position as max(floor, 1 - slope * drawdown). 0 disables.",
    )
    parser.add_argument(
        "--drawdown-governor-floor",
        type=float,
        default=0.25,
        help="Minimum scale used by drawdown governor.",
    )
    parser.add_argument(
        "--target-vol",
        type=float,
        default=0.005,
        help="Target realized volatility for volatility targeting (0 disables).",
    )
    parser.add_argument(
        "--vol-target-lookback",
        type=int,
        default=72,
        help="Lookback bars used to estimate realized volatility.",
    )
    parser.add_argument(
        "--vol-scale-floor",
        type=float,
        default=0.5,
        help="Minimum volatility targeting scale.",
    )
    parser.add_argument(
        "--vol-scale-cap",
        type=float,
        default=1.0,
        help="Maximum volatility targeting scale.",
    )
    parser.add_argument(
        "--early-stop-enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stop when eval reward plateaus.",
    )
    parser.add_argument(
        "--early-stop-warmup-steps",
        type=int,
        default=120_000,
        help="Do not early stop before this many timesteps.",
    )
    parser.add_argument(
        "--early-stop-patience-evals",
        type=int,
        default=6,
        help="Number of eval rounds without improvement before stopping.",
    )
    parser.add_argument(
        "--early-stop-min-delta",
        type=float,
        default=0.0005,
        help="Minimum eval reward improvement to reset patience.",
    )
    parser.add_argument(
        "--anti-flat-enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stop training early when eval activity repeatedly collapses into near-flat behavior.",
    )
    parser.add_argument(
        "--anti-flat-warmup-steps",
        type=int,
        default=120_000,
        help="Do not enforce anti-flat checks before this many timesteps.",
    )
    parser.add_argument(
        "--anti-flat-patience-evals",
        type=int,
        default=3,
        help="Number of violating eval rounds before anti-flat early stop triggers.",
    )
    parser.add_argument(
        "--eval-profile-steps",
        type=int,
        default=2500,
        help=(
            "Playback steps used to profile eval activity for checkpoint "
            "and anti-flat checks (0 uses full eval tail)."
        ),
    )
    parser.add_argument(
        "--checkpoint-min-trade-rate",
        type=float,
        default=5.0,
        help="Minimum trades per 1k bars required for a checkpoint to qualify.",
    )
    parser.add_argument(
        "--checkpoint-max-trade-rate",
        type=float,
        default=25.0,
        help="Maximum trades per 1k bars allowed for a checkpoint to qualify.",
    )
    parser.add_argument(
        "--checkpoint-max-flat-ratio",
        type=float,
        default=0.9,
        help="Maximum flat action ratio allowed for a checkpoint to qualify.",
    )
    parser.add_argument(
        "--checkpoint-max-ls-imbalance",
        type=float,
        default=0.35,
        help="Maximum |long-short| imbalance allowed for a checkpoint to qualify.",
    )
    parser.add_argument(
        "--checkpoint-max-drawdown",
        type=float,
        default=0.30,
        help="Maximum eval max drawdown allowed for a checkpoint to qualify.",
    )
    parser.add_argument(
        "--anti-flat-min-trade-rate",
        type=float,
        default=5.0,
        help="Minimum trades per 1k bars required to avoid anti-flat violation.",
    )
    parser.add_argument(
        "--anti-flat-max-flat-ratio",
        type=float,
        default=0.98,
        help="Maximum flat action ratio allowed before anti-flat violation.",
    )
    parser.add_argument(
        "--anti-flat-max-ls-imbalance",
        type=float,
        default=0.2,
        help="Maximum |long-short| ratio imbalance allowed before anti-flat violation.",
    )
    parser.add_argument(
        "--anti-flat-profile-steps",
        type=int,
        default=2500,
        help="Playback steps used to profile eval activity for anti-flat checks (0 uses full eval tail).",
    )
    parser.add_argument("--verbose", type=int, default=1, help="PPO verbosity level.")
    parser.add_argument("--metrics-log", default="", help="Optional CSV path to append metrics.")
    parser.add_argument("--metrics-log-every", type=int, default=1, help="Write metrics every N log entries.")
    parser.add_argument("--optuna-trials", type=int, default=0, help="Run Optuna hyperparameter search.")
    parser.add_argument("--optuna-steps", type=int, default=50_000, help="Timesteps per Optuna trial.")
    parser.add_argument("--optuna-train-best", action="store_true", help="Train final model with best params.")
    parser.add_argument(
        "--optuna-auto-select",
        action="store_true",
        help="Auto select top candidate trials and write top params JSON.",
    )
    parser.add_argument(
        "--optuna-select-mode",
        choices=["top_k", "top_percent"],
        default="top_k",
        help="Auto-select mode for candidate set.",
    )
    parser.add_argument("--optuna-top-k", type=int, default=5, help="Top K trials to keep.")
    parser.add_argument(
        "--optuna-top-percent",
        type=float,
        default=20.0,
        help="Top percentage of trials to keep (0-100).",
    )
    parser.add_argument(
        "--optuna-min-candidates",
        type=int,
        default=3,
        help="Minimum candidate trials to keep after filtering.",
    )
    parser.add_argument(
        "--optuna-replay-enabled",
        action="store_true",
        help="Replay selected top candidate params with longer training.",
    )
    parser.add_argument(
        "--optuna-replay-steps",
        type=int,
        default=200_000,
        help="Training timesteps used for each replay run.",
    )
    parser.add_argument(
        "--optuna-replay-seeds",
        type=int,
        default=3,
        help="Seeds per candidate for replay runs.",
    )
    parser.add_argument(
        "--optuna-replay-score-mode",
        choices=["reward_only", "risk_adjusted", "conservative", "walk_forward"],
        default="walk_forward",
        help="Scoring mode for replay candidate ranking.",
    )
    parser.add_argument(
        "--optuna-replay-walk-forward-segments",
        type=int,
        default=3,
        help="Walk-forward segments to evaluate per replay seed when score_mode=walk_forward.",
    )
    parser.add_argument(
        "--optuna-replay-walk-forward-steps",
        type=int,
        default=2500,
        help="Playback steps per walk-forward segment when score_mode=walk_forward.",
    )
    parser.add_argument(
        "--optuna-replay-walk-forward-stride",
        type=int,
        default=2500,
        help="Start-index stride between walk-forward segments when score_mode=walk_forward.",
    )
    parser.add_argument(
        "--optuna-replay-max-flat-ratio",
        type=float,
        default=0.98,
        help="Reject replay candidates whose average flat ratio exceeds this threshold.",
    )
    parser.add_argument(
        "--optuna-replay-max-ls-imbalance",
        type=float,
        default=0.2,
        help="Reject replay candidates whose average |long-short| ratio exceeds this threshold.",
    )
    parser.add_argument(
        "--optuna-replay-min-trade-rate",
        type=float,
        default=5.0,
        help="Reject replay candidates whose average trades per 1k bars is below this threshold.",
    )
    parser.add_argument("--optuna-out", default="", help="Optional JSON path for best Optuna params.")
    parser.add_argument(
        "--optuna-top-out",
        default="data/optuna/top_params.json",
        help="JSON path for selected top candidate params list.",
    )
    parser.add_argument(
        "--optuna-replay-out",
        default="data/optuna/replay_results.json",
        help="JSON path for replay summary results.",
    )
    parser.add_argument("--optuna-log", default="", help="Optional CSV path to log Optuna trials.")
    parser.add_argument(
        "--optuna-trials-csv",
        default="data/optuna/trials.csv",
        help="CSV path to save all Optuna trial values and parameters (empty disables).",
    )
    parser.add_argument("--model-out", default=DEFAULT_MODEL_PATH, help="Output model path.")
    parser.add_argument(
        "--session-filter",
        choices=("all", "monday_open", "london", "london_pre_ny", "ny", "overlap"),
        default="all",
        help="Optional session filter applied before train/eval split.",
    )
    parser.add_argument("--replay-action-gate", action="append", default=[], help="Optional replay execution gate feature:min:max.")
    parser.add_argument(
        "--replay-action-gate-mode",
        choices=("force_flat", "entry_only"),
        default="force_flat",
        help="How replay action gates affect open positions.",
    )
    parser.add_argument(
        "--replay-action-scale",
        type=float,
        default=1.0,
        help="Multiplier applied to raw policy actions before replay envelope logic.",
    )
    parser.add_argument(
        "--replay-threshold-bump",
        action="append",
        default=[],
        help="Optional replay regime threshold bump feature:min:max:bump.",
    )
    parser.add_argument("--replay-long-threshold", type=float, default=None, help="Optional replay long entry threshold.")
    parser.add_argument("--replay-short-threshold", type=float, default=None, help="Optional replay short entry threshold.")
    parser.add_argument("--replay-long-exit-threshold", type=float, default=None, help="Optional replay long exit threshold.")
    parser.add_argument("--replay-short-exit-threshold", type=float, default=None, help="Optional replay short exit threshold.")
    parser.add_argument(
        "--feature-scaler-out",
        default="",
        help="Optional JSON path to save feature scaler (default: model_out with .scaler.json).",
    )
    parser.add_argument(
        "--feature-profile",
        choices=(
            "raw53",
            "alpha4",
            "residual",
            "alpha8",
            "alpha8_residual",
            "alpha12",
            "alpha12_residual",
            "alpha16",
            "alpha16_residual",
            "alpha20",
            "alpha20_residual",
            "core20",
            "alpha4_from_core20",
            "alpha8_from_core20",
        ),
        default="alpha20_residual",
        help="Feature profile: raw, alpha layers, residual alpha+context, or core20-derived profiles.",
    )
    parser.add_argument(
        "--env-config-out",
        default="",
        help="Optional JSON path to save TradingConfig (default: model_out with .env.json).",
    )
    parser.add_argument(
        "--training-args-out",
        default="",
        help="Optional JSON path to save the resolved training launch arguments for this run.",
    )
    parser.add_argument(
        "--training-status-out",
        default="",
        help="Optional JSON path to save runtime completion status for this run.",
    )
    parser.add_argument("--resume", action="store_true", help="Resume training from existing model.")
    parser.add_argument(
        "--save-best-checkpoint",
        action="store_true",
        help="Save and export the best eval checkpoint instead of the final training weights.",
    )
    args = parser.parse_args()
    if args.total_steps < 1:
        raise ValueError("--total-steps must be >= 1.")
    if args.learning_rate <= 0.0:
        raise ValueError("--learning-rate must be > 0.")
    if not (0.0 < args.gamma <= 1.0):
        raise ValueError("--gamma must be in (0, 1].")
    if args.n_steps < 1:
        raise ValueError("--n-steps must be >= 1.")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be >= 1.")
    if args.batch_size > args.n_steps:
        raise ValueError("--batch-size cannot exceed --n-steps.")
    if args.ent_coef < 0.0:
        raise ValueError("--ent-coef must be >= 0.")
    if not (0.0 <= args.gae_lambda <= 1.0):
        raise ValueError("--gae-lambda must be in [0, 1].")
    if args.clip_range <= 0.0:
        raise ValueError("--clip-range must be > 0.")
    if args.target_kl < 0.0:
        raise ValueError("--target-kl must be >= 0 (0 disables target_kl early stopping).")
    if args.vf_coef < 0.0:
        raise ValueError("--vf-coef must be >= 0.")
    if args.n_epochs < 1:
        raise ValueError("--n-epochs must be >= 1.")
    if args.transaction_cost_bps < 0.0:
        raise ValueError("--transaction-cost-bps must be >= 0.")
    if args.slippage_bps < 0.0:
        raise ValueError("--slippage-bps must be >= 0.")
    if args.holding_cost_bps < 0.0:
        raise ValueError("--holding-cost-bps must be >= 0.")
    if args.min_position_change < 0.0:
        raise ValueError("--min-position-change must be >= 0.")
    if args.max_position < 0.0:
        raise ValueError("--max-position must be >= 0.")
    if args.position_step < 0.0:
        raise ValueError("--position-step must be >= 0.")
    if args.max_position == 0.0 and args.position_step > 0.0:
        raise ValueError("--position-step must be 0 when --max-position is 0.")
    if args.max_position > 0.0 and args.position_step > args.max_position:
        raise ValueError("--position-step cannot exceed --max-position.")
    if args.max_position == 0.0 and args.min_position_change > 0.0:
        raise ValueError("--min-position-change must be 0 when --max-position is 0.")
    if args.max_position > 0.0 and args.min_position_change > (2.0 * args.max_position):
        raise ValueError("--min-position-change is too large for current --max-position.")
    if args.episode_length < 1:
        raise ValueError("--episode-length must be >= 1.")
    if args.reward_horizon < 1:
        raise ValueError("--reward-horizon must be >= 1.")
    if args.window_size < 1:
        raise ValueError("--window-size must be >= 1.")
    if args.reward_scale < 0.0:
        raise ValueError("--reward-scale must be >= 0.")
    if args.reward_clip < 0.0:
        raise ValueError("--reward-clip must be >= 0.")
    if args.risk_aversion < 0.0:
        raise ValueError("--risk-aversion must be >= 0.")
    if args.drawdown_penalty < 0.0:
        raise ValueError("--drawdown-penalty must be >= 0.")
    if args.downside_penalty < 0.0:
        raise ValueError("--downside-penalty must be >= 0.")
    if args.turnover_penalty < 0.0:
        raise ValueError("--turnover-penalty must be >= 0.")
    if args.exposure_penalty < 0.0:
        raise ValueError("--exposure-penalty must be >= 0.")
    if args.flat_position_penalty < 0.0:
        raise ValueError("--flat-position-penalty must be >= 0.")
    if args.flat_streak_penalty < 0.0:
        raise ValueError("--flat-streak-penalty must be >= 0.")
    if args.flat_position_threshold < 0.0:
        raise ValueError("--flat-position-threshold must be >= 0.")
    if args.path_vol_penalty < 0.0:
        raise ValueError("--path-vol-penalty must be >= 0.")
    if args.path_downside_penalty < 0.0:
        raise ValueError("--path-downside-penalty must be >= 0.")
    if args.target_vol < 0.0:
        raise ValueError("--target-vol must be >= 0.")
    if args.vol_target_lookback < 2:
        raise ValueError("--vol-target-lookback must be >= 2.")
    if args.vol_scale_floor < 0.0:
        raise ValueError("--vol-scale-floor must be >= 0.")
    if args.vol_scale_cap < args.vol_scale_floor:
        raise ValueError("--vol-scale-cap must be >= --vol-scale-floor.")
    if args.drawdown_governor_slope < 0.0:
        raise ValueError("--drawdown-governor-slope must be >= 0.")
    if not (0.0 <= args.drawdown_governor_floor <= 1.0):
        raise ValueError("--drawdown-governor-floor must be in [0, 1].")
    if not (0.0 < args.eval_split < 1.0):
        raise ValueError("--eval-split must be in (0, 1).")
    replay_action_gate_specs = _parse_gate_specs(list(args.replay_action_gate), arg_name="--replay-action-gate")
    replay_threshold_bump_specs = _parse_threshold_bump_specs(list(args.replay_threshold_bump))
    replay_policy_enabled = (
        args.replay_long_threshold is not None
        or args.replay_short_threshold is not None
        or bool(replay_action_gate_specs)
        or bool(replay_threshold_bump_specs)
    )
    if replay_policy_enabled:
        if args.replay_long_threshold is None or args.replay_short_threshold is None:
            raise ValueError("--replay-long-threshold and --replay-short-threshold are required when replay policy is enabled.")
        if float(args.replay_short_threshold) >= float(args.replay_long_threshold):
            raise ValueError("--replay-short-threshold must be < --replay-long-threshold.")
        replay_long_exit_threshold = (
            float(args.replay_long_threshold)
            if args.replay_long_exit_threshold is None
            else float(args.replay_long_exit_threshold)
        )
        replay_short_exit_threshold = (
            float(args.replay_short_threshold)
            if args.replay_short_exit_threshold is None
            else float(args.replay_short_exit_threshold)
        )
        if replay_long_exit_threshold > float(args.replay_long_threshold):
            raise ValueError("--replay-long-exit-threshold must be <= --replay-long-threshold.")
        if replay_short_exit_threshold < float(args.replay_short_threshold):
            raise ValueError("--replay-short-exit-threshold must be >= --replay-short-threshold.")
        if replay_short_exit_threshold >= replay_long_exit_threshold:
            raise ValueError("--replay-short-exit-threshold must be < --replay-long-exit-threshold.")
    else:
        replay_long_exit_threshold = None
        replay_short_exit_threshold = None

    feature_subset_path = str(args.feature_subset_json).strip()
    subset_names: list[str] | None = None
    if feature_subset_path:
        subset_path = Path(feature_subset_path).expanduser()
        subset_payload = json.loads(subset_path.read_text(encoding="utf-8"))
        if isinstance(subset_payload, dict):
            subset_names = subset_payload.get("selected_features", [])
        else:
            subset_names = subset_payload
    requested_feature_names = None if subset_names is None else [str(name) for name in subset_names]
    feature_profile = str(args.feature_profile).strip().lower() or "raw53"
    profile_required_columns = required_raw_columns_for_profile(feature_profile)
    if requested_feature_names is not None and profile_required_columns:
        for name in profile_required_columns:
            if name not in requested_feature_names:
                requested_feature_names.append(name)
    session_support_column = {
        "monday_open": "is_monday_open_window",
        "london": "is_london_session",
        "ny": "is_ny_session",
        "overlap": "is_london_ny_overlap",
    }.get(args.session_filter)
    if requested_feature_names is not None and session_support_column:
        if session_support_column not in requested_feature_names:
            requested_feature_names = [*requested_feature_names, session_support_column]
    replay_policy_feature_names = {
        str(item["feature"])
        for item in [*replay_action_gate_specs, *replay_threshold_bump_specs]
        if str(item.get("feature", "")).strip()
    }
    if requested_feature_names is not None:
        for name in sorted(replay_policy_feature_names):
            if name not in requested_feature_names:
                requested_feature_names.append(name)

    df = load_csv(args.data)
    features_frame, closes, timestamps = build_feature_frame(df, requested_feature_names)
    features_frame, closes, timestamps = filter_feature_rows_by_session(
        features_frame,
        closes,
        timestamps,
        args.session_filter,
    )
    replay_policy_frame = features_frame.copy()
    features_frame = apply_feature_profile(features_frame, feature_profile)
    if subset_names is not None:
        subset_in_profile = [name for name in subset_names if name in features_frame.columns]
        if subset_in_profile:
            features_frame = select_feature_columns(features_frame, subset_in_profile)
        elif feature_profile != "raw53":
            print(
                "Feature subset ignored for profile",
                feature_profile,
                f"(selected names not present in profiled frame; using {features_frame.shape[1]} profiled features).",
            )
    total_rows = len(features_frame)
    eval_size = int(total_rows * args.eval_split)
    if eval_size < 1 or total_rows - eval_size < 1:
        raise ValueError("Not enough data for train/eval split.")
    split_idx = total_rows - eval_size

    eval_replay_policy_frame = replay_policy_frame.iloc[split_idx:].reset_index(drop=True)
    train_frame = features_frame.iloc[:split_idx]
    eval_frame = features_frame.iloc[split_idx:]
    train_closes = closes.iloc[:split_idx].to_numpy(dtype=np.float32)
    eval_closes = closes.iloc[split_idx:].to_numpy(dtype=np.float32)
    train_timestamps = timestamps[:split_idx]
    eval_timestamps = timestamps[split_idx:]
    replay_policy_eval = _resolve_replay_policy(
        frame=eval_replay_policy_frame,
        action_gate_specs=replay_action_gate_specs,
        threshold_bump_specs=replay_threshold_bump_specs,
        action_gate_mode=str(args.replay_action_gate_mode),
        action_scale=float(args.replay_action_scale),
        long_threshold=args.replay_long_threshold,
        short_threshold=args.replay_short_threshold,
        long_exit_threshold=replay_long_exit_threshold,
        short_exit_threshold=replay_short_exit_threshold,
    )

    scaler = fit_scaler(train_frame)
    train_features = apply_scaler(train_frame, scaler).to_numpy(dtype=np.float32)
    eval_features = apply_scaler(eval_frame, scaler).to_numpy(dtype=np.float32)
    feature_dim = train_features.shape[1]

    scaler_path = args.feature_scaler_out.strip()
    if not scaler_path:
        scaler_path = str(Path(args.model_out).with_suffix(".scaler.json"))
    scaler_path = str(Path(scaler_path).expanduser())
    scaler_dir = Path(scaler_path).parent
    scaler_dir.mkdir(parents=True, exist_ok=True)
    save_scaler(scaler, scaler_path)

    random_start = not args.no_random_start
    start_mode = str(args.start_mode).strip().lower() if args.start_mode else ""
    if not start_mode:
        start_mode = "random" if random_start else "first"
    discrete_positions = tuple(
        float(item)
        for item in (part.strip() for part in args.discrete_positions.split(","))
        if item
    )
    train_config = TradingConfig(
        episode_length=args.episode_length,
        transaction_cost_bps=args.transaction_cost_bps,
        slippage_bps=args.slippage_bps,
        holding_cost_bps=args.holding_cost_bps,
        random_start=random_start,
        start_mode=start_mode,
        min_position_change=args.min_position_change,
        discretize_actions=args.discretize_actions,
        native_discrete_actions=args.native_discrete_actions,
        discrete_positions=discrete_positions,
        max_position=args.max_position,
        position_step=args.position_step,
        reward_horizon=args.reward_horizon,
        window_size=args.window_size,
        reward_scale=args.reward_scale,
        reward_clip=args.reward_clip,
        reward_mode=args.reward_mode,
        risk_aversion=args.risk_aversion,
        drawdown_penalty=args.drawdown_penalty,
        downside_penalty=args.downside_penalty,
        turnover_penalty=args.turnover_penalty,
        exposure_penalty=args.exposure_penalty,
        flat_position_penalty=args.flat_position_penalty,
        flat_streak_penalty=args.flat_streak_penalty,
        flat_position_threshold=args.flat_position_threshold,
        path_vol_penalty=args.path_vol_penalty,
        path_downside_penalty=args.path_downside_penalty,
        position_bias_penalty=args.position_bias_penalty,
        position_bias_threshold=args.position_bias_threshold,
        position_bias_ema_alpha=args.position_bias_ema_alpha,
        target_vol=args.target_vol,
        vol_target_lookback=args.vol_target_lookback,
        vol_scale_floor=args.vol_scale_floor,
        vol_scale_cap=args.vol_scale_cap,
        drawdown_governor_slope=args.drawdown_governor_slope,
        drawdown_governor_floor=args.drawdown_governor_floor,
    )
    # Evaluate across multiple anchor points instead of replaying the first eval segment.
    eval_start_mode = "weekly_open" if len(eval_timestamps) > 0 else "random"
    eval_config = TradingConfig(
        episode_length=args.episode_length,
        transaction_cost_bps=args.transaction_cost_bps,
        slippage_bps=args.slippage_bps,
        holding_cost_bps=args.holding_cost_bps,
        random_start=True,
        start_mode=eval_start_mode,
        min_position_change=args.min_position_change,
        discretize_actions=args.discretize_actions,
        native_discrete_actions=args.native_discrete_actions,
        discrete_positions=discrete_positions,
        max_position=args.max_position,
        position_step=args.position_step,
        reward_horizon=args.reward_horizon,
        window_size=args.window_size,
        reward_scale=args.reward_scale,
        reward_clip=args.reward_clip,
        reward_mode=args.reward_mode,
        risk_aversion=args.risk_aversion,
        drawdown_penalty=args.drawdown_penalty,
        downside_penalty=args.downside_penalty,
        turnover_penalty=args.turnover_penalty,
        exposure_penalty=args.exposure_penalty,
        flat_position_penalty=args.flat_position_penalty,
        flat_streak_penalty=args.flat_streak_penalty,
        flat_position_threshold=args.flat_position_threshold,
        path_vol_penalty=args.path_vol_penalty,
        path_downside_penalty=args.path_downside_penalty,
        position_bias_penalty=args.position_bias_penalty,
        position_bias_threshold=args.position_bias_threshold,
        position_bias_ema_alpha=args.position_bias_ema_alpha,
        target_vol=args.target_vol,
        vol_target_lookback=args.vol_target_lookback,
        vol_scale_floor=args.vol_scale_floor,
        vol_scale_cap=args.vol_scale_cap,
        drawdown_governor_slope=args.drawdown_governor_slope,
        drawdown_governor_floor=args.drawdown_governor_floor,
    )
    native_discrete_training = uses_native_discrete_actions(train_config)
    curriculum_steps = min(max(0, int(args.curriculum_steps)), max(0, int(args.total_steps)))
    if native_discrete_training and curriculum_steps > 0 and bool(args.curriculum_enabled):
        print("Curriculum disabled: native discrete action mode requires a fixed action space.")
        curriculum_steps = 0
    curriculum_positions = _build_curriculum_positions(
        float(args.curriculum_max_position),
        float(args.curriculum_position_step),
    )
    curriculum_train_config = _clone_config(
        train_config,
        max_position=float(args.curriculum_max_position),
        position_step=float(args.curriculum_position_step),
        min_position_change=float(args.curriculum_min_position_change),
        discretize_actions=True,
        native_discrete_actions=False,
        discrete_positions=curriculum_positions,
    )
    curriculum_eval_config = _clone_config(
        eval_config,
        max_position=float(args.curriculum_max_position),
        position_step=float(args.curriculum_position_step),
        min_position_change=float(args.curriculum_min_position_change),
        discretize_actions=True,
        native_discrete_actions=False,
        discrete_positions=curriculum_positions,
    )
    if _continuous_supervision_supported(train_config):
        warm_start_obs, warm_start_actions, warm_start_weights, warm_start_summary = _build_warm_start_dataset(
            train_features,
            train_closes,
            train_config,
            labeler=str(args.warm_start_labeler),
            sample_limit=int(args.warm_start_samples),
            lookback_short=int(args.warm_start_lookback_short),
            lookback_long=int(args.warm_start_lookback_long),
            threshold=float(args.warm_start_threshold),
            action_scale=float(args.warm_start_action_scale),
            long_weight=float(args.warm_start_long_weight),
            short_weight=float(args.warm_start_short_weight),
            flat_weight=float(args.warm_start_flat_weight),
        )
    else:
        obs_dim = int(train_features.shape[1] * max(1, int(train_config.window_size)) + 1)
        warm_start_obs = np.zeros((0, obs_dim), dtype=np.float32)
        warm_start_actions = np.zeros((0, 1), dtype=np.float32)
        warm_start_weights = np.zeros((0, 1), dtype=np.float32)
        warm_start_summary = {
            "samples": 0.0,
            "long_ratio": 0.0,
            "short_ratio": 0.0,
            "flat_ratio": 1.0,
            "raw_samples": 0.0,
            "raw_long_ratio": 0.0,
            "raw_short_ratio": 0.0,
            "raw_flat_ratio": 1.0,
            "long_weight": max(float(args.warm_start_long_weight), 0.0),
            "short_weight": max(float(args.warm_start_short_weight), 0.0),
            "flat_weight": max(float(args.warm_start_flat_weight), 0.0),
            "avg_abs_action": 0.0,
            "max_abs_action": 0.0,
            "action_scale": max(float(args.warm_start_action_scale), 0.0),
            "disabled_for_native_discrete": 1.0,
        }

    env_config_path = args.env_config_out.strip()
    if not env_config_path:
        env_config_path = str(Path(args.model_out).with_suffix(".env.json"))
    env_config_path = str(Path(env_config_path).expanduser())
    env_dir = Path(env_config_path).parent
    env_dir.mkdir(parents=True, exist_ok=True)
    training_args_path = args.training_args_out.strip()
    if not training_args_path:
        training_args_path = str(Path(args.model_out).with_name("training_args.json"))
    training_args_path = str(Path(training_args_path).expanduser())
    training_status_path = args.training_status_out.strip()
    if not training_status_path:
        training_status_path = str(Path(args.model_out).with_name("training_status.json"))
    training_status_path = str(Path(training_status_path).expanduser())
    checkpoint_selection_path = str(Path(args.model_out).with_name("checkpoint_selection.json").expanduser())
    _save_training_args_snapshot(
        training_args_path,
        args,
        feature_profile=feature_profile,
        requested_feature_names=requested_feature_names,
        scaler_path=scaler_path,
        env_config_path=env_config_path,
    )
    _save_training_status(
        training_status_path,
        status="running",
        total_steps_target=int(args.total_steps),
    )

    env = _build_env(train_features, train_closes, train_config, train_timestamps)
    eval_env = _build_env(eval_features, eval_closes, eval_config, eval_timestamps)
    curriculum_env = _build_env(
        train_features,
        train_closes,
        curriculum_train_config,
        train_timestamps,
    )
    curriculum_eval_env = _build_env(
        eval_features,
        eval_closes,
        curriculum_eval_config,
        eval_timestamps,
    )
    env.seed(args.seed)
    eval_env.seed(args.seed)
    curriculum_env.seed(args.seed)
    curriculum_eval_env.seed(args.seed)

    model_path = Path(args.model_out)
    print(
        "Training setup:",
        f"feature_profile={feature_profile}",
        f"rows={total_rows}",
        f"train={len(train_features)}",
        f"eval={len(eval_features)}",
        f"eval_start_mode={eval_start_mode}",
        f"total_steps={args.total_steps}",
        f"resume={args.resume}",
    )
    if native_discrete_training and (args.warm_start_enabled or args.imitation_enabled):
        print("Continuous warm-start/imitation disabled in native discrete action mode.")
    if args.warm_start_enabled:
        print(
            "Warm-start dataset:",
            f"labeler={args.warm_start_labeler}",
            f"samples={int(warm_start_summary.get('samples', 0.0))}",
            f"long_ratio={warm_start_summary.get('long_ratio', 0.0):.3f}",
            f"short_ratio={warm_start_summary.get('short_ratio', 0.0):.3f}",
            f"flat_ratio={warm_start_summary.get('flat_ratio', 1.0):.3f}",
            f"raw_samples={int(warm_start_summary.get('raw_samples', 0.0))}",
            f"raw_long_ratio={warm_start_summary.get('raw_long_ratio', 0.0):.3f}",
            f"raw_short_ratio={warm_start_summary.get('raw_short_ratio', 0.0):.3f}",
            f"raw_flat_ratio={warm_start_summary.get('raw_flat_ratio', 1.0):.3f}",
            f"weights=({warm_start_summary.get('long_weight', 1.0):.2f},{warm_start_summary.get('short_weight', 1.0):.2f},{warm_start_summary.get('flat_weight', 1.0):.2f})",
        )

    metrics_log_path = args.metrics_log.strip()
    metrics_log_every = max(1, int(args.metrics_log_every))
    metrics_fh = None
    metrics_counter = 0
    if metrics_log_path:
        log_path = Path(metrics_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_fh = log_path.open("w", encoding="utf-8")
        metrics_fh.write("step,metric,value\n")

    def _write_metric(step: int, metric: str, value: float) -> None:
        nonlocal metrics_counter
        if metrics_fh is None:
            return
        metrics_counter += 1
        if metrics_counter % metrics_log_every != 0:
            return
        metrics_fh.write(f"{step},{metric},{value:.10g}\n")
        if metric.startswith("warm_start/") or metrics_counter % (metrics_log_every * 10) == 0:
            metrics_fh.flush()

    metrics_callback = MetricsLogCallback(_write_metric)
    best_model_tmp_dir: Path | None = None
    playback_candidate_tmp_dir: Path | None = None
    activity_profile_steps = max(0, int(args.eval_profile_steps))
    eval_callbacks: list[PlateauEvalCallback] = []

    def _make_imitation_callback() -> ImitationRolloutCallback | None:
        if not args.imitation_enabled:
            return None
        if not _continuous_supervision_supported(train_config):
            return None
        if int(warm_start_summary.get("samples", 0.0)) <= 0:
            return None
        return ImitationRolloutCallback(
            write_metric=_write_metric,
            observations=warm_start_obs,
            actions=warm_start_actions,
            sample_weights=warm_start_weights,
            max_steps=int(args.imitation_steps),
            epochs_per_rollout=int(args.imitation_epochs_per_rollout),
            batch_size=int(args.imitation_batch_size),
            loss_scale=float(args.imitation_loss_scale),
            verbose=args.verbose,
        )

    def _build_callback_list(eval_callback: BaseCallback | None) -> CallbackList:
        callbacks: list[BaseCallback] = []
        if eval_callback is not None:
            callbacks.append(eval_callback)
        imitation_callback = _make_imitation_callback()
        if imitation_callback is not None:
            callbacks.append(imitation_callback)
        callbacks.append(metrics_callback)
        return CallbackList(callbacks)

    def _profile_eval_activity(model_ref: PPO, config_ref: TradingConfig) -> dict[str, float]:
        return _profile_policy_activity(
            model_ref,
            eval_features,
            eval_closes,
            eval_timestamps,
            config_ref,
            max_steps=activity_profile_steps,
            replay_policy=replay_policy_eval,
        )

    def _make_eval_callback(
        eval_env_ref: DummyVecEnv,
        eval_config_ref: TradingConfig,
        *,
        collect_playback_candidates: bool,
    ) -> EvalCallback:
        nonlocal best_model_tmp_dir, playback_candidate_tmp_dir
        kwargs = {
            "eval_freq": args.eval_freq,
            "n_eval_episodes": args.eval_episodes,
            "deterministic": True,
        }
        if args.save_best_checkpoint:
            if best_model_tmp_dir is None:
                best_model_tmp_dir = Path(tempfile.mkdtemp(prefix="ppo_best_eval_"))
            kwargs["best_model_save_path"] = str(best_model_tmp_dir)
            kwargs["log_path"] = str(best_model_tmp_dir)
        callback = PlateauEvalCallback(
            eval_env_ref,
            write_metric=_write_metric,
            early_stop_enabled=args.early_stop_enabled,
            early_stop_warmup_steps=args.early_stop_warmup_steps,
            early_stop_patience_evals=args.early_stop_patience_evals,
            early_stop_min_delta=args.early_stop_min_delta,
            activity_profiler=(
                lambda model_ref, config_ref=eval_config_ref: _profile_eval_activity(model_ref, config_ref)
            )
            if (args.anti_flat_enabled or args.save_best_checkpoint or args.early_stop_enabled)
            else None,
            anti_flat_enabled=args.anti_flat_enabled,
            anti_flat_warmup_steps=args.anti_flat_warmup_steps,
            anti_flat_patience_evals=args.anti_flat_patience_evals,
            anti_flat_min_trade_rate=args.anti_flat_min_trade_rate,
            anti_flat_max_flat_ratio=args.anti_flat_max_flat_ratio,
            anti_flat_max_ls_imbalance=args.anti_flat_max_ls_imbalance,
            checkpoint_min_trade_rate=args.checkpoint_min_trade_rate,
            checkpoint_max_trade_rate=args.checkpoint_max_trade_rate,
            checkpoint_max_flat_ratio=args.checkpoint_max_flat_ratio,
            checkpoint_max_ls_imbalance=args.checkpoint_max_ls_imbalance,
            checkpoint_max_drawdown=args.checkpoint_max_drawdown,
            playback_candidate_dir=(
                str(playback_candidate_tmp_dir)
                if collect_playback_candidates
                else ""
            ),
            playback_top_n=5,
            collect_playback_candidates=collect_playback_candidates,
            **kwargs,
        )
        eval_callbacks.append(callback)
        return callback

    if args.save_best_checkpoint:
        playback_candidate_tmp_dir = Path(tempfile.mkdtemp(prefix="ppo_playback_candidates_"))

    def _resolve_callback_status() -> tuple[bool, str, int | None]:
        for callback in reversed(eval_callbacks):
            if getattr(callback, "stopped_early", False):
                step = getattr(callback, "num_timesteps", None)
                return True, str(getattr(callback, "stop_reason", "") or ""), int(step) if step is not None else None
        if eval_callbacks:
            step = getattr(eval_callbacks[-1], "num_timesteps", None)
            return False, "", int(step) if step is not None else None
        return False, "", None

    def _save_interrupted_checkpoint(model_ref: PPO, config_ref: TradingConfig) -> None:
        model_to_save = model_ref
        if args.save_best_checkpoint and best_model_tmp_dir is not None:
            best_model_path = best_model_tmp_dir / "best_model.zip"
            if best_model_path.exists():
                model_to_save = PPO.load(str(best_model_path))
                print(f"Using best eval checkpoint after interrupt: {best_model_path}")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_to_save.save(str(model_path))
        save_trading_config(
            config_ref,
            env_config_path,
            extra=_extract_data_context(args.data),
        )
        stopped_early, stop_reason, last_step = _resolve_callback_status()
        _save_training_status(
            training_status_path,
            status="interrupted",
            stop_reason=stop_reason or "external signal or user interrupt",
            exit_code=130,
            stopped_early=stopped_early,
            total_steps_target=int(args.total_steps),
            last_step=last_step,
        )

    def _maybe_run_warm_start(model_ref: PPO) -> None:
        if not args.warm_start_enabled:
            return
        if not _continuous_supervision_supported(train_config):
            print("Warm-start skipped: native discrete action mode")
            return
        if int(warm_start_summary.get("samples", 0.0)) <= 0:
            print("Warm-start skipped: no samples")
            return
        _write_metric(0, "warm_start/active", 1.0)
        _write_metric(0, "warm_start/samples", float(warm_start_summary.get("samples", 0.0)))
        _write_metric(0, "warm_start/avg_abs_action", float(warm_start_summary.get("avg_abs_action", 0.0)))
        _write_metric(0, "warm_start/max_abs_action", float(warm_start_summary.get("max_abs_action", 0.0)))
        _write_metric(0, "warm_start/epochs_requested", float(int(args.warm_start_epochs)))
        print(
            "Warm-start:",
            f"epochs={args.warm_start_epochs}",
            f"batch_size={args.warm_start_batch_size}",
            f"samples={int(warm_start_summary.get('samples', 0.0))}",
        )
        started_at = time.perf_counter()
        final_loss = _warm_start_policy(
            model_ref,
            warm_start_obs,
            warm_start_actions,
            warm_start_weights,
            epochs=int(args.warm_start_epochs),
            batch_size=int(args.warm_start_batch_size),
            loss_scale=float(args.warm_start_loss_scale),
            metric_writer=_write_metric,
            metric_step=0,
            metric_prefix="warm_start",
        )
        _write_metric(0, "warm_start/duration_sec", time.perf_counter() - started_at)
        _write_metric(0, "warm_start/final_loss", final_loss)
        _write_metric(0, "warm_start/active", 0.0)

    def _run_training_with_optional_curriculum(
        model_ref: PPO,
        *,
        total_steps: int,
        final_env_ref: DummyVecEnv,
        final_eval_env_ref: DummyVecEnv,
        final_eval_config_ref: TradingConfig,
    ) -> None:
        run_curriculum = bool(args.curriculum_enabled) and curriculum_steps > 0 and total_steps > 0
        if run_curriculum:
            stage_one_steps = min(curriculum_steps, total_steps)
            print(
                "Curriculum stage 1:",
                f"steps={stage_one_steps}",
                f"max_position={curriculum_train_config.max_position}",
                f"position_step={curriculum_train_config.position_step}",
                f"min_position_change={curriculum_train_config.min_position_change}",
                f"positions={curriculum_train_config.discrete_positions}",
            )
            model_ref.set_env(curriculum_env)
            curriculum_callback = _make_eval_callback(
                curriculum_eval_env,
                curriculum_eval_config,
                collect_playback_candidates=False,
            )
            model_ref.learn(
                total_timesteps=stage_one_steps,
                callback=_build_callback_list(curriculum_callback),
            )
            if getattr(curriculum_callback, "stopped_early", False):
                print(
                    "Curriculum aborted after stage 1:",
                    getattr(curriculum_callback, "stop_reason", "callback requested stop"),
                )
                return
            remaining_steps = max(0, total_steps - stage_one_steps)
            if remaining_steps <= 0:
                return
            print(
                "Curriculum stage 2:",
                f"steps={remaining_steps}",
                f"max_position={final_eval_config_ref.max_position}",
                f"position_step={final_eval_config_ref.position_step}",
            )
            model_ref.set_env(final_env_ref)
            final_callback = _make_eval_callback(
                final_eval_env_ref,
                final_eval_config_ref,
                collect_playback_candidates=True,
            )
            model_ref.learn(
                total_timesteps=remaining_steps,
                callback=_build_callback_list(final_callback),
                reset_num_timesteps=False,
            )
            return

        model_ref.set_env(final_env_ref)
        final_callback = _make_eval_callback(
            final_eval_env_ref,
            final_eval_config_ref,
            collect_playback_candidates=True,
        )
        model_ref.learn(
            total_timesteps=total_steps,
            callback=_build_callback_list(final_callback),
        )

    if args.optuna_trials > 0:
        try:
            import optuna
        except ImportError as exc:
            raise RuntimeError("Optuna not installed. Run: pip install optuna") from exc

        optuna_log_path = args.optuna_log.strip()
        optuna_fh = None
        if optuna_log_path:
            log_path = Path(optuna_log_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            optuna_fh = log_path.open("w", encoding="utf-8")
            optuna_fh.write("trial,value,best_value,duration_sec\n")
        trials_csv_path = args.optuna_trials_csv.strip()
        trials_csv_fh = None
        trials_csv_writer = None
        trial_param_keys = [
            "n_steps",
            "batch_size",
            "learning_rate",
            "gamma",
            "ent_coef",
            "gae_lambda",
            "clip_range",
            "target_kl",
            "vf_coef",
            "n_epochs",
            "min_position_change",
            "position_step",
            "reward_horizon",
            "window_size",
            "risk_aversion",
            "drawdown_penalty",
            "downside_penalty",
            "turnover_penalty",
            "exposure_penalty",
            "target_vol",
            "vol_target_lookback",
            "vol_scale_floor",
            "vol_scale_cap",
            "drawdown_governor_slope",
            "drawdown_governor_floor",
            "max_position",
            "episode_length",
            "reward_clip",
        ]
        if trials_csv_path:
            trials_path = Path(trials_csv_path).expanduser()
            trials_path.parent.mkdir(parents=True, exist_ok=True)
            trials_csv_fh = trials_path.open("w", encoding="utf-8", newline="")
            trials_csv_writer = csv.DictWriter(
                trials_csv_fh,
                fieldnames=[
                    "trial",
                    "value",
                    "best_value",
                    "duration_sec",
                    "state",
                    *trial_param_keys,
                ],
            )
            trials_csv_writer.writeheader()
        trials_rows: list[dict] = []

        def _profile_policy(
            model: PPO,
            features: np.ndarray,
            closes: np.ndarray,
            config: TradingConfig,
            *,
            max_steps: int = 0,
        ) -> dict[str, float]:
            position = 0.0
            equity = 1.0
            peak_equity = 1.0
            trades = 0
            action_long = 0
            action_short = 0
            action_flat = 0
            max_drawdown = 0.0
            total_steps = max(0, len(features) - 1)
            if max_steps > 0:
                total_steps = min(total_steps, int(max_steps))
            for idx in range(total_steps):
                obs = build_window_observation(
                    features,
                    idx,
                    position=position,
                    max_position=float(config.max_position),
                    window_size=int(getattr(config, "window_size", 1)),
                )
                action, _ = model.predict(obs, deterministic=True)
                target, _ = apply_risk_engine(
                    decode_policy_action(action, config=config),
                    current_position=position,
                    config=config,
                    closes=closes,
                    idx=idx,
                    equity=equity,
                    peak_equity=peak_equity,
                )
                if abs(target - position) > 1e-12:
                    trades += 1
                if target > 0.05:
                    action_long += 1
                elif target < -0.05:
                    action_short += 1
                else:
                    action_flat += 1
                transition = simulate_step_transition(
                    current_position=position,
                    target_position=target,
                    closes=closes,
                    idx=idx,
                    equity=equity,
                    peak_equity=peak_equity,
                    config=config,
                )
                equity = transition["equity"]
                peak_equity = transition["peak_equity"]
                max_drawdown = max(max_drawdown, float(transition["drawdown"]))
                position = target
            total_actions = max(1, action_long + action_short + action_flat)
            long_ratio = float(action_long / total_actions)
            short_ratio = float(action_short / total_actions)
            trade_rate_1k = float(trades * 1000.0 / max(1, total_steps))
            return {
                "trades": float(trades),
                "flat_ratio": float(action_flat / total_actions),
                "long_ratio": long_ratio,
                "short_ratio": short_ratio,
                "ls_imbalance": float(abs(long_ratio - short_ratio)),
                "trade_rate_1k": trade_rate_1k,
                "max_drawdown": float(max_drawdown),
            }

        def objective(trial: optuna.Trial) -> float:
            n_steps = trial.suggest_categorical("n_steps", [512, 1024, 2048])
            batch_sizes = [64, 128, 256]
            batch_sizes = [size for size in batch_sizes if size <= n_steps]
            batch_size = trial.suggest_categorical("batch_size", batch_sizes)
            learning_rate = trial.suggest_float("learning_rate", 1e-5, 3e-4, log=True)
            gamma = trial.suggest_float("gamma", 0.97, 0.997)
            ent_coef = trial.suggest_float("ent_coef", 1e-5, 1e-3, log=True)
            gae_lambda = trial.suggest_float("gae_lambda", 0.92, 0.98)
            clip_range = trial.suggest_float("clip_range", 0.05, 0.18)
            target_kl = trial.suggest_float("target_kl", 0.005, 0.02)
            vf_coef = trial.suggest_float("vf_coef", 0.2, 0.8)
            n_epochs = trial.suggest_categorical("n_epochs", [5, 10])
            min_position_change = trial.suggest_float(
                "min_position_change",
                0.03,
                0.18,
                step=0.01,
            )
            position_step = trial.suggest_categorical("position_step", [0.05, 0.1])
            reward_horizon = trial.suggest_categorical("reward_horizon", [16, 32, 48, 96])
            window_size = trial.suggest_categorical("window_size", [16, 32, 48, 72])
            risk_aversion = trial.suggest_float("risk_aversion", 0.1, 0.4, step=0.01)
            drawdown_penalty = trial.suggest_float(
                "drawdown_penalty",
                0.05,
                0.30,
                step=0.01,
            )
            downside_penalty = trial.suggest_float(
                "downside_penalty",
                0.02,
                0.20,
                step=0.01,
            )
            turnover_penalty = trial.suggest_categorical(
                "turnover_penalty",
                [0.0, 1e-4, 5e-4],
            )
            exposure_penalty = trial.suggest_categorical(
                "exposure_penalty",
                [0.0, 1e-4, 5e-4],
            )
            target_vol = trial.suggest_categorical(
                "target_vol",
                [0.0025, 0.005, 0.01],
            )
            vol_target_lookback = trial.suggest_categorical(
                "vol_target_lookback",
                [48, 72, 96],
            )
            vol_scale_floor = trial.suggest_categorical("vol_scale_floor", [0.5, 0.7])
            vol_scale_cap = trial.suggest_categorical("vol_scale_cap", [1.0, 1.15, 1.3])
            drawdown_governor_slope = trial.suggest_categorical(
                "drawdown_governor_slope",
                [2.0, 3.0, 4.0, 5.0],
            )
            drawdown_governor_floor = trial.suggest_categorical(
                "drawdown_governor_floor",
                [0.25, 0.3, 0.4],
            )
            max_position = trial.suggest_categorical("max_position", [0.25, 0.35, 0.5])
            episode_length = trial.suggest_categorical("episode_length", [2048, 4096, 8192])
            reward_clip = trial.suggest_categorical("reward_clip", [0.01, 0.02, 0.05])

            trial_train_config = _clone_config(
                train_config,
                episode_length=episode_length,
                min_position_change=min_position_change,
                position_step=position_step,
                reward_horizon=reward_horizon,
                window_size=window_size,
                risk_aversion=risk_aversion,
                drawdown_penalty=drawdown_penalty,
                downside_penalty=downside_penalty,
                turnover_penalty=turnover_penalty,
                exposure_penalty=exposure_penalty,
                target_vol=target_vol,
                vol_target_lookback=vol_target_lookback,
                vol_scale_floor=vol_scale_floor,
                vol_scale_cap=vol_scale_cap,
                drawdown_governor_slope=drawdown_governor_slope,
                drawdown_governor_floor=drawdown_governor_floor,
                max_position=max_position,
                reward_clip=reward_clip,
            )
            trial_eval_config = _clone_config(
                eval_config,
                episode_length=episode_length,
                min_position_change=min_position_change,
                position_step=position_step,
                reward_horizon=reward_horizon,
                window_size=window_size,
                risk_aversion=risk_aversion,
                drawdown_penalty=drawdown_penalty,
                downside_penalty=downside_penalty,
                turnover_penalty=turnover_penalty,
                exposure_penalty=exposure_penalty,
                target_vol=target_vol,
                vol_target_lookback=vol_target_lookback,
                vol_scale_floor=vol_scale_floor,
                vol_scale_cap=vol_scale_cap,
                drawdown_governor_slope=drawdown_governor_slope,
                drawdown_governor_floor=drawdown_governor_floor,
                max_position=max_position,
                reward_clip=reward_clip,
            )
            trial_env = _build_env(
                train_features,
                train_closes,
                trial_train_config,
                train_timestamps,
            )
            trial_eval_env = _build_env(
                eval_features,
                eval_closes,
                trial_eval_config,
                eval_timestamps,
            )

            model = _train_model(
                env=trial_env,
                learning_rate=learning_rate,
                n_steps=n_steps,
                batch_size=batch_size,
                gamma=gamma,
                ent_coef=ent_coef,
                gae_lambda=gae_lambda,
                clip_range=clip_range,
                target_kl=None if target_kl <= 0.0 else target_kl,
                vf_coef=vf_coef,
                n_epochs=n_epochs,
                total_steps=args.optuna_steps,
                window_size=window_size,
                feature_dim=feature_dim,
                device=args.device,
                policy_log_std_init=args.policy_log_std_init,
                verbose=0,
            )
            model.learn(
                total_timesteps=args.optuna_steps,
                callback=_build_callback_list(None),
            )
            mean_reward, _ = evaluate_policy(
                model,
                trial_eval_env,
                n_eval_episodes=args.eval_episodes,
                deterministic=True,
            )
            objective_profile = _profile_policy_activity(
                model,
                eval_features,
                eval_closes,
                eval_timestamps,
                trial_eval_config,
                max_steps=min(
                    max(1, int(args.optuna_replay_walk_forward_steps)),
                    max(1, len(eval_features) - 1),
                ),
                replay_policy=replay_policy_eval,
            )
            trial_env.close()
            trial_eval_env.close()
            objective_score = float(mean_reward)
            objective_score -= 0.25 * max(
                0.0,
                (float(args.optuna_replay_min_trade_rate) - objective_profile["trade_rate_1k"])
                / max(1.0, float(args.optuna_replay_min_trade_rate)),
            )
            objective_score -= 0.25 * max(
                0.0,
                objective_profile["flat_ratio"] - float(args.optuna_replay_max_flat_ratio),
            )
            objective_score -= 0.5 * max(
                0.0,
                objective_profile["ls_imbalance"] - float(args.optuna_replay_max_ls_imbalance),
            )
            objective_score -= 0.5 * max(0.0, objective_profile["max_drawdown"] - 0.15)
            trial.set_user_attr("trade_rate_1k", objective_profile["trade_rate_1k"])
            trial.set_user_attr("flat_ratio", objective_profile["flat_ratio"])
            trial.set_user_attr("ls_imbalance", objective_profile["ls_imbalance"])
            trial.set_user_attr("max_drawdown", objective_profile["max_drawdown"])
            return objective_score

        def _log_optuna_trial(study: optuna.Study, trial: optuna.Trial) -> None:
            if not optuna_fh or trial.value is None:
                if not trials_csv_writer:
                    return
            duration = trial.duration.total_seconds() if trial.duration else 0.0
            trial_value = float(trial.value) if trial.value is not None else float("nan")
            best_value = float(study.best_value) if study.best_trial is not None else float("nan")
            if optuna_fh and trial.value is not None:
                optuna_fh.write(
                    f"{trial.number},{trial_value:.10g},{best_value:.10g},{duration:.6f}\n"
                )
                optuna_fh.flush()
            if trials_csv_writer:
                row = {
                    "trial": trial.number,
                    "value": f"{trial_value:.10g}",
                    "best_value": f"{best_value:.10g}",
                    "duration_sec": f"{duration:.6f}",
                    "state": trial.state.name,
                    "_value_num": trial_value,
                }
                for key in trial_param_keys:
                    value = trial.params.get(key)
                    row[key] = "" if value is None else f"{float(value):.10g}"
                trials_rows.append(row)

        def _params_to_configs(params: dict) -> tuple[TradingConfig, TradingConfig]:
            train_cfg = _clone_config(
                train_config,
                episode_length=int(params["episode_length"]),
                min_position_change=float(params["min_position_change"]),
                position_step=float(params["position_step"]),
                reward_horizon=int(params.get("reward_horizon", 1)),
                window_size=int(params.get("window_size", 1)),
                risk_aversion=float(params["risk_aversion"]),
                drawdown_penalty=float(params.get("drawdown_penalty", 0.0)),
                downside_penalty=float(
                    params.get("downside_penalty", train_config.downside_penalty)
                ),
                turnover_penalty=float(
                    params.get("turnover_penalty", train_config.turnover_penalty)
                ),
                exposure_penalty=float(
                    params.get("exposure_penalty", train_config.exposure_penalty)
                ),
                target_vol=float(params.get("target_vol", 0.0)),
                vol_target_lookback=int(params.get("vol_target_lookback", 72)),
                vol_scale_floor=float(params.get("vol_scale_floor", 0.5)),
                vol_scale_cap=float(params.get("vol_scale_cap", 1.5)),
                drawdown_governor_slope=float(
                    params.get("drawdown_governor_slope", train_config.drawdown_governor_slope)
                ),
                drawdown_governor_floor=float(
                    params.get("drawdown_governor_floor", train_config.drawdown_governor_floor)
                ),
                max_position=float(params["max_position"]),
                reward_clip=float(params["reward_clip"]),
            )
            eval_cfg = _clone_config(
                eval_config,
                episode_length=int(params["episode_length"]),
                min_position_change=float(params["min_position_change"]),
                position_step=float(params["position_step"]),
                reward_horizon=int(params.get("reward_horizon", 1)),
                window_size=int(params.get("window_size", 1)),
                risk_aversion=float(params["risk_aversion"]),
                drawdown_penalty=float(params.get("drawdown_penalty", 0.0)),
                downside_penalty=float(params.get("downside_penalty", eval_config.downside_penalty)),
                turnover_penalty=float(params.get("turnover_penalty", eval_config.turnover_penalty)),
                exposure_penalty=float(params.get("exposure_penalty", eval_config.exposure_penalty)),
                target_vol=float(params.get("target_vol", 0.0)),
                vol_target_lookback=int(params.get("vol_target_lookback", 72)),
                vol_scale_floor=float(params.get("vol_scale_floor", 0.5)),
                vol_scale_cap=float(params.get("vol_scale_cap", 1.5)),
                drawdown_governor_slope=float(
                    params.get("drawdown_governor_slope", eval_config.drawdown_governor_slope)
                ),
                drawdown_governor_floor=float(
                    params.get("drawdown_governor_floor", eval_config.drawdown_governor_floor)
                ),
                max_position=float(params["max_position"]),
                reward_clip=float(params["reward_clip"]),
            )
            return train_cfg, eval_cfg

        def _run_candidate(
            params: dict, *, total_steps: int, seed: int, verbose: int
        ) -> tuple[float, dict[str, float], dict[str, float]]:
            cand_train_cfg, cand_eval_cfg = _params_to_configs(params)
            cand_env = _build_env(train_features, train_closes, cand_train_cfg, train_timestamps)
            cand_eval_env = _build_env(eval_features, eval_closes, cand_eval_cfg, eval_timestamps)
            model = _train_model(
                env=cand_env,
                learning_rate=float(params["learning_rate"]),
                n_steps=int(params["n_steps"]),
                batch_size=int(params["batch_size"]),
                gamma=float(params["gamma"]),
                ent_coef=float(params["ent_coef"]),
                gae_lambda=float(params["gae_lambda"]),
                clip_range=float(params["clip_range"]),
                target_kl=(
                    None
                    if float(params.get("target_kl", 0.0)) <= 0.0
                    else float(params["target_kl"])
                ),
                vf_coef=float(params["vf_coef"]),
                n_epochs=int(params["n_epochs"]),
                total_steps=total_steps,
                window_size=int(params.get("window_size", 1)),
                feature_dim=feature_dim,
                device=args.device,
                policy_log_std_init=args.policy_log_std_init,
                verbose=verbose,
            )
            model.set_random_seed(seed)
            model.learn(total_timesteps=total_steps, callback=CallbackList([metrics_callback]))
            mean_reward, _ = evaluate_policy(
                model,
                cand_eval_env,
                n_eval_episodes=args.eval_episodes,
                deterministic=True,
            )
            profile = _profile_policy_activity(
                model,
                eval_features,
                eval_closes,
                eval_timestamps,
                cand_eval_cfg,
                replay_policy=replay_policy_eval,
            )
            walk_forward_profile = _aggregate_playback_results([])
            if replay_score_mode == "walk_forward":
                walk_forward_profile = _profile_walk_forward(
                    model,
                    eval_features,
                    eval_closes,
                    eval_timestamps,
                    cand_eval_cfg,
                    segment_steps=replay_walk_forward_steps,
                    segments=replay_walk_forward_segments,
                    stride=replay_walk_forward_stride,
                    replay_policy=replay_policy_eval,
                )
            cand_env.close()
            cand_eval_env.close()
            return float(mean_reward), profile, walk_forward_profile

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=args.optuna_trials, callbacks=[_log_optuna_trial])
        best_params = study.best_trial.params
        print(f"Optuna best value: {study.best_value:.6f}")
        print(f"Optuna best params: {best_params}")
        if trials_csv_writer:
            sorted_rows = sorted(
                trials_rows,
                key=lambda row: (
                    math.isnan(float(row.get("_value_num", float("nan")))),
                    -float(row.get("_value_num", float("-inf")))
                    if not math.isnan(float(row.get("_value_num", float("nan"))))
                    else float("inf"),
                    int(row.get("trial", 0)),
                ),
            )
            for row in sorted_rows:
                row.pop("_value_num", None)
                trials_csv_writer.writerow(row)
            if trials_csv_fh:
                trials_csv_fh.flush()
        if trials_csv_fh:
            trials_csv_fh.close()
        selected_trials: list = []
        final_eval_config_used = eval_config
        if args.optuna_auto_select:
            completed_trials = [
                trial
                for trial in study.trials
                if trial.value is not None
                and trial.state == optuna.trial.TrialState.COMPLETE
            ]
            completed_trials.sort(key=lambda trial: float(trial.value), reverse=True)
            total_completed = len(completed_trials)
            if total_completed > 0:
                if args.optuna_select_mode == "top_percent":
                    pct = max(0.1, min(100.0, float(args.optuna_top_percent)))
                    base_count = int(math.ceil(total_completed * (pct / 100.0)))
                else:
                    base_count = int(max(1, args.optuna_top_k))
                keep_count = max(base_count, int(max(1, args.optuna_min_candidates)))
                keep_count = min(total_completed, keep_count)
                selected = completed_trials[:keep_count]
                selected_trials = selected
                top_payload = []
                for rank, trial in enumerate(selected, start=1):
                    top_payload.append(
                        {
                            "rank": rank,
                            "trial": int(trial.number),
                            "value": float(trial.value),
                            "params": dict(trial.params),
                        }
                    )
                top_out = str(args.optuna_top_out).strip()
                if top_out:
                    top_path = Path(top_out).expanduser()
                    top_path.parent.mkdir(parents=True, exist_ok=True)
                    top_path.write_text(
                        json.dumps(
                            {
                                "mode": args.optuna_select_mode,
                                "top_k": int(args.optuna_top_k),
                                "top_percent": float(args.optuna_top_percent),
                                "min_candidates": int(args.optuna_min_candidates),
                                "total_completed_trials": total_completed,
                                "selected_count": keep_count,
                                "candidates": top_payload,
                            },
                            ensure_ascii=True,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                print(
                    "Optuna auto-select:",
                    f"mode={args.optuna_select_mode}",
                    f"selected={keep_count}/{total_completed}",
                )
        if args.optuna_replay_enabled:
            replay_pool = selected_trials
            if not replay_pool:
                completed = [
                    trial
                    for trial in study.trials
                    if trial.value is not None
                    and trial.state == optuna.trial.TrialState.COMPLETE
                ]
                completed.sort(key=lambda trial: float(trial.value), reverse=True)
                replay_pool = completed[:1]
            replay_steps = max(1, int(args.optuna_replay_steps))
            replay_seeds = max(1, int(args.optuna_replay_seeds))
            replay_candidates = replay_pool
            replay_score_mode = str(args.optuna_replay_score_mode).strip()
            replay_walk_forward_segments = max(1, int(args.optuna_replay_walk_forward_segments))
            replay_walk_forward_steps = max(1, int(args.optuna_replay_walk_forward_steps))
            replay_walk_forward_stride = max(1, int(args.optuna_replay_walk_forward_stride))
            replay_max_flat_ratio = float(args.optuna_replay_max_flat_ratio)
            replay_min_trade_rate = max(0.0, float(args.optuna_replay_min_trade_rate))
            replay_max_ls_imbalance = max(0.0, float(args.optuna_replay_max_ls_imbalance))
            print(
                "Replay progress:",
                f"candidates={len(replay_candidates)}",
                f"seeds_per_candidate={replay_seeds}",
                f"steps={replay_steps}",
                f"score_mode={replay_score_mode}",
                f"min_trade_rate={replay_min_trade_rate}",
                f"max_flat={replay_max_flat_ratio}",
                f"max_ls_imbalance={replay_max_ls_imbalance}",
            )
            if replay_score_mode == "walk_forward":
                print(
                    "Replay walk-forward:",
                    f"segments={replay_walk_forward_segments}",
                    f"segment_steps={replay_walk_forward_steps}",
                    f"stride={replay_walk_forward_stride}",
                )
            replay_rows = []
            for rank, trial in enumerate(replay_candidates, start=1):
                seed_values = []
                seed_trades = []
                seed_trade_rates = []
                seed_flat = []
                seed_long = []
                seed_short = []
                seed_ls_imbalances = []
                seed_wf_returns = []
                seed_wf_sharpes = []
                seed_wf_avg_drawdowns = []
                seed_wf_worst_drawdowns = []
                seed_wf_trade_rates = []
                seed_wf_pass_rates = []
                seed_wf_segments = []
                print(
                    "Replay candidate:",
                    f"rank={rank}",
                    f"trial={trial.number}",
                    f"base_value={float(trial.value):.6g}",
                    f"seeds={replay_seeds}",
                )
                for seed_idx in range(replay_seeds):
                    total_runs = len(replay_candidates) * replay_seeds
                    current_run = (rank - 1) * replay_seeds + seed_idx + 1
                    seed = 10_000 + rank * 100 + seed_idx
                    print(
                        "Replay progress:",
                        f"run={current_run}/{total_runs}",
                        f"candidate={rank}/{len(replay_candidates)}",
                        f"seed={seed_idx + 1}/{replay_seeds}",
                    )
                    score, profile, walk_forward_profile = _run_candidate(
                        dict(trial.params),
                        total_steps=replay_steps,
                        seed=seed,
                        verbose=0,
                    )
                    progress_parts = [
                        "Replay progress:",
                        f"run={current_run}/{total_runs}",
                        f"score={score:.6g}",
                        f"trades={int(profile['trades'])}",
                        f"flat={profile['flat_ratio']:.3f}",
                    ]
                    if replay_score_mode == "walk_forward":
                        progress_parts.extend(
                            [
                                f"wf_segments={int(walk_forward_profile['segments'])}",
                                f"wf_sharpe={walk_forward_profile['avg_sharpe']:.6g}",
                                f"wf_max_dd={walk_forward_profile['avg_max_drawdown']:.6g}",
                            ]
                        )
                    print(*progress_parts)
                    seed_values.append(score)
                    seed_trades.append(float(profile["trades"]))
                    seed_trade_rates.append(float(profile["trade_rate_1k"]))
                    seed_flat.append(float(profile["flat_ratio"]))
                    seed_long.append(float(profile["long_ratio"]))
                    seed_short.append(float(profile["short_ratio"]))
                    seed_ls_imbalances.append(float(profile["ls_imbalance"]))
                    seed_wf_returns.append(float(walk_forward_profile["avg_return"]))
                    seed_wf_sharpes.append(float(walk_forward_profile["avg_sharpe"]))
                    seed_wf_avg_drawdowns.append(float(walk_forward_profile["avg_max_drawdown"]))
                    seed_wf_worst_drawdowns.append(float(walk_forward_profile["worst_max_drawdown"]))
                    seed_wf_trade_rates.append(float(walk_forward_profile["avg_trade_rate_1k"]))
                    seed_wf_pass_rates.append(float(walk_forward_profile["pass_rate"]))
                    seed_wf_segments.append(float(walk_forward_profile["segments"]))
                    if optuna_fh:
                        mean_val = float(np.mean(seed_values))
                        std_val = float(np.std(seed_values))
                        # Emit replay progress into Optuna CSV stream so the chart updates
                        # while replay is running (not only after each candidate completes).
                        optuna_fh.write(
                            f"replay,{int(trial.number)},{mean_val:.10g},{std_val:.10g}\n"
                        )
                        optuna_fh.flush()
                replay_rows.append(
                    {
                        "rank": rank,
                        "trial": int(trial.number),
                        "optuna_value": float(trial.value),
                        "mean_reward": float(np.mean(seed_values)),
                        "std_reward": float(np.std(seed_values)),
                        "min_reward": float(np.min(seed_values)),
                        "max_reward": float(np.max(seed_values)),
                        "runs": replay_seeds,
                        "steps": replay_steps,
                        "avg_trades": float(np.mean(seed_trades)) if seed_trades else 0.0,
                        "avg_flat_ratio": float(np.mean(seed_flat)) if seed_flat else 1.0,
                        "avg_long_ratio": float(np.mean(seed_long)) if seed_long else 0.0,
                        "avg_short_ratio": float(np.mean(seed_short)) if seed_short else 0.0,
                        "avg_trade_rate_1k": float(np.mean(seed_trade_rates)) if seed_trade_rates else 0.0,
                        "min_trade_rate_1k": float(np.min(seed_trade_rates)) if seed_trade_rates else 0.0,
                        "max_flat_ratio": float(np.max(seed_flat)) if seed_flat else 1.0,
                        "max_ls_imbalance": float(np.max(seed_ls_imbalances)) if seed_ls_imbalances else 0.0,
                        "low_trade_seed_count": (
                            int(sum(1 for rate in seed_trade_rates if rate < replay_min_trade_rate))
                            if seed_trade_rates
                            else 0
                        ),
                        "high_flat_seed_count": (
                            int(sum(1 for flat in seed_flat if flat > replay_max_flat_ratio))
                            if seed_flat
                            else 0
                        ),
                        "high_ls_imbalance_seed_count": (
                            int(sum(1 for imbalance in seed_ls_imbalances if imbalance > replay_max_ls_imbalance))
                            if seed_ls_imbalances
                            else 0
                        ),
                        "wf_segments": float(np.mean(seed_wf_segments)) if seed_wf_segments else 0.0,
                        "wf_pass_rate": float(np.mean(seed_wf_pass_rates)) if seed_wf_pass_rates else 0.0,
                        "wf_avg_return": float(np.mean(seed_wf_returns)) if seed_wf_returns else 0.0,
                        "wf_avg_sharpe": float(np.mean(seed_wf_sharpes)) if seed_wf_sharpes else 0.0,
                        "wf_avg_max_drawdown": (
                            float(np.mean(seed_wf_avg_drawdowns)) if seed_wf_avg_drawdowns else 0.0
                        ),
                        "wf_worst_max_drawdown": (
                            float(np.mean(seed_wf_worst_drawdowns)) if seed_wf_worst_drawdowns else 0.0
                        ),
                        "wf_avg_trade_rate_1k": (
                            float(np.mean(seed_wf_trade_rates)) if seed_wf_trade_rates else 0.0
                        ),
                        "scores": seed_values,
                        "params": dict(trial.params),
                    }
                )
            for row in replay_rows:
                mean_reward = row["mean_reward"]
                std_reward = row["std_reward"]
                min_reward = row["min_reward"]
                avg_flat_ratio = row["avg_flat_ratio"]
                avg_long_ratio = row["avg_long_ratio"]
                avg_short_ratio = row["avg_short_ratio"]
                avg_ls_imbalance = abs(avg_long_ratio - avg_short_ratio)
                avg_trade_rate_1k = row["avg_trade_rate_1k"]
                min_trade_rate_1k = row["min_trade_rate_1k"]
                max_flat_ratio = row["max_flat_ratio"]
                max_ls_imbalance = row["max_ls_imbalance"]
                low_trade_seed_count = row["low_trade_seed_count"]
                high_flat_seed_count = row["high_flat_seed_count"]
                high_ls_imbalance_seed_count = row["high_ls_imbalance_seed_count"]
                wf_segments = row["wf_segments"]
                wf_pass_rate = row["wf_pass_rate"]
                wf_avg_return = row["wf_avg_return"]
                wf_avg_sharpe = row["wf_avg_sharpe"]
                wf_avg_max_drawdown = row["wf_avg_max_drawdown"]
                wf_worst_max_drawdown = row["wf_worst_max_drawdown"]
                rejected = (
                    avg_trade_rate_1k < replay_min_trade_rate
                    or min_trade_rate_1k < replay_min_trade_rate
                    or avg_flat_ratio > replay_max_flat_ratio
                    or max_flat_ratio > replay_max_flat_ratio
                    or avg_ls_imbalance > replay_max_ls_imbalance
                    or max_ls_imbalance > replay_max_ls_imbalance
                )
                reject_reason = ""
                if rejected:
                    if avg_trade_rate_1k < replay_min_trade_rate:
                        reject_reason += (
                            f"low_trade_rate({avg_trade_rate_1k:.3f}<{replay_min_trade_rate:.3f}) "
                        )
                    if min_trade_rate_1k < replay_min_trade_rate:
                        reject_reason += (
                            f" any_seed_low_trade({min_trade_rate_1k:.3f}<{replay_min_trade_rate:.3f};"
                            f" count={low_trade_seed_count})"
                        )
                    if avg_flat_ratio > replay_max_flat_ratio:
                        reject_reason += (
                            f"high_flat({avg_flat_ratio:.3f}>{replay_max_flat_ratio:.3f})"
                        )
                    if max_flat_ratio > replay_max_flat_ratio:
                        reject_reason += (
                            f" any_seed_high_flat({max_flat_ratio:.3f}>{replay_max_flat_ratio:.3f};"
                            f" count={high_flat_seed_count})"
                        )
                    if avg_ls_imbalance > replay_max_ls_imbalance:
                        reject_reason += (
                            f" high_ls_imbalance({avg_ls_imbalance:.3f}>{replay_max_ls_imbalance:.3f})"
                        )
                    if max_ls_imbalance > replay_max_ls_imbalance:
                        reject_reason += (
                            f" any_seed_high_ls_imbalance({max_ls_imbalance:.3f}>{replay_max_ls_imbalance:.3f};"
                            f" count={high_ls_imbalance_seed_count})"
                        )
                if replay_score_mode == "walk_forward" and wf_segments <= 0:
                    rejected = True
                    reject_reason += " missing_walk_forward"
                if replay_score_mode == "reward_only":
                    score = mean_reward
                elif replay_score_mode == "walk_forward":
                    reward_component = mean_reward - 0.5 * std_reward + 0.1 * min_reward
                    # Blend eval reward stability with segmented playback quality.
                    score = (
                        reward_component
                        + 2.0 * wf_avg_sharpe
                        + 0.25 * wf_avg_return
                        - 0.5 * wf_avg_max_drawdown
                        - 0.25 * wf_worst_max_drawdown
                        + 0.1 * wf_pass_rate
                    )
                elif replay_score_mode == "conservative":
                    score = mean_reward - 1.0 * std_reward + 0.3 * min_reward
                else:
                    score = mean_reward - 0.5 * std_reward + 0.1 * min_reward
                row["score_mode"] = replay_score_mode
                row["rejected_activity"] = bool(rejected)
                row["reject_reason"] = reject_reason.strip()
                row["score"] = float(-1e12 if rejected else score)
            replay_rows.sort(key=lambda row: row["score"], reverse=True)
            valid_count = sum(0 if row["rejected_activity"] else 1 for row in replay_rows)
            replay_out = str(args.optuna_replay_out).strip()
            if replay_out:
                replay_path = Path(replay_out).expanduser()
                replay_path.parent.mkdir(parents=True, exist_ok=True)
                replay_path.write_text(
                    json.dumps(
                        {
                            "replay_count": len(replay_rows),
                            "replay_steps": replay_steps,
                            "seeds_per_candidate": replay_seeds,
                            "score_mode": replay_score_mode,
                            "walk_forward_segments": replay_walk_forward_segments,
                            "walk_forward_steps": replay_walk_forward_steps,
                            "walk_forward_stride": replay_walk_forward_stride,
                            "min_trade_rate_1k": replay_min_trade_rate,
                            "max_flat_ratio": replay_max_flat_ratio,
                            "max_ls_imbalance": replay_max_ls_imbalance,
                            "valid_candidates": valid_count,
                            "candidate_count": len(replay_rows),
                            "results": replay_rows,
                        },
                        ensure_ascii=True,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            if replay_rows:
                best_replay = next((row for row in replay_rows if not row["rejected_activity"]), None)
                if best_replay is None:
                    print(
                        "Replay best:",
                        "none",
                        f"mode={replay_score_mode}",
                        f"valid_candidates={valid_count}/{len(replay_rows)}",
                    )
                else:
                    print(
                        "Replay best:",
                        f"trial={best_replay['trial']}",
                        f"score={best_replay['score']:.6g}",
                        f"mode={best_replay['score_mode']}",
                        f"mean_reward={best_replay['mean_reward']:.6g}",
                        f"std={best_replay['std_reward']:.6g}",
                        f"avg_trades={best_replay['avg_trades']:.1f}",
                        f"avg_trade_rate_1k={best_replay['avg_trade_rate_1k']:.3f}",
                        f"avg_ls_imbalance={abs(best_replay['avg_long_ratio'] - best_replay['avg_short_ratio']):.3f}",
                        f"avg_flat={best_replay['avg_flat_ratio']:.3f}",
                    )
                    if replay_score_mode == "walk_forward":
                        print(
                            "Replay walk-forward best:",
                            f"segments={best_replay['wf_segments']:.1f}",
                            f"pass_rate={best_replay['wf_pass_rate']:.3f}",
                            f"avg_return={best_replay['wf_avg_return']:.6g}",
                            f"avg_sharpe={best_replay['wf_avg_sharpe']:.6g}",
                            f"avg_max_dd={best_replay['wf_avg_max_drawdown']:.6g}",
                            f"worst_max_dd={best_replay['wf_worst_max_drawdown']:.6g}",
                        )
                    print(f"Replay best params: {best_replay['params']}")
        if optuna_fh:
            optuna_fh.close()
        if args.optuna_out:
            out_path = Path(args.optuna_out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(best_params, ensure_ascii=True, indent=2))
        if not args.optuna_train_best:
            return
        best_train_config, best_eval_config = _params_to_configs(best_params)
        best_env = _build_env(train_features, train_closes, best_train_config, train_timestamps)
        best_eval_env = _build_env(eval_features, eval_closes, best_eval_config, eval_timestamps)
        final_train_config = best_train_config
        final_eval_config_used = best_eval_config
        model = _train_model(
            env=best_env,
            learning_rate=float(best_params["learning_rate"]),
            n_steps=int(best_params["n_steps"]),
            batch_size=int(best_params["batch_size"]),
            gamma=float(best_params["gamma"]),
            ent_coef=float(best_params["ent_coef"]),
            gae_lambda=float(best_params["gae_lambda"]),
            clip_range=float(best_params["clip_range"]),
            target_kl=(
                None
                if float(best_params.get("target_kl", 0.0)) <= 0.0
                else float(best_params["target_kl"])
            ),
            vf_coef=float(best_params["vf_coef"]),
            n_epochs=int(best_params["n_epochs"]),
            total_steps=args.total_steps,
            window_size=int(best_params.get("window_size", 1)),
            feature_dim=feature_dim,
            device=args.device,
            policy_log_std_init=args.policy_log_std_init,
            verbose=args.verbose,
        )
        model.set_random_seed(args.seed)
        _maybe_run_warm_start(model)
        try:
            _run_training_with_optional_curriculum(
                model,
                total_steps=args.total_steps,
                final_env_ref=best_env,
                final_eval_env_ref=best_eval_env,
                final_eval_config_ref=best_eval_config,
            )
        except KeyboardInterrupt:
            print("Training interrupted by user; saving current checkpoint.")
            _save_interrupted_checkpoint(model, final_train_config)
            if metrics_fh:
                metrics_fh.flush()
                metrics_fh.close()
            if best_model_tmp_dir is not None:
                shutil.rmtree(best_model_tmp_dir, ignore_errors=True)
            if playback_candidate_tmp_dir is not None:
                shutil.rmtree(playback_candidate_tmp_dir, ignore_errors=True)
            raise SystemExit(130) from None
    elif args.resume:
        if not model_path.exists():
            raise FileNotFoundError(f"Resume requested but model not found: {model_path}")
        final_train_config = train_config
        final_eval_config_used = eval_config
        model = PPO.load(str(model_path), env=env, device=args.device)
        print(f"Resolved device: {model.device}")
        model.verbose = args.verbose
        model.set_random_seed(args.seed)
        _maybe_run_warm_start(model)
        try:
            model.learn(
                total_timesteps=args.total_steps,
                callback=_build_callback_list(
                    _make_eval_callback(eval_env, eval_config, collect_playback_candidates=True)
                ),
            )
        except KeyboardInterrupt:
            print("Training interrupted by user; saving current checkpoint.")
            _save_interrupted_checkpoint(model, final_train_config)
            if metrics_fh:
                metrics_fh.flush()
                metrics_fh.close()
            if best_model_tmp_dir is not None:
                shutil.rmtree(best_model_tmp_dir, ignore_errors=True)
            if playback_candidate_tmp_dir is not None:
                shutil.rmtree(playback_candidate_tmp_dir, ignore_errors=True)
            raise SystemExit(130) from None
    else:
        final_train_config = train_config
        final_eval_config_used = eval_config
        model = _train_model(
            env=env,
            learning_rate=args.learning_rate,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            gamma=args.gamma,
            ent_coef=args.ent_coef,
            gae_lambda=args.gae_lambda,
            clip_range=args.clip_range,
            target_kl=None if args.target_kl <= 0.0 else args.target_kl,
            vf_coef=args.vf_coef,
            n_epochs=args.n_epochs,
            total_steps=args.total_steps,
            window_size=args.window_size,
            feature_dim=feature_dim,
            device=args.device,
            policy_log_std_init=args.policy_log_std_init,
            verbose=args.verbose,
        )
        model.set_random_seed(args.seed)
        _maybe_run_warm_start(model)
        try:
            _run_training_with_optional_curriculum(
                model,
                total_steps=args.total_steps,
                final_env_ref=env,
                final_eval_env_ref=eval_env,
                final_eval_config_ref=eval_config,
            )
        except KeyboardInterrupt:
            print("Training interrupted by user; saving current checkpoint.")
            _save_interrupted_checkpoint(model, final_train_config)
            if metrics_fh:
                metrics_fh.flush()
                metrics_fh.close()
            if best_model_tmp_dir is not None:
                shutil.rmtree(best_model_tmp_dir, ignore_errors=True)
            if playback_candidate_tmp_dir is not None:
                shutil.rmtree(playback_candidate_tmp_dir, ignore_errors=True)
            raise SystemExit(130) from None

    model_to_save = model
    checkpoint_selection_payload: dict[str, object] = {
        "selection_mode": "best_eval_fallback",
        "output_model_path": str(model_path),
        "candidate_count": 0,
        "selected_source": "final_state",
        "candidates": [],
    }
    if args.save_best_checkpoint and best_model_tmp_dir is not None:
        best_model_path = best_model_tmp_dir / "best_model.zip"
        if best_model_path.exists():
            model_to_save = PPO.load(str(best_model_path))
            print(f"Using best eval checkpoint: {best_model_path}")
            checkpoint_selection_payload.update(
                {
                    "selected_source": "best_eval",
                    "selected_checkpoint_path": str(best_model_path),
                }
            )
        else:
            print("Best eval checkpoint not found; falling back to final model state.")
    if args.save_best_checkpoint and playback_candidate_tmp_dir is not None:
        final_stage_callbacks = [callback for callback in eval_callbacks if callback.get_playback_candidates()]
        playback_candidates = final_stage_callbacks[-1].get_playback_candidates() if final_stage_callbacks else []
        playback_summary = _evaluate_playback_candidates(
            playback_candidates,
            features=eval_features,
            closes=eval_closes,
            timestamps=eval_timestamps,
            config=final_eval_config_used,
            device=args.device,
            replay_policy=replay_policy_eval,
        )
        checkpoint_selection_payload.update(
            {
                "selection_mode": "playback_top_n",
                "top_n": 5,
                "candidate_count": int(playback_summary.get("candidate_count", 0)),
                "candidates": playback_summary.get("candidates", []),
            }
        )
        selected = playback_summary.get("selected")
        if isinstance(selected, dict):
            selected_path = str(selected.get("path") or "").strip()
            selected_step = selected.get("step")
            selected_playback = selected.get("playback")
            if selected_path and Path(selected_path).exists() and isinstance(selected_playback, dict):
                model_to_save = PPO.load(selected_path)
                checkpoint_selection_payload.update(
                    {
                        "selected_source": "playback_top_n",
                        "selected_checkpoint_path": selected_path,
                        "selected_step": selected_step,
                        "selected_eval_mean_reward": selected.get("eval_mean_reward"),
                        "selected_checkpoint_gate": selected.get("checkpoint_gate"),
                        "selected_playback": selected_playback if isinstance(selected_playback, dict) else {},
                    }
                )
                print(
                    "Using best playback checkpoint:",
                    f"step={selected_step}",
                    f"path={selected_path}",
                    f"return={float((selected_playback or {}).get('total_return', 0.0)):.6g}",
                    f"sharpe={float((selected_playback or {}).get('sharpe', 0.0)):.6g}",
                )

    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_to_save.save(str(model_path))
    checkpoint_selection_payload["output_model_path"] = str(model_path)
    _save_checkpoint_selection(checkpoint_selection_path, checkpoint_selection_payload)
    save_trading_config(
        final_train_config,
        env_config_path,
        extra=_extract_data_context(args.data),
    )
    stopped_early, stop_reason, last_step = _resolve_callback_status()
    _save_training_status(
        training_status_path,
        status="stopped_early" if stopped_early else "completed",
        stop_reason=stop_reason,
        exit_code=0,
        stopped_early=stopped_early,
        total_steps_target=int(args.total_steps),
        last_step=last_step,
    )
    if metrics_fh:
        metrics_fh.flush()
        metrics_fh.close()
    if best_model_tmp_dir is not None:
        shutil.rmtree(best_model_tmp_dir, ignore_errors=True)
    if playback_candidate_tmp_dir is not None:
        shutil.rmtree(playback_candidate_tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
