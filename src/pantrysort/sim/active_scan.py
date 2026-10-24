"""Active QR scanning: the arm picks an item up and presents it to a camera.

Passive multi-camera decode (perception.identify) handles items whose side
stickers happen to face a decodable camera. For the rest, the robot grasps the
item and holds it close in front of a *presentation* camera, where even a small
sticker renders large and head-on and decodes reliably. This mirrors how a real
arm-mounted sorter confirms an unreadable label: bring it to the lens.

Only presentation cameras (``present=True`` with a ``present_at`` point, see
sim/camera.py) are used as targets; the arm-mounted ``robot_cam`` is never one.
The flow is two passes:

  * Pass 1 - glide the item to each presentation camera's ``present_at`` point
    and try a straight read. No rotation here.
  * Pass 2 (last resort, once per item) - only if every straight read failed,
    glide to the single camera that saw the largest QR quad and rotate the item
    about ``wrist_roll`` in one monotonic direction (90/180/270 deg stops),
    holding still at each stop before reading. No wrist_flex tilt.

Kinematic station assumptions (see sim/station.py): ``move_ee_to_smooth`` IKs the
grasp point to a world position under velocity/acceleration caps, items are
rigidly held after ``attach_nearest`` and follow the gripper, ``_ramp_to`` glides
joints to a goal under the same caps, and ``publish`` advances/animates. pydrake
imports stay inside functions.
"""

from __future__ import annotations

import logging
from math import ceil

import numpy as np

from pantrysort.sim.station import MAX_JOINT_ACCEL

logger = logging.getLogger("pantrysort.sim.active_scan")

SETTLE_FRAMES = 4


def present_point_for_camera(station, camera_name: str, distance: float | None = None):
    """The presentation point for ``camera_name``: its spec's ``present_at``.

    Returns ``None`` when the camera is not a presentation camera (no spec, or
    ``present=False`` / no ``present_at``). ``distance`` is accepted for
    backward-compatible call sites but ignored - the target is the configured
    ``present_at`` world point, not a point computed along the optical axis.
    """
    spec = station.camera_specs.get(camera_name)
    if spec is None or not getattr(spec, "present", False) or spec.present_at is None:
        return None
    return np.asarray(spec.present_at, dtype=float)


def _read_presented(station, camera_name, expected_world=None,
                    min_qr_px=70.0, pos_tol=0.07):
    """Decode a QR from `camera_name` only, accepting it only if it is large
    (close -> the presented item) and, when `expected_world` is given, its
    back-projected world point is within `pos_tol` of where the held item is.
    This stops a previously-presented or background item from being misread."""
    from pantrysort.perception.qr import decode_qr_codes

    frame = station.camera_rgb(camera_name)
    if frame is None:
        return None
    best, best_size = None, 0.0
    for qr in decode_qr_codes(frame):
        c = np.asarray(qr.corners, dtype=float)
        size = float(max(np.ptp(c[:, 0]), np.ptp(c[:, 1])))
        if size < min_qr_px:
            continue
        if expected_world is not None:
            u, v = qr.center_px
            p = station.locate_pixel(u, v, camera_name)
            if p is None or np.linalg.norm(p - np.asarray(expected_world, dtype=float)) > pos_tol:
                continue
        if size > best_size:
            best, best_size = qr, size
    if best is None:
        return None
    return best.text, frame, camera_name


def _qr_signal(station, camera_name, expected_world=None, pos_tol=0.06):
    """How visible the held item's QR is right now, even if not yet decodable.

    Returns `(decoded_text_or_None, quad_area_px)`. Uses detect() so a QR that
    is located but not readable still yields a positive area, which lets pass 1
    rank cameras and the rotation search climb toward a fronto-parallel view.
    """
    import cv2

    from pantrysort.perception.qr import _to_gray, decode_qr_codes

    frame = station.camera_rgb(camera_name)
    if frame is None:
        return None, 0.0

    # A full decode (with our rectification fallback) is the goal. Accept only a
    # large QR that back-projects to the held item (reject neighbors).
    for qr in decode_qr_codes(frame):
        cpx = np.asarray(qr.corners, dtype=float)
        size = float(max(np.ptp(cpx[:, 0]), np.ptp(cpx[:, 1])))
        if size < 70.0:
            continue
        if expected_world is not None:
            u, v = qr.center_px
            pw = station.locate_pixel(u, v, camera_name)
            if pw is None or np.linalg.norm(pw - np.asarray(expected_world, dtype=float)) > pos_tol:
                continue
        return qr.text, _quad_area(cpx)

    # No decode: still report how large any detected QR quad is, to steer search.
    gray = _to_gray(frame)
    det = cv2.QRCodeDetector()
    ok, quads = det.detectMulti(gray)
    if ok and quads is not None:
        areas = [_quad_area(np.asarray(q, dtype=float).reshape(4, 2))
                 for q in np.asarray(quads).reshape(-1, 4, 2)]
        return None, max(areas) if areas else 0.0
    return None, 0.0


