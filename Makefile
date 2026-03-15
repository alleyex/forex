PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
RUFF ?= $(PYTHON) -m ruff
PYTEST ?= $(PYTHON) -m pytest

.PHONY: help install-dev lint test check check-core check-hygiene check-architecture check-deadcode check-unused release-check

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
	@echo "  make release-check       # release preflight validation and package build"
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

check-core: test check-architecture

check-hygiene: lint check-unused check-deadcode

release-check:
	./scripts/release_check.sh

check: check-core check-hygiene
