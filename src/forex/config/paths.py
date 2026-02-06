from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT_DIR / "src" / "forex"
DATA_DIR = str(ROOT_DIR / "data")
RAW_HISTORY_DIR = str(ROOT_DIR / "data" / "raw_history")

TOKEN_FILE = os.getenv("TOKEN_FILE", str(ROOT_DIR / "token.json"))
SYMBOL_LIST_FILE = os.getenv("SYMBOL_LIST_FILE", str(ROOT_DIR / "symbol.json"))
TIMEFRAMES_FILE = os.getenv("TIMEFRAMES_FILE", str(ROOT_DIR / "timeframes.json"))

TRAIN_PPO_SCRIPT = str(SRC_DIR / "tools" / "rl" / "train_ppo.py")
RUN_LIVE_SIM_SCRIPT = str(SRC_DIR / "tools" / "rl" / "run_live_sim.py")
MODEL_DIR = str(SRC_DIR / "ml" / "rl" / "models")
DEFAULT_MODEL_PATH = str(SRC_DIR / "ml" / "rl" / "models" / "ppo_forex.zip")
