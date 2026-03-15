#!/usr/bin/env bash

set -euo pipefail

export QT_OPENGL="${QT_OPENGL:-software}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

exec python3 -m forex.app.cli.train "$@"
