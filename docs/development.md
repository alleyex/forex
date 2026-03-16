# Development Guide

## Tooling Baseline

- Python `3.10+`
- Editable install via `pip install -e`
- Code quality tools configured in `pyproject.toml`

## Initial Setup

```bash
./scripts/bootstrap.sh
```

## Common Commands

```bash
make help
make format
make test
make check-core
make check-hygiene
```

## Entry Points

- `forex`: launcher UI
- `forex-train`: training UI
- `forex-live`: live UI

Module equivalents:

```bash
python3 -m forex.app.cli.launcher
python3 -m forex.app.cli.train
python3 -m forex.app.cli.live
```

Shell convenience scripts:

```bash
./scripts/run-train.sh
./scripts/run-live.sh
```

## Architecture Expectations

- `domain` should remain framework-free and independent.
- `application` can coordinate use cases but should not depend on UI code.
- `infrastructure` implements external concerns and should not depend on UI or app layers.
- `ui` handles presentation and user interaction.

Architectural boundaries are enforced with import-linter contracts.

## Local Files

These files are intentionally local-only and should not be committed:

- `.env`
- `token.json`
- `symbol.json`
- `timeframes.json`
- logs under `runtime/`
- generated artifacts under `data/`

## CI Expectations

Continuous integration enforces core gates first, and reports hygiene drift separately. This keeps the repository shippable while older code is gradually normalized.
