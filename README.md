# Forex Platform

Desktop trading UI, cTrader integration, and reinforcement-learning tooling for training, simulation, and live operations.

## Overview

This repository is organized as a layered Python application with:

- `src/forex/domain`: core domain models and rules
- `src/forex/application`: use cases and orchestration
- `src/forex/infrastructure`: broker adapters, storage, and external integrations
- `src/forex/ui`: desktop UI for training and live workflows
- `src/forex/ml`: RL environments, features, and training utilities
- `src/forex/tools`: diagnostics, research, and operational tooling
- `tests`: automated tests
- `docs`: architecture, operations, and governance documents

Additional project guidance:

- Development workflow: [`docs/development.md`](docs/development.md)
- Contribution guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Architecture notes: [`docs/architecture.md`](docs/architecture.md)
- Repository structure: [`docs/project_structure.md`](docs/project_structure.md)
- Operations runbook: [`docs/operations.md`](docs/operations.md)
- Data governance: [`docs/data_governance.md`](docs/data_governance.md)
- Versioning and releases: [`docs/versioning.md`](docs/versioning.md)
- Security policy: [`SECURITY.md`](SECURITY.md)
- Changelog: [`CHANGELOG.md`](CHANGELOG.md)

## Quick Start

Recommended Python version: `3.10+`

```bash
./scripts/bootstrap.sh
```

Create local configuration from the sample file before running live features:

```bash
cp .env.example .env
```

## Running The Application

Launcher:

```bash
forex
```

Training UI:

```bash
QT_OPENGL=software LOG_LEVEL=INFO forex-train
```

Live UI:

```bash
QT_OPENGL=software LOG_LEVEL=INFO forex-live
```

Module entrypoints are also available:

```bash
python3 -m forex.app.cli.launcher
python3 -m forex.app.cli.train
python3 -m forex.app.cli.live
```

Convenience scripts:

```bash
./scripts/run-train.sh
./scripts/run-live.sh
```

## Development Commands

Use `make help` to list the available workflows.

```bash
make install-dev
make lint
make test
make check-core
make check-hygiene
make release-check
make check-release-metadata
make bump-version VERSION=0.1.1
```

## Configuration

Runtime configuration is environment-driven. See `.env.example` and `src/forex/config/runtime.py`.

Common variables:

- `TOKEN_FILE`: local token file path
- `BROKER_PROVIDER`: broker provider name, default `ctrader`
- `LOG_LEVEL`: logging level, default `INFO`
- `LOG_FILE`: optional log output file
- `CTRADER_REQUEST_TIMEOUT`: request timeout in seconds
- `CTRADER_OAUTH_TIMEOUT`: OAuth auth timeout
- `CTRADER_OAUTH_LOGIN_TIMEOUT`: browser login flow timeout
- `CTRADER_RETRY_MAX_ATTEMPTS`: retry attempts, `0` disables retries
- `CTRADER_RETRY_BACKOFF_SECONDS`: retry backoff delay
- `METRICS_LOG_INTERVAL`: metrics snapshot interval

## Repository Conventions

- Production code lives under `src/`
- Tests live under `tests/`
- Developer scripts live under `scripts/`
- Runtime artifacts stay in `runtime/` or ignored local files
- Research outputs and operational notes stay in `docs/`
- Generated data belongs in `data/` and should not be committed unless intentional
