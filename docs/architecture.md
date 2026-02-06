# Architecture Notes

## 1) Entry and Bootstrap
- `src/app/entrypoints/*`: primary entry points (train/live/auth).
- CLI entry points via `pyproject.toml`:
  - `forex-train` -> `app.entrypoints.train:main`
  - `forex-live` -> `app.entrypoints.live:main`
- Legacy wrappers: `main_train.py` / `main_live.py` / `app.py` (optional; prefer CLI or `python -m app.entrypoints.*`).
- `src/app/bootstrap.py`: initializes logging, provider registry, use cases, event bus, and app state.
- `config/runtime.py`: reads environment config (TOKEN_FILE, BROKER_PROVIDER, LOG_LEVEL).

## 2) Application Layer
- `application/broker/use_cases.py`: main application flows; UI calls use-cases only.
- `application/broker/protocols.py`: Protocols that UI depends on.
- `application/broker/adapters.py`: converts service outputs into domain DTOs.

## 3) Domain Layer
- `domain/accounts.py`: Account, AccountFundsSnapshot.

## 4) Infrastructure Layer
- `infrastructure/broker/base.py`: base mixins/callbacks for broker services.
- `infrastructure/broker/errors.py`: shared broker error utilities.
- `infrastructure/broker/*`: provider implementations live here (verify the concrete provider folders present).

## 5) UI Layer
- `ui/train/`: training/replay UI.
- `ui/live/`: live trading UI.
- `ui/shared/`: shared UI pieces (currently a minimal base; expand as needed).

## 6) Event and State
- `application/events.py`: EventBus for in-process signals.
- `application/state.py`: AppState for shared status.

## 7) Core Flows
- AppAuth -> OAuth -> MainWindow
- AccountList -> AccountFunds
- Trendbar subscribe / Trendbar history fetch

## 8) Recommended Extensions
- Feature engineering: `ml/features/` with a pipeline and caching.
- RL/PPO: `ml/rl/ppo/`.
- Backtesting: `backtest/engine/`, `backtest/metrics/`, `backtest/report/`.
