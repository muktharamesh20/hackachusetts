"""Launch the Drake pantry sorting simulation and run the sort loop.

Usage:
    python scripts/run_sim.py

Reads configuration from the environment (see .env.example). If Drake is not
installed the loop still runs the perception -> routing -> inventory flow and
prints an inventory report.
"""

from __future__ import annotations

import logging
import time

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
    # Drake's forwarded log records have no source path, which RichHandler can't render.
    drake_log = logging.getLogger("drake")
    drake_log.propagate = False
    drake_log.addHandler(logging.StreamHandler())

    loop = SortLoop(use_sim=True)
    result = loop.run()

    scanned = sum(1 for s in result.scans if s.source == "camera" and s.payload is not None)
    print(f"\nSorted {result.num_sorted} item(s); {scanned} identified by QR camera scan.")
    for label, counts in result.boxes:
        print(f"  {label}: " + ", ".join(f"{n} -> {loc}" for loc, n in counts.items()))
    if result.discarded:
        print(f"{len(result.discarded)} expired item(s) sent to the discard bin: "
              + ", ".join(i.name for i in result.discarded))
    if result.unresolved:
        print(f"{len(result.unresolved)} item(s) had no storage route.")

    meshcat = getattr(loop._station, "meshcat", None)
    if meshcat is not None:
        print(f"\nMeshcat: {meshcat.web_url()}")
        print("Replay the run from Meshcat's Animation controls (top right, 'play').")
        print("Press Ctrl+C to exit.")
        try:
            while True:  # keep the Meshcat server alive (works with or without a TTY)
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
