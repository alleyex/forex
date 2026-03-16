from __future__ import annotations

import json

from forex.ui.train.services.ui_params_store import UIParamsStore


def test_training_store_saves_nested_and_top_level(tmp_path, monkeypatch) -> None:
    current_path = tmp_path / "training_params.json"
    monkeypatch.setitem(UIParamsStore._CURRENT_PATHS, "training", current_path)

    store = UIParamsStore("training")
    params = {
        "total_steps": 320000,
        "learning_rate": 0.0001,
        "seed": 10101,
        "curriculum_enabled": True,
        "curriculum_steps": 25000,
        "curriculum_max_position": 0.2,
        "curriculum_position_step": 0.1,
        "curriculum_min_position_change": 0.05,
        "transaction_cost_bps": 0.4,
        "window_size": 4,
        "downside_penalty": 0.02,
        "turnover_penalty": 0.001,
        "flat_position_penalty": 0.0005,
        "flat_streak_penalty": 0.0002,
        "flat_position_threshold": 0.01,
        "target_vol": 0.01,
        "start_mode": "random",
        "feature_profile": "residual",
        "optuna_replay_score_mode": "walk_forward",
        "optuna_replay_walk_forward_segments": 3,
        "optuna_replay_walk_forward_steps": 5000,
        "optuna_replay_walk_forward_stride": 10000,
        "anti_flat_enabled": True,
        "anti_flat_warmup_steps": 50000,
        "anti_flat_patience_evals": 3,
        "anti_flat_min_trade_rate": 5.0,
        "anti_flat_max_flat_ratio": 0.98,
        "anti_flat_max_ls_imbalance": 0.2,
        "anti_flat_profile_steps": 2500,
        "selected_features": ["returns_1", "adx_14", "since_ny_open_return"],
    }
    store.save(params)

    payload = json.loads(current_path.read_text(encoding="utf-8"))
    assert payload["total_steps"] == 320000
    assert payload["learning_rate"] == 0.0001
    assert payload["seed"] == 10101
    assert payload["curriculum_enabled"] is True
    assert payload["curriculum_steps"] == 25000
    assert payload["curriculum_max_position"] == 0.2
    assert payload["curriculum_position_step"] == 0.1
    assert payload["curriculum_min_position_change"] == 0.05
    assert payload["transaction_cost_bps"] == 0.4
    assert payload["window_size"] == 4
    assert payload["downside_penalty"] == 0.02
    assert payload["turnover_penalty"] == 0.001
    assert payload["flat_position_penalty"] == 0.0005
    assert payload["flat_streak_penalty"] == 0.0002
    assert payload["flat_position_threshold"] == 0.01
    assert payload["target_vol"] == 0.01
    assert payload["start_mode"] == "random"
    assert payload["feature_profile"] == "residual"
    assert payload["optuna_replay_score_mode"] == "walk_forward"
    assert payload["optuna_replay_walk_forward_segments"] == 3
    assert payload["optuna_replay_walk_forward_steps"] == 5000
    assert payload["optuna_replay_walk_forward_stride"] == 10000
    assert payload["anti_flat_enabled"] is True
    assert payload["anti_flat_warmup_steps"] == 50000
    assert payload["anti_flat_patience_evals"] == 3
    assert payload["anti_flat_min_trade_rate"] == 5.0
    assert payload["anti_flat_max_flat_ratio"] == 0.98
    assert payload["anti_flat_max_ls_imbalance"] == 0.2
    assert payload["anti_flat_profile_steps"] == 2500
    assert payload["selected_features"] == ["returns_1", "adx_14", "since_ny_open_return"]


def test_training_store_load_prefers_nested_but_falls_back_to_top_level(
    tmp_path, monkeypatch
) -> None:
    current_path = tmp_path / "training_params.json"
    monkeypatch.setitem(UIParamsStore._CURRENT_PATHS, "training", current_path)

    payload = {
        "version": 1,
        "total_steps": 500000,
        "learning_rate": 0.001,
        "seed": 7,
        "transaction_cost_bps": 1.0,
        "training": {
            "total_steps": 320000,
            "curriculum_enabled": True,
            "curriculum_steps": 25000,
            "curriculum_max_position": 0.2,
            "curriculum_position_step": 0.1,
            "curriculum_min_position_change": 0.05,
            "transaction_cost_bps": 0.4,
            "feature_profile": "alpha4",
            "flat_position_penalty": 0.0005,
            "flat_streak_penalty": 0.0002,
            "flat_position_threshold": 0.01,
            "optuna_replay_score_mode": "walk_forward",
            "optuna_replay_walk_forward_segments": 3,
            "optuna_replay_walk_forward_steps": 5000,
            "optuna_replay_walk_forward_stride": 10000,
            "anti_flat_enabled": True,
            "anti_flat_warmup_steps": 50000,
            "anti_flat_patience_evals": 3,
            "anti_flat_min_trade_rate": 5.0,
            "anti_flat_max_flat_ratio": 0.98,
            "anti_flat_max_ls_imbalance": 0.2,
            "anti_flat_profile_steps": 2500,
            "selected_features": ["returns_1", "adx_14"],
        },
    }
    current_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    loaded = UIParamsStore("training").load()
    assert loaded["total_steps"] == 320000
    assert loaded["transaction_cost_bps"] == 0.4
    assert loaded["feature_profile"] == "alpha4"
    assert loaded["learning_rate"] == 0.001
    assert loaded["seed"] == 7
    assert loaded["curriculum_enabled"] is True
    assert loaded["curriculum_steps"] == 25000
    assert loaded["curriculum_max_position"] == 0.2
    assert loaded["curriculum_position_step"] == 0.1
    assert loaded["curriculum_min_position_change"] == 0.05
    assert loaded["flat_position_penalty"] == 0.0005
    assert loaded["flat_streak_penalty"] == 0.0002
    assert loaded["flat_position_threshold"] == 0.01
    assert loaded["optuna_replay_score_mode"] == "walk_forward"
    assert loaded["optuna_replay_walk_forward_segments"] == 3
    assert loaded["optuna_replay_walk_forward_steps"] == 5000
    assert loaded["optuna_replay_walk_forward_stride"] == 10000
    assert loaded["anti_flat_enabled"] is True
    assert loaded["anti_flat_warmup_steps"] == 50000
    assert loaded["anti_flat_patience_evals"] == 3
    assert loaded["anti_flat_min_trade_rate"] == 5.0
    assert loaded["anti_flat_max_flat_ratio"] == 0.98
    assert loaded["anti_flat_max_ls_imbalance"] == 0.2
    assert loaded["anti_flat_profile_steps"] == 2500
    assert loaded["selected_features"] == ["returns_1", "adx_14"]


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
