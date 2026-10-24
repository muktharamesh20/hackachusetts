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


PRESENT_DISTANCES = (0.14, 0.18, 0.12, 0.16)  # tried in order; first reachable wins


def present_and_read(station, item_label: str, dt: float = 0.05, hold_frames: int = SETTLE_FRAMES,
                     on_capture=None, cameras=None):
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
        station.plant.SetFreeBodyPose(station.plant_context, body, X_orig)
        return None

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
        if hit is not None:
            logger.info("Active scan read %s by presenting to %s", item_label, name)
            result = hit
            break

    # Return the item to its slot and release.
    station.detach()
    station.plant.SetFreeBodyPose(station.plant_context, body, X_orig)
    station.set_gripper(0.0)
    station.publish(dt)
    return result


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
