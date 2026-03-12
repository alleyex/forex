from __future__ import annotations

import numpy as np
import pytest

from forex.tools.rl.supervised_segment_diagnostics import _pick_focus_segment, _segment_label_stats


def test_segment_label_stats_reports_positive_negative_and_nonzero_ratios() -> None:
    stats = _segment_label_stats(np.asarray([1, 0, -1, 1, 0], dtype=np.int32))

    assert stats["rows"] == pytest.approx(5.0)
    assert stats["positive_ratio"] == pytest.approx(0.4)
    assert stats["negative_ratio"] == pytest.approx(0.2)
    assert stats["nonzero_ratio"] == pytest.approx(0.6)


def test_pick_focus_segment_defaults_to_worst_return() -> None:
    segments = [
        {"total_return": 0.01},
        {"total_return": -0.03},
        {"total_return": 0.02},
    ]

    assert _pick_focus_segment(segments, None) == 1
    assert _pick_focus_segment(segments, 3) == 2
