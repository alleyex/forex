from __future__ import annotations

from pathlib import Path
from typing import Iterable


def latest_file_in_dir(
    directory: str | Path,
    suffixes: Iterable[str],
    fallback: str,
) -> str:
    path = Path(directory)
    if not path.exists():
        return fallback

    matches = [item for item in path.iterdir() if item.is_file() and item.suffix in suffixes]
    if not matches:
        return fallback

    latest = max(matches, key=lambda item: item.stat().st_mtime)
    return str(latest)
