from __future__ import annotations

import json

from forex.config.data_governance import SCHEMA_VERSION, write_metadata_for_csv


def test_write_metadata_for_csv(tmp_path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("col\n1\n", encoding="utf-8")
    meta_path = write_metadata_for_csv(
        csv_path,
        artifact_type="raw_history_csv",
        details={"rows": 1},
    )
    meta = json.loads((tmp_path / "sample.csv.meta.json").read_text(encoding="utf-8"))
    assert meta_path.endswith("sample.csv.meta.json")
    assert meta["schema_version"] == SCHEMA_VERSION
    assert meta["artifact_type"] == "raw_history_csv"
