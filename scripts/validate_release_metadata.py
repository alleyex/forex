#!/usr/bin/env python3
"""Validate version and changelog metadata for releases."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
PYPROJECT_VERSION_PATTERN = re.compile(r'^version = "([^"]+)"$', re.MULTILINE)
PACKAGE_VERSION_PATTERN = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)
UNRELEASED_HEADING_PATTERN = re.compile(r"^## \[Unreleased\]$", re.MULTILINE)
RELEASE_HEADING_TEMPLATE = r"^## \[{version}\] - (\d{{4}}-\d{{2}}-\d{{2}})$"


@dataclass(frozen=True)
class ReleaseFiles:
    pyproject: Path
    package_init: Path
    changelog: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate synchronized version metadata and changelog release entries.",
    )
    parser.add_argument(
        "--tag",
        help="Optional git tag to validate, for example v0.1.1.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def release_files(repo_root: Path) -> ReleaseFiles:
    return ReleaseFiles(
        pyproject=repo_root / "pyproject.toml",
        package_init=repo_root / "src/forex/__init__.py",
        changelog=repo_root / "CHANGELOG.md",
    )


def extract_version(path: Path, pattern: re.Pattern[str], label: str) -> str:
    match = pattern.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"Could not find {label} version in {path}")
    return match.group(1)


def read_project_version(files: ReleaseFiles) -> str:
    pyproject_version = extract_version(files.pyproject, PYPROJECT_VERSION_PATTERN, "pyproject")
    package_version = extract_version(files.package_init, PACKAGE_VERSION_PATTERN, "package")
    if pyproject_version != package_version:
        raise SystemExit(
            "Version mismatch: "
            f"pyproject.toml={pyproject_version!r}, "
            f"src/forex/__init__.py={package_version!r}",
        )
    return pyproject_version


def validate_tag(tag: str, version: str) -> None:
    expected_tag = f"v{version}"
    if tag != expected_tag:
        raise SystemExit(f"Tag {tag!r} does not match project version {version!r}")


def validate_changelog(changelog_path: Path, version: str) -> None:
    changelog_text = changelog_path.read_text(encoding="utf-8")
    if UNRELEASED_HEADING_PATTERN.search(changelog_text) is None:
        raise SystemExit("CHANGELOG.md is missing the [Unreleased] heading")

    release_heading_pattern = re.compile(
        RELEASE_HEADING_TEMPLATE.format(version=re.escape(version)),
        re.MULTILINE,
    )
    if release_heading_pattern.search(changelog_text) is None:
        raise SystemExit(
            f"CHANGELOG.md is missing a release entry for version {version!r}",
        )


def main() -> None:
    args = parse_args()
    files = release_files(args.repo_root.resolve())
    version = read_project_version(files)
    if VERSION_PATTERN.fullmatch(version) is None:
        raise SystemExit(f"Project version {version!r} is not a semantic version")
    if args.tag is not None:
        validate_tag(args.tag, version)
    validate_changelog(files.changelog, version)
    print(f"Release metadata validated for version {version}")


if __name__ == "__main__":
    main()
