from __future__ import annotations

from forex.ml.rl.envs.trading_config_io import load_trading_config, save_trading_config
from forex.ml.rl.envs.trading_env import TradingConfig


def test_trading_config_io_roundtrip(tmp_path) -> None:
    config = TradingConfig(
        transaction_cost_bps=1.5,
        slippage_bps=0.7,
        holding_cost_bps=0.2,
        episode_length=1024,
        random_start=False,
        min_position_change=0.05,
        discretize_actions=True,
        discrete_positions=(-1.0, -0.5, 0.0, 0.5, 1.0),
        max_position=1.5,
        position_step=0.1,
        reward_scale=2.0,
        reward_clip=0.8,
        risk_aversion=0.3,
    )
    path = tmp_path / "ppo.env.json"
    save_trading_config(config, path)
    loaded = load_trading_config(path)
    assert loaded == config


def test_trading_config_io_extra_fields_preserved_and_ignored_by_loader(tmp_path) -> None:
    config = TradingConfig()
    path = tmp_path / "ppo.env.json"
    save_trading_config(
        config,
        path,
        extra={
            "symbol_id": 1,
            "timeframe": "M15",
        },
    )
    payload = path.read_text(encoding="utf-8")
    assert '"symbol_id": 1' in payload
    assert '"timeframe": "M15"' in payload
    loaded = load_trading_config(path)
    assert loaded == config
