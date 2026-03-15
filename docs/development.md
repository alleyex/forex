# Development Guide

## Tooling Baseline

- Python `3.10+`
- Editable install via `pip install -e`
- Code quality tools configured in `pyproject.toml`

## Initial Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
pip install -e '.[dev,ui,ml,ctrader]'
```

## Common Commands

```bash
make help
make install-dev
make format
make lint
make test
make check
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

Continuous integration runs formatting, linting, architecture checks, and tests on pushes and pull requests. Keep local commands aligned with CI before submitting changes.
