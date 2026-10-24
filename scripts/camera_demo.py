"""Render the overhead camera and save raw (pinhole) and fisheye frames.

Run from an environment with Drake installed (Linux/macOS or Windows via WSL):

    python scripts/camera_demo.py [--out DIR]

Writes ``camera_raw.png`` and ``camera_fisheye.png`` plus prints the
vision-estimated world position of each item next to its ground truth, so you
can see the fisheye distortion and sanity-check localization.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from pantrysort.config import SimConfig
from pantrysort.sim.station import build_station


def main() -> None:
    ap = argparse.ArgumentParser(description="Overhead fisheye camera demo.")
    ap.add_argument("--out", default=".", help="Output directory for PNGs.")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    station = build_station(
        config=SimConfig(meshcat=False, qr_scanner=False, overhead_camera=True)
    )
    if station.camera is None:
        print("No VTK renderer available; cannot render the camera.")
        return

    import cv2

    raw = station.camera_rgb()
    fe = station.camera_fisheye()
    cv2.imwrite(str(out / "camera_raw.png"), cv2.cvtColor(raw, cv2.COLOR_RGBA2BGRA))
    cv2.imwrite(str(out / "camera_fisheye.png"), cv2.cvtColor(fe, cv2.COLOR_RGBA2BGRA))
    print(f"Wrote {out/'camera_raw.png'} and {out/'camera_fisheye.png'}")

    cm = station.camera_model()
    print("\nitem                     true (x,y,z)            vision (x,y,z)        err(cm)")
    for item in station.scene.items:
        p_true = np.array(item.position, dtype=float)
        u, v, _ = cm.world_to_pixel(p_true)
        if not (0 <= u < cm.width and 0 <= v < cm.height):
            print(f"{item.label:24s} (out of frame)")
            continue
        p_est = station.locate_pixel(u, v)
        if p_est is None:
            print(f"{item.label:24s} (no depth)")
            continue
        err = float(np.linalg.norm(p_est - p_true)) * 100
        print(f"{item.label:24s} {np.round(p_true,3)}   {np.round(p_est,3)}   {err:5.1f}")


if __name__ == "__main__":
    main()
