"""Run the sort loop live in Meshcat and record two camera videos.

Records one MP4 from the arm's own BASE camera and one from an EXTERNAL camera,
written under ``outputs/sim_recordings/<timestamp>/`` (gitignored). Meshcat stays
up afterwards so you can watch/replay the 3D scene too.

Usage (from WSL):
    PANTRYSORT_MESHCAT=true ~/.venvs/pantrysort/bin/python scripts/run_sim_record.py
    # options:
    #   --external NAME   which external camera to record (default: iphone_left)
    #   --fps N           playback fps of the saved videos (default: 20)
    #   --distort-base    record the base camera's fisheye-distorted frames
    #   --no-meshcat      run headless (still records the videos)
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

from pantrysort.config import CONFIG, Config, SimConfig
from pantrysort.pipeline.sort_loop import SortLoop
from pantrysort.sim.recording import CameraVideoRecorder

OUT_ROOT = Path("outputs/sim_recordings")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the sim with Meshcat + record camera videos.")
    ap.add_argument("--external", default="iphone_left", help="External camera to record.")
    ap.add_argument("--fps", type=float, default=20.0)
    ap.add_argument("--distort-base", action="store_true",
                    help="Record the base camera's fisheye-distorted view.")
    ap.add_argument("--no-meshcat", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    drake_log = logging.getLogger("drake")
    drake_log.propagate = False
    drake_log.addHandler(logging.StreamHandler())

    sim_cfg = SimConfig(
        time_step=CONFIG.sim.time_step,
        realtime_rate=CONFIG.sim.realtime_rate,
        meshcat=not args.no_meshcat,
        qr_scanner=False,
        overhead_camera=True,
    )
    config = Config(sim=sim_cfg, policy=CONFIG.policy, inventory=CONFIG.inventory)

    loop = SortLoop(use_sim=True, config=config)
    station = loop._maybe_build_station()
    if station is None or not station.cameras:
        print("No Drake station/cameras available; cannot record camera videos.")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT_ROOT / stamp
    base = "robot_cam" if "robot_cam" in station.camera_names() else None
    external = args.external if args.external in station.camera_names() else None

    cameras: dict[str, str] = {}
    if base:
        cameras[base] = "arm_base_view.mp4"
    if external:
        cameras[external] = "external_view.mp4"

    recorder = CameraVideoRecorder(
        station, cameras, out_dir=out_dir, fps=args.fps,
        distorted={base: args.distort_base} if base else {},
    )
    recorder.start()
    print(f"Recording camera videos to {out_dir.resolve()}")

    result = loop.run()
    written = recorder.stop()

    print(f"\nSorted {result.num_sorted} item(s).")
    for name, path in written.items():
        print(f"  {name:12s} -> {path}")

    if station.meshcat is not None:
        print(f"\nMeshcat: {station.meshcat.web_url()}")
        print("Replay from Meshcat's Animation controls. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
