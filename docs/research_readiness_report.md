# Research Readiness Report

## Verdict

`STOP`

## Reasons

- Best baseline avg_sharpe is only 0.0469.
- Best baseline pass_rate is only 0.33.
- No baseline keeps average max drawdown under 15% (best 0.1750).
- Current evidence does not justify advancing to RL.

## Best Heuristic

- strategy: `short_bias`
- session: `all`
- source: `/Users/alleyex/Documents/forex/data/optuna/heuristic_session_scan_15y_6x10k.json`
- avg_return: `116.628122`
- avg_sharpe: `0.044381`
- avg_max_drawdown: `0.379710`
- avg_trade_rate_1k: `37.07`
- pass_rate: `0.00`

## Best Supervised

- strategy: `-`
- session: `-`
- source: `/Users/alleyex/Documents/forex/data/optuna/supervised_ny_linear_t010.json`
- avg_return: `0.695003`
- avg_sharpe: `0.046890`
- avg_max_drawdown: `0.174985`
- avg_trade_rate_1k: `108.73`
- pass_rate: `0.33`
