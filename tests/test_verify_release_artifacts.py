from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path("scripts/verify_release_artifacts.py")


def run_script(dist_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dist-dir", str(dist_dir)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_verify_release_artifacts_accepts_expected_inventory(tmp_path: Path) -> None:
    (tmp_path / "forex-0.1.0-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / "forex-0.1.0.tar.gz").write_bytes(b"sdist")
    (tmp_path / "SHA256SUMS.txt").write_text("deadbeef  forex-0.1.0.tar.gz\n", encoding="utf-8")

    result = run_script(tmp_path)

    assert result.returncode == 0
    assert "Verified release artifact inventory" in result.stdout


def test_verify_release_artifacts_rejects_unexpected_files(tmp_path: Path) -> None:
    (tmp_path / "forex-0.1.0-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / "forex-0.1.0.tar.gz").write_bytes(b"sdist")
    (tmp_path / "SHA256SUMS.txt").write_text("deadbeef  forex-0.1.0.tar.gz\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("unexpected", encoding="utf-8")

    result = run_script(tmp_path)

    assert result.returncode != 0
    assert "Unexpected files in dist" in result.stderr


def test_verify_release_artifacts_requires_single_wheel(tmp_path: Path) -> None:
    (tmp_path / "forex-0.1.0-a.whl").write_bytes(b"wheel-a")
    (tmp_path / "forex-0.1.0-b.whl").write_bytes(b"wheel-b")
    (tmp_path / "forex-0.1.0.tar.gz").write_bytes(b"sdist")
    (tmp_path / "SHA256SUMS.txt").write_text("deadbeef  forex-0.1.0.tar.gz\n", encoding="utf-8")

    result = run_script(tmp_path)

    assert result.returncode != 0
    assert "Expected exactly 1 wheel artifact" in result.stderr