def _quad_area(c: np.ndarray) -> float:
    """Shoelace area of a 4-point quad (px^2)."""
    x, y = c[:, 0], c[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))


# wrist_roll / wrist_flex joint indices (0 pan,1 lift,2 elbow,3 wrist_flex,4 wrist_roll,5 gripper)
_ROLL_IDX, _FLEX_IDX = 4, 3


def _rotate_and_read(station, camera_name, expected_world, dt, hold_frames):
    """Last-resort rotation search at one presentation camera's present point.

    Rotates the held item about ``wrist_roll`` ONLY (no wrist_flex tilt) in a
    single monotonic direction, stopping at +/-90, 180 and 270 degrees. The
    direction (+ or -) is chosen from ``wrist_roll_room`` to fit the most stops,
    keeping a 0.05 rad margin from the joint limit; stops that do not fit are
    skipped and total rotation never exceeds 270 degrees. Moves between stops
    with ``_ramp_to`` (slow, visible - no SetPositions snaps) and holds still for
    at least 0.5 s of sim time at each stop before reading.

    Returns `(text, frame, camera)` on the first successful read, else None.
    """
    q_start = station.joint_positions().copy()
    down, up = station.wrist_roll_room()  # remaining room (down, up) from current, rad
    margin = 0.05
    stops_rad = [np.deg2rad(d) for d in (90.0, 180.0, 270.0)]

    # Pick the direction that fits the most stops within the available room.
    up_fits = sum(1 for s in stops_rad if s <= up - margin)
    down_fits = sum(1 for s in stops_rad if s <= down - margin)
    if up_fits >= down_fits:
        sign, room = 1.0, up
    else:
        sign, room = -1.0, down

    hold = max(1, ceil(0.5 / dt))  # >= 0.5 s of sim time still at each stop
    stop_i = 0
    for s in stops_rad:
        if s > room - margin:
            continue  # this stop would exceed the joint limit; skip it
        stop_i += 1
        q_goal = q_start.copy()
        q_goal[_ROLL_IDX] = q_start[_ROLL_IDX] + sign * s
        station._ramp_to(q_goal, dt, max_speed=1.0, max_accel=MAX_JOINT_ACCEL)
        for _ in range(hold):
            station.publish(dt)
        logger.info("Rotate search %s: stop %d (%+d deg)",
                    camera_name, stop_i, int(round(sign * np.rad2deg(s))))
        hit = _read_presented(station, camera_name, expected_world=expected_world)
        if hit is None:
            text, _area = _qr_signal(station, camera_name, expected_world)
            if text is not None:
                frame = station.camera_rgb(camera_name)
                hit = (text, frame, camera_name)
        if hit is not None:
            logger.info("Rotate search read %s at stop %d", camera_name, stop_i)
            return hit

    # Nothing decoded; glide the wrist back to where it started for a clean handoff.
    station._ramp_to(q_start, dt, max_speed=1.0, max_accel=MAX_JOINT_ACCEL)
    return None


