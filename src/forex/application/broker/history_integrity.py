from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_TIMEFRAME_STEP_MINUTES = {
    "M1": 1,
    "M2": 2,
    "M3": 3,
    "M4": 4,
    "M5": 5,
    "M10": 10,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "H12": 720,
    "D1": 1440,
    "W1": 10080,
}


@dataclass(frozen=True)
class GapItem:
    start_utc_minutes: int
    end_utc_minutes: int
    diff_minutes: int
    missing_bars: int


@dataclass(frozen=True)
class HistoryIntegrityReport:
    csv_path: str
    timeframe: str
    expected_step_minutes: int
    row_count: int
    duplicate_count: int
    backward_count: int
    gap_count: int
    missing_bars: int
    gaps: list[GapItem]

    def to_dict(self) -> dict:
        return {
            "csv_path": self.csv_path,
            "timeframe": self.timeframe,
            "expected_step_minutes": self.expected_step_minutes,
            "row_count": self.row_count,
            "duplicate_count": self.duplicate_count,
            "backward_count": self.backward_count,
            "gap_count": self.gap_count,
            "missing_bars": self.missing_bars,
            "gaps": [asdict(item) for item in self.gaps],
        }


class HistoryIntegrityService:
    def analyze(
        self,
        csv_path: str | Path,
        *,
        timeframe: Optional[str] = None,
        exclude_weekends: bool = True,
    ) -> HistoryIntegrityReport:
        path = Path(csv_path)
        rows = self._read_timestamps(path)
        timeframe_name = (timeframe or self._read_timeframe_from_meta(path) or "unknown").upper()
        expected_step = self._resolve_expected_step(timeframe_name, rows)
        duplicates = self._count_duplicates(rows)
        backward = self._count_backward(rows)
        gaps, missing_bars = self._detect_gaps(rows, expected_step, exclude_weekends=exclude_weekends)
        return HistoryIntegrityReport(
            csv_path=str(path),
            timeframe=timeframe_name,
            expected_step_minutes=expected_step,
            row_count=len(rows),
            duplicate_count=duplicates,
            backward_count=backward,
            gap_count=len(gaps),
            missing_bars=missing_bars,
            gaps=gaps,
        )

    @staticmethod
    def export_json(report: HistoryIntegrityReport, output_path: str | Path) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
        return str(path)

    @staticmethod
    def export_gaps_csv(report: HistoryIntegrityReport, output_path: str | Path) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "start_utc_minutes",
                    "end_utc_minutes",
                    "diff_minutes",
                    "missing_bars",
                    "start_utc",
                    "end_utc",
                ],
            )
            writer.writeheader()
            for gap in report.gaps:
                writer.writerow(
                    {
                        "start_utc_minutes": gap.start_utc_minutes,
                        "end_utc_minutes": gap.end_utc_minutes,
                        "diff_minutes": gap.diff_minutes,
                        "missing_bars": gap.missing_bars,
                        "start_utc": _fmt_utc_minutes(gap.start_utc_minutes),
                        "end_utc": _fmt_utc_minutes(gap.end_utc_minutes),
                    }
                )
        return str(path)

    @staticmethod
    def _read_timestamps(path: Path) -> list[int]:
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {path}")
        out: list[int] = []
        with path.open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if "utc_timestamp_minutes" not in (reader.fieldnames or []):
                raise ValueError("Missing required column: utc_timestamp_minutes")
            for row in reader:
                raw = row.get("utc_timestamp_minutes")
                if raw in (None, ""):
                    continue
                try:
                    out.append(int(float(raw)))
                except (TypeError, ValueError):
                    continue
        if not out:
            raise ValueError("No usable rows found in CSV")
        return out

    @staticmethod
    def _read_timeframe_from_meta(path: Path) -> Optional[str]:
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        if not meta_path.exists():
            return None
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        details = data.get("details") if isinstance(data, dict) else None
        if not isinstance(details, dict):
            return None
        value = details.get("timeframe")
        if not value:
            return None
        return str(value).strip().upper()

    @staticmethod
    def _resolve_expected_step(timeframe: str, values: list[int]) -> int:
        by_tf = _TIMEFRAME_STEP_MINUTES.get(timeframe.upper()) if timeframe else None
        if by_tf is not None:
            return by_tf
        sorted_unique = sorted(set(values))
        diffs = [b - a for a, b in zip(sorted_unique, sorted_unique[1:]) if b > a]
        if not diffs:
            return 1
        counts: dict[int, int] = {}
        for diff in diffs:
            counts[diff] = counts.get(diff, 0) + 1
        return max(counts.keys(), key=lambda key: counts[key])

    @staticmethod
    def _count_duplicates(values: list[int]) -> int:
        sorted_values = sorted(values)
        return sum(1 for a, b in zip(sorted_values, sorted_values[1:]) if b == a)

    @staticmethod
    def _count_backward(values: list[int]) -> int:
        return sum(1 for a, b in zip(values, values[1:]) if b < a)

    def _detect_gaps(
        self,
        values: list[int],
        expected_step: int,
        *,
        exclude_weekends: bool,
    ) -> tuple[list[GapItem], int]:
        if expected_step <= 0:
            return ([], 0)
        unique_sorted = sorted(set(values))
        gaps: list[GapItem] = []
        missing_total = 0
        for start, end in zip(unique_sorted, unique_sorted[1:]):
            diff = end - start
            if diff <= expected_step:
                continue
            if exclude_weekends:
                missing = self._missing_non_weekend_bars(start, end, expected_step)
            else:
                missing = max(0, diff // expected_step - 1)
            if missing <= 0:
                continue
            gaps.append(
                GapItem(
                    start_utc_minutes=start,
                    end_utc_minutes=end,
                    diff_minutes=diff,
                    missing_bars=missing,
                )
            )
            missing_total += missing
        return (gaps, missing_total)

    @staticmethod
    def _missing_non_weekend_bars(start: int, end: int, step: int) -> int:
        missing = 0
        candidate = start + step
        while candidate < end:
            dt = datetime.fromtimestamp(candidate * 60, tz=timezone.utc)
            if dt.weekday() < 5:
                missing += 1
            candidate += step
        return missing


def _fmt_utc_minutes(value: int) -> str:
    dt = datetime.fromtimestamp(value * 60, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M")
