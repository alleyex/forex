from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class UIParamsStore:
    """Persistence helper for training/simulation UI params."""

    _CURRENT_PATHS = {
        "training": Path("data/training/training_params.json"),
        "simulation": Path("data/simulation/simulation_params.json"),
    }
    _LEGACY_PATHS = {
        "training": (
            Path("data/optuna/training_params.json"),
            Path("data/settings/ui_params.json"),
        ),
        "simulation": (
            Path("data/optuna/training_params.json"),
            Path("data/settings/ui_params.json"),
        ),
    }
    _LEGACY_KEYS = {
        "training": {
            "data_path",
            "total_steps",
            "learning_rate",
            "gamma",
            "n_steps",
            "batch_size",
            "ent_coef",
            "gae_lambda",
            "clip_range",
            "target_kl",
            "device",
            "vf_coef",
            "n_epochs",
            "episode_length",
            "eval_split",
            "save_best_checkpoint",
            "transaction_cost_bps",
            "slippage_bps",
            "holding_cost_bps",
            "random_start",
            "start_mode",
            "min_position_change",
            "max_position",
            "position_step",
            "reward_horizon",
            "window_size",
            "reward_scale",
            "reward_clip",
            "reward_mode",
            "risk_aversion",
            "drawdown_penalty",
            "downside_penalty",
            "target_vol",
            "vol_target_lookback",
            "vol_scale_floor",
            "vol_scale_cap",
            "drawdown_governor_slope",
            "drawdown_governor_floor",
            "early_stop_enabled",
            "early_stop_warmup_steps",
            "early_stop_patience_evals",
            "early_stop_min_delta",
            "optuna_trials",
            "optuna_steps",
            "optuna_auto_select",
            "optuna_select_mode",
            "optuna_top_k",
            "optuna_top_percent",
            "optuna_min_candidates",
            "optuna_top_out",
            "optuna_replay_enabled",
            "optuna_replay_steps",
            "optuna_replay_seeds",
            "optuna_replay_score_mode",
            "optuna_replay_min_trade_rate",
            "optuna_replay_max_flat_ratio",
            "optuna_replay_max_ls_imbalance",
            "optuna_replay_out",
            "optuna_out",
            "resume",
            "optuna_train_best",
            "discretize_actions",
            "discrete_positions",
        },
        "simulation": {
            "data",
            "model",
            "log_every",
            "max_steps",
            "transaction_cost_bps",
            "slippage_bps",
        },
    }

    def __init__(self, section: str) -> None:
        self._section = section

    def load(self) -> dict[str, Any]:
        current_path = self._current_path()
        payload = self._load_section_from_path(current_path)
        if payload is not None:
            return payload

        for path in self._LEGACY_PATHS.get(self._section, ()):
            payload = self._load_section_from_path(path)
            if payload is not None:
                return payload
        return {}

    def save(self, params: dict[str, Any]) -> None:
        path = self._current_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            path.write_text(json.dumps(dict(params), ensure_ascii=True, indent=2), encoding="utf-8")
        except OSError:
            return

    def _current_path(self) -> Path:
        return self._CURRENT_PATHS[self._section]

    def _load_section_from_path(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return self._extract_section(loaded)

    def _extract_section(self, payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None

        nested = payload.get(self._section)
        if isinstance(nested, dict):
            allowed = self._LEGACY_KEYS.get(self._section, set())
            nested_filtered = {
                key: value
                for key, value in nested.items()
                if not allowed or key in allowed
            }
            merged = dict(self._extract_legacy_section(payload))
            merged.update(nested_filtered)
            return merged

        if self._section == "training" and self._looks_like_training(payload):
            return payload
        if self._section == "simulation" and self._looks_like_simulation(payload):
            return payload
        return None

    def _extract_legacy_section(self, payload: dict[str, Any]) -> dict[str, Any]:
        allowed = self._LEGACY_KEYS.get(self._section, set())
        return {
            key: value
            for key, value in payload.items()
            if key in allowed and not isinstance(value, dict)
        }

    @staticmethod
    def _looks_like_training(payload: dict[str, Any]) -> bool:
        markers = ("data_path", "total_steps", "learning_rate", "transaction_cost_bps")
        return any(marker in payload for marker in markers)

    @staticmethod
    def _looks_like_simulation(payload: dict[str, Any]) -> bool:
        markers = ("data", "model", "log_every", "max_steps")
        return any(marker in payload for marker in markers)
