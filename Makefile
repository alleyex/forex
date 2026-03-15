PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
RUFF ?= $(PYTHON) -m ruff
PYTEST ?= $(PYTHON) -m pytest

.PHONY: help install-dev lint test check check-core check-hygiene check-architecture check-deadcode check-unused check-release-metadata release-check bump-version release-checksums

help:
	@echo "Targets:"
	@echo "  make install-dev         # install editable package with dev dependencies"
	@echo "  make lint                # run Ruff"
	@echo "  make test                # run pytest"
	@echo "  make check-core          # blocking CI-quality checks"
	@echo "  make check-hygiene       # non-blocking hygiene checks for gradual cleanup"
	@echo "  make check-architecture  # import-linter contracts"
	@echo "  make check-unused        # unused imports and variables"
	@echo "  make check-deadcode      # vulture dead code scan"
	@echo "  make check-release-metadata # validate version and changelog release metadata"
	@echo "  make release-checksums   # generate SHA256SUMS.txt for dist artifacts"
	@echo "  make release-check       # release preflight validation and package build"
	@echo "  make bump-version        # synchronize package version metadata (VERSION=x.y.z)"
	@echo "  make check               # run all quality gates"

install-dev:
	$(PIP) install -U pip
	$(PIP) install -e '.[dev,ui,ml,ctrader]'

lint:
	$(RUFF) check src tests

test:
	$(PYTEST)

check-architecture:
	PYTHONPATH=src lint-imports --config pyproject.toml

check-unused:
	$(RUFF) check src tests --select F401,F841

check-deadcode:
	$(PYTHON) -m vulture src tests vulture_whitelist.py --min-confidence 60

check-release-metadata:
	$(PYTHON) ./scripts/validate_release_metadata.py

release-checksums:
	$(PYTHON) ./scripts/generate_release_checksums.py --dist-dir dist

check-core: test check-architecture

check-hygiene: lint check-unused check-deadcode

release-check:
	./scripts/release_check.sh

bump-version:
	@test -n "$(VERSION)" || (echo "VERSION is required, e.g. make bump-version VERSION=0.1.1" && exit 1)
	$(PYTHON) ./scripts/bump_version.py "$(VERSION)"

check: check-core check-hygiene
