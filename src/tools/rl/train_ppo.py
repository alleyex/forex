from __future__ import annotations

import argparse
import json
from pathlib import Path
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, EvalCallback
from stable_baselines3.common.evaluation import evaluate_policy

from ml.rl.envs.trading_env import TradingConfig, TradingEnv
from ml.rl.features.feature_builder import build_features, load_csv
from config.paths import DEFAULT_MODEL_PATH


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
    )
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description="Train PPO on forex history with an MLP policy.")
    parser.add_argument("--data", required=True, help="Path to raw history CSV.")
    parser.add_argument("--total-steps", type=int, default=200_000, help="Total PPO timesteps.")
    parser.add_argument("--learning-rate", type=float, default=3e-4, help="PPO learning rate.")
    parser.add_argument("--gamma", type=float, default=0.99, help="PPO discount factor.")
    parser.add_argument("--n-steps", type=int, default=2048, help="PPO rollout steps per update.")
    parser.add_argument("--batch-size", type=int, default=64, help="PPO minibatch size.")
    parser.add_argument("--ent-coef", type=float, default=0.0, help="Entropy coefficient.")
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
    parser.add_argument("--optuna-out", default="", help="Optional JSON path for best Optuna params.")
    parser.add_argument("--optuna-log", default="", help="Optional CSV path to log Optuna trials.")
    parser.add_argument("--model-out", default=DEFAULT_MODEL_PATH, help="Output model path.")
    parser.add_argument("--resume", action="store_true", help="Resume training from existing model.")
    args = parser.parse_args()

    df = load_csv(args.data)
    feature_set = build_features(df)

    total_rows = len(feature_set.features)
    eval_size = int(total_rows * args.eval_split)
    if eval_size < 1 or total_rows - eval_size < 1:
        raise ValueError("Not enough data for train/eval split.")
    split_idx = total_rows - eval_size

    train_features = feature_set.features[:split_idx]
    train_closes = feature_set.closes[:split_idx]
    eval_features = feature_set.features[split_idx:]
    eval_closes = feature_set.closes[split_idx:]

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

        def objective(trial: "optuna.Trial") -> float:
            n_steps = trial.suggest_categorical("n_steps", [256, 512, 1024, 2048])
            batch_sizes = [32, 64, 128, 256]
            batch_sizes = [size for size in batch_sizes if size <= n_steps]
            batch_size = trial.suggest_categorical("batch_size", batch_sizes)
            learning_rate = trial.suggest_float("learning_rate", 1e-5, 1e-3, log=True)
            gamma = trial.suggest_float("gamma", 0.9, 0.9999)
            ent_coef = trial.suggest_float("ent_coef", 1e-6, 1e-2, log=True)

            model = _train_model(
                env=_build_env(train_features, train_closes, train_config),
                learning_rate=learning_rate,
                n_steps=n_steps,
                batch_size=batch_size,
                gamma=gamma,
                ent_coef=ent_coef,
                total_steps=args.optuna_steps,
                verbose=0,
            )
            model.learn(
                total_timesteps=args.optuna_steps,
                callback=CallbackList([metrics_callback]),
            )
            mean_reward, _ = evaluate_policy(
                model,
                eval_env,
                n_eval_episodes=args.eval_episodes,
                deterministic=True,
            )
            return float(mean_reward)

        def _log_optuna_trial(study: "optuna.Study", trial: "optuna.Trial") -> None:
            if not optuna_fh or trial.value is None:
                return
            duration = trial.duration.total_seconds() if trial.duration else 0.0
            optuna_fh.write(
                f"{trial.number},{float(trial.value):.10g},{float(study.best_value):.10g},{duration:.6f}\n"
            )
            optuna_fh.flush()

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=args.optuna_trials, callbacks=[_log_optuna_trial])
        best_params = study.best_trial.params
        print(f"Optuna best value: {study.best_value:.6f}")
        print(f"Optuna best params: {best_params}")
        if optuna_fh:
            optuna_fh.close()
        if args.optuna_out:
            out_path = Path(args.optuna_out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(best_params, ensure_ascii=True, indent=2))
        if not args.optuna_train_best:
            return
        model = _train_model(
            env=env,
            learning_rate=float(best_params["learning_rate"]),
            n_steps=int(best_params["n_steps"]),
            batch_size=int(best_params["batch_size"]),
            gamma=float(best_params["gamma"]),
            ent_coef=float(best_params["ent_coef"]),
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
