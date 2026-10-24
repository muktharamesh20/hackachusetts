"""Non-interactive LeRobot calibration for the SO-101 follower, in two steps.

``lerobot-calibrate`` waits for Enter key presses. This script does the same
calibration (same math, same output file) but splits it so each step can be
started on cue without a keyboard:

  home    Arm held in the middle of its range: write half-turn homing offsets
          (the current pose becomes encoder 2047 on every joint) and stage them.
  ranges  Stream positions while every joint is moved to both hard stops. Stops
          when ``--stop-file`` appears (or after ``--timeout`` s), validates the
          ranges and saves the calibration where LeRobot looks for it.

Torque stays off the whole time; nothing is driven.

Usage:
    python scripts/calibrate_arm.py home   --port /dev/tty.usbmodemXXXX
    python scripts/calibrate_arm.py ranges --port /dev/tty.usbmodemXXXX
    touch /tmp/pantrysort_calibrate.stop   # finish the ranges step
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from check_arm import EXPECTED, default_port

FULL_TURN_MOTOR = "wrist_roll"  # spins freely; LeRobot gives it the full 0..4095 range
MIN_SPAN = 600                   # ticks (~53 deg); smaller means a joint wasn't moved enough
DEFAULT_STOP_FILE = "/tmp/pantrysort_calibrate.stop"


def make_robot(port: str, robot_id: str):
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

    return SO101Follower(SO101FollowerConfig(port=port, id=robot_id))


def staging_path(robot) -> Path:
    return robot.calibration_fpath.with_suffix(".homing.json")


def step_home(robot) -> int:
    bus = robot.bus
    bus.connect(handshake=True)
    try:
        bus.disable_torque()
        from lerobot.motors.feetech import OperatingMode

        for motor in bus.motors:
            bus.write("Operating_Mode", motor, OperatingMode.POSITION.value)
        offsets = bus.set_half_turn_homings()
        pos = bus.sync_read("Present_Position", normalize=False, num_retry=5)
    finally:
        bus.disconnect(disable_torque=True)

    staging_path(robot).write_text(json.dumps({k: int(v) for k, v in offsets.items()}, indent=2))
    print(f"{'motor':<14}{'homing_offset':>14}{'pos now':>9}")
    for motor in EXPECTED:
        print(f"{motor:<14}{offsets[motor]:>14}{pos[motor]:>9}")
    bad = [m for m in EXPECTED if abs(pos[m] - 2047) > 40]
    if bad:
        print(f"WARN: {', '.join(bad)} did not land near 2047 (was the arm moving?). Re-run home.")
        return 2
    print(f"Homing staged at {staging_path(robot)}. Next: the ranges step.")
    return 0


def step_ranges(robot, stop_file: Path, timeout: float) -> int:
    from lerobot.motors import MotorCalibration

    stage = staging_path(robot)
    if not stage.is_file():
        print("No staged homing offsets. Run the home step first.")
        return 1
    offsets = json.loads(stage.read_text())
    stop_file.unlink(missing_ok=True)

    bus = robot.bus
    bus.connect(handshake=True)
    recorded = [m for m in bus.motors if m != FULL_TURN_MOTOR]
    try:
        bus.disable_torque()
        pos = bus.sync_read("Present_Position", recorded, normalize=False, num_retry=5)
        mins, maxes = dict(pos), dict(pos)
        print(f"Recording. Move each joint to both hard stops. Stop with: touch {stop_file}",
              flush=True)
        t0 = last_print = time.monotonic()
        while not stop_file.exists() and time.monotonic() - t0 < timeout:
            pos = bus.sync_read("Present_Position", recorded, normalize=False, num_retry=5)
            for m in recorded:
                mins[m], maxes[m] = min(mins[m], pos[m]), max(maxes[m], pos[m])
            if time.monotonic() - last_print >= 2:
                last_print = time.monotonic()
                print(f"[{last_print - t0:5.0f}s] "
                      + "  ".join(f"{m}:{maxes[m] - mins[m]}" for m in recorded), flush=True)
            time.sleep(0.02)
    finally:
        bus.disconnect(disable_torque=True)
    stop_file.unlink(missing_ok=True)

    print(f"\n{'motor':<14}{'min':>6}{'max':>6}{'span':>6}")
    short = []
    for m in recorded:
        span = maxes[m] - mins[m]
        print(f"{m:<14}{mins[m]:>6}{maxes[m]:>6}{span:>6}" + ("   <-- too small" if span < MIN_SPAN else ""))
        if span < MIN_SPAN:
            short.append(m)
    if short:
        print(f"NOT SAVED: move {', '.join(short)} through their full range and re-run ranges.")
        return 2

    mins[FULL_TURN_MOTOR], maxes[FULL_TURN_MOTOR] = 0, 4095
    robot.calibration = {
        m: MotorCalibration(id=mot.id, drive_mode=0, homing_offset=int(offsets[m]),
                            range_min=int(mins[m]), range_max=int(maxes[m]))
        for m, mot in robot.bus.motors.items()
    }
    bus.connect(handshake=True)
    try:
        bus.write_calibration(robot.calibration)
    finally:
        bus.disconnect(disable_torque=True)
    robot._save_calibration()
    stage.unlink(missing_ok=True)
    print(f"Calibration saved to {robot.calibration_fpath}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("step", choices=["home", "ranges"])
    parser.add_argument("--port", default=default_port())
    parser.add_argument("--id", default="pantry_arm")
    parser.add_argument("--stop-file", type=Path, default=Path(DEFAULT_STOP_FILE))
    parser.add_argument("--timeout", type=float, default=600.0, help="ranges step limit (s)")
    args = parser.parse_args()
    if not args.port:
        print("No arm port found.")
        return 1
    robot = make_robot(args.port, args.id)
    if args.step == "home":
        return step_home(robot)
    return step_ranges(robot, args.stop_file, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
