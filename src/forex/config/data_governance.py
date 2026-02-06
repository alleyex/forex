from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DataMetadata:
    schema_version: int
    generated_at: str
    artifact_type: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "artifact_type": self.artifact_type,
            "details": self.details,
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_metadata_for_csv(
    csv_path: str | Path,
    *,
    artifact_type: str,
    details: dict[str, Any],
) -> str:
    path = Path(csv_path)
    metadata = DataMetadata(
        schema_version=SCHEMA_VERSION,
        generated_at=_utc_now_iso(),
        artifact_type=artifact_type,
        details=details,
    )
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(metadata.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return str(meta_path)


def normalize_timeframe(timeframe: Optional[str]) -> str:
    if not timeframe:
        return "unknown"
    return timeframe.upper()
