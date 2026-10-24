# WIP (camera-vision task 13): YOLOX report helper, not finished or verified.
# Not imported by the sim; safe to ignore. docs/yolo_report.md is not written yet.
"""Evaluate the pretrained YOLOX shadow detector on rendered sim frames.

Produces the measurements behind ``docs/yolo_report.md``. Nothing here trains or
fine-tunes anything; it only runs the pretrained COCO weights and records what
they find. The QR pipeline stays authoritative.

Subcommands (run in WSL with the pantrysort venv, from the repo root):

``frames``  Build a station (Meshcat off) for a scene, render full frames from
            every rig camera (``robot_cam`` pinhole + fisheye, ``iphone_left``,
            ``iphone_right``) with the scene at rest, plus one held-in-gripper
            presentation view, and run each model at each score threshold on
            every frame. Writes ``frames.json``, the raw frames and annotated
            copies to ``--out``.

``summary`` Print markdown tables from SortLoop shadow outputs
            (``outputs/yolo/<timestamp>/observations.jsonl``).

``frames-summary`` Print a markdown table + latency stats from ``frames.json``.

``annotate`` Copy selected annotated frames into ``docs/images/yolo/``
            (downscaled PNGs, each kept under ~500 KB).

Examples:
    ~/.venvs/pantrysort/bin/python scripts/yolo_eval.py frames --scene flat_grid
    ~/.venvs/pantrysort/bin/python scripts/yolo_eval.py frames --scene belt_boxes
    ~/.venvs/pantrysort/bin/python scripts/yolo_eval.py summary outputs/yolo/<ts>
    ~/.venvs/pantrysort/bin/python scripts/yolo_eval.py annotate SRC.png DST.png
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import time
from pathlib import Path

import numpy as np

from pantrysort.perception.yolo import (
    YOLOX_WEIGHTS,
    YoloDetection,
    YoloxDetector,
    ensure_weights,
    expected_coco_class,
)

logger = logging.getLogger("yolo_eval")

CACHE = "~/.cache/pantrysort/yolox"
MAX_PNG_BYTES = 500_000


# --------------------------------------------------------------------------- helpers

def load_detector(model: str, score_thr: float) -> YoloxDetector:
    path = ensure_weights(model, CACHE)
    if path is None:
        raise SystemExit(f"No verified {model} weights in {CACHE}.")
    return YoloxDetector(path, YOLOX_WEIGHTS[model].input_size, score_thr, 0.45, name=model)


def timed_detect(det: YoloxDetector, image: np.ndarray,
                 repeats: int) -> tuple[list[YoloDetection], float]:
    """Detections plus median latency (ms) over ``repeats`` runs (first is warm-up)."""
    det.detect(image)
    lat = []
    dets: list[YoloDetection] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        dets = det.detect(image)
        lat.append((time.perf_counter() - t0) * 1000.0)
    return dets, statistics.median(lat)


def annotate(image: np.ndarray, dets: list[YoloDetection], title: str) -> np.ndarray:
    """BGR copy of an RGB(A) frame with boxes + ``class score`` labels drawn."""
    import cv2

    img = np.ascontiguousarray(np.asarray(image)[..., [2, 1, 0]]).astype(np.uint8)
    for d in dets:
        x1, y1, x2, y2 = (int(round(v)) for v in d.box_xyxy)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        text = f"{d.cls_name} {d.score:.2f}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        y_text = max(y1, th + 4)
        cv2.rectangle(img, (x1, y_text - th - 4), (x1 + tw + 4, y_text), (0, 0, 255), -1)
        cv2.putText(img, text, (x1 + 2, y_text - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(img, title, (8, img.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (0, 255, 0), 2, cv2.LINE_AA)
    return img


def save_png_small(path: Path, bgr: np.ndarray, max_bytes: int = MAX_PNG_BYTES) -> int:
    """Write a PNG, downscaling until it is under ``max_bytes``. Returns size."""
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    img = bgr
    while True:
        ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        if not ok:
            raise RuntimeError(f"PNG encode failed for {path}")
        if len(buf) <= max_bytes or img.shape[1] < 200:
            path.write_bytes(buf.tobytes())
            return len(buf)
        img = cv2.resize(img, (int(img.shape[1] * 0.8), int(img.shape[0] * 0.8)),
                         interpolation=cv2.INTER_AREA)


def item_pixels(station, cam: str) -> dict[str, tuple[float, float]]:
    """Pinhole pixel of every item center that projects inside ``cam``'s frame
    (in front of the lens, not checked for occlusion)."""
    model = station.camera_model(cam)
    px: dict[str, tuple[float, float]] = {}
    for it in station.scene.items:
        u, v, z = model.world_to_pixel(station.scene_item_position(it.label))
        if z > 0 and 0 <= u < model.width and 0 <= v < model.height:
            px[it.label] = (u, v)
    return px


def match_box(det: YoloDetection, px: dict[str, tuple[float, float]]) -> str | None:
    """Item whose projected center lies inside the box (nearest to box center)."""
    x1, y1, x2, y2 = det.box_xyxy
    inside = [(np.hypot(u - det.center_px[0], v - det.center_px[1]), name)
              for name, (u, v) in px.items() if x1 <= u <= x2 and y1 <= v <= y2]
    return min(inside)[1] if inside else None


# --------------------------------------------------------------------------- frames

Frame = tuple[str, str, np.ndarray, "dict[str, tuple[float, float]] | None"]


def render_frames(station, held_label: str | None) -> list[Frame]:
    """[(frame_id, camera, rgba, item_pixels)] at rest for every camera, plus one
    held-in-gripper presentation view. ``item_pixels`` is None for fisheye
    frames (the pinhole projection does not apply to the distorted image)."""
    frames: list[Frame] = []
    for cam in station.camera_names():
        rgb = station.camera_rgb(cam)
        if rgb is not None:
            fid = f"{cam}_pinhole" if cam == "robot_cam" else cam
            frames.append((fid, cam, rgb, item_pixels(station, cam)))
        if cam == "robot_cam":
            fish = station.camera_fisheye(cam)
            if fish is not None:
                frames.append(("robot_cam_fisheye", cam, fish, None))
    if held_label is not None:
        from pantrysort.sim.active_scan import present_and_read

        grabbed: list[Frame] = []

        def on_capture(cam: str, _lbl: str) -> None:
            if not grabbed:
                rgb = station.camera_rgb(cam)
                if rgb is not None:
                    grabbed.append((f"held_{cam}", cam, rgb, item_pixels(station, cam)))

        present_and_read(station, held_label, hold_frames=6, on_capture=on_capture)
        frames.extend(grabbed)
    return frames


def cmd_frames(args: argparse.Namespace) -> None:
    import cv2

    from pantrysort.config import SimConfig
    from pantrysort.sim.pantry_scene import scene_for_mode
    from pantrysort.sim.station import build_station

    out = Path(args.out) / args.scene
    out.mkdir(parents=True, exist_ok=True)
    scene = scene_for_mode(args.scene)
    station = build_station(scene, SimConfig(meshcat=False, realtime_rate=0.0,
                                             scene_mode=args.scene))
    if not station.cameras:
        raise SystemExit("No cameras (VTK renderer unavailable).")
    if scene.boxes:
        station.convey_box_to_station(0)
        candidates = list(scene.box_items(0))
    else:
        candidates = list(scene.items)
    sku = {it.label: it.barcode for it in scene.items}
    held = args.held or (candidates[0].label if candidates else None)

    # Item pixels are captured with each frame, so matching reflects the scene
    # exactly as rendered (the held view moves the arm and item afterwards).
    frames = render_frames(station, held)
    detectors = {(m, t): load_detector(m, t) for m in args.models for t in args.thr}
    records = []
    for fid, cam, img, px in frames:
        cv2.imwrite(str(out / f"{fid}.png"), cv2.cvtColor(img, cv2.COLOR_RGBA2BGR))
        for (model, thr), det in detectors.items():
            dets, lat = timed_detect(det, img, args.repeats)
            rows = []
            for d in dets:
                m = match_box(d, px) if px is not None else None
                exp = expected_coco_class(sku.get(m), m) if m else None
                rows.append({"cls": d.cls_name, "score": round(d.score, 3),
                             "box": [round(v, 1) for v in d.box_xyxy],
                             "item": m, "expected": exp,
                             "correct": None if exp is None else d.cls_name == exp})
            records.append({"scene": args.scene, "frame": fid, "camera": cam,
                            "model": model, "score_thr": thr, "latency_ms": round(lat, 1),
                            "shape": list(img.shape), "detections": rows,
                            "items_in_view": sorted(px) if px is not None else None,
                            "held_item": held if fid.startswith("held_") else None})
            cv2.imwrite(str(out / f"{fid}__{model}_{thr:g}.png"),
                        annotate(img, dets, f"{args.scene} {fid} {model} thr={thr:g}"))
            logger.info("%s %s %s@%g: %d dets, %.0f ms: %s", args.scene, fid, model, thr,
                        len(dets), lat,
                        ", ".join(f"{r['cls']} {r['score']:.2f}->{r['item']}" for r in rows))
    (out / "frames.json").write_text(json.dumps(records, indent=1), encoding="utf-8")
    logger.info("Wrote %s", out / "frames.json")


# --------------------------------------------------------------------------- summary

def cmd_summary(args: argparse.Namespace) -> None:
    for run in args.runs:
        run = Path(run)
        obs = [json.loads(line) for line in
               (run / "observations.jsonl").read_text(encoding="utf-8").splitlines() if line]
        summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
        print(f"\n### {run}\n")
        print("| QR label | SKU | Camera | Source | Expected | Detected | Top class (score) "
              "| Correct |")
        print("|---|---|---|---|---|---|---|---|")
        for o in obs:
            top = f"{o['top_class']} ({o['top_score']:.2f})" if o["top_class"] else "-"
            corr = "n/a" if o["unmappable"] else ("yes" if o["correct"] else "no")
            print(f"| {o['label']} | {o['sku'] or '-'} | {o['camera']} | {o['source']} "
                  f"| {o['expected'] or '-'} | {'yes' if o['detected'] else 'no'} | {top} "
                  f"| {corr} |")
        print("\n" + json.dumps(summary, indent=1))


def cmd_frames_summary(args: argparse.Namespace) -> None:
    records = []
    for p in args.files:
        records += json.loads(Path(p).read_text(encoding="utf-8"))
    print("| Scene | Frame | Model | Thr | ms | #dets | Detections (class score -> item) |")
    print("|---|---|---|---|---|---|---|")
    for r in records:
        dets = "; ".join(
            f"{d['cls']} {d['score']:.2f}" + (f" -> {d['item']}" if d["item"] else "")
            for d in r["detections"]) or "-"
        print(f"| {r['scene']} | {r['frame']} | {r['model']} | {r['score_thr']:g} "
              f"| {r['latency_ms']:.0f} | {len(r['detections'])} | {dets} |")
    print("\nMedian latency per model (all frames, all thresholds):")
    for model in sorted({r["model"] for r in records}):
        lat = [r["latency_ms"] for r in records if r["model"] == model]
        print(f"  {model}: median {statistics.median(lat):.0f} ms, "
              f"min {min(lat):.0f}, max {max(lat):.0f} (n={len(lat)})")


def cmd_annotate(args: argparse.Namespace) -> None:
    import cv2

    img = cv2.imread(args.src, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"Cannot read {args.src}")
    size = save_png_small(Path(args.dst), img)
    print(f"{args.dst}: {size / 1000:.0f} KB")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("frames", help="Run detectors on rendered frames of a scene.")
    f.add_argument("--scene", default="flat_grid")
    f.add_argument("--models", nargs="+", default=["yolox_s", "yolox_nano"])
    f.add_argument("--thr", nargs="+", type=float, default=[0.25, 0.1])
    f.add_argument("--repeats", type=int, default=10, help="Timed runs per frame/model.")
    f.add_argument("--held", default=None, help="Item to present (default: first).")
    f.add_argument("--out", default="outputs/yolo_eval")
    s = sub.add_parser("summary", help="Markdown tables from SortLoop shadow outputs.")
    s.add_argument("runs", nargs="+")
    fs = sub.add_parser("frames-summary", help="Markdown table from frames.json files.")
    fs.add_argument("files", nargs="+")
    a = sub.add_parser("annotate", help="Copy a PNG into docs, downscaled under 500 KB.")
    a.add_argument("src")
    a.add_argument("dst")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    {"frames": cmd_frames, "summary": cmd_summary, "frames-summary": cmd_frames_summary,
     "annotate": cmd_annotate}[args.cmd](args)


if __name__ == "__main__":
    main()
