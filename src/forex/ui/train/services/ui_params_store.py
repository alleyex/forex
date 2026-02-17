from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class UIParamsStore:
    """Persistence helper for training/simulation UI params."""

    _CURRENT_PATH = Path("data/optuna/training_params.json")
    _LEGACY_PATHS = (
        Path("data/settings/ui_params.json"),
        Path("data/simulation/simulation_params.json"),
    )
    _SCHEMA_VERSION = 1

    def __init__(self, section: str) -> None:
        self._section = section

    def load(self) -> dict[str, Any]:
        payload = self._load_section_from_path(self._CURRENT_PATH)
        if payload is not None:
            return payload

        for path in self._LEGACY_PATHS:
            payload = self._load_section_from_path(path)
            if payload is not None:
                return payload
        return {}

    def save(self, params: dict[str, Any]) -> None:
        path = self._CURRENT_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        root: dict[str, Any] = {}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    root = loaded
            except (OSError, json.JSONDecodeError):
                root = {}

        root["version"] = self._SCHEMA_VERSION
        root[self._section] = dict(params)

        try:
            path.write_text(json.dumps(root, ensure_ascii=True, indent=2), encoding="utf-8")
        except OSError:
            return

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
            return nested

        if self._section == "training" and self._looks_like_training(payload):
            return payload
        if self._section == "simulation" and self._looks_like_simulation(payload):
            return payload
        return None

    @staticmethod
    def _looks_like_training(payload: dict[str, Any]) -> bool:
        markers = ("data_path", "total_steps", "learning_rate", "transaction_cost_bps")
        return any(marker in payload for marker in markers)

    @staticmethod
    def _looks_like_simulation(payload: dict[str, Any]) -> bool:
        markers = ("data", "model", "log_every", "max_steps")
        return any(marker in payload for marker in markers)
