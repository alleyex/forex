from __future__ import annotations

import csv
from datetime import datetime, timezone

from forex.application.broker.history_integrity import HistoryIntegrityService


def _write_csv(path, rows: list[int]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["utc_timestamp_minutes", "timestamp", "open", "high", "low", "close"])
        writer.writeheader()
        for value in rows:
            writer.writerow(
                {
                    "utc_timestamp_minutes": value,
                    "timestamp": "",
                    "open": 0,
                    "high": 0,
                    "low": 0,
                    "close": 0,
                }
            )


def _utc_minutes(year: int, month: int, day: int, hour: int, minute: int) -> int:
    dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    return int(dt.timestamp() // 60)


def test_analyze_detects_duplicates_backward_and_gaps(tmp_path) -> None:
    path = tmp_path / "history.csv"
    _write_csv(path, [100, 115, 130, 130, 160, 145, 190])
    service = HistoryIntegrityService()

    report = service.analyze(path, timeframe="M15", exclude_weekends=False)

    assert report.expected_step_minutes == 15
    assert report.row_count == 7
    assert report.duplicate_count == 1
    assert report.backward_count == 1
    assert report.gap_count == 1
    assert report.missing_bars == 1


def test_analyze_can_exclude_weekend_gaps(tmp_path) -> None:
    # Friday 23:45 -> Monday 00:00 gap should be weekend-only.
    start = _utc_minutes(2024, 1, 5, 23, 45)
    end = _utc_minutes(2024, 1, 8, 0, 0)
    path = tmp_path / "weekend.csv"
    _write_csv(path, [start, end])
    service = HistoryIntegrityService()

    report_with_weekend = service.analyze(path, timeframe="M15", exclude_weekends=False)
    report_without_weekend = service.analyze(path, timeframe="M15", exclude_weekends=True)

    assert report_with_weekend.gap_count == 1
    assert report_with_weekend.missing_bars > 0
    assert report_without_weekend.gap_count == 0
    assert report_without_weekend.missing_bars == 0
