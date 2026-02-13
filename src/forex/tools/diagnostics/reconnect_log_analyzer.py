from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path


_ATTEMPT_RE = re.compile(r"attempt\s+(\d+)", re.IGNORECASE)


@dataclass
class ReconnectLogStats:
    lines: int = 0
    disconnect_events: int = 0
    reconnect_scheduled: int = 0
    connect_started: int = 0
    connected: int = 0
    app_auth_sent: int = 0
    app_auth_success: int = 0
    account_auth_success: int = 0
    funds_timeout: int = 0
    request_deferred: int = 0
    dns_lookup_failed: int = 0
    app_auth_timeout: int = 0
    runtime_stalled: int = 0
    runtime_resume: int = 0
    lockout: int = 0
    max_attempt: int = 0

    @property
    def reconnect_success_ratio(self) -> float:
        if self.reconnect_scheduled <= 0:
            return 0.0
        return self.app_auth_success / float(self.reconnect_scheduled)


def analyze_reconnect_log(lines: list[str]) -> ReconnectLogStats:
    stats = ReconnectLogStats(lines=len(lines))
    for raw in lines:
        line = str(raw or "")
        if not line:
            continue
        lower = line.lower()

        if "偵測到斷線" in line or "[network] 已斷線" in lower:
            stats.disconnect_events += 1
        if "後重連" in line and "attempt" in lower:
            stats.reconnect_scheduled += 1
            m = _ATTEMPT_RE.search(line)
            if m:
                stats.max_attempt = max(stats.max_attempt, int(m.group(1)))
        if "正在連線到 ctrader" in lower:
            stats.connect_started += 1
        if "已連線！" in line:
            stats.connected += 1
        if "正在發送應用程式認證" in line:
            stats.app_auth_sent += 1
        if "應用程式認證成功" in line or "應用程式已授權" in line:
            stats.app_auth_success += 1
        if "帳戶認證成功" in line or "帳戶已授權" in line:
            stats.account_auth_success += 1
        if "[timeout] 取得帳戶資金逾時" in lower:
            stats.funds_timeout += 1
        if "請求逾時或失敗" in line and "deferred" in lower:
            stats.request_deferred += 1
        if "dns lookup failed" in lower:
            stats.dns_lookup_failed += 1
        if "app 認證逾時" in line:
            stats.app_auth_timeout += 1
        if "runtime_stalled" in lower:
            stats.runtime_stalled += 1
        if "runtime_resume" in lower:
            stats.runtime_resume += 1
        if "authorization lockout" in lower or "lockout" in lower:
            stats.lockout += 1
    return stats


def render_summary(stats: ReconnectLogStats) -> str:
    return "\n".join(
        [
            "Reconnect Log Summary",
            f"lines: {stats.lines}",
            f"disconnect_events: {stats.disconnect_events}",
            f"reconnect_scheduled: {stats.reconnect_scheduled}",
            f"max_attempt: {stats.max_attempt}",
            f"connect_started: {stats.connect_started}",
            f"connected: {stats.connected}",
            f"app_auth_sent: {stats.app_auth_sent}",
            f"app_auth_success: {stats.app_auth_success}",
            f"account_auth_success: {stats.account_auth_success}",
            f"funds_timeout: {stats.funds_timeout}",
            f"request_deferred: {stats.request_deferred}",
            f"dns_lookup_failed: {stats.dns_lookup_failed}",
            f"app_auth_timeout: {stats.app_auth_timeout}",
            f"runtime_stalled: {stats.runtime_stalled}",
            f"runtime_resume: {stats.runtime_resume}",
            f"lockout: {stats.lockout}",
            f"reconnect_success_ratio: {stats.reconnect_success_ratio:.2f}",
        ]
    )


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _find_matching_logs(base_dir: Path, basename: str) -> list[Path]:
    if not basename:
        return []
    ignore_dirs = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "node_modules",
    }
    matches: list[Path] = []
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        if basename in files:
            matches.append(Path(root) / basename)
    return matches


def _latest_by_mtime(paths: list[Path]) -> Path:
    return max(paths, key=lambda p: p.stat().st_mtime)


def resolve_log_file(log_file: Path, *, cwd: Path) -> tuple[Path | None, str | None]:
    candidate = log_file if log_file.is_absolute() else (cwd / log_file)
    if candidate.exists():
        return candidate, None
    # For explicit paths (absolute or nested relative), do not guess.
    if log_file.is_absolute() or str(log_file.parent) not in ("", "."):
        return None, None
    matches = _find_matching_logs(cwd, log_file.name)
    if not matches:
        return None, None
    if len(matches) == 1:
        found = matches[0]
        return found, f"info: log file not found at '{log_file}', using discovered file '{found}'."
    latest = _latest_by_mtime(matches)
    return (
        latest,
        f"info: found {len(matches)} files named '{log_file.name}', using latest '{latest}'.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze cTrader live reconnect logs.")
    parser.add_argument(
        "log_file",
        nargs="?",
        type=Path,
        default=Path("live_soak.log"),
        help="Path to exported log text file (default: live_soak.log)",
    )
    args = parser.parse_args()

    requested = Path(args.log_file)
    resolved, info = resolve_log_file(requested, cwd=Path.cwd())
    if resolved is None:
        print(f"log file not found: {requested} (cwd: {Path.cwd()})")
        print("tip: pass full path, run from project root, or set LOG_FILE when starting forex-live")
        return 2
    if info:
        print(info)
    lines = _read_lines(resolved)
    stats = analyze_reconnect_log(lines)
    print(f"log_file: {resolved}")
    print(render_summary(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
