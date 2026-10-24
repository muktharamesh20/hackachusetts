"""First powered test of the calibrated SO-101: hold in place, nudge one joint, return.

Safety measures:
  * Goal_Position is set to the present position *before* torque is enabled, so
    the arm can't jump to a stale goal left in the motors.
  * Torque_Limit is reduced (``--torque-limit``, out of 1000) for the test.
  * Each command is clipped to ``MAX_STEP_DEG`` from the present position
    (LeRobot's ``max_relative_target``) and the move is ramped slowly.
  * Aborts (torque off) if any joint drifts after torque-on, or if the tested
    joint lags its command by more than ``MAX_TRACK_ERR_DEG``.
  * Torque is always disabled on exit, Ctrl-C, or error. Run this with the arm
    resting somewhere it can go limp safely.

Usage:
    python scripts/arm_motion_test.py --joint shoulder_pan --delta 5
"""

from __future__ import annotations

import argparse
import sys
import time

from check_arm import EXPECTED, default_port

MAX_STEP_DEG = 2.0         # per-command clip
RATE_DEG_S = 5.0           # ramp speed
HZ = 30
MAX_HOLD_DRIFT_DEG = 3.0   # allowed movement right after torque-on
MAX_TRACK_ERR_DEG = 6.0
MAX_DELTA_DEG = 15.0       # refuse bigger test moves


def read_deg(robot) -> dict[str, float]:
    return robot.bus.sync_read("Present_Position", num_retry=3)


def fmt(p: dict[str, float]) -> str:
    return "  ".join(f"{k}={v:7.2f}" for k, v in p.items())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--port", default=default_port())
    parser.add_argument("--id", default="pantry_arm")
    parser.add_argument("--joint", default="shoulder_pan", choices=[m for m in EXPECTED if m != "gripper"])
    parser.add_argument("--delta", type=float, default=5.0, help="degrees to move and come back")
    parser.add_argument("--torque-limit", type=int, default=500, help="0..1000 (1000 = full)")
    parser.add_argument("--rate", type=float, default=RATE_DEG_S, help="ramp speed (deg/s)")
    parser.add_argument("--pause", type=float, default=0.0, help="wait after torque-on (s)")
    args = parser.parse_args()
    if abs(args.delta) > MAX_DELTA_DEG:
        print(f"Refusing a {args.delta} deg test move (max {MAX_DELTA_DEG}).")
        return 1

    from lerobot.motors.feetech import OperatingMode
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

    robot = SO101Follower(SO101FollowerConfig(port=args.port, id=args.id,
                                              max_relative_target=MAX_STEP_DEG))
    bus = robot.bus
    bus.connect(handshake=True)
    try:
        if not bus.is_calibrated:
            print("Arm is not calibrated (motor registers don't match the calibration file).")
            return 1

        # Same setup as SOFollower.configure(), but the goal is synced before torque-on.
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

        start = read_deg(robot)
        print("start   ", fmt(start))
        bus.sync_write("Goal_Position", start)
        bus.enable_torque()
        print(f"Torque ON (limit {args.torque_limit}/1000). Holding for 1 s...")
        time.sleep(1.0)
        held = read_deg(robot)
        drift = {m: held[m] - start[m] for m in start}
        print("held    ", fmt(held))
        worst = max(drift, key=lambda m: abs(drift[m]))
        if abs(drift[worst]) > MAX_HOLD_DRIFT_DEG:
            print(f"ABORT: {worst} moved {drift[worst]:.1f} deg on torque-on.")
            return 2

        if args.pause > 0:
            time.sleep(args.pause)
        j, q0 = args.joint, held[args.joint]
        goal = dict(held)

        def ramp_to(target: float) -> bool:
            n = max(1, int(abs(target - goal[j]) / args.rate * HZ))
            first = goal[j]
            loads = []
            for k in range(1, n + 1):
                goal[j] = first + (target - first) * k / n
                robot.send_action({f"{m}.pos": v for m, v in goal.items()})
                time.sleep(1 / HZ)
                err = goal[j] - read_deg(robot)[j]
                if k % 5 == 0:
                    loads.append(bus.read("Present_Load", j, normalize=False))
                if abs(err) > MAX_TRACK_ERR_DEG:
                    print(f"ABORT: {j} lagging command by {err:.1f} deg (blocked?).")
                    return False
            time.sleep(0.5)
            # LeRobot already decodes the sign bit, so the sign is the direction (0..1000 magnitude).
            mags = [abs(ld) for ld in loads]
            if mags:
                print(f"  {j} load while moving: avg {sum(mags) / len(mags):.0f}, max {max(mags)}"
                      " (out of 1000)")
            return True

        print(f"Moving {j} {q0:.1f} -> {q0 + args.delta:.1f} deg")
        if not ramp_to(q0 + args.delta):
            return 2
        out = read_deg(robot)[j]
        print(f"  reached {out:.2f} (error {q0 + args.delta - out:+.2f} deg)")
        print(f"Returning {j} -> {q0:.1f} deg")
        if not ramp_to(q0):
            return 2
        back = read_deg(robot)
        print(f"  reached {back[j]:.2f} (error {q0 - back[j]:+.2f} deg)")
        print("end     ", fmt(back))
        print("PASS")
        return 0
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130
    finally:
        try:
            bus.disable_torque(num_retry=3)
            for m in bus.motors:  # restore the default torque limit for normal use
                bus.write("Torque_Limit", m, 1000)
        except Exception as exc:
            print(f"warning during shutdown: {exc}")
        bus.disconnect(disable_torque=True)
        print("Torque OFF.")


if __name__ == "__main__":
    sys.exit(main())
