from __future__ import annotations

import re
from pathlib import Path

import forex


def test_package_version_matches_pyproject() -> None:
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', pyproject_text, re.MULTILINE)
    assert match is not None
    assert forex.__version__ == match.group(1)
