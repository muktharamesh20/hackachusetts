"""Execute a pick-and-place for one item by stepping a policy in the station.

Bridge between a :class:`~pantrysort.policy.lerobot_policy.Policy` and the Drake
station. Each control step:

  1. read the grasp-point position from the arm's current joint angles,
  2. ask the policy for an end-effector target + gripper command,
  3. move a short step toward the target (first-order tracking) and IK the arm
     there, open/close the gripper, attach/release the item, and
  4. publish a frame to Meshcat.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pantrysort.policy.lerobot_policy import Policy, PolicyObservation

TRACK_RATE = 0.25    # fraction of the remaining distance covered per step
GRIPPER_RATE = 0.5


def execute_pick_and_place(
    station,
    policy: Policy,
    grasp_position: np.ndarray,
    drop_position: np.ndarray,
    max_steps: int = 400,
    dt: float = 0.05,
    grasp_width: float | None = None,
    drop_yaw: float = 0.0,
) -> bool:
    """Run the policy until it reports ``done`` or ``max_steps`` elapses.

    ``grasp_width`` (m) sets where the item sits between the jaws and how far they
    close; ``drop_yaw`` is the item's final heading on the pad. Returns True if the
    policy signalled completion.
    """
    policy.reset()
    if grasp_width is not None:
        station.prepare_grasp(grasp_width)
    gripper = 0.0
    done = False
    steps = 0

    while not done and steps < max_steps:
        ee = station.ee_position()
        obs = PolicyObservation(
            ee_position=ee.copy(),
            gripper=gripper,
            target_position=np.asarray(grasp_position, dtype=float),
            goal_position=np.asarray(drop_position, dtype=float),
        )
        action = policy.select_action(obs)

        target = np.asarray(action.ee_target, dtype=float)
        station.move_ee_to(_step_around_base(ee, target, TRACK_RATE))

        gripper += GRIPPER_RATE * (float(action.gripper) - gripper)
        if action.gripper >= 0.5 and not station.holding:
            station.attach_nearest()
        elif action.gripper < 0.5 and station.holding:
            station.drop_held_onto(np.asarray(drop_position, dtype=float), dt, yaw=drop_yaw)
        station.set_gripper(gripper)

        done = action.done
        station.publish(dt)
        steps += 1

    # Let the gripper finish opening and settle for a moment between items.
    for _ in range(4):
        gripper *= 1 - GRIPPER_RATE
        station.set_gripper(gripper)
        station.publish(dt)
    return done


@dataclass
class ScanReading:
    """What the gripper camera saw over one item."""

    image: np.ndarray | None          # RGBA frame (None if the camera is unavailable)
    qr: object | None = None          # DecodedQr of the sticker, if one was read


def scan_item(station, sticker_point: np.ndarray, dt: float = 0.05,
              dwell_frames: int = 4) -> ScanReading:
    """Hover the gripper's scanner over ``sticker_point`` and decode the QR there.

    Tries a few camera heights (reachability and decode quality vary across the
    intake grid). If several codes are in view (neighbours), takes the one
    nearest the image center, which is the sticker the camera is aimed at.
    """
    from pantrysort.perception.qr import decode_qr_codes
    from pantrysort.sim.station import SCAN_DISTANCES

    image = None
    for distance in SCAN_DISTANCES:
        q = station.scan_pose(np.asarray(sticker_point, dtype=float), distance)
        if q is None:
            continue
        station.move_joints_to(q, dt)
        for _ in range(dwell_frames):  # hold still while "scanning"
            station.publish(dt)
        image = station.scanner_image()
        if image is None:
            return ScanReading(None)
        codes = decode_qr_codes(image)
        if codes:
            h, w = image.shape[:2]
            best = min(codes, key=lambda c: np.hypot(c.center_px[0] - w / 2,
                                                     c.center_px[1] - h / 2))
            return ScanReading(image, best)
    return ScanReading(image)


def scan_item_rig(station, dt: float = 0.05) -> ScanReading:
    """Read QR stickers from the fixed camera rig (no gripper camera).

    Renders each rig camera in turn and decodes any QR codes it sees. Returns
    the first successful read, keeping the `ScanReading` shape so the Meshcat
    scan-card display works unchanged. The camera image returned is the fisheye
    (what the wide base lens actually sees) for the base camera, else the raw
    frame. With QR stickers on the item sides, the side-viewing rig cameras can
    read them where a top-down or gripper camera could not.
    """
    from pantrysort.perception.qr import decode_qr_codes

    image = None
    for name in station.camera_names():
        frame = station.camera_rgb(name)
        if frame is None:
            continue
        image = frame
        codes = decode_qr_codes(frame)
        if codes:
            h, w = frame.shape[:2]
            best = min(codes, key=lambda c: np.hypot(c.center_px[0] - w / 2,
                                                     c.center_px[1] - h / 2))
            return ScanReading(frame, best)
    return ScanReading(image)

MIN_RADIUS = 0.15  # keep the hand this far from the SO-101's base axis while swinging (m)


def _step_around_base(current: np.ndarray, target: np.ndarray, rate: float) -> np.ndarray:
    """One tracking step in cylindrical coordinates about the arm base (z axis).

    A straight Cartesian line between, e.g., the intake tray and the freezer
    passes through the robot's own base; sweeping the angle instead makes the arm
    swing around it like a real pick-and-place.
    """
    r0, th0 = np.hypot(current[0], current[1]), np.arctan2(current[1], current[0])
    r1, th1 = np.hypot(target[0], target[1]), np.arctan2(target[1], target[0])
    dth = (th1 - th0 + np.pi) % (2 * np.pi) - np.pi  # shortest way around
    r = r0 + rate * (r1 - r0)
    # Only enforce the clearance while swinging, so final targets stay exact.
    if abs(dth) > 0.2:
        r = max(r, MIN_RADIUS)
    th = th0 + rate * dth
    z = current[2] + rate * (target[2] - current[2])
    return np.array([r * np.cos(th), r * np.sin(th), z])
