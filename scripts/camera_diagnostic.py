"""Camera diagnostic: present each item to the cameras and save what they see.

Testing tool (run with Drake, e.g. in WSL). For each scene item it:

  1. has the arm present the item to the external (ground iPhone) cameras and
     decode its QR (the reliable path), saving each view;
  2. then, as an experiment, has the arm present the item to its own BASE
     fisheye camera and sweep ``wrist_roll`` to aim the sticker at that lens,
     saving BOTH the undistorted (pinhole) and distorted (fisheye) frames at
     each angle; the external read is used as the ground-truth label.

A multiview panel (base + external side by side) is saved per item. Everything
goes under ``outputs/camera_diagnostics/<timestamp>/<item>/`` (gitignored), so
images from one item stay together and each run is separate.

Usage (from WSL):
    ~/.venvs/pantrysort/bin/python scripts/camera_diagnostic.py [--items N] [--hold 10]
"""

from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime
from pathlib import Path

import numpy as np

from pantrysort.config import SimConfig
from pantrysort.sim.station import build_station

logger = logging.getLogger("camera_diagnostic")

OUT_ROOT = Path("outputs/camera_diagnostics")
WRIST_SWEEP = np.linspace(-1.2, 1.2, 7)  # wrist_roll angles to try at the base cam


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()


def _save_rgba(path: Path, rgba: np.ndarray) -> None:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))


def _panel(images: list[tuple[str, np.ndarray]]) -> np.ndarray:
    """Stack labeled frames side by side into one multiview image."""
    import cv2

    tiles = []
    h = min(img.shape[0] for _, img in images)
    for label, img in images:
        rgb = img[:, :, :3]
        scale = h / img.shape[0]
        rgb = cv2.resize(rgb, (int(img.shape[1] * scale), h))
        cv2.putText(rgb, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 0), 2, cv2.LINE_AA)
        tiles.append(rgb)
    return np.hstack(tiles)


def _decode_count(frame: np.ndarray) -> int:
    from pantrysort.perception.qr import decode_qr_codes

    return len(decode_qr_codes(frame))


def diagnose_item(station, item_label: str, out_dir: Path, hold: int) -> None:

    item_dir = out_dir / _safe(item_label)
    item_dir.mkdir(parents=True, exist_ok=True)
    external = [n for n in station.camera_names() if n != "robot_cam"]
    base = "robot_cam" if "robot_cam" in station.camera_names() else None

    # --- 1) External present-and-read, saving each external view -------------
    captured: list[tuple[str, np.ndarray]] = []

    def on_capture(cam_name: str, _lbl: str) -> None:
        frame = station.camera_rgb(cam_name)
        if frame is not None:
            _save_rgba(item_dir / f"external_{cam_name}.png", frame)
            captured.append((cam_name, frame))

    from pantrysort.sim.active_scan import present_and_read

    read = present_and_read(station, item_label, hold_frames=hold,
                            on_capture=on_capture, cameras=external)
    label_text = read[0] if read else "UNREADABLE"
    logger.info("%s: external read -> %s", item_label, label_text)

    # --- 2) Base fisheye-cam attempt, sweeping wrist_roll --------------------
    base_views: list[tuple[str, np.ndarray]] = []
    if base is not None:
        _sweep_base_camera(station, item_label, base, item_dir, hold, base_views)

    # --- 3) Multiview panel --------------------------------------------------
    panel_sources = captured[:1] + base_views[:1]
    if panel_sources:
        import cv2

        panel = _panel([(n, f) for n, f in panel_sources])
        cv2.imwrite(str(item_dir / "multiview.png"), cv2.cvtColor(panel, cv2.COLOR_RGB2BGR))
    (item_dir / "label.txt").write_text(label_text + "\n")


def _sweep_base_camera(station, item_label, base, item_dir, hold, base_views) -> None:
    """Grasp the item, hold it before the base camera, sweep wrist_roll to aim
    the sticker at the fisheye lens, saving undistorted + distorted each angle."""
    from pantrysort.sim.active_scan import present_point_for_camera

    body = station.item_bodies.get(item_label)
    if body is None:
        return
    X_orig = station._body_pose(body)
    shape = station.item_shapes.get(item_label)
    if shape is not None:
        station.prepare_grasp(shape.grip_width)
    p_item = np.asarray(station._body_pose(body).translation(), dtype=float)
    station.move_ee_to_smooth(p_item, 0.05)
    for _ in range(hold):
        station.publish(0.05)
    station.set_gripper(1.0)
    if station.attach_nearest() is None:
        return

    target = None
    for dist in (0.12, 0.14, 0.10, 0.16):
        cand = present_point_for_camera(station, base, dist)
        if cand is not None:
            target = cand
            break
    if target is not None:
        station.move_ee_to_smooth(target, 0.05)
        for _ in range(hold):
            station.publish(0.05)

    best_angle, best_detect = None, -1
    for ang in WRIST_SWEEP:
        q = station.joint_positions().copy()
        q[4] = ang  # wrist_roll (0:pan 1:lift 2:elbow 3:wrist_flex 4:wrist_roll 5:gripper)
        station.plant.SetPositions(station.plant_context, station.arm, q)
        station._update_held()
        for _ in range(max(2, hold // 2)):
            station.publish(0.05)
        undist = station.camera_rgb(base)
        dist_img = station.camera_fisheye(base)
        tag = f"{ang:+.2f}".replace(".", "p").replace("+", "pos").replace("-", "neg")
        if undist is not None:
            _save_rgba(item_dir / f"base_undistorted_roll_{tag}.png", undist)
        if dist_img is not None:
            _save_rgba(item_dir / f"base_distorted_roll_{tag}.png", dist_img)
        n = _decode_count(undist) if undist is not None else 0
        if n > best_detect:
            best_detect, best_angle = n, ang
            if undist is not None:
                base_views.clear()
                base_views.append((f"base undist roll={ang:+.2f}", undist))

    logger.info("%s: base-cam best wrist_roll=%s (decoded %d)", item_label,
                None if best_angle is None else round(float(best_angle), 2), best_detect)

    station.detach()
    station.plant.SetFreeBodyPose(station.plant_context, body, X_orig)
    station.set_gripper(0.0)
    station.publish(0.05)


def main() -> None:
    ap = argparse.ArgumentParser(description="Camera diagnostic (multiview + base-cam sweep).")
    ap.add_argument("--items", type=int, default=0, help="Limit to the first N items (0 = all).")
    ap.add_argument("--hold", type=int, default=10, help="Frames to hold still per capture.")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT_ROOT / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Saving diagnostics under %s", out_dir.resolve())

    station = build_station(
        config=SimConfig(meshcat=False, qr_scanner=False, overhead_camera=True)
    )
    if not station.cameras:
        logger.error("No cameras (VTK renderer unavailable); cannot run diagnostic.")
        return

    items = station.scene.items
    if args.items > 0:
        items = items[: args.items]
    for item in items:
        diagnose_item(station, item.label, out_dir, args.hold)

    logger.info("Done. Images in %s", out_dir.resolve())


if __name__ == "__main__":
    main()
