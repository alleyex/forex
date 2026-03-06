# Timeframe Readiness Comparison (5Y Clean Data)

## Verdict

All three tested timeframes remain `STOP`.

The problem is no longer "15m is too noisy." After cleaning the 5-year `15m` data and testing `15m`, `1h`, and `4h`, none of the baseline pipelines produced a strong enough, stable enough edge to justify advancing back into RL.

## Summary Table

| Timeframe | Verdict | Best heuristic | Session | Avg return | Avg sharpe | Avg max DD | Avg trade rate/1k | Pass rate |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 15m | STOP | `short` | `ny` | `-0.0109` | `-0.0078` | `0.0247` | `20.80` | `0.00` |
| 1h | STOP | `short_bias` | `ny` | `-0.0039` | `-0.0085` | `0.0136` | `53.78` | `0.33` |
| 4h | STOP | `momentum` | `all` | `-0.0044` | `-0.0133` | `0.0337` | `80.67` | `0.67` |

## What Improved

- `1h` and `4h` were somewhat more stable than `15m`.
- Drawdown metrics were generally lower than the noisier `15m` baselines.
- Some heuristic candidates began to pass individual segments more often.

## What Did Not Improve

- No timeframe achieved positive average Sharpe at the readiness level.
- No timeframe produced a baseline strong enough to justify advancing into RL.
- Supervised baselines stayed negative on all three timeframes.

## Best Supervised Candidates

| Timeframe | Feature set | Avg return | Avg sharpe | Avg max DD | Avg trade rate/1k | Pass rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 15m | `curated_v2` | `-0.0534` | `-0.0326` | `0.0608` | `73.53` | `0.00` |
| 1h | `full` | `-0.0373` | `-0.0350` | `0.0752` | `275.33` | `0.00` |
| 4h | `curated_v2` | `-0.0085` | `-0.0149` | `0.0456` | `262.22` | `0.00` |

## Interpretation

- Moving from `15m` to `1h` did not uncover a usable edge.
- Moving from `1h` to `4h` did not uncover a usable edge either.
- The remaining weakness appears to be task/market specific, not just timeframe specific.

## Recommendation

Stop spending more cycles on timeframe tuning for this market/task.

The next useful step is:

1. Pick a new symbol or market.
2. Reuse the same clean-data pipeline.
3. Re-run the same readiness checks before touching RL.

## Source Reports

- [/Users/alleyex/Documents/forex/docs/research_readiness_report_clean15m_5y.md](/Users/alleyex/Documents/forex/docs/research_readiness_report_clean15m_5y.md)
- [/Users/alleyex/Documents/forex/docs/research_readiness_report_clean1h_5y.md](/Users/alleyex/Documents/forex/docs/research_readiness_report_clean1h_5y.md)
- [/Users/alleyex/Documents/forex/docs/research_readiness_report_clean4h_5y.md](/Users/alleyex/Documents/forex/docs/research_readiness_report_clean4h_5y.md)
