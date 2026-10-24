"""YOLOX shadow detection: pure pre/post-processing, mapping, tracker math, and
the guarantee that YOLO never changes QR identification or routing.

Only the detector smoke test needs onnxruntime + the cached weights.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import numpy as np
import pytest

from pantrysort.perception.yolo import (
    COCO_CLASSES,
    SKU_TO_COCO,
    YOLOX_WEIGHTS,
    YoloDetection,
    YoloShadowTracker,
    decode_outputs,
    ensure_weights,
    expected_coco_class,
    letterbox,
    make_detector,
    multiclass_nms,
    nms,
    postprocess,
    to_bgr,
    unletterbox_boxes,
)

TODAY = date(2026, 1, 15)


# --------------------------------------------------------------------------- pre/post

def test_coco_has_80_classes():
    assert len(COCO_CLASSES) == 80
    assert COCO_CLASSES[47] == "apple" and COCO_CLASSES[39] == "bottle"


def _anchor_index(size: int, stride: int, gx: int, gy: int) -> int:
    off = 0
    for s in (8, 16, 32):
        if s == stride:
            return off + gy * (size // s) + gx
        off += (size // s) ** 2
    raise ValueError(stride)


def test_decode_grid_offsets_and_strides():
    size = 64  # anchors: 8x8 + 4x4 + 2x2 = 84
    raw = np.zeros((84, 85), dtype=np.float32)
    i = _anchor_index(size, 16, gx=2, gy=1)
    raw[i, :4] = [0.5, 0.25, np.log(2.0), 0.0]
    out = decode_outputs(raw, size)
    cx, cy, w, h = out[i, :4]
    assert cx == pytest.approx((2 + 0.5) * 16)
    assert cy == pytest.approx((1 + 0.25) * 16)
    assert w == pytest.approx(2.0 * 16)
    assert h == pytest.approx(1.0 * 16)


def test_decode_rejects_wrong_anchor_count():
    with pytest.raises(ValueError):
        decode_outputs(np.zeros((10, 85)), 64)


def test_nms_suppresses_overlap_and_keeps_disjoint():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=float)
    keep = nms(boxes, np.array([0.9, 0.8, 0.7]), 0.45)
    assert keep == [0, 2]


def test_multiclass_nms_is_class_aware():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11]], dtype=float)
    scores = np.zeros((2, 80))
    scores[0, 47] = 0.9   # apple
    scores[1, 39] = 0.8   # bottle, same place: different class, kept
    out = multiclass_nms(boxes, scores, nms_thr=0.45, score_thr=0.25)
    assert [(i, c) for i, _, c in out] == [(0, 47), (1, 39)]


def test_postprocess_end_to_end_on_synthetic_output():
    size = 64
    raw = np.zeros((1, 84, 85), dtype=np.float32)
    raw[0, :, 4] = 0.0  # objectness 0 everywhere ...
    i = _anchor_index(size, 8, gx=3, gy=4)
    raw[0, i, :4] = [0.5, 0.5, np.log(1.5), np.log(1.0)]  # 12 x 8 box at (28, 36)
    raw[0, i, 4] = 0.9
    raw[0, i, 5 + 47] = 0.8
    ratio = 0.5  # original image was 2x the input
    dets = postprocess(raw, size, ratio, score_thr=0.25)
    assert len(dets) == 1
    d = dets[0]
    assert d.cls_name == "apple" and d.score == pytest.approx(0.72)
    assert d.box_xyxy == pytest.approx((44.0, 64.0, 68.0, 80.0))
    assert d.center_px == pytest.approx((56.0, 72.0))


def test_letterbox_pads_and_unmaps_boxes():
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    img[:, :] = (10, 20, 30)
    blob, r = letterbox(img, 64)
    assert blob.shape == (3, 64, 64) and blob.dtype == np.float32
    assert r == pytest.approx(0.32)
    assert blob[:, 0, 0].tolist() == [10, 20, 30]          # image, top-left aligned
    assert blob[:, 63, 0].tolist() == [114, 114, 114]      # padding below
    # A box covering the whole resized image maps back to the full original.
    back = unletterbox_boxes(np.array([[0, 0, 64, 32]]), r)
    assert back[0] == pytest.approx([0, 0, 200, 100])


def test_to_bgr_from_rgba():
    rgba = np.zeros((2, 2, 4), dtype=np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3] = 1, 2, 3, 255
    assert to_bgr(rgba)[0, 0].tolist() == [3, 2, 1]


# --------------------------------------------------------------------------- mapping

def test_mapping_table():
    assert expected_coco_class("APPLE", "Apple [1]") == "apple"
    assert expected_coco_class("OLIVE-OIL", "Olive oil (bottle)") == "bottle"
    for sku in ("BEANS-BLK-CAN", "MILK-CARTON", "CEREAL-BOX", "TOILET-PAPER"):
        assert expected_coco_class(sku) is None
    assert expected_coco_class(None, "Banana") == "banana"   # name fallback
    assert expected_coco_class(None, "Mystery box") is None
    assert all(v is None or v in COCO_CLASSES for v in SKU_TO_COCO.values())


def test_mapping_covers_catalog():
    from pantrysort.perception.catalog import FoodCatalog

    cat = FoodCatalog.load()
    missing = [e.sku for e in cat if e.sku not in SKU_TO_COCO]
    assert not missing


# --------------------------------------------------------------------------- tracker

@dataclass
class FakeDetector:
    """Returns fixed detections; ``center_px[0]`` encodes the item index for locate."""

    dets: list[YoloDetection]
    name: str = "fake"
    last_latency_ms: float = 5.0

    def detect(self, image):
        return list(self.dets)


def _det(cls_name, score, item_idx):
    return YoloDetection(cls_name, score, (0, 0, 1, 1), (float(item_idx), 0.0))


POSITIONS = {"Apple": np.array([0.2, 0.0, 0.03]),
             "Milk (carton)": np.array([0.3, 0.1, 0.05]),
             "Olive oil (bottle)": np.array([0.3, -0.1, 0.06])}
_LABELS = list(POSITIONS)


def _locate(u, v):
    i = int(u)
    return POSITIONS[_LABELS[i]] + 0.01 if 0 <= i < len(_LABELS) else None


def test_tracker_accuracy_math(tmp_path):
    det = FakeDetector([_det("apple", 0.9, 0), _det("orange", 0.4, 0),
                        _det("bottle", 0.3, 1), _det("cup", 0.7, 2)])
    tr = YoloShadowTracker(det)
    frame = np.zeros((4, 4, 4), dtype=np.uint8)
    a = tr.observe("Apple", "APPLE", "iphone_left", frame, _locate, POSITIONS)
    m = tr.observe("Milk (carton)", "MILK-CARTON", "robot_cam", frame, _locate, POSITIONS)
    o = tr.observe("Olive oil (bottle)", "OLIVE-OIL", "iphone_right", frame, _locate,
                   POSITIONS, source="camera-active")
    assert (a.detected, a.top_class, a.correct) == (True, "apple", True)
    assert (m.detected, m.unmappable, m.correct) == (True, True, None)
    assert (o.detected, o.top_class, o.correct) == (True, "cup", False)
    assert a.num_detections == 4 and a.latency_ms == 5.0

    s = tr.summary()
    assert s["observations"] == 3 and s["detected"] == 3
    assert s["mappable"] == 2 and s["correct"] == 1 and s["unmappable"] == 1
    assert s["accuracy_mappable"] == pytest.approx(0.5)
    assert "1/2 mappable" in tr.summary_line()

    out = tr.write(tmp_path / "run")
    lines = (out / "observations.jsonl").read_text().splitlines()
    assert len(lines) == 3 and json.loads(lines[1])["unmappable"] is True
    assert json.loads((out / "summary.json").read_text())["correct"] == 1


def test_tracker_ignores_detections_on_other_items_or_unlocatable():
    det = FakeDetector([_det("apple", 0.9, 1), _det("apple", 0.9, 99)])
    tr = YoloShadowTracker(det)
    obs = tr.observe("Apple", "APPLE", "cam", np.zeros((2, 2, 4), np.uint8), _locate, POSITIONS)
    assert not obs.detected and obs.correct is False and obs.top_class is None
    assert tr.summary()["detection_rate"] == 0.0


def test_make_detector_respects_disable_flag():
    cfg = SimpleNamespace(yolo=SimpleNamespace(enabled=False))
    assert make_detector(cfg) is None


def test_ensure_weights_rejects_bad_hash(tmp_path):
    (tmp_path / "yolox_nano.onnx").write_bytes(b"not a model")
    assert ensure_weights("yolox_nano", tmp_path) is None
    assert ensure_weights("yolox_missing", tmp_path) is None
    assert ensure_weights("yolox_s", tmp_path / "empty") is None


# --------------------------------------------------------------------------- QR is authoritative

class _FakeStation:
    """Minimal camera station: every item is read passively by 'cam_a'."""

    def __init__(self, scene):
        self.scene = scene
        self.cameras = {"cam_a": object()}
        self.scan_display = None
        self._labels = [it.label for it in scene.items]

    def start_recording(self):
        pass

    def finish_recording(self):
        pass

    def identify_items(self):
        return {it.label: SimpleNamespace(text=it.qr.encode(), cameras=("cam_a",),
                                          votes=1, total_reads=1)
                for it in self.scene.items}

    def camera_rgb(self, name):
        return np.zeros((8, 8, 4), dtype=np.uint8)

    def scene_item_position(self, label):
        return np.asarray(self.scene.items[self._labels.index(label)].position, dtype=float)

    def locate_pixel(self, u, v, name=None):
        i = int(u)
        return self.scene_item_position(self._labels[i]) if 0 <= i < len(self._labels) else None


class _AlwaysWrong:
    """Confident wrong class on every item, plus a detector that sometimes raises."""

    name = "always-wrong"
    last_latency_ms = 1.0

    def __init__(self, n_items):
        self.n = n_items
        self.calls = 0

    def detect(self, image):
        self.calls += 1
        if self.calls == 3:
            raise RuntimeError("boom")  # shadow failures must be swallowed
        return [_det("toilet", 0.99, i) for i in range(self.n)]


def _run(detector, tmp_path, monkeypatch):
    from pantrysort.inventory.factory import make_store
    from pantrysort.pipeline.sort_loop import SortLoop
    from pantrysort.sim.pantry_scene import intake_scene

    scene = intake_scene(today=TODAY)
    loop = SortLoop(scene=scene, store=make_store(locations=scene.locations),
                    detector=detector, yolo_out_root=tmp_path / "yolo")
    station = _FakeStation(scene)
    monkeypatch.setattr(loop, "_maybe_build_station", lambda: station)
    monkeypatch.setattr(loop, "_pick_and_place", lambda *a, **k: None)
    res = loop.run(today=TODAY)
    key = [(s.detection.label, s.detection.category, s.raw_text, s.source) for s in res.scans]
    routes = [(i.name, i.location_id, i.expiration_date, i.quantity) for i in res.sorted_items]
    return res, key, routes


def test_yolo_never_changes_qr_identification_or_routing(tmp_path, monkeypatch):
    base, key0, routes0 = _run(None, tmp_path, monkeypatch)
    wrong = _AlwaysWrong(len(base.scans))
    res, key1, routes1 = _run(wrong, tmp_path, monkeypatch)

    assert key1 == key0 and routes1 == routes0
    assert [d.name for d in res.discarded] == [d.name for d in base.discarded]
    assert base.yolo is None
    assert res.yolo is not None
    s = res.yolo.summary()
    assert s["observations"] == len(base.scans) - 1   # one detect() call raised
    assert s["correct"] == 0 and s["mappable"] >= 1
    assert (res.yolo_dir / "summary.json").is_file()


# --------------------------------------------------------------------------- real model

def test_detector_smoke():
    pytest.importorskip("onnxruntime")
    from pantrysort.config import YoloConfig

    cfg = YoloConfig()
    if ensure_weights(cfg.model, cfg.cache_dir) is None:
        pytest.skip(f"no verified {cfg.model} weights in {cfg.cache_dir}")
    det = make_detector(SimpleNamespace(yolo=cfg))
    assert det is not None and det.input_size == YOLOX_WEIGHTS[cfg.model].input_size
    frame = np.full((240, 320, 4), 200, dtype=np.uint8)
    dets = det.detect(frame)
    assert isinstance(dets, list) and det.last_latency_ms > 0
    for d in dets:
        assert d.cls_name in COCO_CLASSES and 0 <= d.score <= 1
