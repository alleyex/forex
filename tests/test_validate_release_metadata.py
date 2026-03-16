from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path("scripts/validate_release_metadata.py")


def write_release_files(
    repo_root: Path,
    *,
    version: str = "0.1.0",
    package_version: str | None = None,
    changelog: str | None = None,
) -> None:
    (repo_root / "src/forex").mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text(
        f'[project]\nname = "forex"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (repo_root / "src/forex/__init__.py").write_text(
        f'__version__ = "{package_version or version}"\n',
        encoding="utf-8",
    )
    changelog_text = changelog or (
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        f"## [{version}] - 2026-03-15\n\n"
        "### Added\n\n"
        "- Initial release metadata.\n"
    )
    (repo_root / "CHANGELOG.md").write_text(changelog_text, encoding="utf-8")


def run_script(*args: str, repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args, "--repo-root", str(repo_root)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_validator_accepts_synchronized_release_metadata(tmp_path: Path) -> None:
    write_release_files(tmp_path)

    result = run_script(repo_root=tmp_path)

    assert result.returncode == 0
    assert "Release metadata validated for version 0.1.0" in result.stdout


def test_validator_rejects_tag_version_mismatch(tmp_path: Path) -> None:
    write_release_files(tmp_path)

    result = run_script("--tag", "v0.1.1", repo_root=tmp_path)

    assert result.returncode != 0
    assert "does not match project version" in result.stderr


def test_validator_rejects_missing_unreleased_heading(tmp_path: Path) -> None:
    write_release_files(
        tmp_path,
        changelog="# Changelog\n\n## [0.1.0] - 2026-03-15\n",
    )

    result = run_script(repo_root=tmp_path)

    assert result.returncode != 0
    assert "missing the [Unreleased] heading" in result.stderr


def test_validator_rejects_missing_version_entry(tmp_path: Path) -> None:
    write_release_files(
        tmp_path,
        changelog="# Changelog\n\n## [Unreleased]\n\n## [0.0.9] - 2026-03-14\n",
    )

    result = run_script(repo_root=tmp_path)

    assert result.returncode != 0
    assert "missing a release entry" in result.stderr


def test_validator_rejects_version_mismatch(tmp_path: Path) -> None:
    write_release_files(tmp_path, package_version="0.1.1")

    result = run_script(repo_root=tmp_path)

    assert result.returncode != 0
    assert "Version mismatch" in result.stderr
