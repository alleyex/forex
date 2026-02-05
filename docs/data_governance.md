# Data Governance

## Overview

Runtime artifacts are stored under `data/` and ignored by git. The code records a metadata sidecar for key outputs.

## Schema Version

- Current schema version: `1`
- Source of truth: `src/config/data_governance.py`

## Raw History CSV

When history is downloaded, a CSV is written to `data/raw_history/` and a metadata file is generated beside it.

Example filenames:

- `data/raw_history/1234_M5_20240101-20240201.csv`
- `data/raw_history/1234_M5_20240101-20240201.csv.meta.json`

Metadata fields:

- `schema_version`
- `generated_at`
- `artifact_type`: `raw_history_csv`
- `details`:
  - `symbol_id`
  - `timeframe`
  - `row_count`
  - `columns`
  - `range_start`
  - `range_end`

## Extending

If you introduce new artifact types (models, reports, analytics):

- Add a new `artifact_type`
- Write a `.meta.json` sidecar via `write_metadata_for_csv`
- Bump `SCHEMA_VERSION` if the metadata structure changes
