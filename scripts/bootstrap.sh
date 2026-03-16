#!/usr/bin/env bash

set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -e '.[dev,ui,ml,ctrader]'

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

echo "Bootstrap complete."
