"""Read-only health check for the real SO-101 follower arm.

Never enables torque or moves anything. It:
  1. scans the serial port at every baud rate and lists responding motor IDs,
  2. checks the six expected motors (IDs 1-6, STS3215) answer at 1 Mbps,
  3. prints raw position, voltage, temperature and load for each motor,
  4. reports whether a LeRobot calibration file exists for ``--id``.

Usage:
    python scripts/check_arm.py --port /dev/tty.usbmodemXXXX [--id pantry_arm] [--watch]

``--watch`` keeps printing raw positions so you can move joints by hand and
confirm each one is wired to the right ID and reads change smoothly.
"""

from __future__ import annotations

import argparse
import glob
import sys
import time

EXPECTED = {
    "shoulder_pan": 1,
    "shoulder_lift": 2,
    "elbow_flex": 3,
    "wrist_flex": 4,
    "wrist_roll": 5,
    "gripper": 6,
}
STS3215_MODEL = 777
# STS3215 supply limits (volts); the 7.4 V kit and 12 V kit both fall inside this.
VOLTAGE_RANGE = (6.0, 13.0)
MAX_TEMP_C = 55


def default_port() -> str | None:
    ports = sorted(glob.glob("/dev/tty.usbmodem*") + glob.glob("/dev/ttyACM*"))
    return ports[0] if ports else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--port", default=default_port(), help="serial port of the follower arm")
    parser.add_argument("--id", default="pantry_arm", help="LeRobot robot id (calibration name)")
    parser.add_argument("--watch", action="store_true", help="stream raw positions until Ctrl-C")
    args = parser.parse_args()

    if not args.port:
        print("No /dev/tty.usbmodem* port found. Is the USB cable in and the arm powered?")
        return 1

    from lerobot.motors import Motor, MotorNormMode
    from lerobot.motors.feetech import FeetechMotorsBus
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

    print(f"Port: {args.port}")
    print("Scanning all baud rates (motors must be powered by the arm's power supply)...")
    found = FeetechMotorsBus.scan_port(args.port)
    if not found:
        print("\nFAIL: no motors answered. Check the arm's power supply (USB alone does not power"
              " the motors) and the 3-pin cable from the controller board to the first motor.")
        return 1
    for baud, ids in found.items():
        print(f"  {baud} baud: motor IDs {sorted(ids)}")

    ok = True
    ids_at_1m = set(found.get(1_000_000, []))
    missing = [n for n, i in EXPECTED.items() if i not in ids_at_1m]
    if missing:
        ok = False
        print(f"\nFAIL: expected IDs 1-6 at 1000000 baud; missing: {', '.join(missing)}")
        if any(1 in ids and len(ids) == 1 for ids in found.values()):
            print("  Several motors may still share the factory ID 1. Run lerobot-setup-motors.")
        else:
            print("  Check daisy-chain cables to those motors, or run lerobot-setup-motors.")
        return 1

    bus = FeetechMotorsBus(
        port=args.port,
        motors={n: Motor(i, "sts3215", MotorNormMode.RANGE_M100_100) for n, i in EXPECTED.items()},
    )
    bus.connect(handshake=False)
    try:
        bus.disable_torque()  # make sure nothing is holding, so joints can be moved by hand
        print(f"\n{'motor':<14}{'id':>3}{'model':>7}{'pos(raw)':>10}{'volt':>7}{'temp':>6}{'load':>6}")
        for name, mid in EXPECTED.items():
            model = bus.ping(name, num_retry=2)
            pos = bus.read("Present_Position", name, normalize=False, num_retry=2)
            volt = bus.read("Present_Voltage", name, normalize=False, num_retry=2) / 10
            temp = bus.read("Present_Temperature", name, normalize=False, num_retry=2)
            load = bus.read("Present_Load", name, normalize=False, num_retry=2)
            flags = []
            if model != STS3215_MODEL:
                flags.append(f"unexpected model {model}")
            if not VOLTAGE_RANGE[0] <= volt <= VOLTAGE_RANGE[1]:
                flags.append("voltage out of range")
            if temp > MAX_TEMP_C:
                flags.append("hot")
            ok &= not flags
            print(f"{name:<14}{mid:>3}{model:>7}{pos:>10}{volt:>7.1f}{temp:>6}{load:>6}"
                  + (f"   <-- {', '.join(flags)}" if flags else ""))

        if args.watch:
            print("\nTorque is off. Move each joint by hand; Ctrl-C to stop.")
            names = list(EXPECTED)
            print("  " + "".join(f"{n[:12]:>14}" for n in names))
            try:
                while True:
                    pos = bus.sync_read("Present_Position", normalize=False)
                    print("\r  " + "".join(f"{pos[n]:>14}" for n in names), end="", flush=True)
                    time.sleep(0.05)
            except KeyboardInterrupt:
                print()
    finally:
        bus.disconnect(disable_torque=True)

    robot = SO101Follower(SO101FollowerConfig(port=args.port, id=args.id))
    if robot.calibration:
        print(f"\nCalibration file found: {robot.calibration_fpath}")
    else:
        print(f"\nNo calibration yet for id '{args.id}' (expected at {robot.calibration_fpath}).")

    print("\nPASS: all 6 motors respond." if ok else "\nWARN: motors respond but see flags above.")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
