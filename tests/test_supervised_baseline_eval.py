from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from forex.tools.rl.supervised_baseline_eval import (
    _apply_action_gate,
    _apply_feature_gates,
    _build_gate_mask,
    _build_threshold_bump_array,
    _build_targets,
    _score_to_raw_target,
    _parse_action_gate_specs,
    _parse_feature_gate_specs,
    _parse_threshold_bump_specs,
)


def test_build_targets_forward_return_mode_matches_threshold_signs() -> None:
    closes = np.asarray([100.0, 101.0, 102.0, 103.0], dtype=np.float32)

    labels, future_returns = _build_targets(
        closes,
        horizon=1,
        threshold=0.005,
        target_mode="forward_return",
    )

    assert labels.tolist()[:3] == [1, 1, 1]
    assert future_returns.tolist()[:3] == pytest.approx([0.01, 102.0 / 101.0 - 1.0, 103.0 / 102.0 - 1.0])


def test_build_targets_breakout_follow_through_requires_directional_dominance() -> None:
    closes = np.asarray(
        [
            100.0, 106.0, 108.0, 109.0,
            100.0, 95.0, 92.0, 91.0,
            100.0, 106.0, 94.0, 101.0,
        ],
        dtype=np.float32,
    )

    labels, _ = _build_targets(
        closes,
        horizon=3,
        threshold=0.04,
        target_mode="breakout_follow_through",
        follow_through_ratio=1.25,
    )

    assert labels[0] == 1
    assert labels[4] == -1
    assert labels[8] == 0


def test_parse_feature_gate_specs_supports_open_bounds() -> None:
    gates = _parse_feature_gate_specs(
        [
            "pre_london_compression:0.6:",
            "volatility_regime_z::-0.5",
        ]
    )

    assert gates == [
        {"feature": "pre_london_compression", "min": 0.6, "max": None},
        {"feature": "volatility_regime_z", "min": None, "max": -0.5},
    ]


def test_parse_action_gate_specs_supports_open_bounds() -> None:
    gates = _parse_action_gate_specs(
        [
            "asia_range_width_atr::12.0",
            "pre_london_compression:0.1:",
        ]
    )

    assert gates == [
        {"feature": "asia_range_width_atr", "min": None, "max": 12.0},
        {"feature": "pre_london_compression", "min": 0.1, "max": None},
    ]


def test_parse_threshold_bump_specs_supports_open_bounds_and_bump_value() -> None:
    bumps = _parse_threshold_bump_specs(
        [
            "volatility_regime_z:0.8::0.05",
            "ny_reversal_pressure::0.0010:0.03",
        ]
    )

    assert bumps == [
        {"feature": "volatility_regime_z", "min": 0.8, "max": None, "bump": 0.05},
        {"feature": "ny_reversal_pressure", "min": None, "max": 0.001, "bump": 0.03},
    ]


def test_apply_feature_gates_filters_rows_and_keeps_alignment() -> None:
    features = pd.DataFrame(
        {
            "pre_london_compression": [0.2, 0.7, 0.8, 0.4],
            "volatility_regime_z": [-0.2, -0.8, 0.1, -0.4],
        }
    )
    closes = pd.Series([100.0, 101.0, 102.0, 103.0], dtype=np.float32)
    timestamps = ["t0", "t1", "t2", "t3"]

    filtered_features, filtered_closes, filtered_timestamps = _apply_feature_gates(
        features,
        closes,
        timestamps,
        [
            {"feature": "pre_london_compression", "min": 0.6, "max": None},
            {"feature": "volatility_regime_z", "min": -0.9, "max": -0.1},
        ],
    )

    assert filtered_features["pre_london_compression"].tolist() == [0.7]
    assert filtered_closes.tolist() == pytest.approx([101.0])
    assert filtered_timestamps == ["t1"]


