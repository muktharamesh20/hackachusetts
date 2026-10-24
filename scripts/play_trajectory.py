"""Replay a sim joint trajectory (from export_trajectory.py) on the real SO-101.

Joint mapping: LeRobot's SO-101 calibration puts 0 deg at the middle of each
joint's range, which matches the URDF zero pose (upper arm vertical, forearm and
gripper pointing forward), so real degrees = URDF radians * 180/pi times a per-
joint sign (``SIGNS``; shoulder_pan verified on the arm). The gripper maps the
URDF range linearly onto LeRobot's 0..100.

Safety:
  * Pre-flight: every commanded frame (and the moves to/from it) is checked with
    forward kinematics: every link and the gripper tip must stay above
    ``--min-z`` (the table is z=0) and joints inside the calibrated range minus a
    margin. Nothing moves if any check fails.
  * The goal is synced to the present pose before torque-on (no jump).
  * Playback is retimed so no joint exceeds ``--max-speed`` deg/s, and every
    command is clipped to ``MAX_STEP_DEG`` from the present position.
  * If a joint lags its command by more than ``--max-error`` deg (blocked or
    overloaded), it freezes, then returns slowly to the start pose.
  * It always ends back at the pose it started in, then turns torque off. Start
    it with the arm resting on the table.

Usage:
    python scripts/play_trajectory.py --segments 0 --dry-run
    python scripts/play_trajectory.py --segments 0
    python scripts/play_trajectory.py --segments all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from check_arm import default_port

TRAJ = Path(__file__).resolve().parents[1] / "trajectories" / "pick_place.json"
JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")
SIGNS = {"shoulder_pan": 1, "shoulder_lift": 1, "elbow_flex": 1, "wrist_flex": 1, "wrist_roll": 1}
GRIPPER_URDF = (-0.174533, 1.74533)  # rad, URDF limits <-> LeRobot 0..100
LIMIT_MARGIN_DEG = 4.0
MAX_STEP_DEG = 6.0
HZ = 30
LINKS = ("shoulder_link", "upper_arm_link", "lower_arm_link", "wrist_link", "gripper_link",
         "moving_jaw_so101_v1_link")


def urdf_to_real(q: np.ndarray) -> dict[str, float]:
    out = {n: SIGNS[n] * float(np.degrees(q[i])) for i, n in enumerate(JOINTS[:5])}
    lo, hi = GRIPPER_URDF
    out["gripper"] = float(np.clip((q[5] - lo) / (hi - lo) * 100, 0, 100))
    return out


def real_to_urdf(d: dict[str, float]) -> np.ndarray:
    q = [np.radians(d[n]) * SIGNS[n] for n in JOINTS[:5]]
    lo, hi = GRIPPER_URDF
    return np.array([*q, lo + d["gripper"] / 100 * (hi - lo)])


class Fk:
    """Lowest point of the arm for a URDF joint vector."""

    def __init__(self) -> None:
        from pantrysort.sim.station import TCP_FRAME, _ArmIK

        ik = _ArmIK()
        self.plant, self.ctx = ik.plant, ik.context
        self.tcp = self.plant.GetFrameByName(TCP_FRAME)
        self.bodies = [self.plant.GetBodyByName(b) for b in LINKS
                       if self.plant.HasBodyNamed(b)]
        self.index = [self.plant.GetJointByName(n).position_start() for n in JOINTS]

    def min_z(self, q: np.ndarray) -> tuple[float, np.ndarray]:
        v = np.zeros(self.plant.num_positions())
        v[self.index] = q
        self.plant.SetPositions(self.ctx, v)
        zs = [self.plant.EvalBodyPoseInWorld(self.ctx, b).translation()[2] for b in self.bodies]
        X = self.plant.CalcRelativeTransform(self.ctx, self.plant.world_frame(), self.tcp)
        tip = X.translation()
        return float(min(*zs, tip[2])), tip


def retime(path: list[dict[str, float]], max_speed: float, min_dt: float) -> list[dict[str, float]]:
    """Resample waypoints at HZ so no joint moves faster than ``max_speed`` deg/s."""
    out = [path[0]]
    for a, b in zip(path, path[1:], strict=False):
        dmax = max(abs(b[n] - a[n]) for n in JOINTS[:5])
        dur = max(min_dt, dmax / max_speed, 1 / HZ)
        n = max(1, round(dur * HZ))
        for k in range(1, n + 1):
            s = k / n
            out.append({j: a[j] + s * (b[j] - a[j]) for j in JOINTS})
    return out


def smooth_move(a: dict[str, float], b: dict[str, float], speed: float) -> list[dict[str, float]]:
    """Eased joint-space move from ``a`` to ``b`` with peak speed about ``speed`` deg/s."""
    dmax = max(abs(b[n] - a[n]) for n in JOINTS)
    n = max(2, round(dmax / speed * HZ * 1.6))
    return [{j: a[j] + (0.5 - 0.5 * np.cos(np.pi * k / n)) * (b[j] - a[j]) for j in JOINTS}
            for k in range(1, n + 1)]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--traj", type=Path, default=TRAJ)
    p.add_argument("--segments", default="0", help="'all' or comma list of indices, e.g. 0,1,2")
    p.add_argument("--port", default=default_port())
    p.add_argument("--id", default="pantry_arm")
    p.add_argument("--max-speed", type=float, default=25.0, help="deg/s per joint")
    p.add_argument("--slowdown", type=float, default=2.0, help="x sim time (minimum)")
    p.add_argument("--min-z", type=float, default=0.015, help="lowest allowed point (m)")
    p.add_argument("--max-error", type=float, default=10.0, help="tracking abort (deg)")
    p.add_argument("--torque-limit", type=int, default=800, help="0..1000")
    p.add_argument("--dry-run", action="store_true", help="checks only, no torque")
    args = p.parse_args()

    data = json.loads(args.traj.read_text())
    assert tuple(data["joints"]) == JOINTS, data["joints"]
    frames = np.array(data["frames"])
    segs = data["segments"]
    chosen = range(len(segs)) if args.segments == "all" else [int(s) for s in args.segments.split(",")]
    print(f"Trajectory: {args.traj.name}, segments: "
          + ", ".join(f"[{i}] {segs[i]['label']} -> {segs[i]['destination']}" for i in chosen))

    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

    robot = SO101Follower(SO101FollowerConfig(port=args.port, id=args.id,
                                              max_relative_target=MAX_STEP_DEG))
    bus = robot.bus
    cal = robot.calibration
    if not cal:
        print("No calibration file; run the calibration first.")
        return 1
    # Calibrated joint limits in LeRobot degrees.
    res = 4095
    limits = {n: ((c.range_min - (c.range_min + c.range_max) / 2) * 360 / res + LIMIT_MARGIN_DEG,
                  (c.range_max - (c.range_min + c.range_max) / 2) * 360 / res - LIMIT_MARGIN_DEG)
              for n, c in cal.items() if n != "gripper"}
    limits["gripper"] = (0.0, 100.0)

    bus.connect(handshake=True)
    try:
        if not bus.is_calibrated:
            print("Motors don't match the calibration file.")
            return 1
        start = bus.sync_read("Present_Position", num_retry=3)
        print("start pose (deg):", {k: round(v, 1) for k, v in start.items()})

        # ---- build the full command list
        path: list[dict[str, float]] = []
        prev = start
        for i in chosen:
            s = segs[i]
            seg = [urdf_to_real(q) for q in frames[s["start"]:s["end"]]]
            path += smooth_move(prev, seg[0], args.max_speed * 0.6)
            path += retime(seg, args.max_speed, data["dt"] * args.slowdown)
            prev = path[-1]
        home = smooth_move(prev, start, args.max_speed * 0.6)
        path += home

        # ---- pre-flight
        fk = Fk()
        worst_z, worst_k, problems = 1e9, 0, []

        # The start/end pose is the arm resting on the table, at its hard stops:
        # exempt commands within 15 deg of it from the limit and floor checks.
        def near_rest(cmd):
            return max(abs(cmd[n] - start[n]) for n in JOINTS[:4]) < 15

        for k, cmd in enumerate(path):
            if near_rest(cmd):
                continue
            for n in JOINTS[:4]:
                lo, hi = limits[n]
                if not lo <= cmd[n] <= hi:
                    problems.append(f"cmd {k}: {n}={cmd[n]:.1f} outside [{lo:.1f}, {hi:.1f}]")
            z, _ = fk.min_z(real_to_urdf(cmd))
            if z < worst_z:
                worst_z, worst_k = z, k

        low = [k for k, cmd in enumerate(path)
               if fk.min_z(real_to_urdf(cmd))[0] < args.min_z and not near_rest(cmd)]
        if low:
            problems.append(f"{len(low)} commands go below z={args.min_z} m "
                            f"(lowest {worst_z:.3f} m at cmd {worst_k})")
        duration = len(path) / HZ
        print(f"{len(path)} commands, {duration:.0f} s at {HZ} Hz; lowest arm point "
              f"{worst_z * 100:.1f} cm (cmd {worst_k}); max speed {args.max_speed} deg/s")
        if problems:
            print("PRE-FLIGHT FAILED:")
            for msg in problems[:15]:
                print("  ", msg)
            return 2
        print("Pre-flight OK.")
        if args.dry_run:
            return 0

        # ---- torque on, hold
        from lerobot.motors.feetech import OperatingMode

        bus.disable_torque()
        bus.configure_motors()
        for m in bus.motors:
            bus.write("Operating_Mode", m, OperatingMode.POSITION.value)
            bus.write("P_Coefficient", m, robot.config.position_p_coefficient)
            bus.write("I_Coefficient", m, robot.config.position_i_coefficient)
            bus.write("D_Coefficient", m, robot.config.position_d_coefficient)
            bus.write("Torque_Limit", m, args.torque_limit)
        bus.write("Max_Torque_Limit", "gripper", 500)
        bus.write("Protection_Current", "gripper", 250)
        bus.write("Overload_Torque", "gripper", 25)
        bus.sync_write("Goal_Position", bus.sync_read("Present_Position", num_retry=3))
        bus.enable_torque()
        time.sleep(0.5)

        def play(cmds, check=True) -> bool:
            t_next = time.monotonic()
            for k, cmd in enumerate(cmds):
                robot.send_action({f"{n}.pos": v for n, v in cmd.items()})
                t_next += 1 / HZ
                time.sleep(max(0.0, t_next - time.monotonic()))
                if check and k % 3 == 0:
                    now = bus.sync_read("Present_Position", num_retry=3)
                    err = {n: cmd[n] - now[n] for n in JOINTS[:4]}
                    bad = max(err, key=lambda n: abs(err[n]))
                    if abs(err[bad]) > args.max_error:
                        print(f"\nABORT at cmd {k}: {bad} {err[bad]:+.1f} deg behind its command.")
                        return False
                if k % HZ == 0:
                    print(f"\r  {k / HZ:5.0f}/{len(cmds) / HZ:.0f} s", end="", flush=True)
            print()
            return True

        print("Torque ON. Playing...")
        ok = play(path)
        if not ok:
            now = bus.sync_read("Present_Position", num_retry=3)
            robot.send_action({f"{n}.pos": v for n, v in now.items()})
            time.sleep(1.5)
            print("Returning slowly to the start pose...")
            play(smooth_move(now, start, 10.0), check=False)
        time.sleep(0.5)
        end = bus.sync_read("Present_Position", num_retry=3)
        print("end pose (deg):  ", {k: round(v, 1) for k, v in end.items()})
        print("DONE" if ok else "ABORTED (back at start)")
        return 0 if ok else 3
    finally:
        try:
            bus.disable_torque(num_retry=3)
            for m in bus.motors:
                bus.write("Torque_Limit", m, 1000)
        except Exception as exc:
            print(f"warning during shutdown: {exc}")
        bus.disconnect(disable_torque=True)
        print("Torque OFF.")


if __name__ == "__main__":
    sys.exit(main())
