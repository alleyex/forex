# Contributing

## Development Environment

1. Create and activate a virtual environment.
2. Install the editable package with development dependencies.
3. Copy `.env.example` to `.env` if local runtime configuration is needed.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
pip install -e '.[dev,ui,ml,ctrader]'
```

## Daily Workflow

Before opening a change for review:

```bash
make format
make lint
make test
make check
```

## Project Structure

- `src/forex/domain`: domain entities and pure business rules
- `src/forex/application`: application services and use cases
- `src/forex/infrastructure`: broker integrations and persistence
- `src/forex/ui`: desktop presentation layer
- `src/forex/ml`: research and model training code
- `src/forex/tools`: diagnostics and support tooling
- `tests`: automated tests

## Engineering Rules

- Keep domain code isolated from UI, app, and infrastructure concerns.
- Prefer extending existing entrypoints and services instead of creating parallel flows.
- Add or update tests for behavior changes.
- Keep generated data, secrets, and machine-local artifacts out of version control.
- Use small, reviewable commits with a clear scope.

## Pull Request Checklist

- The change has a clear purpose and bounded scope.
- Documentation is updated if behavior or setup changed.
- New configuration is reflected in `.env.example` if applicable.
- Tests or validation steps were run locally.
