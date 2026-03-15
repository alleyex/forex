#!/usr/bin/env python3
"""Generate SHA256 checksums for release artifacts."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate SHA256SUMS.txt for distribution artifacts.",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist"),
        help="Distribution directory containing built release artifacts.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. Defaults to <dist-dir>/SHA256SUMS.txt.",
    )
    return parser.parse_args()


def sha256_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def iter_release_artifacts(dist_dir: Path) -> list[Path]:
    artifacts = sorted(
        path
        for path in dist_dir.iterdir()
        if path.is_file() and path.name != "SHA256SUMS.txt"
    )
    if not artifacts:
        raise SystemExit(f"No release artifacts found in {dist_dir}")
    return artifacts


def main() -> None:
    args = parse_args()
    dist_dir = args.dist_dir.resolve()
    output_path = (args.output or dist_dir / "SHA256SUMS.txt").resolve()
    artifacts = iter_release_artifacts(dist_dir)

    lines = [f"{sha256_digest(path)}  {path.name}" for path in artifacts]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote checksums for {len(artifacts)} artifacts to {output_path}")


if __name__ == "__main__":
    main()
