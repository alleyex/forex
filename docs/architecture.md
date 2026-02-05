# Architecture Notes

## 1) Entry and Bootstrap
- `main_train.py` / `app.py`: app entry points.
- `bootstrap.py`: initializes logging, provider registry, use cases, event bus, and app state.
- `config/runtime.py`: reads environment config (TOKEN_FILE, BROKER_PROVIDER, LOG_LEVEL).

## 2) Application Layer
- `application/broker/use_cases.py`: main application flows; UI calls use-cases only.
- `application/broker/protocols.py`: Protocols that UI depends on.
- `application/broker/adapters.py`: converts service outputs into domain DTOs.

## 3) Domain Layer
- `domain/accounts.py`: Account, AccountFundsSnapshot.

## 4) Infrastructure Layer
- `infrastructure/broker/ctrader/provider.py`: provider implementation (cTrader).
- `infrastructure/broker/ctrader/services/*`: concrete services (auth, account list, funds, trendbar).
- `infrastructure/broker/fake/*`: fake provider for tests/offline.

## 5) UI Layer
- `ui/train/`: training/replay UI.
- `ui/live/`: live trading UI.
- `ui/shared/controllers/`: shared UI controllers (connection, process runner).
- `ui/shared/dialogs/`: shared auth/account dialogs.
- `ui/shared/widgets/`: reusable widgets.
- `ui/shared/styles/`: shared QSS and tokens.
- `ui/shared/utils/`: shared formatters and helpers.

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
