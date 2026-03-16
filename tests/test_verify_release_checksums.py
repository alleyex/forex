from __future__ import annotations

import subprocess
import sys
from pathlib import Path

GENERATE_SCRIPT = Path("scripts/generate_release_checksums.py")
VERIFY_SCRIPT = Path("scripts/verify_release_checksums.py")


def create_artifacts(dist_dir: Path) -> tuple[Path, Path]:
    wheel_path = dist_dir / "forex-0.1.0-py3-none-any.whl"
    sdist_path = dist_dir / "forex-0.1.0.tar.gz"
    wheel_path.write_bytes(b"wheel-bytes")
    sdist_path.write_bytes(b"sdist-bytes")
    return wheel_path, sdist_path


def test_verify_release_checksums_accepts_matching_manifest(tmp_path: Path) -> None:
    create_artifacts(tmp_path)
    subprocess.run(
        [sys.executable, str(GENERATE_SCRIPT), "--dist-dir", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--dist-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Verified checksums for 2 artifacts" in result.stdout


def test_verify_release_checksums_rejects_modified_artifact(tmp_path: Path) -> None:
    wheel_path, _ = create_artifacts(tmp_path)
    subprocess.run(
        [sys.executable, str(GENERATE_SCRIPT), "--dist-dir", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel_path.write_bytes(b"tampered-wheel-bytes")

    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--dist-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Checksum mismatch" in result.stderr


def test_verify_release_checksums_rejects_manifest_drift(tmp_path: Path) -> None:
    create_artifacts(tmp_path)
    manifest_path = tmp_path / "SHA256SUMS.txt"
    manifest_path.write_text("deadbeef  only-one-file.whl\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--dist-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "do not match release artifacts" in result.stderr
