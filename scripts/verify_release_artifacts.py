#!/usr/bin/env python3
"""Verify the expected release artifact inventory."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that dist/ contains only the expected release artifacts.",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist"),
        help="Distribution directory containing built release artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dist_dir = args.dist_dir.resolve()
    if not dist_dir.is_dir():
        raise SystemExit(f"Distribution directory not found: {dist_dir}")

    files = sorted(path.name for path in dist_dir.iterdir() if path.is_file())
    wheel_files = [name for name in files if name.endswith(".whl")]
    sdist_files = [name for name in files if name.endswith(".tar.gz")]
    checksum_files = [name for name in files if name == "SHA256SUMS.txt"]

    expected_files = set(wheel_files + sdist_files + checksum_files)
    unexpected_files = [name for name in files if name not in expected_files]

    if len(wheel_files) != 1:
        raise SystemExit(f"Expected exactly 1 wheel artifact, found {wheel_files!r}")
    if len(sdist_files) != 1:
        raise SystemExit(f"Expected exactly 1 source distribution, found {sdist_files!r}")
    if len(checksum_files) != 1:
        raise SystemExit(f"Expected SHA256SUMS.txt in dist, found {checksum_files!r}")
    if unexpected_files:
        raise SystemExit(f"Unexpected files in dist: {unexpected_files!r}")

    print(
        "Verified release artifact inventory: "
        f"{wheel_files[0]}, {sdist_files[0]}, {checksum_files[0]}",
    )


if __name__ == "__main__":
    main()
