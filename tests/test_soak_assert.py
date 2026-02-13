from __future__ import annotations

from forex.tools.diagnostics.reconnect_log_analyzer import analyze_reconnect_log
from forex.tools.diagnostics.soak_assert import SoakThresholds, evaluate_soak


def test_evaluate_soak_passes_with_healthy_reconnect_profile() -> None:
    lines = [
        "[11:41:15] [INFO] 連線中斷，3.0s 後重連 (attempt 1)",
        "[11:41:18] [INFO] 正在連線到 cTrader...",
        "[11:41:30] [INFO] 應用程式認證成功！",
        "[11:41:33] [INFO] 帳戶認證成功！",
        "[11:41:55] [INFO] runtime_stalled | idle=20s | phase=READY",
        "[11:42:01] [INFO] runtime_resume | reason=oauth_authenticated",
    ]
    stats = analyze_reconnect_log(lines)
    failures = evaluate_soak(stats, SoakThresholds())
    assert failures == []


def test_evaluate_soak_fails_on_attempt_and_resume_ratio() -> None:
    lines = [
        "[11:41:15] [INFO] 連線中斷，3.0s 後重連 (attempt 99)",
        "[11:41:50] [INFO] runtime_stalled | idle=20s | phase=READY",
    ]
    stats = analyze_reconnect_log(lines)
    failures = evaluate_soak(
        stats,
        SoakThresholds(
            min_app_auth_success=0,
            min_account_auth_success=0,
            max_attempt=5,
            min_runtime_resume_ratio=1.0,
        ),
    )
    assert any("max_attempt" in message for message in failures)
    assert any("runtime_resume_ratio" in message for message in failures)
