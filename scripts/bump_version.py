#!/usr/bin/env python3
"""Synchronize project version metadata."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
PYPROJECT_VERSION_PATTERN = re.compile(r'^(version = )"([^"]+)"$', re.MULTILINE)
PACKAGE_VERSION_PATTERN = re.compile(r'^(__version__ = )"([^"]+)"$', re.MULTILINE)


@dataclass(frozen=True)
class VersionFiles:
    """Repository files that must stay version-synchronized."""

    pyproject: Path
    package_init: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read or update the project version in all tracked metadata files.",
    )
    parser.add_argument(
        "new_version",
        nargs="?",
        help="Semantic version to write, for example 0.1.1",
    )
    parser.add_argument(
        "--current",
        action="store_true",
        help="Print the current synchronized version and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the version update plan without writing files.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def version_files(repo_root: Path) -> VersionFiles:
    return VersionFiles(
        pyproject=repo_root / "pyproject.toml",
        package_init=repo_root / "src/forex/__init__.py",
    )


def extract_version(path: Path, pattern: re.Pattern[str], label: str) -> str:
    match = pattern.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"Could not find {label} version in {path}")
    return match.group(2)


def read_current_version(files: VersionFiles) -> str:
    pyproject_version = extract_version(
        files.pyproject,
        PYPROJECT_VERSION_PATTERN,
        "pyproject",
    )
    package_version = extract_version(
        files.package_init,
        PACKAGE_VERSION_PATTERN,
        "package",
    )
    if pyproject_version != package_version:
        raise SystemExit(
            "Version metadata is out of sync between pyproject.toml and src/forex/__init__.py",
        )
    return pyproject_version


def validate_new_version(version: str) -> None:
    if not VERSION_PATTERN.fullmatch(version):
        raise SystemExit(
            f"Invalid version {version!r}. Expected semantic version format X.Y.Z.",
        )


def replace_version(
    path: Path,
    pattern: re.Pattern[str],
    new_version: str,
) -> bool:
    original_text = path.read_text(encoding="utf-8")
    updated_text, replacements = pattern.subn(rf'\1"{new_version}"', original_text, count=1)
    if replacements != 1:
        raise SystemExit(f"Failed to update version in {path}")
    if updated_text == original_text:
        return False
    path.write_text(updated_text, encoding="utf-8")
    return True


def update_versions(files: VersionFiles, new_version: str, dry_run: bool) -> list[Path]:
    changed_files: list[Path] = []
    for path, pattern in (
        (files.pyproject, PYPROJECT_VERSION_PATTERN),
        (files.package_init, PACKAGE_VERSION_PATTERN),
    ):
        original_text = path.read_text(encoding="utf-8")
        updated_text, replacements = pattern.subn(
            rf'\1"{new_version}"',
            original_text,
            count=1,
        )
        if replacements != 1:
            raise SystemExit(f"Failed to update version in {path}")
        if updated_text == original_text:
            continue
        changed_files.append(path)
        if not dry_run:
            path.write_text(updated_text, encoding="utf-8")
    return changed_files


def main() -> None:
    args = parse_args()
    files = version_files(args.repo_root.resolve())
    current_version = read_current_version(files)

    if args.current:
        print(current_version)
        return

    if args.new_version is None:
        raise SystemExit("Provide a new version or use --current.")

    validate_new_version(args.new_version)
    changed_files = update_versions(files, args.new_version, args.dry_run)

    if not changed_files:
        print(f"Version already set to {args.new_version}")
        return

    action = "Would update" if args.dry_run else "Updated"
    print(f"{action} version: {current_version} -> {args.new_version}")
    for path in changed_files:
        print(path.relative_to(args.repo_root.resolve()))


if __name__ == "__main__":
    main()
