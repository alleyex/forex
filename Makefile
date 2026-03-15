PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
BLACK ?= $(PYTHON) -m black
RUFF ?= $(PYTHON) -m ruff
PYTEST ?= $(PYTHON) -m pytest

.PHONY: help install-dev format format-check lint test check check-architecture check-deadcode check-unused

help:
	@echo "Targets:"
	@echo "  make install-dev         # install editable package with dev dependencies"
	@echo "  make format              # run code formatter"
	@echo "  make format-check        # verify formatting"
	@echo "  make lint                # run Ruff"
	@echo "  make test                # run pytest"
	@echo "  make check-architecture  # import-linter contracts"
	@echo "  make check-unused        # unused imports and variables"
	@echo "  make check-deadcode      # vulture dead code scan"
	@echo "  make check               # run all quality gates"

install-dev:
	$(PIP) install -U pip
	$(PIP) install -e '.[dev,ui,ml,ctrader]'

format:
	$(BLACK) src tests
	$(RUFF) check src tests --fix

format-check:
	$(BLACK) --check src tests

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

check: format-check lint test check-architecture check-unused check-deadcode
