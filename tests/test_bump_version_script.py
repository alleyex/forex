from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path("scripts/bump_version.py")


def load_script_module():
    spec = importlib.util.spec_from_file_location("bump_version_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_version_files(repo_root: Path, pyproject_version: str, package_version: str) -> None:
    (repo_root / "src/forex").mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text(
        f'[project]\nname = "forex"\nversion = "{pyproject_version}"\n',
        encoding="utf-8",
    )
    (repo_root / "src/forex/__init__.py").write_text(
        f'__version__ = "{package_version}"\n',
        encoding="utf-8",
    )


def run_script(*args: str, repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args, "--repo-root", str(repo_root)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_current_version_reads_synchronized_metadata(tmp_path: Path) -> None:
    write_version_files(tmp_path, "0.1.0", "0.1.0")

    result = run_script("--current", repo_root=tmp_path)

    assert result.returncode == 0
    assert result.stdout.strip() == "0.1.0"


def test_dry_run_reports_files_without_writing(tmp_path: Path) -> None:
    write_version_files(tmp_path, "0.1.0", "0.1.0")

    result = run_script("0.1.1", "--dry-run", repo_root=tmp_path)

    assert result.returncode == 0
    assert "Would update version: 0.1.0 -> 0.1.1" in result.stdout
    assert 'version = "0.1.0"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '__version__ = "0.1.0"' in (
        tmp_path / "src/forex/__init__.py"
    ).read_text(encoding="utf-8")


def test_script_updates_both_version_files(tmp_path: Path) -> None:
    write_version_files(tmp_path, "0.1.0", "0.1.0")

    result = run_script("0.1.1", repo_root=tmp_path)

    assert result.returncode == 0
    assert 'version = "0.1.1"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '__version__ = "0.1.1"' in (
        tmp_path / "src/forex/__init__.py"
    ).read_text(encoding="utf-8")


def test_script_rejects_invalid_versions(tmp_path: Path) -> None:
    write_version_files(tmp_path, "0.1.0", "0.1.0")

    result = run_script("1.2", repo_root=tmp_path)

    assert result.returncode != 0
    assert "Invalid version" in result.stderr


def test_module_reports_out_of_sync_versions(tmp_path: Path) -> None:
    module = load_script_module()
    write_version_files(tmp_path, "0.1.0", "0.1.1")

    files = module.version_files(tmp_path)

    with pytest.raises(SystemExit, match="out of sync"):
        module.read_current_version(files)
