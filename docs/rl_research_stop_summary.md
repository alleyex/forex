# RL Research Stop Summary

## Scope

This summary records the end-state of the PPO-based forex research line on `/Users/alleyex/Documents/forex/data/raw_history/history.csv` after extending the dataset to roughly 15 years (`2011-03-05` to `2026-03-04`, `141,064` rows).

The core question was whether the project could produce a stable, risk-adjusted RL trading policy with materially positive Sharpe, ideally much higher than the current near-zero range.

## Final Decision

Stop the current PPO research line on this task definition.

Reason:

- The data does not show a stable, cross-regime edge under the current target and execution setup.
- PPO did not outperform simple heuristics or simple supervised baselines in a way that justified continued tuning.
- More data improved confidence in the conclusion, but did not reveal a stable tradable signal.

## What Was Tested

### Evaluation fixes

- Sharpe calculation was corrected to use equity returns instead of raw equity differences.
- Walk-forward evaluation was added and integrated into replay/ranking.

### RL-side changes

- Risk-adjusted reward shaping
- Turnover penalty
- Flat-position penalties
- Anti-flat early stop
- Curriculum stage
- Heuristic warm-start
- Balanced warm-start labels
- Position-bias penalty
- Session-filtered training (`all`, `monday_open`, `london`, `ny`, `overlap`)

### Non-RL baselines

- Fixed `long`, `short`, `flat`
- `momentum`
- `breakout20`
- `breakout50`
- `mean_revert`
- `short_bias`
- Regime-switched heuristics
- NY-only supervised linear baseline

## Main Findings

### 1. PPO never produced a stable, positive-quality solution

The most useful intermediate improvements were:

- warm-start removed the no-trade basin
- anti-flat prevented wasted training
- NY-only filtering reduced instability during training

But none of these produced a playback result with robust positive Sharpe and acceptable drawdown.

Examples:

- `NY-only PPO seed 10101`
  - `Return = -16.12%`
  - `Sharpe = -0.0388`
  - `Max DD = 32.56%`
- `NY-only PPO seed 10102`
  - `Return = -32.57%`
  - `Sharpe = -0.0727`
  - `Max DD = 43.80%`

### 2. Heuristic baselines showed regime dependence, not stable edge

On shorter samples, `short` or `short_bias` sometimes looked promising, especially in NY session. After extending the sample to 15 years and running wider walk-forward checks:

- `short / all-session`
  - average Sharpe stayed low
  - drawdowns were extreme
  - some segments were strongly positive, others strongly negative
- `short_bias / ny-session`
  - was the least-bad heuristic
  - but still only had weak average Sharpe and limited pass count

This indicates partial directional bias in some subperiods, not a stable all-weather strategy.

### 3. More data made the conclusion clearer

Moving from ~5 years to ~15 years did not reveal a stronger stable edge.

Instead it showed:

- large performance dispersion across segments
- strong regime dependence
- no strategy family consistently clearing quality gates

### 4. Supervised baseline was slightly better than heuristic, but still too weak

The NY-only supervised linear baseline improved on heuristic baselines, but still did not reach a meaningful pass rate or Sharpe level.

Best threshold sweep result:

- aggressive threshold (`long=0.10`, `short=-0.10`)
  - `avg_return = +69.50%`
  - `avg_sharpe = 0.0469`
  - `avg_max_dd = 17.50%`
  - `pass_count = 1/3`

This is still far below the target quality bar and does not support continued PPO tuning.

## Why This Line Should Stop

The limiting factor is no longer optimizer settings, PPO architecture, or reward coefficients.

The limiting factor is:

- weak edge magnitude
- unstable edge across time
- insufficient cross-regime consistency

This means continued tuning is likely to produce:

- more local overfitting
- more threshold games
- little improvement in true out-of-sample quality

## Recommended Next Direction

Do not continue tuning this PPO setup on this target.

Preferred next options:

1. Change the task definition
   - different symbol
   - different timeframe
   - different target horizon
   - different execution assumptions

2. Start from baseline research again
   - validate simple heuristics first
   - then validate simple supervised models
   - only reintroduce RL if a stable baseline edge is proven

3. If staying in FX, narrow the research question
   - specific session only
   - specific regime only
   - explicit directional bias hypothesis

## Practical Rule Going Forward

Before starting a new RL line:

- require a heuristic or supervised baseline with clearly positive walk-forward Sharpe
- require acceptable drawdown across multiple segments
- require more than isolated wins in one or two subperiods

If those conditions are not met, RL should not be the next tool.
