from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path("scripts/generate_release_checksums.py")


def test_generate_release_checksums_writes_expected_manifest(tmp_path: Path) -> None:
    wheel_path = tmp_path / "forex-0.1.0-py3-none-any.whl"
    sdist_path = tmp_path / "forex-0.1.0.tar.gz"
    wheel_path.write_bytes(b"wheel-bytes")
    sdist_path.write_bytes(b"sdist-bytes")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dist-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    manifest_path = tmp_path / "SHA256SUMS.txt"
    assert manifest_path.is_file()

    expected_lines = [
        f"{hashlib.sha256(wheel_path.read_bytes()).hexdigest()}  {wheel_path.name}",
        f"{hashlib.sha256(sdist_path.read_bytes()).hexdigest()}  {sdist_path.name}",
    ]
    assert manifest_path.read_text(encoding="utf-8").splitlines() == expected_lines


def test_generate_release_checksums_requires_artifacts(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dist-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "No release artifacts found" in result.stderr
