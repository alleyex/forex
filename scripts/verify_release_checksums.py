#!/usr/bin/env python3
"""Verify SHA256 checksums for release artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from generate_release_checksums import iter_release_artifacts, sha256_digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify SHA256SUMS.txt for distribution artifacts.",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist"),
        help="Distribution directory containing built release artifacts.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Optional checksum manifest path. Defaults to <dist-dir>/SHA256SUMS.txt.",
    )
    return parser.parse_args()


def parse_manifest(manifest_path: Path) -> dict[str, str]:
    if not manifest_path.is_file():
        raise SystemExit(f"Checksum manifest not found: {manifest_path}")

    entries: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        digest, separator, filename = line.partition("  ")
        if not separator or not filename:
            raise SystemExit(f"Invalid checksum entry in {manifest_path}: {line!r}")
        entries[filename] = digest
    if not entries:
        raise SystemExit(f"Checksum manifest is empty: {manifest_path}")
    return entries


def main() -> None:
    args = parse_args()
    dist_dir = args.dist_dir.resolve()
    manifest_path = (args.manifest or dist_dir / "SHA256SUMS.txt").resolve()
    manifest_entries = parse_manifest(manifest_path)
    artifacts = iter_release_artifacts(dist_dir)

    artifact_names = {path.name for path in artifacts}
    if set(manifest_entries) != artifact_names:
        raise SystemExit(
            "Checksum manifest entries do not match release artifacts: "
            f"manifest={sorted(manifest_entries)}, artifacts={sorted(artifact_names)}",
        )

    for artifact in artifacts:
        expected_digest = manifest_entries[artifact.name]
        actual_digest = sha256_digest(artifact)
        if actual_digest != expected_digest:
            raise SystemExit(
                f"Checksum mismatch for {artifact.name}: "
                f"expected {expected_digest}, got {actual_digest}",
            )

    print(f"Verified checksums for {len(artifacts)} artifacts in {manifest_path}")


if __name__ == "__main__":
    main()
