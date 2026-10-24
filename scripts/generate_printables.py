"""Generate printable 3MF models of pantry objects and add them to the sim.

Writes ``assets/printables/<name>.3mf`` for every object in
``pantrysort.sim.printables.PRINTABLES`` (cans, boxes, bottles, bags, toothpaste,
soap, toilet paper, ...). Each mesh is checked to be watertight, outward-facing,
and grippable by the SO-101 before it is written. The 3MFs are then converted
for the sim (same path as the apples), updating ``assets/items/shapes.yaml``.

Usage:
    PYTHONPATH=src python scripts/generate_printables.py            # all objects
    PYTHONPATH=src python scripts/generate_printables.py soup_can toothpaste
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pantrysort.sim.mesh_io import write_3mf
from pantrysort.sim.printables import PRINTABLES, validate

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "assets" / "printables"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_items  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help=f"subset of: {', '.join(PRINTABLES)}")
    parser.add_argument("--no-sim", action="store_true", help="only write the 3MF files")
    args = parser.parse_args(argv)

    unknown = [n for n in args.names if n not in PRINTABLES]
    if unknown:
        parser.error(f"unknown object(s): {', '.join(unknown)}")

    written = []
    for name in args.names or list(PRINTABLES):
        printable = PRINTABLES[name]
        mesh = printable.mesh()
        problems = validate(mesh)
        if problems:
            print(f"error: {name}: {'; '.join(problems)}", file=sys.stderr)
            return 1
        path = OUT_DIR / f"{name}.3mf"
        write_3mf(path, mesh, title=printable.title)
        written.append(path)
    print(f"Wrote {len(written)} printable(s) to {OUT_DIR.relative_to(REPO_ROOT)}/")

    if not args.no_sim:
        return prepare_items.main([str(p) for p in written])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
