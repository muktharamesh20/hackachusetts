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
WRIST_RATE = 0.25    # same for the wrist's heading turn while carrying an item
GRIPPER_RATE = 0.5


def execute_pick_and_place(
    station,
    policy: Policy,
    grasp_position: np.ndarray,
    drop_position: np.ndarray,
    max_steps: int = 400,
    dt: float = 0.05,
    grasp_width: float | None = None,
    drop_yaw: float | None = None,
) -> bool:
    """Run the policy until it reports ``done`` or ``max_steps`` elapses.

    ``grasp_width`` (m) sets where the item sits between the jaws and how far they
    close; ``drop_yaw`` is the item's final heading in the bin (the wrist rotates
    the item to it while carrying; None = keep the heading it was picked at).
    Returns True if the policy signalled completion.
    """
    policy.reset()
    if grasp_width is not None:
        station.prepare_grasp(grasp_width)
    drop_position = np.asarray(drop_position, dtype=float)
    gripper = 0.0
    done = False
    steps = 0
    # Jaw heading relative to "sideways to the reach direction" (rad, signed and
    # unwrapped so the wrist turns continuously). It eases from wherever the
    # wrist is now to a grasp heading, then, once an item is held, to whatever
    # puts the item at ``drop_yaw`` over the bin: the wrist turns the item during
    # transport, so it never spins on release.
    ee = station.ee_position()
    rel = _wrap_full_turn(station.jaw_heading() - _sideways(ee))
    rel_target = _choose_turn(station, rel, 0.0)

    while not done and steps < max_steps:
        ee = station.ee_position()
        obs = PolicyObservation(
            ee_position=ee.copy(),
            gripper=gripper,
            target_position=np.asarray(grasp_position, dtype=float),
            goal_position=drop_position,
        )
        action = policy.select_action(obs)

        rel += WRIST_RATE * (rel_target - rel)
        step = _step_around_base(ee, np.asarray(action.ee_target, dtype=float), TRACK_RATE)
        station.move_ee_to(step, jaw_heading=_sideways(step) + rel)

        gripper += GRIPPER_RATE * (float(action.gripper) - gripper)
        if action.gripper >= 0.5 and not station.holding:
            if station.attach_nearest() and drop_yaw is not None:
                # The item turns with the jaws: pick the jaw heading over the bin
                # that gives the item its drop yaw.
                held_offset = station.held_item_yaw() - station.jaw_heading()
                rel_target = _choose_turn(
                    station, rel, drop_yaw - held_offset - _sideways(drop_position))
        elif action.gripper < 0.5 and station.holding:
            # Land at the heading it's held at: no turn of its own on release.
            station.drop_held_onto(drop_position, dt, yaw=None)
            rel_target = rel  # hold the wrist still while the gripper opens
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


def _sideways(p: np.ndarray) -> float:
    """Default jaw heading at ``p``: tangent to the arm's reach direction."""
    from pantrysort.sim.pantry_scene import PAN_AXIS_XY

    return float(np.arctan2(p[1] - PAN_AXIS_XY[1], p[0] - PAN_AXIS_XY[0]) + np.pi / 2)


def _wrap_full_turn(a: float) -> float:
    """Wrap to [-pi, pi)."""
    return float((a + np.pi) % (2 * np.pi) - np.pi)


ROLL_MARGIN = 0.25  # rad kept clear of wrist_roll's limits


def _choose_turn(station, rel: float, goal: float) -> float:
    """Pick the target heading ``goal + k*pi`` (equivalent for a two-jaw grasp)
    that's the smallest wrist turn from ``rel`` while keeping wrist_roll inside
    its limits, so the wrist never has to flip mid-move."""
    down, up = station.wrist_roll_room()
    gain = station.heading_per_roll() or 1.0
    base = rel + _wrap_full_turn(goal - rel)
    candidates = sorted((base + k * np.pi for k in (-2, -1, 0, 1, 2)),
                        key=lambda c: abs(c - rel))
    for c in candidates:
        d_roll = (c - rel) / gain
        if -down + ROLL_MARGIN <= d_roll <= up - ROLL_MARGIN:
            return float(c)
    return float(candidates[0])


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
