from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

import ast
import re

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from forex.config.paths import SRC_DIR, TRAIN_PPO_SCRIPT
from forex.config.paths import DATA_DIR
from forex.ui.shared.controllers.process_runner import ProcessRunner
from forex.ui.train.state.training_state import TrainingState
from forex.ui.shared.utils.formatters import format_training_message


class PPOTrainingController(QObject):
    best_params_found = Signal(dict)
    replay_best_params_logged = Signal(dict)
    replay_best_summary_logged = Signal(str)
    optuna_trial_logged = Signal(str)
    optuna_best_params_logged = Signal(dict)
    device_resolved = Signal(str)
    run_initialized = Signal(str, str)

    def __init__(
        self,
        *,
        parent: QObject,
        state: TrainingState,
        ingest_log: Callable[[str], None],
        ingest_optuna_log: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[int, QProcess.ExitStatus], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._ingest_log = ingest_log
        self._ingest_optuna_log = ingest_optuna_log
        self._on_finished = on_finished
        self._runner = ProcessRunner(
            parent=self,
            on_stdout_line=self._on_stdout_line,
            on_stderr_line=self._on_stderr_line,
            on_finished=self._on_finished_internal,
        )
        self._metrics_log_path: Optional[str] = None
        self._metrics_tail_timer = QTimer(self)
        self._metrics_tail_timer.setInterval(50)
        self._metrics_tail_timer.timeout.connect(self._tail_metrics_log)
        self._metrics_last_offset = 0
        self._use_metrics_log = False
        self._optuna_log_path: Optional[str] = None
        self._optuna_tail_timer = QTimer(self)
        self._optuna_tail_timer.setInterval(200)
        self._optuna_tail_timer.timeout.connect(self._tail_optuna_log)
        self._optuna_last_offset = 0
        self._feature_subset_path: Optional[str] = None
        self._current_run_id: str = ""
        self._current_run_dir: Optional[Path] = None
        self._used_best_checkpoint = False
        self._best_checkpoint_path: Optional[str] = None
        self._best_checkpoint_missing = False

    def start(self, params: dict, data_path: str) -> None:
        if self._runner.is_running():
            self._state.log_message.emit(format_training_message("already_running"))
            return

        optuna_only = bool(params.get("optuna_only"))
        if optuna_only and params.get("optuna_trials", 0) <= 0:
            self._state.log_message.emit(format_training_message("optuna_trials_required"))
            return

        self._state.log_message.emit(format_training_message("start"))
        run_id, run_dir = self._prepare_run_context(params)
        self._current_run_id = run_id
        self._current_run_dir = run_dir
        self._used_best_checkpoint = False
        self._best_checkpoint_path = None
        self._best_checkpoint_missing = False
        self.run_initialized.emit(run_id, str(run_dir))
        self._start_metrics_log_tailer()
        self._use_metrics_log = True
        if params.get("optuna_trials", 0) > 0:
            self._start_optuna_log_tailer()
        args = [
            TRAIN_PPO_SCRIPT,
            "--data",
            data_path,
            "--model-out",
            str(run_dir / "model.zip"),
            "--feature-scaler-out",
            str(run_dir / "model.scaler.json"),
            "--env-config-out",
            str(run_dir / "model.env.json"),
            "--training-args-out",
            str(run_dir / "training_args.json"),
            "--training-status-out",
            str(run_dir / "training_status.json"),
            "--total-steps",
            str(params["total_steps"]),
            "--learning-rate",
            str(params["learning_rate"]),
            "--gamma",
            str(params["gamma"]),
            "--n-steps",
            str(params["n_steps"]),
            "--batch-size",
            str(params["batch_size"]),
            "--ent-coef",
            str(params["ent_coef"]),
            "--gae-lambda",
            str(params["gae_lambda"]),
            "--clip-range",
            str(params["clip_range"]),
            "--target-kl",
            str(params.get("target_kl", 0.0)),
            "--device",
            str(params.get("device", "auto")),
            "--seed",
            str(params.get("seed", 0)),
            "--vf-coef",
            str(params["vf_coef"]),
            "--n-epochs",
            str(params["n_epochs"]),
            "--episode-length",
            str(params["episode_length"]),
            "--eval-split",
            str(params["eval_split"]),
            "--transaction-cost-bps",
            str(params["transaction_cost_bps"]),
            "--slippage-bps",
            str(params["slippage_bps"]),
            "--holding-cost-bps",
            str(params["holding_cost_bps"]),
            "--min-position-change",
            str(params["min_position_change"]),
            "--max-position",
            str(params["max_position"]),
            "--position-step",
            str(params["position_step"]),
            "--reward-horizon",
            str(params["reward_horizon"]),
            "--window-size",
            str(params.get("window_size", 1)),
            "--start-mode",
            str(params.get("start_mode", "random")),
            "--feature-profile",
            str(params.get("feature_profile", "alpha20_residual")),
            "--reward-scale",
            str(params["reward_scale"]),
            "--reward-clip",
            str(params["reward_clip"]),
            "--reward-mode",
            str(params.get("reward_mode", "tp_sl_proxy")),
            "--risk-aversion",
            str(params["risk_aversion"]),
            "--drawdown-penalty",
            str(params.get("drawdown_penalty", 0.0)),
            "--downside-penalty",
            str(params.get("downside_penalty", 0.0)),
            "--turnover-penalty",
            str(params.get("turnover_penalty", 0.0)),
            "--exposure-penalty",
            str(params.get("exposure_penalty", 0.0)),
            "--flat-position-penalty",
            str(params.get("flat_position_penalty", 0.0)),
            "--flat-streak-penalty",
            str(params.get("flat_streak_penalty", 0.0)),
            "--flat-position-threshold",
            str(params.get("flat_position_threshold", 1e-6)),
            "--target-vol",
            str(params.get("target_vol", 0.0)),
            "--vol-target-lookback",
            str(params.get("vol_target_lookback", 72)),
            "--vol-scale-floor",
            str(params.get("vol_scale_floor", 0.5)),
            "--vol-scale-cap",
            str(params.get("vol_scale_cap", 1.5)),
            "--drawdown-governor-slope",
            str(params.get("drawdown_governor_slope", 0.0)),
            "--drawdown-governor-floor",
            str(params.get("drawdown_governor_floor", 0.3)),
        ]
        selected_features = params.get("selected_features", [])
        if isinstance(selected_features, list) and selected_features:
            tmp_dir = Path(tempfile.gettempdir())
            subset_path = tmp_dir / f"ppo_feature_subset_{id(self)}.json"
            subset_payload = {"selected_features": selected_features}
            subset_path.write_text(
                json.dumps(subset_payload, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            self._feature_subset_path = str(subset_path)
            args.extend(["--feature-subset-json", self._feature_subset_path])
        if params.get("curriculum_enabled", False):
            args.append("--curriculum-enabled")
        args.extend(["--curriculum-steps", str(params.get("curriculum_steps", 25000))])
        args.extend(
            ["--curriculum-max-position", str(params.get("curriculum_max_position", 0.2))]
        )
        args.extend(
            ["--curriculum-position-step", str(params.get("curriculum_position_step", 0.1))]
        )
        args.extend(
            [
                "--curriculum-min-position-change",
                str(params.get("curriculum_min_position_change", 0.05)),
            ]
        )
        args.append(
            "--early-stop-enabled" if params.get("early_stop_enabled", True) else "--no-early-stop-enabled"
        )
        args.extend(["--early-stop-warmup-steps", str(params.get("early_stop_warmup_steps", 120000))])
        args.extend(
            ["--early-stop-patience-evals", str(params.get("early_stop_patience_evals", 8))]
        )
        args.extend(["--early-stop-min-delta", str(params.get("early_stop_min_delta", 0.001))])
        args.append(
            "--anti-flat-enabled" if params.get("anti_flat_enabled", True) else "--no-anti-flat-enabled"
        )
        args.extend(["--anti-flat-warmup-steps", str(params.get("anti_flat_warmup_steps", 120000))])
        args.extend(
            ["--anti-flat-patience-evals", str(params.get("anti_flat_patience_evals", 3))]
        )
        args.extend(
            ["--eval-profile-steps", str(params.get("eval_profile_steps", 2500))]
        )
        args.extend(
            [
                "--checkpoint-min-trade-rate",
                str(params.get("checkpoint_min_trade_rate", 5.0)),
            ]
        )
        args.extend(
            [
                "--checkpoint-max-trade-rate",
                str(params.get("checkpoint_max_trade_rate", 25.0)),
            ]
        )
        args.extend(
            [
                "--checkpoint-max-flat-ratio",
                str(params.get("checkpoint_max_flat_ratio", 0.9)),
            ]
        )
        args.extend(
            [
                "--checkpoint-max-ls-imbalance",
                str(params.get("checkpoint_max_ls_imbalance", 0.35)),
            ]
        )
        args.extend(
            [
                "--checkpoint-max-drawdown",
                str(params.get("checkpoint_max_drawdown", 0.30)),
            ]
        )
        args.extend(
            ["--anti-flat-min-trade-rate", str(params.get("anti_flat_min_trade_rate", 5.0))]
        )
        args.extend(
            ["--anti-flat-max-flat-ratio", str(params.get("anti_flat_max_flat_ratio", 0.98))]
        )
        args.extend(
            [
                "--anti-flat-max-ls-imbalance",
                str(params.get("anti_flat_max_ls_imbalance", 0.2)),
            ]
        )
        args.extend(
            ["--anti-flat-profile-steps", str(params.get("anti_flat_profile_steps", 2500))]
        )
        args.extend(["--metrics-log", self._metrics_log_path or ""])
        if not params.get("random_start", True) and not params.get("start_mode"):
            args.append("--no-random-start")
        if params.get("optuna_trials", 0) > 0:
            args.extend(
                [
                    "--optuna-trials",
                    str(params["optuna_trials"]),
                    "--optuna-steps",
                    str(params["optuna_steps"]),
                ]
            )
            if self._optuna_log_path:
                args.extend(["--optuna-log", self._optuna_log_path])
            if params.get("optuna_auto_select"):
                args.append("--optuna-auto-select")
            select_mode = str(params.get("optuna_select_mode", "top_k")).strip()
            args.extend(["--optuna-select-mode", select_mode])
            args.extend(["--optuna-top-k", str(params.get("optuna_top_k", 5))])
            args.extend(["--optuna-top-percent", str(params.get("optuna_top_percent", 20.0))])
            args.extend(
                ["--optuna-min-candidates", str(params.get("optuna_min_candidates", 3))]
            )
            top_out = str(params.get("optuna_top_out", "")).strip() or str(run_dir / "optuna_top_params.json")
            args.extend(["--optuna-top-out", top_out])
            if params.get("optuna_replay_enabled"):
                args.append("--optuna-replay-enabled")
                args.extend(
                    ["--optuna-replay-steps", str(params.get("optuna_replay_steps", 200000))]
                )
                args.extend(
                    ["--optuna-replay-seeds", str(params.get("optuna_replay_seeds", 3))]
                )
                args.extend(
                    [
                        "--optuna-replay-score-mode",
                        str(params.get("optuna_replay_score_mode", "walk_forward")),
                    ]
                )
                args.extend(
                    [
                        "--optuna-replay-walk-forward-segments",
                        str(params.get("optuna_replay_walk_forward_segments", 3)),
                    ]
                )
                args.extend(
                    [
                        "--optuna-replay-walk-forward-steps",
                        str(params.get("optuna_replay_walk_forward_steps", 2500)),
                    ]
                )
                args.extend(
                    [
                        "--optuna-replay-walk-forward-stride",
                        str(params.get("optuna_replay_walk_forward_stride", 2500)),
                    ]
                )
                args.extend(
                    [
                        "--optuna-replay-min-trade-rate",
                        str(params.get("optuna_replay_min_trade_rate", 5.0)),
                    ]
                )
                args.extend(
                    [
                        "--optuna-replay-max-flat-ratio",
                        str(params.get("optuna_replay_max_flat_ratio", 0.98)),
                    ]
                )
                args.extend(
                    [
                        "--optuna-replay-max-ls-imbalance",
                        str(params.get("optuna_replay_max_ls_imbalance", 0.2)),
                    ]
                )
                replay_out = str(params.get("optuna_replay_out", "")).strip() or str(run_dir / "optuna_replay_results.json")
                args.extend(["--optuna-replay-out", replay_out])
            optuna_out = str(params.get("optuna_out", "")).strip() or str(run_dir / "optuna_best_params.json")
            args.extend(["--optuna-out", optuna_out])
            if optuna_only:
                args.extend(["--verbose", "0"])
        if params.get("save_best_checkpoint", True):
            args.append("--save-best-checkpoint")
        started = self._runner.start(sys.executable, args, env={"PYTHONPATH": str(SRC_DIR)})
        if not started:
            self._state.log_message.emit(format_training_message("start_failed"))
            self._stop_metrics_log_tailer()
            self._stop_optuna_log_tailer()

    @staticmethod
    def _prepare_run_context(params: dict) -> tuple[str, Path]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        profile = str(params.get("feature_profile", "raw53")).strip().lower() or "raw53"
        seed = int(params.get("seed", 0))
        suffix = uuid4().hex[:6]
        run_id = f"{timestamp}_{profile}_s{seed}_{suffix}"
        run_dir = Path(DATA_DIR) / "training" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_id, run_dir

    def is_running(self) -> bool:
        return self._runner.is_running()

    def stop(self, *, blocking: bool = False) -> None:
        if not self._runner.is_running():
            return
        if blocking:
            self._runner.stop_blocking()
        else:
            self._runner.stop(kill_after_ms=10000)

    def _on_stdout_line(self, line: str) -> None:
        if self._use_metrics_log:
            if self._should_log_summary(line):
                self._state.log_message.emit(line)
        else:
            self._state.log_message.emit(line)
            self._ingest_log(line)
        self._handle_optuna_line(line)
        if line.startswith("Optuna best params:"):
            payload = line.split(":", 1)[1].strip()
            try:
                params = ast.literal_eval(payload)
            except (ValueError, SyntaxError):
                return
            if isinstance(params, dict):
                self.best_params_found.emit(params)
        if line.startswith("Replay best params:"):
            payload = line.split(":", 1)[1].strip()
            try:
                params = ast.literal_eval(payload)
            except (ValueError, SyntaxError):
                return
            if isinstance(params, dict):
                self.replay_best_params_logged.emit(params)
        if line.startswith("Replay best:"):
            self.replay_best_summary_logged.emit(line.strip())
        if line.startswith("Resolved device:"):
            self.device_resolved.emit(line.split(":", 1)[1].strip())
        if line.startswith("Using best eval checkpoint:"):
            self._used_best_checkpoint = True
            self._best_checkpoint_missing = False
            self._best_checkpoint_path = line.split(":", 1)[1].strip()
        elif line.startswith("Best eval checkpoint not found;"):
            self._used_best_checkpoint = False
            self._best_checkpoint_missing = True
            self._best_checkpoint_path = None

    def _on_stderr_line(self, line: str) -> None:
        self._state.log_message.emit(format_training_message("stderr", line=line))
        self._handle_optuna_line(line)

    def _on_finished_internal(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._state.log_message.emit(
            format_training_message(
                "finished",
                exit_status=exit_status == QProcess.NormalExit,
                exit_code=exit_code,
            )
        )
        self._tail_metrics_log()
        self._tail_optuna_log()
        self._stop_metrics_log_tailer()
        self._stop_optuna_log_tailer()
        if self._on_finished:
            self._on_finished(exit_code, exit_status)

    def _start_metrics_log_tailer(self) -> None:
        tmp_dir = Path(tempfile.gettempdir())
        self._metrics_log_path = str(tmp_dir / f"ppo_metrics_{id(self)}.csv")
        self._metrics_last_offset = 0
        self._metrics_tail_timer.start()

    def _stop_metrics_log_tailer(self) -> None:
        self._metrics_tail_timer.stop()
        if self._metrics_log_path:
            try:
                Path(self._metrics_log_path).unlink(missing_ok=True)
            except Exception:
                pass
        self._metrics_log_path = None
        self._metrics_last_offset = 0
        self._use_metrics_log = False

    def _tail_metrics_log(self) -> None:
        if not self._metrics_log_path:
            return
        path = Path(self._metrics_log_path)
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as fh:
                fh.seek(self._metrics_last_offset)
                data = fh.read()
                self._metrics_last_offset = fh.tell()
        except Exception:
            return
        if not data:
            return
        for line in data.strip().splitlines():
            if line.startswith("step"):
                continue
            self._ingest_log(line)

    def _start_optuna_log_tailer(self) -> None:
        if self._ingest_optuna_log is None:
            return
        tmp_dir = Path(tempfile.gettempdir())
        self._optuna_log_path = str(tmp_dir / f"ppo_optuna_{id(self)}.csv")
        self._optuna_last_offset = 0
        self._optuna_tail_timer.start()

    def _stop_optuna_log_tailer(self) -> None:
        self._optuna_tail_timer.stop()
        if self._optuna_log_path:
            try:
                Path(self._optuna_log_path).unlink(missing_ok=True)
            except Exception:
                pass
        self._optuna_log_path = None
        self._optuna_last_offset = 0

    def _tail_optuna_log(self) -> None:
        if not self._optuna_log_path or self._ingest_optuna_log is None:
            return
        path = Path(self._optuna_log_path)
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as fh:
                fh.seek(self._optuna_last_offset)
                data = fh.read()
                self._optuna_last_offset = fh.tell()
        except Exception:
            return
        if not data:
            return
        for line in data.strip().splitlines():
            if line.startswith("trial"):
                continue
            self._ingest_optuna_log(line)

    @staticmethod
    def _should_log_summary(line: str) -> bool:
        return (
            line.startswith("Training setup:")
            or line.startswith("Resolved device:")
            or line.startswith("Early stop:")
            or line.startswith("Using best eval checkpoint")
            or line.startswith("Optuna best")
            or line.startswith("Optuna auto-select:")
            or line.startswith("Replay candidate:")
            or line.startswith("Replay progress:")
            or line.startswith("Replay best:")
        )

    def _handle_optuna_line(self, line: str) -> None:
        summary, best_params = self._parse_optuna_trial_details(line)
        if summary:
            self.optuna_trial_logged.emit(summary)
        if best_params:
            self.optuna_best_params_logged.emit(best_params)

    @staticmethod
    def _parse_optuna_trial_details(line: str) -> tuple[Optional[str], Optional[dict]]:
        match = re.search(
            r"Trial\s+(?P<trial>\d+)\s+finished with value:\s+(?P<value>[-+0-9.eE]+)",
            line,
        )
        best_match = re.search(
            r"Best is trial\s+(?P<best_trial>\d+)\s+with value:\s+(?P<best_value>[-+0-9.eE]+)",
            line,
        )
        if not match or not best_match:
            return None, None
        trial = match.group("trial")
        value = match.group("value")
        best_trial = best_match.group("best_trial")
        best_value = best_match.group("best_value")
        summary = f"Trial {trial}: value={value} | best={best_value} (trial {best_trial})"
        best_params = None
        if trial == best_trial:
            params_match = re.search(
                r"parameters:\s+(\{.*?\})(?:\.\s+Best is trial|$)",
                line,
            )
            if params_match:
                params_text = params_match.group(1)
                try:
                    parsed = ast.literal_eval(params_text)
                except (ValueError, SyntaxError):
                    parsed = None
                if isinstance(parsed, dict):
                    best_params = parsed
        return summary, best_params

    def build_checkpoint_summary(self) -> dict:
        payload = {
            "run_id": self._current_run_id or "-",
            "run_dir": str(self._current_run_dir) if self._current_run_dir else "-",
            "used_best_checkpoint": self._used_best_checkpoint,
            "best_checkpoint_path": self._best_checkpoint_path or "",
            "best_checkpoint_missing": self._best_checkpoint_missing,
        }
        run_dir = self._current_run_dir
        if run_dir is None:
            return payload
        status_path = run_dir / "training_status.json"
        if status_path.exists():
            try:
                status_payload = json.loads(status_path.read_text(encoding="utf-8"))
                if isinstance(status_payload, dict):
                    payload.update(
                        {
                            "run_status": status_payload.get("status") or "-",
                            "run_stop_reason": status_payload.get("stop_reason") or "-",
                            "run_exit_code": status_payload.get("exit_code"),
                            "run_stopped_early": status_payload.get("stopped_early"),
                            "run_last_step": status_payload.get("last_step"),
                            "run_total_steps_target": status_payload.get("total_steps_target"),
                        }
                    )
            except Exception:
                pass
        diagnostics_path = run_dir / "training_diagnostics.csv"
        if not diagnostics_path.exists():
            return payload
        try:
            import csv

            with diagnostics_path.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            return payload
        if not rows:
            return payload

        def _to_float(value: object) -> float:
            try:
                text = str(value).strip()
                if not text:
                    return float("-inf")
                return float(text)
            except Exception:
                return float("-inf")

        best_row = max(
            rows,
            key=lambda row: _to_float(row.get("best_eval_reward") or row.get("eval_mean_reward")),
        )
        last_row = rows[-1]
        payload.update(
            {
                "best_eval_reward": best_row.get("best_eval_reward") or best_row.get("eval_mean_reward") or "-",
                "best_eval_mean_reward": best_row.get("eval_mean_reward") or "-",
                "best_checkpoint_gate": best_row.get("checkpoint_gate") or "-",
                "best_rolling_sharpe": best_row.get("rolling_sharpe") or "-",
                "best_eval_trade_rate_1k": best_row.get("eval_trade_rate_1k") or "-",
                "best_eval_ls_imbalance": best_row.get("eval_ls_imbalance") or "-",
                "best_eval_max_drawdown": best_row.get("eval_max_drawdown") or "-",
                "last_eval_mean_reward": last_row.get("eval_mean_reward") or "-",
                "last_checkpoint_gate": last_row.get("checkpoint_gate") or "-",
            }
        )
        return payload
