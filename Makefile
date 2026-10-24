.PHONY: help install install-dev test lint format verify sim clean

help:
	@echo "PantrySort dev commands:"
	@echo "  make install      Editable install (runtime deps)"
	@echo "  make install-dev  Editable install with dev extras"
	@echo "  make test         Run pytest"
	@echo "  make lint         Ruff lint + format check"
	@echo "  make format       Auto-format with ruff"
	@echo "  make verify       Import-check pydrake + lerobot and print versions"
	@echo "  make sim          Run the Drake sorting simulation"
	@echo "  make clean        Remove caches and build artifacts"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check src tests scripts
	ruff format --check src tests scripts

format:
	ruff format src tests scripts
	ruff check --fix src tests scripts

verify:
	python scripts/verify_env.py

sim:
	python scripts/run_sim.py

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
