CONDA_ENV ?= pyside6-env-310
CONDA_RUN = conda run -n $(CONDA_ENV)

.PHONY: help check-all check-architecture check-unused check-deadcode

help:
	@echo "Targets:"
	@echo "  make check-all           # run all static architecture/dead-code checks"
	@echo "  make check-architecture  # import-linter contracts"
	@echo "  make check-unused        # ruff unused imports/variables"
	@echo "  make check-deadcode      # vulture with whitelist"
	@echo ""
	@echo "Optional:"
	@echo "  make check-all CONDA_ENV=pyside6-env-310"

check-architecture:
	$(CONDA_RUN) bash -lc 'PYTHONPATH=src lint-imports --config pyproject.toml'

check-unused:
	$(CONDA_RUN) python -m ruff check src tests --select F401,F841 --output-format concise

check-deadcode:
	$(CONDA_RUN) python -m vulture src tests vulture_whitelist.py --min-confidence 60

check-all: check-architecture check-unused check-deadcode
