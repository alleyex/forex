# Project Structure

## Repository Top Level

- `src/`: application source code
- `tests/`: automated tests
- `docs/`: architecture, operations, and development guidance
- `scripts/`: developer and operator convenience scripts
- `data/`: generated datasets, training artifacts, and simulations
- `runtime/`: runtime logs and transient local outputs
- `config/local/`: machine-local configuration overlays

## Source Layout

- `src/forex/app`: application bootstrap and CLI entrypoints
- `src/forex/domain`: core business entities and invariants
- `src/forex/application`: use cases, orchestration, and adapters
- `src/forex/infrastructure`: broker integrations, persistence, and external services
- `src/forex/ui`: desktop presentation layer
- `src/forex/ml`: research, environments, features, and training code
- `src/forex/tools`: diagnostics and support utilities
- `src/forex/config`: runtime and logging configuration

## Conventions

- New executable workflows should be added under package entrypoints or `scripts/`, not as new root-level files.
- Runtime secrets and local broker artifacts must stay outside version control.
- Operational tooling should be discoverable from `Makefile`, `scripts/`, or documented CLI entrypoints.
- New documentation should live in `docs/` and be linked from `README.md` when it affects onboarding or operations.
