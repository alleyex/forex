# Data Directory

This directory is reserved for runtime/generated data.

- Keep only lightweight placeholders in git.
- Raw history, soak logs, and other artifacts should stay untracked.
- Active UI settings are split by responsibility:
  - `data/training/training_params.json`: training parameters only
  - `data/simulation/simulation_params.json`: playback parameters only
- Training diagnostics live in `data/training/`.
- Optuna outputs live in `data/optuna/` and are not auto-applied on startup.
