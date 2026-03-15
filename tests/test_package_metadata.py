from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


def test_project_metadata_has_release_fields() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["description"]
    assert project["readme"] == "README.md"
    assert project["requires-python"] == ">=3.10"
    assert project["license"]["text"] == "Proprietary"
    assert sorted(project["keywords"]) == [
        "ctrader",
        "desktop-ui",
        "forex",
        "reinforcement-learning",
        "trading",
    ]

    classifiers = set(project["classifiers"])
    assert "Development Status :: 3 - Alpha" in classifiers
    assert "Programming Language :: Python :: 3.10" in classifiers
    assert "Programming Language :: Python :: 3.11" in classifiers
    assert "Typing :: Typed" in classifiers


def test_project_urls_cover_repository_governance() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project_urls = pyproject["project"]["urls"]

    assert project_urls == {
        "Homepage": "https://github.com/alleyex/forex",
        "Repository": "https://github.com/alleyex/forex",
        "Issues": "https://github.com/alleyex/forex/issues",
        "Changelog": "https://github.com/alleyex/forex/blob/main/CHANGELOG.md",
    }
