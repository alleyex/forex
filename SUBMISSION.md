# RL Trading Environment — work sample for Tensium
Peter Lin · my own original project (not produced for any client)

## What this is
A production RL environment for FX, built solo end to end: a Gymnasium environment with a
multi-mode reward/risk engine, Stable-Baselines3 PPO training, and a walk-forward evaluation
harness with heuristic + supervised baselines. Layered architecture
(domain / application / infrastructure / ui / ml) with import-linter-enforced boundaries; full
lint / type / test / CI hygiene.

I'm sending this not because the policy "won" — it didn't — but because it shows how I design a
reward, attack it, measure signal vs noise, and stop a line when the edge doesn't survive out of
sample. The domain is financial RL, not coding-eval; the discipline is what transfers.

## Read first (the judgement, not just the code)
- `docs/rl_research_stop_summary.md` — how I evaluated it and why I stopped the line
- `src/forex/ml/rl/envs/trading_env.py` — the environment + multi-mode reward / risk engine
- `src/forex/tools/rl/walk_forward_eval.py` — out-of-sample walk-forward harness
- `docs/research_readiness_report*.md` — data-quality / leakage validation

## Run it (Python 3.10+)
```bash
# install (editable, ml extras)
make install-dev                      # or: ./scripts/bootstrap.sh

# 1) train a PPO policy (full reference config)
DATA_PATH=data/raw_history/history.csv ./scripts/run-train-best-playback.sh

# 2) walk-forward (out-of-sample) evaluation of the trained model
python3 -m forex.tools.rl.walk_forward_eval \
  --data data/raw_history/history.csv \
  --model data/training/runs/best_playback_s12/model.zip \
  --feature-scaler data/training/runs/best_playback_s12/model.scaler.json \
  --env-config data/training/runs/best_playback_s12/model.env.json \
  --json-out walk_forward.json

# 3) baselines the policy must beat
python3 -m forex.tools.rl.heuristic_baseline_eval  --data data/raw_history/history.csv --json-out heuristics.json
python3 -m forex.tools.rl.supervised_baseline_eval --data data/raw_history/history.csv --json-out supervised.json
```

Note: raw market data is not committed (data governance). The commands show the workflow, and I can
share a data sample on request.

## Headline result (the honest finding)
On ~15 years (2011–2026, 141,064 bars), PPO produced no stable, cross-regime, risk-adjusted edge
and did not beat simple heuristic / supervised baselines; the apparent edge did not survive
walk-forward. Full reasoning and receipts: `docs/rl_research_stop_summary.md`
