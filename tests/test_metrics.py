from __future__ import annotations

import pytest

from forex.utils.metrics import compute_sharpe_ratio_from_equity


def test_compute_sharpe_ratio_from_equity_uses_step_returns_not_absolute_deltas() -> None:
    equity_series = [1.0, 2.0, 3.0]

    sharpe = compute_sharpe_ratio_from_equity(equity_series)

    assert sharpe == pytest.approx(3.0)


def test_compute_sharpe_ratio_from_equity_returns_zero_for_flat_returns() -> None:
    equity_series = [1.0, 1.1, 1.21]

    sharpe = compute_sharpe_ratio_from_equity(equity_series)

    assert sharpe == 0.0
