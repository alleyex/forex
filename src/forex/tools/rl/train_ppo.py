from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, EvalCallback
from stable_baselines3.common.evaluation import evaluate_policy

from forex.ml.rl.envs.trading_env import TradingConfig, TradingEnv
from forex.ml.rl.envs.trading_config_io import save_trading_config
from forex.ml.rl.features.feature_builder import (
    apply_scaler,
    build_feature_frame,
    fit_scaler,
    load_csv,
    save_scaler,
)
from forex.config.paths import DEFAULT_MODEL_PATH


def _build_env(features, closes, config: TradingConfig) -> DummyVecEnv:
    return DummyVecEnv([lambda: Monitor(TradingEnv(features, closes, config))])


class MetricsLogCallback(BaseCallback):
    def __init__(self, write_metric, verbose: int = 0) -> None:
        super().__init__(verbose=verbose)
        self._write_metric = write_metric

    def _on_step(self) -> bool:
        step = int(self.num_timesteps)
        for info in self.locals.get("infos", []):
            metrics = info.get("episode")
            if not metrics:
                continue
            if "r" in metrics:
                self._write_metric(step, "ep_rew_mean", float(metrics["r"]))
        return True

    def _on_rollout_end(self) -> None:
        step = int(self.num_timesteps)
        mean_reward = self.logger.name_to_value.get("rollout/ep_rew_mean")
        if mean_reward is not None:
            self._write_metric(step, "ep_rew_mean", float(mean_reward))


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
    vf_coef: float,
    n_epochs: int,
    total_steps: int,
    verbose: int = 1,
) -> PPO:
    model = PPO(
        "MlpPolicy",
        env,
        verbose=verbose,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
        gamma=gamma,
        ent_coef=ent_coef,
        gae_lambda=gae_lambda,
        clip_range=clip_range,
        vf_coef=vf_coef,
        n_epochs=n_epochs,
    )
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


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        # Ensure progress logs are flushed promptly when running under QProcess pipes.
        sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description="Train PPO on forex history with an MLP policy.")
    parser.add_argument("--data", required=True, help="Path to raw history CSV.")
    parser.add_argument("--total-steps", type=int, default=200_000, help="Total PPO timesteps.")
    parser.add_argument("--learning-rate", type=float, default=3e-4, help="PPO learning rate.")
    parser.add_argument("--gamma", type=float, default=0.99, help="PPO discount factor.")
    parser.add_argument("--n-steps", type=int, default=2048, help="PPO rollout steps per update.")
    parser.add_argument("--batch-size", type=int, default=64, help="PPO minibatch size.")
    parser.add_argument("--ent-coef", type=float, default=0.0, help="Entropy coefficient.")
    parser.add_argument("--gae-lambda", type=float, default=0.95, help="PPO GAE lambda.")
    parser.add_argument("--clip-range", type=float, default=0.2, help="PPO clip range.")
    parser.add_argument("--vf-coef", type=float, default=0.5, help="PPO value function coefficient.")
    parser.add_argument("--n-epochs", type=int, default=10, help="PPO epochs per update.")
    parser.add_argument("--episode-length", type=int, default=2048, help="Episode length in bars.")
    parser.add_argument("--eval-split", type=float, default=0.2, help="Eval split (fraction from tail).")
    parser.add_argument("--eval-freq", type=int, default=10_000, help="Eval frequency in timesteps.")
    parser.add_argument("--eval-episodes", type=int, default=5, help="Eval episodes per evaluation.")
    parser.add_argument("--transaction-cost-bps", type=float, default=1.0, help="Transaction cost in bps.")
    parser.add_argument("--slippage-bps", type=float, default=0.5, help="Slippage in bps.")
    parser.add_argument("--holding-cost-bps", type=float, default=0.0, help="Holding cost in bps per step.")
    parser.add_argument("--no-random-start", action="store_true", help="Disable random episode starts.")
    parser.add_argument("--min-position-change", type=float, default=0.0, help="Minimum position change.")
    parser.add_argument("--discretize-actions", action="store_true", help="Snap actions to discrete positions.")
    parser.add_argument(
        "--discrete-positions",
        default="-1,0,1",
        help="Comma-separated discrete positions (e.g. -1,0,1).",
    )
    parser.add_argument("--max-position", type=float, default=1.0, help="Maximum absolute position size.")
    parser.add_argument("--position-step", type=float, default=0.0, help="Position step size (0 disables).")
    parser.add_argument("--reward-scale", type=float, default=1.0, help="Scale reward by this factor.")
    parser.add_argument("--reward-clip", type=float, default=0.0, help="Clip reward to +/- value (0 disables).")
    parser.add_argument("--risk-aversion", type=float, default=0.0, help="Penalty for variance of PnL.")
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
        choices=["reward_only", "risk_adjusted", "conservative"],
        default="risk_adjusted",
        help="Scoring mode for replay candidate ranking.",
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
        default=0.5,
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
        "--feature-scaler-out",
        default="",
        help="Optional JSON path to save feature scaler (default: model_out with .scaler.json).",
    )
    parser.add_argument(
        "--env-config-out",
        default="",
        help="Optional JSON path to save TradingConfig (default: model_out with .env.json).",
    )
    parser.add_argument("--resume", action="store_true", help="Resume training from existing model.")
    args = parser.parse_args()

    df = load_csv(args.data)
    features_frame, closes, _timestamps = build_feature_frame(df)
    total_rows = len(features_frame)
    eval_size = int(total_rows * args.eval_split)
    if eval_size < 1 or total_rows - eval_size < 1:
        raise ValueError("Not enough data for train/eval split.")
    split_idx = total_rows - eval_size

    train_frame = features_frame.iloc[:split_idx]
    eval_frame = features_frame.iloc[split_idx:]
    train_closes = closes.iloc[:split_idx].to_numpy(dtype=np.float32)
    eval_closes = closes.iloc[split_idx:].to_numpy(dtype=np.float32)

    scaler = fit_scaler(train_frame)
    train_features = apply_scaler(train_frame, scaler).to_numpy(dtype=np.float32)
    eval_features = apply_scaler(eval_frame, scaler).to_numpy(dtype=np.float32)

    scaler_path = args.feature_scaler_out.strip()
    if not scaler_path:
        scaler_path = str(Path(args.model_out).with_suffix(".scaler.json"))
    scaler_path = str(Path(scaler_path).expanduser())
    scaler_dir = Path(scaler_path).parent
    scaler_dir.mkdir(parents=True, exist_ok=True)
    save_scaler(scaler, scaler_path)

    random_start = not args.no_random_start
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
        min_position_change=args.min_position_change,
        discretize_actions=args.discretize_actions,
        discrete_positions=discrete_positions,
        max_position=args.max_position,
        position_step=args.position_step,
        reward_scale=args.reward_scale,
        reward_clip=args.reward_clip,
        risk_aversion=args.risk_aversion,
    )
    eval_config = TradingConfig(
        episode_length=args.episode_length,
        transaction_cost_bps=args.transaction_cost_bps,
        slippage_bps=args.slippage_bps,
        holding_cost_bps=args.holding_cost_bps,
        random_start=False,
        min_position_change=args.min_position_change,
        discretize_actions=args.discretize_actions,
        discrete_positions=discrete_positions,
        max_position=args.max_position,
        position_step=args.position_step,
        reward_scale=args.reward_scale,
        reward_clip=args.reward_clip,
        risk_aversion=args.risk_aversion,
    )

    env_config_path = args.env_config_out.strip()
    if not env_config_path:
        env_config_path = str(Path(args.model_out).with_suffix(".env.json"))
    env_config_path = str(Path(env_config_path).expanduser())
    env_dir = Path(env_config_path).parent
    env_dir.mkdir(parents=True, exist_ok=True)
    save_trading_config(
        train_config,
        env_config_path,
        extra=_extract_data_context(args.data),
    )

    env = _build_env(train_features, train_closes, train_config)
    eval_env = _build_env(eval_features, eval_closes, eval_config)

    model_path = Path(args.model_out)
    print(
        "Training setup:",
        f"rows={total_rows}",
        f"train={len(train_features)}",
        f"eval={len(eval_features)}",
        f"total_steps={args.total_steps}",
        f"resume={args.resume}",
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
        if metrics_counter % (metrics_log_every * 10) == 0:
            metrics_fh.flush()

    metrics_callback = MetricsLogCallback(_write_metric)

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
            "vf_coef",
            "n_epochs",
            "min_position_change",
            "position_step",
            "risk_aversion",
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

        def objective(trial: "optuna.Trial") -> float:
            n_steps = trial.suggest_categorical("n_steps", [256, 512, 1024, 2048])
            batch_sizes = [32, 64, 128, 256]
            batch_sizes = [size for size in batch_sizes if size <= n_steps]
            batch_size = trial.suggest_categorical("batch_size", batch_sizes)
            learning_rate = trial.suggest_float("learning_rate", 1e-5, 1e-3, log=True)
            gamma = trial.suggest_float("gamma", 0.9, 0.9999)
            ent_coef = trial.suggest_float("ent_coef", 1e-6, 1e-2, log=True)
            gae_lambda = trial.suggest_float("gae_lambda", 0.90, 0.99)
            clip_range = trial.suggest_float("clip_range", 0.10, 0.30)
            vf_coef = trial.suggest_float("vf_coef", 0.10, 1.00)
            n_epochs = trial.suggest_categorical("n_epochs", [5, 10, 20])
            min_position_change = trial.suggest_float("min_position_change", 0.0, 0.2, step=0.01)
            position_step = trial.suggest_categorical("position_step", [0.0, 0.05, 0.1, 0.2])
            risk_aversion = trial.suggest_float("risk_aversion", 0.0, 0.3, step=0.01)
            max_position = trial.suggest_categorical("max_position", [0.5, 1.0, 1.5, 2.0])
            episode_length = trial.suggest_categorical("episode_length", [256, 512, 1024, 2048])
            reward_clip = trial.suggest_categorical("reward_clip", [0.0, 0.005, 0.01, 0.02])

            trial_train_config = _clone_config(
                train_config,
                episode_length=episode_length,
                min_position_change=min_position_change,
                position_step=position_step,
                risk_aversion=risk_aversion,
                max_position=max_position,
                reward_clip=reward_clip,
            )
            trial_eval_config = _clone_config(
                eval_config,
                episode_length=episode_length,
                min_position_change=min_position_change,
                position_step=position_step,
                risk_aversion=risk_aversion,
                max_position=max_position,
                reward_clip=reward_clip,
            )
            trial_env = _build_env(train_features, train_closes, trial_train_config)
            trial_eval_env = _build_env(eval_features, eval_closes, trial_eval_config)

            model = _train_model(
                env=trial_env,
                learning_rate=learning_rate,
                n_steps=n_steps,
                batch_size=batch_size,
                gamma=gamma,
                ent_coef=ent_coef,
                gae_lambda=gae_lambda,
                clip_range=clip_range,
                vf_coef=vf_coef,
                n_epochs=n_epochs,
                total_steps=args.optuna_steps,
                verbose=0,
            )
            model.learn(
                total_timesteps=args.optuna_steps,
                callback=CallbackList([metrics_callback]),
            )
            mean_reward, _ = evaluate_policy(
                model,
                trial_eval_env,
                n_eval_episodes=args.eval_episodes,
                deterministic=True,
            )
            trial_env.close()
            trial_eval_env.close()
            return float(mean_reward)

        def _log_optuna_trial(study: "optuna.Study", trial: "optuna.Trial") -> None:
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
                risk_aversion=float(params["risk_aversion"]),
                max_position=float(params["max_position"]),
                reward_clip=float(params["reward_clip"]),
            )
            eval_cfg = _clone_config(
                eval_config,
                episode_length=int(params["episode_length"]),
                min_position_change=float(params["min_position_change"]),
                position_step=float(params["position_step"]),
                risk_aversion=float(params["risk_aversion"]),
                max_position=float(params["max_position"]),
                reward_clip=float(params["reward_clip"]),
            )
            return train_cfg, eval_cfg

        def _profile_policy(model: PPO, features: np.ndarray, config: TradingConfig) -> dict[str, float]:
            position = 0.0
            trades = 0
            action_long = 0
            action_short = 0
            action_flat = 0
            total_steps = max(0, len(features) - 1)
            for idx in range(total_steps):
                denom = max(1e-6, float(config.max_position) if config.max_position else 1.0)
                obs = np.concatenate(
                    [features[idx], np.array([position / denom], dtype=np.float32)]
                ).astype(np.float32)
                action, _ = model.predict(obs, deterministic=True)
                target = float(np.clip(float(action[0]), -config.max_position, config.max_position))
                if config.discretize_actions and config.discrete_positions:
                    target = min(config.discrete_positions, key=lambda v: abs(float(v) - target))
                if config.position_step > 0.0:
                    target = round(target / config.position_step) * config.position_step
                if config.max_position > 0.0:
                    target = float(np.clip(target, -config.max_position, config.max_position))
                if abs(target - position) < config.min_position_change:
                    target = float(position)
                if abs(target - position) > 1e-12:
                    trades += 1
                if target > 0.05:
                    action_long += 1
                elif target < -0.05:
                    action_short += 1
                else:
                    action_flat += 1
                position = target
            total_actions = max(1, action_long + action_short + action_flat)
            return {
                "trades": float(trades),
                "flat_ratio": float(action_flat / total_actions),
                "long_ratio": float(action_long / total_actions),
                "short_ratio": float(action_short / total_actions),
            }

        def _run_candidate(
            params: dict, *, total_steps: int, seed: int, verbose: int
        ) -> tuple[float, dict[str, float]]:
            cand_train_cfg, cand_eval_cfg = _params_to_configs(params)
            cand_env = _build_env(train_features, train_closes, cand_train_cfg)
            cand_eval_env = _build_env(eval_features, eval_closes, cand_eval_cfg)
            model = _train_model(
                env=cand_env,
                learning_rate=float(params["learning_rate"]),
                n_steps=int(params["n_steps"]),
                batch_size=int(params["batch_size"]),
                gamma=float(params["gamma"]),
                ent_coef=float(params["ent_coef"]),
                gae_lambda=float(params["gae_lambda"]),
                clip_range=float(params["clip_range"]),
                vf_coef=float(params["vf_coef"]),
                n_epochs=int(params["n_epochs"]),
                total_steps=total_steps,
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
            profile = _profile_policy(model, eval_features, cand_eval_cfg)
            cand_env.close()
            cand_eval_env.close()
            return float(mean_reward), profile

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
            replay_rows = []
            for rank, trial in enumerate(replay_candidates, start=1):
                seed_values = []
                seed_trades = []
                seed_flat = []
                seed_long = []
                seed_short = []
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
                    score, profile = _run_candidate(
                        dict(trial.params),
                        total_steps=replay_steps,
                        seed=seed,
                        verbose=0,
                    )
                    print(
                        "Replay progress:",
                        f"run={current_run}/{total_runs}",
                        f"score={score:.6g}",
                        f"trades={int(profile['trades'])}",
                        f"flat={profile['flat_ratio']:.3f}",
                    )
                    seed_values.append(score)
                    seed_trades.append(float(profile["trades"]))
                    seed_flat.append(float(profile["flat_ratio"]))
                    seed_long.append(float(profile["long_ratio"]))
                    seed_short.append(float(profile["short_ratio"]))
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
                        "avg_trade_rate_1k": (
                            float(np.mean(seed_trades)) * 1000.0 / max(1.0, float(len(eval_features) - 1))
                        ),
                        "scores": seed_values,
                        "params": dict(trial.params),
                    }
                )
            for row in replay_rows:
                mean_reward = row["mean_reward"]
                std_reward = row["std_reward"]
                min_reward = row["min_reward"]
                avg_trades = row["avg_trades"]
                avg_flat_ratio = row["avg_flat_ratio"]
                avg_long_ratio = row["avg_long_ratio"]
                avg_short_ratio = row["avg_short_ratio"]
                avg_ls_imbalance = abs(avg_long_ratio - avg_short_ratio)
                avg_trade_rate_1k = row["avg_trade_rate_1k"]
                rejected = (
                    avg_trade_rate_1k < replay_min_trade_rate
                    or avg_flat_ratio > replay_max_flat_ratio
                    or avg_ls_imbalance > replay_max_ls_imbalance
                )
                reject_reason = ""
                if rejected:
                    if avg_trade_rate_1k < replay_min_trade_rate:
                        reject_reason += (
                            f"low_trade_rate({avg_trade_rate_1k:.3f}<{replay_min_trade_rate:.3f}) "
                        )
                    if avg_flat_ratio > replay_max_flat_ratio:
                        reject_reason += (
                            f"high_flat({avg_flat_ratio:.3f}>{replay_max_flat_ratio:.3f})"
                        )
                    if avg_ls_imbalance > replay_max_ls_imbalance:
                        reject_reason += (
                            f" high_ls_imbalance({avg_ls_imbalance:.3f}>{replay_max_ls_imbalance:.3f})"
                        )
                if replay_score_mode == "reward_only":
                    score = mean_reward
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
                best_replay = next((row for row in replay_rows if not row["rejected_activity"]), replay_rows[0])
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
        save_trading_config(
            best_train_config,
            env_config_path,
            extra=_extract_data_context(args.data),
        )
        best_env = _build_env(train_features, train_closes, best_train_config)
        best_eval_env = _build_env(eval_features, eval_closes, best_eval_config)
        model = _train_model(
            env=best_env,
            learning_rate=float(best_params["learning_rate"]),
            n_steps=int(best_params["n_steps"]),
            batch_size=int(best_params["batch_size"]),
            gamma=float(best_params["gamma"]),
            ent_coef=float(best_params["ent_coef"]),
            gae_lambda=float(best_params["gae_lambda"]),
            clip_range=float(best_params["clip_range"]),
            vf_coef=float(best_params["vf_coef"]),
            n_epochs=int(best_params["n_epochs"]),
            total_steps=args.total_steps,
            verbose=args.verbose,
        )
        eval_callback = EvalCallback(
            best_eval_env,
            eval_freq=args.eval_freq,
            n_eval_episodes=args.eval_episodes,
            deterministic=True,
        )
        model.learn(
            total_timesteps=args.total_steps,
            callback=CallbackList([eval_callback, metrics_callback]),
        )
    elif args.resume:
        if not model_path.exists():
            raise FileNotFoundError(f"Resume requested but model not found: {model_path}")
        model = PPO.load(str(model_path), env=env)
        model.verbose = args.verbose
        eval_callback = EvalCallback(
            eval_env,
            eval_freq=args.eval_freq,
            n_eval_episodes=args.eval_episodes,
            deterministic=True,
        )
        model.learn(
            total_timesteps=args.total_steps,
            callback=CallbackList([eval_callback, metrics_callback]),
        )
    else:
        model = _train_model(
            env=env,
            learning_rate=args.learning_rate,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            gamma=args.gamma,
            ent_coef=args.ent_coef,
            gae_lambda=args.gae_lambda,
            clip_range=args.clip_range,
            vf_coef=args.vf_coef,
            n_epochs=args.n_epochs,
            total_steps=args.total_steps,
            verbose=args.verbose,
        )
        eval_callback = EvalCallback(
            eval_env,
            eval_freq=args.eval_freq,
            n_eval_episodes=args.eval_episodes,
            deterministic=True,
        )
        model.learn(
            total_timesteps=args.total_steps,
            callback=CallbackList([eval_callback, metrics_callback]),
        )

    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_path))
    if metrics_fh:
        metrics_fh.flush()
        metrics_fh.close()


if __name__ == "__main__":
    main()
