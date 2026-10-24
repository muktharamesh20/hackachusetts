"""Active QR scanning: the arm picks an item up and presents it to a camera.

Passive multi-camera decode (perception.identify) handles items whose side
stickers happen to face a decodable camera. For the rest, the robot grasps the
item and holds it close in front of a camera, where even a small sticker renders
large and head-on and decodes reliably. This mirrors how a real arm-mounted
sorter confirms an unreadable label: bring it to the lens.

Kinematic station assumptions (see sim/station.py): ``move_ee_to`` IKs the grasp
point to a world position, items are rigidly held after ``attach_nearest`` and
follow the gripper, and ``publish`` advances/animates. pydrake imports stay
inside functions.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("pantrysort.sim.active_scan")

PRESENT_DISTANCE = 0.12   # hold the item this far in front of the camera lens (m)
SETTLE_FRAMES = 4


LIFT_CLEARANCE = 0.08   # how far to raise a grasped item straight up (m)


def _lift_straight_up(station, dt: float, clearance: float = LIFT_CLEARANCE, steps: int = 10):
    """Raise the held item straight up (x,y fixed) so it clears neighbours before
    any sideways swing. Does nothing if not holding."""
    if not station.holding:
        return
    start = station.ee_position().copy()
    for k in range(1, steps + 1):
        s = k / steps
        station.move_ee_to(np.array([start[0], start[1], start[2] + s * clearance]))
        station.publish(dt)

def present_point_for_camera(station, camera_name: str, distance: float = PRESENT_DISTANCE):
    """World point ``distance`` m in front of ``camera_name`` along its optical axis."""
    cm = station.camera_model(camera_name)
    if cm is None:
        return None
    cam_pos = cm.X_WC[:3, 3]
    cam_fwd = cm.X_WC[:3, 2]  # +z points into the scene
    return np.asarray(cam_pos + cam_fwd * distance, dtype=float)


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
    is located but not readable still yields a positive area, which lets the
    reorientation search climb toward a fronto-parallel view.
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


def _reorient_and_read(station, camera_name, expected_world, dt, hold_frames):
    """Rotate the held item in front of `camera_name` to find a decodable view.

    This handles items like the apple whose curved sticker only reads from some
    angles. It sweeps `wrist_roll` (and a little `wrist_flex` tilt), and is
    observation-guided: at each step it measures the QR quad area, climbs toward
    larger (more fronto-parallel) views, and stops as soon as a decode succeeds.
    Returns `(text, frame, camera)` or None. Restores the wrist if it fails.
    """
    q_start = station.joint_positions().copy()
    lo, hi = station.wrist_roll_room()  # (down, up) room from current, rad
    rolls = _search_offsets(lo, hi)
    tilts = (0.0, 0.18, -0.18)

    best_area = -1.0
    for tilt in tilts:
        for droll in rolls:
            q = station.joint_positions().copy()
            q[_ROLL_IDX] = q_start[_ROLL_IDX] + droll
            q[_FLEX_IDX] = q_start[_FLEX_IDX] + tilt
            station.plant.SetPositions(station.plant_context, station.arm, q)
            station._update_held()
            for _ in range(max(2, hold_frames // 2)):
                station.publish(dt)
            text, area = _qr_signal(station, camera_name, expected_world)
            if text is not None:
                frame = station.camera_rgb(camera_name)
                logger.info("Reorient read %s (roll%+.2f tilt%+.2f)", camera_name, droll, tilt)
                return text, frame, camera_name
            best_area = max(best_area, area)
    # Nothing decoded; leave the wrist where the biggest QR quad was seen is not
    # tracked here, so just restore the starting pose for a clean handoff.
    station.plant.SetPositions(station.plant_context, station.arm, q_start)
    station._update_held()
    station.publish(dt)
    return None


def _search_offsets(down: float, up: float, step: float = 0.35):
    """wrist_roll offsets to try, ordered small-first and alternating sign, kept
    inside the joint's remaining room."""
    offs = [0.0]
    k = 1
    while True:
        a = k * step
        added = False
        if a <= up - 0.05:
            offs.append(a)
            added = True
        if a <= down - 0.05:
            offs.append(-a)
            added = True
        if not added:
            break
        k += 1
    return offs


PRESENT_DISTANCES = (0.14, 0.18, 0.12, 0.16)  # tried in order; first reachable wins


def present_and_read(station, item_label: str, dt: float = 0.05, hold_frames: int = SETTLE_FRAMES,
                     on_capture=None, cameras=None, keep_held: bool = False):
    """Grasp `item_label`, present it to each camera, and decode its QR.

    Motion uses the velocity/acceleration-limited `move_ee_to_smooth` so the
    arm glides rather than snaps. `hold_frames` keeps the item still in front
    of the camera (raise it in testing so the rendered frame is crisp).
    `on_capture(camera_name, item_label)` is called while the item is held and
    settled, for a caller that wants to save frames. `cameras` restricts which
    rig cameras to present to (default: all).

    Returns `(text, image, camera)` on success or `None`. The item is set
    back to its original pose and released before returning, so the normal
    pick-and-place can grasp it afterwards.
    """
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

    # Lift the item straight up before any sideways motion, so it clears its
    # neighbours instead of dragging through them.
    _lift_straight_up(station, dt)

    names = cameras if cameras is not None else station.camera_names()
    result = None
    for name in names:
        target = None
        for dist in PRESENT_DISTANCES:
            cand = present_point_for_camera(station, name, dist)
            if cand is not None and _reachable(station, cand):
                target = cand
                break
        if target is None:
            continue
        station.move_ee_to_smooth(target, dt)
        for _ in range(hold_frames):
            station.publish(dt)
        if on_capture is not None:
            on_capture(name, item_label)
        held_pos = np.asarray(station._body_pose(body).translation(), dtype=float)
        hit = _read_presented(station, name, expected_world=held_pos)
        if hit is None:
            # One pose did not read (e.g. the apple's curved sticker); rotate/tilt
            # the item in front of this camera to find a readable view.
            hit = _reorient_and_read(station, name, held_pos, dt, hold_frames)
        if hit is not None:
            logger.info("Active scan read %s by presenting to %s", item_label, name)
            result = hit
            break

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


def _reachable(station, p_world, tol: float = 0.05) -> bool:
    """Does IK place the grasp point within `tol` of `p_world`?

    Uses the IK solver directly (not a rate-limited move) and checks forward
    kinematics on a scratch context, so it does not disturb the live arm.
    """
    p_world = np.asarray(p_world, dtype=float)
    q, ok = station._ik.solve(p_world, station.joint_positions(), station._grasp_offset)
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
