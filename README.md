# Forex Project

This repository contains a desktop trading UI, broker integration (cTrader), and RL tooling for training and simulation.

## Layout

- `src/` application code (app, application, domain, infrastructure, ui, ml, tools)
- `data/` runtime artifacts (ignored from git)
- `docs/` architecture and operational notes

## Setup

Recommended Python version: 3.10+

```bash
pip install -e '.[dev]'
```

If you only need the UI or ML parts, you can install:

```bash
pip install -e '.[ui]'
pip install -e '.[ml]'
```

## Run

Training UI (wrapper entrypoint):

```bash
QT_OPENGL=software LOG_LEVEL=INFO python main_train.py
```

Live UI (wrapper entrypoint):

```bash
QT_OPENGL=software LOG_LEVEL=INFO python main_live.py
```

Direct module entrypoints:

```bash
QT_OPENGL=software LOG_LEVEL=INFO python -m app.entrypoints.train
QT_OPENGL=software LOG_LEVEL=INFO python -m app.entrypoints.live
python -m app.entrypoints.app
```

## Tests

```bash
pytest -q
```

## Configuration

Environment variables (defaults in `src/config/runtime.py`):

- `TOKEN_FILE`: path to token.json
- `BROKER_PROVIDER`: `ctrader` by default
- `LOG_LEVEL`: `INFO` by default
- `LOG_FILE`: optional file output for logs
- `CTRADER_REQUEST_TIMEOUT`: request timeout seconds
- `CTRADER_OAUTH_TIMEOUT`: OAuth auth timeout seconds
- `CTRADER_OAUTH_LOGIN_TIMEOUT`: OAuth login browser flow timeout
- `CTRADER_RETRY_MAX_ATTEMPTS`: 0 disables retries
- `CTRADER_RETRY_BACKOFF_SECONDS`: retry backoff delay
- `METRICS_LOG_INTERVAL`: metrics snapshot log interval

## Operations

See `docs/operations.md` for runbooks, troubleshooting, and operational tips.

## Data Governance

See `docs/data_governance.md` for data layout, schema versioning, and metadata format.
