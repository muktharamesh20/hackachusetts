# PantrySort 🥫🤖

A robotics system for **autonomous food pantry sorting** that combines:

- **[Drake](https://drake.mit.edu/)** — physics-based simulation, manipulation planning, and grasp/motion generation.
- **[LeRobot](https://github.com/huggingface/lerobot)** (🤗) — learned visuomotor policies for perception-driven pick-and-place.
- **Pantry inventory domain logic** — tracking every item in and out with expiration dates, quantities, calories, and allergens.

The goal: help food pantries receive, identify, store, and distribute donated food efficiently and safely, reducing waste from expired goods and improving the nutritional quality of what gets distributed.

---

## Why this exists

Food pantries are overwhelmingly volunteer-run and process huge, unpredictable streams of donated food. The two hardest operational problems are:

1. **Physical sorting** — a mixed bin of cans, boxes, jars, and bags must be identified and placed into the correct storage location (by category, by expiration, by allergen).
2. **Inventory accounting** — knowing what you have, when it expires, how many calories/servings it represents, and what to distribute first (FEFO — First Expired, First Out).

PantrySort tackles both: a robot arm (simulated in Drake, driven by a LeRobot policy) does the physical sorting, while an inventory service records every item's lifecycle.

See [`docs/PROBLEM_AND_SOLUTION.md`](docs/PROBLEM_AND_SOLUTION.md) for the full problem statement and solution design.

---

## Project layout

```
hackachusetts/
├── README.md
├── docs/
│   └── PROBLEM_AND_SOLUTION.md      # Full problem/solution writeup
├── pyproject.toml                   # Package + dependency definitions
├── requirements.txt                 # Pinned runtime deps (pip fallback)
├── requirements-dev.txt             # Dev/test/lint deps
├── environment.yml                  # Conda environment (recommended)
├── Makefile                         # Common dev commands
├── .env.example                     # Example configuration
├── .gitignore
├── src/
│   └── pantrysort/
│       ├── __init__.py
│       ├── config.py                # Central configuration
│       ├── inventory/               # Inventory domain (expiry, calories, FEFO)
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── store.py
│       │   └── nutrition.py
│       ├── perception/              # Item identification
│       │   ├── __init__.py
│       │   └── classifier.py
│       ├── sim/                     # Drake simulation + manipulation
│       │   ├── __init__.py
│       │   ├── station.py
│       │   ├── pantry_scene.py
│       │   └── pick_and_place.py
│       ├── policy/                  # LeRobot policy integration
│       │   ├── __init__.py
│       │   ├── lerobot_policy.py
│       │   └── dataset.py
│       └── pipeline/                # Orchestration (sort loop)
│           ├── __init__.py
│           └── sort_loop.py
├── scripts/
│   ├── run_sim.py                   # Launch the Drake sorting simulation
│   ├── record_dataset.py            # Record a LeRobot dataset from the sim
│   └── train_policy.py              # Train a LeRobot policy
├── tests/
│   ├── test_inventory.py
│   └── test_nutrition.py
├── assets/
│   └── models/                      # SDF/URDF scene + item assets (placeholder)
└── .kiro/
    ├── steering/                    # Project-wide guidance for Kiro
    └── specs/
        └── pantry-sorting/          # Requirements → Design → Tasks
```

---

## Quick start

> **On Windows?** Drake has no Windows wheels - run the simulation under WSL.
> See [`DEV_NOTES.md`](DEV_NOTES.md) for a known-good WSL + Python 3.12 setup.
> Use Python 3.10-3.12 everywhere (3.13/3.14 are too new for Drake).

### 1. Create the environment

**Option A — Conda (recommended, handles ffmpeg + Python version cleanly):**

```bash
conda env create -f environment.yml
conda activate pantrysort
pip install -e .
```

**Option B — venv + pip:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
# ffmpeg with libsvtav1 is required by LeRobot for video encoding:
#   macOS:  brew install ffmpeg
#   Ubuntu: sudo apt install ffmpeg
pip install --upgrade pip
pip install -e ".[dev]"
```

> **Python version:** use 3.10–3.12. LeRobot requires >=3.10; `pydrake` wheels are published for 3.10–3.12.

### 2. Verify the install

```bash
make verify        # checks pydrake + lerobot import and prints versions
```

### 3. Run the simulation

```bash
python scripts/run_sim.py
```

This spins up a Drake `MultibodyPlant` pantry scene with an arm and a bin of items, and runs the sort loop. With no trained policy present it falls back to a scripted Drake pick-and-place planner.

---

## Development

```bash
make install       # editable install with dev extras
make test          # run pytest
make lint          # ruff + format check
make verify        # import-check the heavy robotics deps
```

## Specs

This project is built spec-first. See [`.kiro/specs/pantry-sorting/`](.kiro/specs/pantry-sorting/):

- `requirements.md` — what the system must do (EARS-style acceptance criteria)
- `design.md` — architecture, components, data flow
- `tasks.md` — incremental implementation plan

## License

MIT (see `LICENSE`).
