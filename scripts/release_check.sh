#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python3}"

echo "[release-check] Verifying package version metadata"
"$PYTHON_BIN" ./scripts/validate_release_metadata.py

echo "[release-check] Ensuring release build tools are available"
"$PYTHON_BIN" - <<'PY'
import importlib.util
import subprocess
import sys

required_modules = ("build", "twine")
missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
if missing:
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
PY

echo "[release-check] Running core checks"
make check-core

echo "[release-check] Running hygiene checks"
make check-hygiene

echo "[release-check] Building distribution artifacts"
"$PYTHON_BIN" -m build

echo "[release-check] Validating distribution metadata"
"$PYTHON_BIN" -m twine check dist/*

echo "[release-check] Completed successfully"
