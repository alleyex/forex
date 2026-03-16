from __future__ import annotations

import os
from pathlib import Path

from forex.tools.diagnostics.reconnect_log_analyzer import (
    analyze_reconnect_log,
    render_summary,
    resolve_log_file,
)


def test_analyze_reconnect_log_counts_key_events() -> None:
    lines = [
        "[11:41:15] [ERROR] [NETWORK] Disconnected (...)",
        "[11:41:15] [INFO] Detected disconnect; automatic reconnect will be attempted",
        "[11:41:15] [INFO] Connection interrupted, reconnecting in 3.0s (attempt 1)",
        "[11:41:18] [INFO] Connecting to cTrader...",
        "[11:41:30] [INFO] Connected!",
        "[11:41:30] [INFO] Sending application authentication...",
        "[11:41:31] [INFO] Application authorized!",
        "[11:41:33] [INFO] Account authorized!",
        "[11:41:43] [INFO] Request timed out or failed: (5, 'Deferred')",
        "[11:41:45] [INFO] [TIMEOUT] Account funds request timed out",
        "[11:41:50] [INFO] runtime_stalled | idle=20s | phase=READY",
        "[11:41:55] [INFO] runtime_resume | reason=oauth_authenticated",
    ]

    stats = analyze_reconnect_log(lines)

    assert stats.lines == len(lines)
    assert stats.disconnect_events >= 1
    assert stats.reconnect_scheduled == 1
    assert stats.max_attempt == 1
    assert stats.connect_started == 1
    assert stats.connected == 1
    assert stats.app_auth_sent == 1
    assert stats.app_auth_success == 1
    assert stats.account_auth_success == 1
    assert stats.request_deferred == 1
    assert stats.funds_timeout == 1
    assert stats.runtime_stalled == 1
    assert stats.runtime_resume == 1


def test_render_summary_contains_metrics() -> None:
    stats = analyze_reconnect_log(
        ["[11:00:00] [INFO] Connection interrupted, reconnecting in 3s (attempt 2)"]
    )
    summary = render_summary(stats)

    assert "Reconnect Log Summary" in summary
    assert "reconnect_scheduled: 1" in summary
    assert "max_attempt: 2" in summary


def test_resolve_log_file_keeps_existing_path(tmp_path: Path) -> None:
    target = tmp_path / "live_soak.log"
    target.write_text("x\n", encoding="utf-8")

    resolved, info = resolve_log_file(target, cwd=tmp_path)

    assert resolved == target
    assert info is None


def test_resolve_log_file_finds_single_match_in_tree(tmp_path: Path) -> None:
    nested = tmp_path / "logs"
    nested.mkdir(parents=True)
    target = nested / "live_soak.log"
    target.write_text("x\n", encoding="utf-8")

    resolved, info = resolve_log_file(Path("live_soak.log"), cwd=tmp_path)

    assert resolved == target
    assert info is not None
    assert "using discovered file" in info


def test_resolve_log_file_uses_latest_when_multiple_matches(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    older = a / "live_soak.log"
    newer = b / "live_soak.log"
    older.write_text("old\n", encoding="utf-8")
    newer.write_text("new\n", encoding="utf-8")

    # ensure deterministic mtime order
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_700_000_100, 1_700_000_100))

    resolved, info = resolve_log_file(Path("live_soak.log"), cwd=tmp_path)

    assert resolved == newer
    assert info is not None
    assert "using latest" in info
