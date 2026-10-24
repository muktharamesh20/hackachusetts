"""Launch the Drake pantry sorting simulation and run the sort loop.

Usage:
    python scripts/run_sim.py

Reads configuration from the environment (see .env.example). If Drake is not
installed the loop still runs the perception -> routing -> inventory flow and
prints an inventory report.
"""

from __future__ import annotations

import logging

from pantrysort.config import CONFIG
from pantrysort.pipeline.sort_loop import SortLoop


def main() -> None:
    try:
        from rich.logging import RichHandler

        handlers = [RichHandler(rich_tracebacks=True, show_path=False)]
        fmt = "%(message)s"
    except Exception:
        handlers = [logging.StreamHandler()]
        fmt = "%(levelname)s %(name)s: %(message)s"

    logging.basicConfig(level=CONFIG.log_level, format=fmt, handlers=handlers)

    loop = SortLoop(use_sim=True)
    result = loop.run()

    print(f"\nSorted {result.num_sorted} item(s).")
    if result.unresolved:
        print(f"{len(result.unresolved)} item(s) had no storage route.")

    if loop._station is not None and getattr(loop._station, "meshcat", None):
        print("\nMeshcat is running. Open the printed URL to view the scene.")
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