def test_build_gate_mask_combines_multiple_bounds() -> None:
    features = pd.DataFrame(
        {
            "pre_london_compression": [0.08, 0.12, 0.15, 0.09],
            "asia_range_width_atr": [11.0, 13.0, 9.0, 10.0],
        }
    )

    mask = _build_gate_mask(
        features,
        [
            {"feature": "pre_london_compression", "min": 0.1, "max": None},
            {"feature": "asia_range_width_atr", "min": None, "max": 12.0},
        ],
    )

    assert mask.tolist() == [False, False, True, False]


def test_build_threshold_bump_array_accumulates_matching_bumps() -> None:
    features = pd.DataFrame(
        {
            "volatility_regime_z": [0.7, 0.9, 1.1],
            "ny_reversal_pressure": [0.0008, 0.0012, 0.0005],
        }
    )

    bumps = _build_threshold_bump_array(
        features,
        [
            {"feature": "volatility_regime_z", "min": 0.8, "max": None, "bump": 0.05},
            {"feature": "ny_reversal_pressure", "min": 0.001, "max": None, "bump": 0.02},
        ],
    )

    assert bumps.tolist() == pytest.approx([0.0, 0.07, 0.05])


def test_score_to_raw_target_maps_score_into_long_flat_short() -> None:
    assert _score_to_raw_target(
        0.3,
        current_position=0.0,
        long_threshold=0.25,
        short_threshold=-0.25,
        long_exit_threshold=0.25,
        short_exit_threshold=-0.25,
        max_position=1.0,
    ) == pytest.approx(1.0)
    assert _score_to_raw_target(
        0.0,
        current_position=0.0,
        long_threshold=0.25,
        short_threshold=-0.25,
        long_exit_threshold=0.25,
        short_exit_threshold=-0.25,
        max_position=1.0,
    ) == pytest.approx(0.0)
    assert _score_to_raw_target(
        -0.3,
        current_position=0.0,
        long_threshold=0.25,
        short_threshold=-0.25,
        long_exit_threshold=0.25,
        short_exit_threshold=-0.25,
        max_position=1.0,
    ) == pytest.approx(-1.0)


def test_score_to_raw_target_supports_hysteresis_for_existing_positions() -> None:
    assert _score_to_raw_target(
        0.10,
        current_position=1.0,
        long_threshold=0.25,
        short_threshold=-0.25,
        long_exit_threshold=0.05,
        short_exit_threshold=-0.05,
        max_position=1.0,
    ) == pytest.approx(1.0)
    assert _score_to_raw_target(
        0.00,
        current_position=1.0,
        long_threshold=0.25,
        short_threshold=-0.25,
        long_exit_threshold=0.05,
        short_exit_threshold=-0.05,
        max_position=1.0,
    ) == pytest.approx(0.0)
    assert _score_to_raw_target(
        -0.10,
        current_position=-1.0,
        long_threshold=0.25,
        short_threshold=-0.25,
        long_exit_threshold=0.05,
        short_exit_threshold=-0.05,
        max_position=1.0,
    ) == pytest.approx(-1.0)
    assert _score_to_raw_target(
        0.00,
        current_position=-1.0,
        long_threshold=0.25,
        short_threshold=-0.25,
        long_exit_threshold=0.05,
        short_exit_threshold=-0.05,
        max_position=1.0,
    ) == pytest.approx(0.0)


def test_apply_action_gate_entry_only_blocks_new_entry_but_allows_exit() -> None:
    assert _apply_action_gate(
        1.0,
        current_position=0.0,
        gate_enabled=False,
        action_gate_mode="entry_only",
    ) == pytest.approx(0.0)
    assert _apply_action_gate(
        -1.0,
        current_position=1.0,
        gate_enabled=False,
        action_gate_mode="entry_only",
    ) == pytest.approx(0.0)
    assert _apply_action_gate(
        1.0,
        current_position=1.0,
        gate_enabled=False,
        action_gate_mode="entry_only",
    ) == pytest.approx(1.0)
