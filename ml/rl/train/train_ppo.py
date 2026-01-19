from __future__ import annotations

import argparse
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import EvalCallback

from ml.rl.envs.trading_env import TradingConfig, TradingEnv
from ml.rl.features.feature_builder import build_features, load_csv


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
    parser.add_argument("--model-out", default="ml/rl/models/ppo_forex.zip", help="Output model path.")
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

    train_config = TradingConfig(episode_length=args.episode_length)
    eval_config = TradingConfig(episode_length=args.episode_length, random_start=False)
    env = DummyVecEnv([lambda: Monitor(TradingEnv(train_features, train_closes, train_config))])
    eval_env = DummyVecEnv([lambda: Monitor(TradingEnv(eval_features, eval_closes, eval_config))])

    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=args.learning_rate,
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        gamma=args.gamma,
        ent_coef=args.ent_coef,
    )
    eval_callback = EvalCallback(
        eval_env,
        eval_freq=args.eval_freq,
        n_eval_episodes=args.eval_episodes,
        deterministic=True,
    )
    model.learn(total_timesteps=args.total_steps, callback=eval_callback)

    model_path = Path(args.model_out)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_path))


if __name__ == "__main__":
    main()
