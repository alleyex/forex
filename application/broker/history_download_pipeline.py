from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

from application.broker.protocols import AppAuthServiceLike, TrendbarHistoryServiceLike
from application.broker.use_cases import BrokerUseCases
from config.paths import RAW_HISTORY_DIR


class HistoryDownloadPipeline:
    """Coordinates history download and raw file persistence."""

    def __init__(
        self,
        broker_use_cases: BrokerUseCases,
        app_auth_service: AppAuthServiceLike,
        raw_dir: Union[str, Path] = RAW_HISTORY_DIR,
    ) -> None:
        self._use_cases = broker_use_cases
        self._app_auth_service = app_auth_service
        self._raw_dir = Path(raw_dir)
        self._history_service: Optional[TrendbarHistoryServiceLike] = None

    def fetch_to_raw(
        self,
        account_id: int,
        symbol_id: int,
        count: int = 100,
        *,
        timeframe: str = "M5",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
        output_path: Optional[Union[str, Path]] = None,
        on_saved: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> bool:
        if self._history_service is None:
            self._history_service = self._use_cases.create_trendbar_history(self._app_auth_service)

        def handle_history(rows: list[dict]) -> None:
            try:
                path = self._write_csv(rows, symbol_id, timeframe, output_path=output_path)
            except Exception as exc:  # pragma: no cover - safety net for callback flow
                if on_error:
                    on_error(str(exc))
                return
            if on_saved:
                on_saved(path)

        self._history_service.clear_log_history()
        self._history_service.set_callbacks(
            on_history_received=handle_history,
            on_error=on_error,
            on_log=on_log,
        )
        self._history_service.fetch(
            account_id=account_id,
            symbol_id=symbol_id,
            count=count,
            timeframe=timeframe,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        return True

    def _write_csv(
        self,
        rows: Iterable[dict],
        symbol_id: int,
        timeframe: str,
        *,
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        rows_list = list(rows)
        if not rows_list:
            raise ValueError("No history data received")

        start, end = self._infer_range(rows_list)
        filename = f"{symbol_id}_{timeframe}_{start}-{end}.csv"
        if output_path is None:
            self._raw_dir.mkdir(parents=True, exist_ok=True)
            path = self._raw_dir / filename
        else:
            out_path = Path(output_path)
            if out_path.suffix.lower() == ".csv":
                path = out_path
                path.parent.mkdir(parents=True, exist_ok=True)
            else:
                out_path.mkdir(parents=True, exist_ok=True)
                path = out_path / filename

        fieldnames = list(rows_list[0].keys())
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows_list)

        return str(path)

    @staticmethod
    def _infer_range(rows: Iterable[dict]) -> tuple[str, str]:
        timestamps = [row.get("timestamp") for row in rows if row.get("timestamp")]
        if not timestamps:
            return ("unknown", "unknown")
        return (HistoryDownloadPipeline._format_ts(timestamps[0]), HistoryDownloadPipeline._format_ts(timestamps[-1]))

    @staticmethod
    def _format_ts(value: str) -> str:
        return value.replace(" ", "_").replace(":", "")
