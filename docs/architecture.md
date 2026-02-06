# Architecture Notes

## 1) Entry and Bootstrap
- `src/forex/app/entrypoints/*`: primary entry points (train/live/auth).
- CLI entry points via `pyproject.toml`:
  - `forex-train` -> `forex.app.entrypoints.train:main`
  - `forex-live` -> `forex.app.entrypoints.live:main`
- Legacy wrappers: `main_train.py` / `main_live.py` / `app.py` (optional; prefer CLI or `python -m forex.app.entrypoints.*`).
- `src/forex/app/bootstrap.py`: initializes logging, provider registry, use cases, event bus, and app state.
- `forex.config.runtime`: reads environment config (TOKEN_FILE, BROKER_PROVIDER, LOG_LEVEL).

## 2) Application Layer
- `forex.application.broker.use_cases`: main application flows; UI calls use-cases only.
- `forex.application.broker.protocols`: Protocols that UI depends on.
- `forex.application.broker.adapters`: converts service outputs into domain DTOs.

## 3) Domain Layer
- `forex.domain.accounts`: Account, AccountFundsSnapshot.

## 4) Infrastructure Layer
- `forex.infrastructure.broker.base`: base mixins/callbacks for broker services.
- `forex.infrastructure.broker.errors`: shared broker error utilities.
- `forex.infrastructure.broker.*`: provider implementations live here (verify the concrete provider folders present).

## 5) UI Layer
- `forex.ui.train`: training/replay UI.
- `forex.ui.live`: live trading UI.
- `forex.ui.shared`: shared UI pieces (currently a minimal base; expand as needed).

## 6) Event and State
- `forex.application.events`: EventBus for in-process signals.
- `forex.application.state`: AppState for shared status.

## 7) Core Flows
- AppAuth -> OAuth -> MainWindow
- AccountList -> AccountFunds
- Trendbar subscribe / Trendbar history fetch

## 8) Recommended Extensions
- Feature engineering: `forex.ml.features` with a pipeline and caching.
- RL/PPO: `forex.ml.rl.ppo`.
- Backtesting: `forex.backtest.engine`, `forex.backtest.metrics`, `forex.backtest.report`.
