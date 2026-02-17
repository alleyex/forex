from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from forex.ml.rl.envs.trading_env import TradingConfig


def save_trading_config(
    config: TradingConfig,
    path: str | Path,
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = asdict(config)
    payload["discrete_positions"] = list(config.discrete_positions)
    if extra:
        payload.update(extra)
    Path(path).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def load_trading_config(path: str | Path) -> TradingConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Trading config must be a JSON object.")
    kwargs: dict[str, Any] = {}
    defaults = TradingConfig()
    for key, default_value in asdict(defaults).items():
        if key not in data:
            continue
        value = data[key]
        if key == "discrete_positions":
            if isinstance(value, (list, tuple)):
                kwargs[key] = tuple(float(item) for item in value)
            elif isinstance(value, str):
                kwargs[key] = tuple(
                    float(item)
                    for item in (part.strip() for part in value.split(","))
                    if item
                )
            continue
        if isinstance(default_value, bool):
            kwargs[key] = bool(value)
        elif isinstance(default_value, int):
            kwargs[key] = int(value)
        elif isinstance(default_value, float):
            kwargs[key] = float(value)
        else:
            kwargs[key] = value
    return TradingConfig(**kwargs)