def present_and_read(station, item_label: str, dt: float = 0.05, hold_frames: int = SETTLE_FRAMES,
                     on_capture=None, cameras=None, keep_held: bool = False):
    """Grasp `item_label`, present it to each presentation camera, and decode.

    Motion uses the velocity/acceleration-limited `move_ee_to_smooth` so the
    arm glides rather than snaps. `hold_frames` keeps the item still in front
    of the camera (raise it in testing so the rendered frame is crisp).
    `on_capture(camera_name, item_label)` is called while the item is held and
    settled, for a caller that wants to save frames. `cameras` restricts which
    presentation cameras to use (default: all presentation cameras), intersected
    with the rig's presentation set so `robot_cam` is never a target.

    Two passes: (1) a straight read at every presentation `present_at` point with
    no rotation; (2) only if all of those fail, a single rotation search at the
    camera that saw the largest QR quad. Returns `(text, image, camera)` on
    success or `None`. On failure the item is set back to its original pose and
    released; with `keep_held=True` a successful read leaves the item grasped.
    """
    from pantrysort.sim.camera import presentation_cameras

    body = station.item_bodies.get(item_label)
    if body is None:
        return None
    X_orig = station._body_pose(body)

    # 1) Grasp: glide to the item, close, attach.
    p_item = np.asarray(station._body_pose(body).translation(), dtype=float)
    shape = station.item_shapes.get(item_label)
    if shape is not None:
        station.prepare_grasp(shape.grip_width)
    station.move_ee_to_smooth(p_item, dt)
    for _ in range(hold_frames):
        station.publish(dt)
    station.set_gripper(1.0)
    grabbed = station.attach_nearest()
    station.publish(dt)
    if grabbed is None:
        logger.debug("present_and_read: failed to grasp %s", item_label)
        station.detach()
        station.set_gripper(0.0)
        station.publish(dt)
        return None

    # Target only presentation cameras (never robot_cam), in rig order. Respect
    # the caller's `cameras=` filter by intersecting with the presentation set.
    present_names = presentation_cameras(list(station.camera_specs.values()))
    if cameras is not None:
        allowed = set(cameras)
        present_names = [n for n in present_names if n in allowed]

    result = None
    # Pass 1: straight reads at each present_at, recording QR quad area per camera.
    best_signal: list[tuple[float, str, np.ndarray]] = []
    for name in present_names:
        target = present_point_for_camera(station, name)
        if target is None:
            continue
        if not _reachable(station, target):
            logger.info("Active scan: present point for %s unreachable; skipping", name)
            continue
        station.move_ee_to_smooth(target, dt)
        for _ in range(hold_frames):
            station.publish(dt)
        if on_capture is not None:
            on_capture(name, item_label)
        held_pos = np.asarray(station._body_pose(body).translation(), dtype=float)
        hit = _read_presented(station, name, expected_world=held_pos)
        if hit is not None:
            logger.info("Active scan read %s by presenting to %s (straight)", item_label, name)
            result = hit
            break
        # No straight read: record how large this camera saw the QR quad, to pick
        # the one camera the rotation search (pass 2) will run at.
        _text, area = _qr_signal(station, name, held_pos)
        best_signal.append((area, name, held_pos))

    # Pass 2: last resort, at most once per item. Rotate at the single camera
    # that saw the largest QR quad (fallback: the first presentation camera).
    if result is None and present_names:
        if best_signal:
            _area, name, held_pos = max(best_signal, key=lambda t: t[0])
        else:
            name = present_names[0]
            held_pos = None
        target = present_point_for_camera(station, name)
        if target is not None and _reachable(station, target):
            station.move_ee_to_smooth(target, dt)
            for _ in range(hold_frames):
                station.publish(dt)
            if held_pos is None:
                held_pos = np.asarray(station._body_pose(body).translation(), dtype=float)
            logger.info("Active scan: rotation search for %s at %s", item_label, name)
            result = _rotate_and_read(station, name, held_pos, dt, hold_frames)
        else:
            logger.info("Active scan: rotation camera %s unreachable; no search", name)

    if result is not None and keep_held:
        # Leave the item grasped so the caller can place it directly: no
        # teleport, no redundant re-grasp. The arm holds it at the camera.
        return result

    # Otherwise set the item back down near where it came from and release. We
    # move it there with the arm (so it glides, never teleports), then open the
    # gripper. If the grasp had failed, the item never moved, so just release.
    if station.holding:
        _lower_and_release(station, np.asarray(X_orig.translation(), dtype=float), dt)
    else:
        station.set_gripper(0.0)
        station.publish(dt)
    return result


def _lower_and_release(station, home, dt: float, steps: int = 16) -> None:
    """Glide the held item back to ``home`` and gently set it down (no teleport)."""
    above = np.asarray(home, dtype=float) + np.array([0.0, 0.0, 0.05])
    for _ in range(steps):
        ee = station.ee_position()
        step = ee + 0.3 * (above - ee)
        station.move_ee_to(step)
        station.publish(dt)
    station.drop_held_onto(np.asarray(home, dtype=float), dt, yaw=None)
    for _ in range(4):
        station.set_gripper(0.0)
        station.publish(dt)


def _reachable(station, p_world, tol: float = 0.05, item_up_in_hand=None,
               item_yaw: float | None = None, item_x_in_hand=None) -> bool:
    """Does IK place the grasp point within `tol` of `p_world`?

    Uses the IK solver directly (not a rate-limited move) and checks forward
    kinematics on a scratch context, so it does not disturb the live arm.
    With `item_up_in_hand` (and optionally `item_yaw` / `item_x_in_hand`) the
    check uses the upright-hold IK, as `Station.move_held_upright_to` does.
    """
    p_world = np.asarray(p_world, dtype=float)
    q, ok = station._ik.solve(p_world, station.joint_positions(), station._grasp_offset,
                              item_up_in_hand=item_up_in_hand, item_yaw=item_yaw,
                              item_x_in_hand=item_x_in_hand)
    if not ok:
        return False
    # Evaluate the grasp point at q on the IK's own plant/context.
    ik = station._ik
    ik.plant.SetPositions(ik.context, ik.arm, q)
    X = ik.plant.CalcRelativeTransform(
        ik.context, ik.plant.world_frame(), ik.plant.GetFrameByName("gripper_frame_link")
    )
    reached = np.asarray(X.multiply(station._grasp_offset), dtype=float)
    return bool(np.linalg.norm(reached - p_world) < tol)
