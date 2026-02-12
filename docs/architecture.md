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

### Live UI module split (`src/forex/ui/live`)
- `main_window.py`: composition root for live UI. Holds wiring, Qt signal connections, and delegates logic to services/controllers/coordinators.
- `window_state.py`: initializes runtime state/timers/flags for `LiveMainWindow`.
- `ui_builder.py`: builds Auto Trading panel widgets and tab UI.

#### Coordinators (orchestrate one functional area)
- `layout_coordinator.py`: splitter sizing, panel alignment, resize behavior.
- `chart_coordinator.py`: chart window/range handling, quote-candle display update policy.
- `autotrade_coordinator.py`: strategy decision flow, position execution, sizing/risk helper logic.

#### Services (focused supporting logic)
- `auto_log_service.py`: auto-trade log level inference and normalized log output.
- `auto_settings_validator.py`: pre-start validation for auto-trade settings.
- `auto_settings_persistence.py`: auto-trade settings load/save and lot/risk mode UI sync.
- `auto_runtime_service.py`: model loading and order-service setup/execution callback handling.
- `auto_lifecycle_service.py`: auto-trade start/stop lifecycle transitions.
- `auto_recovery_service.py`: watchdog + history-poll recovery logic.
- `symbol_list_service.py`: symbol list refresh/apply + trade symbol combo synchronization.
- `value_formatter_service.py`: price/time/current-price formatting utilities used by controllers.

#### Controllers (I/O + UI table/event updates)
- `account_controller.py`: account list handling, account switching, account-scoped state.
- `market_data_controller.py`: recent history/trendbar request & handling.
- `quote_controller.py`: quote subscription and quote table updates.
- `positions_controller.py`: positions subscription/request/table updates + account summary rendering.
- `symbol_controller.py`: symbol catalog/detail lookup and quote-symbol management.

## 6) Event and State
- `forex.application.events`: EventBus for in-process signals.
- `forex.application.state`: AppState for shared status.

## 7) Core Flows
- AppAuth -> OAuth -> MainWindow
- AccountList -> AccountFunds
- Trendbar subscribe / Trendbar history fetch
- Live Auto Trade start:
  1. `auto_settings_validator` checks UI parameters
  2. `auto_runtime_service` loads model + scaler and ensures order service
  3. `autotrade_coordinator` executes decision/position flow on candle close
  4. `auto_recovery_service` watchdog/history-poll keeps feed healthy

## 8) Recommended Extensions
- Feature engineering: `forex.ml.features` with a pipeline and caching.
- RL/PPO: `forex.ml.rl.ppo`.
- Backtesting: `forex.backtest.engine`, `forex.backtest.metrics`, `forex.backtest.report`.
