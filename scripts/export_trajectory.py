"""Run the sort loop in the Drake sim and save the SO-101 joint trajectory to JSON.

The recording holds every frame the sim publishes (joint angles in URDF radians,
in ARM_JOINTS + gripper order) and one segment per pick-and-place, so
``scripts/play_trajectory.py`` can replay some or all of them on the real arm.
QR scanning is turned off: the trajectory is pure pick-and-place motion.

Usage:
    python scripts/export_trajectory.py [--out trajectories/pick_place.json]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from pantrysort.config import CONFIG, Config, SimConfig
from pantrysort.pipeline.sort_loop import SortLoop

DT = 0.05  # every Station.publish in the pick-and-place loop advances this much
OUT = Path(__file__).resolve().parents[1] / "trajectories" / "pick_place.json"


class RecordingSortLoop(SortLoop):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.frames: list[list[float]] = []
        self.segments: list[dict] = []

    def _maybe_build_station(self):
        station = super()._maybe_build_station()
        if station is not None and not getattr(station, "_recording_hooked", False):
            publish = station.publish

            def recording_publish(dt):
                publish(dt)
                self.frames.append([float(v) for v in station.joint_positions()])

            station.publish = recording_publish
            station._recording_hooked = True
        return station

    def _pick_and_place(self, station, scene_item, detection, location_id):
        start = len(self.frames)
        super()._pick_and_place(station, scene_item, detection, location_id)
        self.segments.append({"label": scene_item.label, "destination": location_id,
                              "start": start, "end": len(self.frames)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    from pantrysort.sim.station import ARM_JOINTS, GRIPPER_JOINT

    config = Config(sim=SimConfig(meshcat=False, qr_scanner=False, realtime_rate=0.0),
                    policy=CONFIG.policy, inventory=CONFIG.inventory)
    loop = RecordingSortLoop(config=config, use_sim=True)
    loop.run()
    if not loop.frames:
        raise SystemExit("No frames recorded (is Drake installed?).")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "joints": [*ARM_JOINTS, GRIPPER_JOINT],
        "units": "rad (URDF)",
        "dt": DT,
        "frames": loop.frames,
        "segments": loop.segments,
    }))
    q = np.array(loop.frames)
    print(f"Saved {len(q)} frames ({len(q) * DT:.0f} s of sim time), "
          f"{len(loop.segments)} pick-and-place segments -> {args.out}")
    for i, s in enumerate(loop.segments):
        print(f"  [{i}] {s['label']:<28} -> {s['destination']:<13} frames {s['start']}-{s['end']}")
    print("Joint range used (deg):")
    for n, lo, hi in zip([*ARM_JOINTS, GRIPPER_JOINT], np.degrees(q.min(0)),
                         np.degrees(q.max(0)), strict=True):
        print(f"  {n:<14} {lo:7.1f} .. {hi:7.1f}")


if __name__ == "__main__":
    main()
