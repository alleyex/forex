from __future__ import annotations

import json
from pathlib import Path

from forex.ui.train.services import UIParamsStore


def _configure_paths(monkeypatch, current: Path, legacy: tuple[Path, ...]) -> None:
    monkeypatch.setattr(UIParamsStore, "_CURRENT_PATH", current)
    monkeypatch.setattr(UIParamsStore, "_LEGACY_PATHS", legacy)


def test_save_preserves_other_section_and_version(tmp_path, monkeypatch):
    current = tmp_path / "training_params.json"
    current.write_text(
        json.dumps({"version": 1, "training": {"transaction_cost_bps": 0.45}}),
        encoding="utf-8",
    )
    _configure_paths(monkeypatch, current, ())

    simulation_store = UIParamsStore("simulation")
    simulation_store.save({"slippage_bps": 0.2})

    payload = json.loads(current.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["training"] == {"transaction_cost_bps": 0.45}
    assert payload["simulation"] == {"slippage_bps": 0.2}


def test_load_training_from_flat_legacy_payload(tmp_path, monkeypatch):
    current = tmp_path / "training_params.json"
    legacy = tmp_path / "legacy_training.json"
    legacy.write_text(
        json.dumps({"data_path": "x.csv", "transaction_cost_bps": 0.45}),
        encoding="utf-8",
    )
    _configure_paths(monkeypatch, current, (legacy,))

    training_store = UIParamsStore("training")
    data = training_store.load()

    assert data["data_path"] == "x.csv"
    assert data["transaction_cost_bps"] == 0.45


def test_load_simulation_prefers_nested_section(tmp_path, monkeypatch):
    current = tmp_path / "training_params.json"
    current.write_text(
        json.dumps(
            {
                "version": 1,
                "training": {"transaction_cost_bps": 0.45},
                "simulation": {"data": "sim.csv", "max_steps": 1000},
            }
        ),
        encoding="utf-8",
    )
    _configure_paths(monkeypatch, current, ())

    simulation_store = UIParamsStore("simulation")
    data = simulation_store.load()

    assert data == {"data": "sim.csv", "max_steps": 1000}
