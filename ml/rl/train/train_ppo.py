from __future__ import annotations

import argparse
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

from ml.rl.envs.trading_env import TradingConfig, TradingEnv
from ml.rl.features.feature_builder import build_features, load_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Train PPO on forex history with an MLP policy.")
    parser.add_argument("--data", required=True, help="Path to raw history CSV.")
    parser.add_argument("--total-steps", type=int, default=200_000, help="Total PPO timesteps.")
    parser.add_argument("--episode-length", type=int, default=2048, help="Episode length in bars.")
    parser.add_argument("--model-out", default="ml/rl/models/ppo_forex.zip", help="Output model path.")
    args = parser.parse_args()

    df = load_csv(args.data)
    feature_set = build_features(df)

    config = TradingConfig(episode_length=args.episode_length)
    env = DummyVecEnv([lambda: TradingEnv(feature_set.features, feature_set.closes, config)])

    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        gamma=0.99,
        ent_coef=0.0,
    )
    model.learn(total_timesteps=args.total_steps)

    model_path = Path(args.model_out)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_path))


if __name__ == "__main__":
    main()
