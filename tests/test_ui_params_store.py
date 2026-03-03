from __future__ import annotations

import json
from pathlib import Path

from forex.ui.train.services.ui_params_store import UIParamsStore


def test_training_store_saves_nested_and_top_level(tmp_path, monkeypatch) -> None:
    current_path = tmp_path / "training_params.json"
    monkeypatch.setitem(UIParamsStore._CURRENT_PATHS, "training", current_path)

    store = UIParamsStore("training")
    params = {
        "total_steps": 320000,
        "learning_rate": 0.0001,
        "transaction_cost_bps": 0.4,
        "window_size": 4,
        "downside_penalty": 0.02,
        "target_vol": 0.01,
        "start_mode": "random",
    }
    store.save(params)

    payload = json.loads(current_path.read_text(encoding="utf-8"))
    assert payload["total_steps"] == 320000
    assert payload["learning_rate"] == 0.0001
    assert payload["transaction_cost_bps"] == 0.4
    assert payload["window_size"] == 4
    assert payload["downside_penalty"] == 0.02
    assert payload["target_vol"] == 0.01
    assert payload["start_mode"] == "random"


def test_training_store_load_prefers_nested_but_falls_back_to_top_level(tmp_path, monkeypatch) -> None:
    current_path = tmp_path / "training_params.json"
    monkeypatch.setitem(UIParamsStore._CURRENT_PATHS, "training", current_path)

    payload = {
        "version": 1,
        "total_steps": 500000,
        "learning_rate": 0.001,
        "transaction_cost_bps": 1.0,
        "training": {
            "total_steps": 320000,
            "transaction_cost_bps": 0.4,
        },
    }
    current_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    loaded = UIParamsStore("training").load()
    assert loaded["total_steps"] == 320000
    assert loaded["transaction_cost_bps"] == 0.4
    assert loaded["learning_rate"] == 0.001


def test_simulation_store_saves_nested_and_top_level(tmp_path, monkeypatch) -> None:
    current_path = tmp_path / "training_params.json"
    monkeypatch.setitem(UIParamsStore._CURRENT_PATHS, "simulation", current_path)

    store = UIParamsStore("simulation")
    params = {
        "data": "/tmp/history.csv",
        "model": "/tmp/model.zip",
        "log_every": 1000,
        "max_steps": 0,
        "transaction_cost_bps": 0.225,
        "slippage_bps": 0.03,
    }
    store.save(params)

    payload = json.loads(current_path.read_text(encoding="utf-8"))
    assert payload["data"] == "/tmp/history.csv"
    assert payload["model"] == "/tmp/model.zip"
    assert payload["transaction_cost_bps"] == 0.225
    assert payload["slippage_bps"] == 0.03


def test_simulation_store_load_ignores_training_top_level_fields(tmp_path, monkeypatch) -> None:
    current_path = tmp_path / "training_params.json"
    monkeypatch.setitem(UIParamsStore._CURRENT_PATHS, "simulation", current_path)

    payload = {
        "version": 1,
        "total_steps": 500000,
        "learning_rate": 0.001,
        "transaction_cost_bps": 0.4,
        "slippage_bps": 0.03,
        "simulation": {
            "data": "/tmp/history.csv",
            "model": "/tmp/model.zip",
            "log_every": 1000,
            "max_steps": 0,
            "transaction_cost_bps": 0.225,
            "slippage_bps": 0.03,
        },
    }
    current_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    loaded = UIParamsStore("simulation").load()
    assert loaded["data"] == "/tmp/history.csv"
    assert loaded["model"] == "/tmp/model.zip"
    assert loaded["transaction_cost_bps"] == 0.225
    assert loaded["slippage_bps"] == 0.03
    assert "total_steps" not in loaded
    assert "learning_rate" not in loaded
