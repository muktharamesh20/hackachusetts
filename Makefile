.PHONY: help install install-dev test lint format verify sim clean arm-check arm-watch arm-calibrate arm-cal-home arm-cal-ranges

# Real SO-101 follower arm. Override on the command line, e.g. `make arm-check ARM_PORT=/dev/tty.usbmodemXXXX`.
ARM_PORT ?= $(firstword $(wildcard /dev/tty.usbmodem*))
ARM_ID ?= pantry_arm

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
	@echo "  make arm-check    Read-only health check of the real SO-101 (no motion)"
	@echo "  make arm-watch    Stream raw joint positions while you move the arm by hand"
	@echo "  make arm-calibrate  Interactive LeRobot calibration of the SO-101 follower"

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

arm-check:
	python scripts/check_arm.py --port $(ARM_PORT) --id $(ARM_ID)

arm-watch:
	python scripts/check_arm.py --port $(ARM_PORT) --id $(ARM_ID) --watch

arm-calibrate:
	lerobot-calibrate --robot.type=so101_follower --robot.port=$(ARM_PORT) --robot.id=$(ARM_ID)

# Keyboard-free calibration in two steps (same result as arm-calibrate).
arm-cal-home:
	cd scripts && python calibrate_arm.py home --port $(ARM_PORT) --id $(ARM_ID)

arm-cal-ranges:
	cd scripts && python calibrate_arm.py ranges --port $(ARM_PORT) --id $(ARM_ID)
