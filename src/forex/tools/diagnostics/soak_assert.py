from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from forex.tools.diagnostics.reconnect_log_analyzer import (
    ReconnectLogStats,
    analyze_reconnect_log,
    resolve_log_file,
)


@dataclass(frozen=True)
class SoakThresholds:
    min_app_auth_success: int = 1
    min_account_auth_success: int = 1
    max_attempt: int = 20
    max_funds_timeout: int = 30
    min_reconnect_success_ratio: float = 0.5
    min_runtime_resume_ratio: float = 0.5


def is_insufficient_data(stats: ReconnectLogStats, *, min_lines: int = 20) -> bool:
    key_events = (
        stats.disconnect_events
        + stats.reconnect_scheduled
        + stats.connect_started
        + stats.connected
        + stats.app_auth_sent
        + stats.app_auth_success
        + stats.account_auth_success
        + stats.funds_timeout
        + stats.request_deferred
        + stats.runtime_stalled
        + stats.runtime_resume
    )
    return stats.lines < max(1, int(min_lines)) or key_events == 0


def evaluate_soak(stats: ReconnectLogStats, thresholds: SoakThresholds) -> list[str]:
    failures: list[str] = []
    if stats.app_auth_success < thresholds.min_app_auth_success:
        failures.append(
            f"app_auth_success={stats.app_auth_success} < {thresholds.min_app_auth_success}"
        )
    if stats.account_auth_success < thresholds.min_account_auth_success:
        failures.append(
            "account_auth_success="
            f"{stats.account_auth_success} < {thresholds.min_account_auth_success}"
        )
    if stats.max_attempt > thresholds.max_attempt:
        failures.append(f"max_attempt={stats.max_attempt} > {thresholds.max_attempt}")
    if stats.funds_timeout > thresholds.max_funds_timeout:
        failures.append(f"funds_timeout={stats.funds_timeout} > {thresholds.max_funds_timeout}")

    if stats.reconnect_scheduled > 0:
        if stats.reconnect_success_ratio < thresholds.min_reconnect_success_ratio:
            failures.append(
                "reconnect_success_ratio="
                f"{stats.reconnect_success_ratio:.2f} < {thresholds.min_reconnect_success_ratio:.2f}"
            )

    if stats.runtime_stalled > 0:
        resume_ratio = stats.runtime_resume / float(stats.runtime_stalled)
        if resume_ratio < thresholds.min_runtime_resume_ratio:
            failures.append(
                f"runtime_resume_ratio={resume_ratio:.2f} < {thresholds.min_runtime_resume_ratio:.2f}"
            )

    return failures


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate reconnect soak log against pass/fail thresholds."
    )
    parser.add_argument(
        "log_file",
        nargs="?",
        type=Path,
        default=Path("runtime/live_soak.log"),
        help="Path to soak log (default: runtime/live_soak.log)",
    )
    parser.add_argument("--min-app-auth-success", type=int, default=1)
    parser.add_argument("--min-account-auth-success", type=int, default=1)
    parser.add_argument("--max-attempt", type=int, default=20)
    parser.add_argument("--max-funds-timeout", type=int, default=30)
    parser.add_argument("--min-reconnect-success-ratio", type=float, default=0.5)
    parser.add_argument("--min-runtime-resume-ratio", type=float, default=0.5)
    parser.add_argument("--min-lines", type=int, default=20)
    parser.add_argument("--fail-on-insufficient-data", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    requested = Path(args.log_file)
    resolved, info = resolve_log_file(requested, cwd=Path.cwd())
    if resolved is None:
        print(f"log file not found: {requested} (cwd: {Path.cwd()})")
        return 2
    if info:
        print(info)

    lines = _read_lines(resolved)
    stats = analyze_reconnect_log(lines)
    thresholds = SoakThresholds(
        min_app_auth_success=max(0, int(args.min_app_auth_success)),
        min_account_auth_success=max(0, int(args.min_account_auth_success)),
        max_attempt=max(0, int(args.max_attempt)),
        max_funds_timeout=max(0, int(args.max_funds_timeout)),
        min_reconnect_success_ratio=max(0.0, float(args.min_reconnect_success_ratio)),
        min_runtime_resume_ratio=max(0.0, float(args.min_runtime_resume_ratio)),
    )
    failures = evaluate_soak(stats, thresholds)

    print(f"log_file: {resolved}")
    if is_insufficient_data(stats, min_lines=max(1, int(args.min_lines))):
        print("soak_assert: INSUFFICIENT_DATA")
        print(
            "summary:"
            f" lines={stats.lines}"
            f" reconnect_scheduled={stats.reconnect_scheduled}"
            f" app_auth_success={stats.app_auth_success}"
            f" account_auth_success={stats.account_auth_success}"
        )
        return 1 if bool(args.fail_on_insufficient_data) else 0

    print("soak_assert: PASS" if not failures else "soak_assert: FAIL")
    print(
        "summary:"
        f" reconnect_scheduled={stats.reconnect_scheduled}"
        f" max_attempt={stats.max_attempt}"
        f" app_auth_success={stats.app_auth_success}"
        f" account_auth_success={stats.account_auth_success}"
        f" funds_timeout={stats.funds_timeout}"
        f" reconnect_success_ratio={stats.reconnect_success_ratio:.2f}"
        f" runtime_stalled={stats.runtime_stalled}"
        f" runtime_resume={stats.runtime_resume}"
    )
    if failures:
        print("reasons:")
        for reason in failures:
            print(f"- {reason}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
