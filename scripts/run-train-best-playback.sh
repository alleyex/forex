#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export QT_OPENGL="${QT_OPENGL:-software}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

RUN_TAG="${RUN_TAG:-best_playback_s12}"
DATA_PATH="${DATA_PATH:-data/raw_history/history-m10-1y.csv}"
RUN_DIR="data/training/runs/${RUN_TAG}"

mkdir -p "$RUN_DIR"

python3 -m forex.app.cli.train \
  --data "$DATA_PATH" \
  --feature-profile alpha20_residual \
  --seed 12 \
  --total-steps 1200000 \
  --learning-rate 3e-05 \
  --gamma 0.9788018156 \
  --n-steps 2048 \
  --batch-size 256 \
  --ent-coef 7.01154e-05 \
  --gae-lambda 0.9323691635 \
  --clip-range 0.15 \
  --target-kl 0.02 \
  --vf-coef 0.6095610779 \
  --n-epochs 8 \
  --episode-length 5120 \
  --eval-split 0.2 \
  --eval-freq 10000 \
  --eval-episodes 8 \
  --transaction-cost-bps 0.225 \
  --slippage-bps 0.03 \
  --holding-cost-bps 0.05 \
  --start-mode random \
  --min-position-change 0.15 \
  --max-position 1.0 \
  --position-step 0.05 \
  --reward-horizon 72 \
  --window-size 64 \
  --reward-scale 1.0 \
  --reward-clip 0.08 \
  --reward-mode path_penalty \
  --risk-aversion 0.1 \
  --drawdown-penalty 0.0 \
  --downside-penalty 0.02 \
  --turnover-penalty 0.0001 \
  --exposure-penalty 0.0 \
  --path-vol-penalty 0.25 \
  --path-downside-penalty 0.25 \
  --drawdown-governor-slope 3.0 \
  --drawdown-governor-floor 0.3 \
  --target-vol 0.008 \
  --vol-target-lookback 72 \
  --vol-scale-floor 0.5 \
  --vol-scale-cap 1.0 \
  --checkpoint-min-trade-rate 5.0 \
  --checkpoint-max-trade-rate 50.0 \
  --checkpoint-max-flat-ratio 0.98 \
  --checkpoint-max-ls-imbalance 0.2 \
  --checkpoint-max-drawdown 0.3 \
  --anti-flat-min-trade-rate 5.0 \
  --anti-flat-max-flat-ratio 0.98 \
  --anti-flat-max-ls-imbalance 0.2 \
  --anti-flat-profile-steps 2500 \
  --save-best-checkpoint \
  --model-out "${RUN_DIR}/model.zip" \
  --feature-scaler-out "${RUN_DIR}/model.scaler.json" \
  --env-config-out "${RUN_DIR}/model.env.json" \
  --training-args-out "${RUN_DIR}/training_args.json" \
  --training-status-out "${RUN_DIR}/training_status.json"
