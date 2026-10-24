"""Shadow-mode YOLOX object detection.

A pretrained YOLOX COCO model (Megvii-BaseDetection, Apache-2.0) runs on CPU via
onnxruntime alongside the QR pipeline. It only *observes*: for each item the QR
pipeline identifies, it runs on that camera frame, matches its detections to the
item by back-projecting box centers through depth, and records whether it saw
something there and whether the class fits. It never changes labels, routes or
inventory. No training or fine-tuning happens anywhere.

Pre/post-processing follows the official ``demo/ONNXRuntime/onnx_inference.py``:
BGR input letterboxed onto a 114-gray canvas (top-left aligned), CHW float32
with no mean/std normalization; raw ``(1, N, 85)`` outputs decoded over the
stride-8/16/32 grids, score = objectness * class prob, class-wise NMS.

``onnxruntime`` is an optional extra (``pip install .[yolo]``); everything else
here is pure numpy/OpenCV so it is testable without it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger("pantrysort.yolo")

# --------------------------------------------------------------------------- model

COCO_CLASSES: tuple[str, ...] = (
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
)

_RELEASE = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0"


@dataclass(frozen=True)
class WeightSpec:
    url: str
    sha256: str
    input_size: int


# Official YOLOX release assets (tag 0.1.1rc0), pinned by SHA-256.
YOLOX_WEIGHTS: dict[str, WeightSpec] = {
    "yolox_s": WeightSpec(
        f"{_RELEASE}/yolox_s.onnx",
        "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063",
        640,
    ),
    "yolox_nano": WeightSpec(
        f"{_RELEASE}/yolox_nano.onnx",
        "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d",
        416,
    ),
}

STRIDES = (8, 16, 32)
PAD_VALUE = 114

# Catalog SKU -> the COCO class an off-the-shelf detector could reasonably call
# it. None means COCO has no fitting class (cans, cartons, boxes, bags, ...).
SKU_TO_COCO: dict[str, str | None] = {
    "APPLE": "apple",
    "OLIVE-OIL": "bottle",
    "SHAMPOO": "bottle",
    "BEANS-BLK-CAN": None,
    "TUNA-CAN": None,
    "FORMULA-CAN": None,
    "SPAGHETTI-BOX": None,
    "CEREAL-BOX": None,
    "RICE-BAG": None,
    "FLOUR-BAG": None,
    "SALT": None,
    "PB-JAR": None,
    "MILK-CARTON": None,
    "PEAS-FROZEN-BAG": None,
    "TOOTHPASTE": None,
    "SOAP-BAR": None,
    "TOILET-PAPER": None,
}

# Fallback by product-name keyword, for labels without a known SKU.
_NAME_TO_COCO: tuple[tuple[str, str], ...] = (
    ("apple", "apple"), ("banana", "banana"), ("orange", "orange"),
    ("carrot", "carrot"), ("broccoli", "broccoli"), ("bottle", "bottle"),
    ("cup", "cup"), ("bowl", "bowl"),
)


def expected_coco_class(sku: str | None = None, label: str | None = None) -> str | None:
    """COCO class a correct detection of this item would have (None = unmappable)."""
    if sku is not None and sku in SKU_TO_COCO:
        return SKU_TO_COCO[sku]
    if label:
        name = label.lower()
        for key, cls in _NAME_TO_COCO:
            if key in name:
                return cls
    return None


# --------------------------------------------------------------------------- pre/post

@dataclass(frozen=True)
class YoloDetection:
    cls_name: str
    score: float
    box_xyxy: tuple[float, float, float, float]  # original-image pixels
    center_px: tuple[float, float]


def to_bgr(image: np.ndarray) -> np.ndarray:
    """RGBA/RGB uint8 (Drake camera frames) -> contiguous BGR uint8."""
    img = np.asarray(image)
    if img.ndim == 2:
        img = np.stack([img] * 3, axis=-1)
    return np.ascontiguousarray(img[..., [2, 1, 0]]).astype(np.uint8, copy=False)


def letterbox(img_bgr: np.ndarray, size: int) -> tuple[np.ndarray, float]:
    """YOLOX preproc: resize keeping aspect, paste top-left on a 114 canvas, CHW f32."""
    import cv2

    h, w = img_bgr.shape[:2]
    r = min(size / h, size / w)
    nh, nw = int(h * r), int(w * r)
    padded = np.full((size, size, 3), PAD_VALUE, dtype=np.uint8)
    resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    padded[:nh, :nw] = resized
    return np.ascontiguousarray(padded.transpose(2, 0, 1), dtype=np.float32), r


def unletterbox_boxes(boxes_xyxy: np.ndarray, ratio: float) -> np.ndarray:
    """Map boxes from the letterboxed input back to original-image pixels."""
    return np.asarray(boxes_xyxy, dtype=float) / ratio


def decode_outputs(raw: np.ndarray, input_size: int,
                   strides: Iterable[int] = STRIDES) -> np.ndarray:
    """Decode raw YOLOX head outputs ``(N, 5 + C)`` to (cx, cy, w, h) input pixels."""
    out = np.array(raw, dtype=np.float32, copy=True)
    grids, exp_strides = [], []
    for s in strides:
        n = input_size // s
        xv, yv = np.meshgrid(np.arange(n), np.arange(n))
        grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
        exp_strides.append(np.full((n * n, 1), s))
    grid = np.concatenate(grids, 0)
    stride = np.concatenate(exp_strides, 0)
    if grid.shape[0] != out.shape[0]:
        raise ValueError(f"expected {grid.shape[0]} anchors for size {input_size}, "
                         f"got {out.shape[0]}")
    out[:, :2] = (out[:, :2] + grid) * stride
    out[:, 2:4] = np.exp(out[:, 2:4]) * stride
    return out


def nms(boxes: np.ndarray, scores: np.ndarray, thr: float) -> list[int]:
    """Greedy IoU non-maximum suppression; returns kept indices (best first)."""
    boxes = np.asarray(boxes, dtype=float)
    x1, y1, x2, y2 = boxes.T
    areas = np.maximum(x2 - x1, 0) * np.maximum(y2 - y1, 0)
    order = np.argsort(-np.asarray(scores))
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
        w = np.maximum(0.0, np.minimum(x2[i], x2[rest]) - np.maximum(x1[i], x1[rest]))
        h = np.maximum(0.0, np.minimum(y2[i], y2[rest]) - np.maximum(y1[i], y1[rest]))
        inter = w * h
        iou = inter / np.maximum(areas[i] + areas[rest] - inter, 1e-12)
        order = rest[iou <= thr]
    return keep


def multiclass_nms(boxes: np.ndarray, scores: np.ndarray, nms_thr: float,
                   score_thr: float) -> list[tuple[int, float, int]]:
    """Class-aware NMS. ``scores`` is (N, C). Returns [(box_idx, score, cls)]."""
    out: list[tuple[int, float, int]] = []
    for c in range(scores.shape[1]):
        idx = np.nonzero(scores[:, c] > score_thr)[0]
        if idx.size == 0:
            continue
        for k in nms(boxes[idx], scores[idx, c], nms_thr):
            out.append((int(idx[k]), float(scores[idx[k], c]), c))
    out.sort(key=lambda t: -t[1])
    return out


def postprocess(raw: np.ndarray, input_size: int, ratio: float,
                score_thr: float = 0.25, nms_thr: float = 0.45,
                class_names: tuple[str, ...] = COCO_CLASSES) -> list[YoloDetection]:
    """Raw ``(N, 85)`` (or ``(1, N, 85)``) head output -> detections in image pixels."""
    raw = np.asarray(raw)
    if raw.ndim == 3:
        raw = raw[0]
    pred = decode_outputs(raw, input_size)
    cx, cy, w, h = pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3]
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
    boxes = unletterbox_boxes(boxes, ratio)
    scores = pred[:, 4:5] * pred[:, 5:]
    dets = []
    for i, score, c in multiclass_nms(boxes, scores, nms_thr, score_thr):
        x1, y1, x2, y2 = (float(v) for v in boxes[i])
        name = class_names[c] if c < len(class_names) else str(c)
        dets.append(YoloDetection(name, score, (x1, y1, x2, y2),
                                  ((x1 + x2) / 2, (y1 + y2) / 2)))
    return dets


# --------------------------------------------------------------------------- detector

class YoloxDetector:
    """YOLOX ONNX model on onnxruntime (CPU). ``onnxruntime`` is imported lazily."""

    def __init__(self, model_path: str | Path, input_size: int = 640,
                 score_thr: float = 0.25, nms_thr: float = 0.45, name: str = "yolox") -> None:
        import onnxruntime as ort

        self.name = name
        self.model_path = str(model_path)
        self.input_size = int(input_size)
        self.score_thr = score_thr
        self.nms_thr = nms_thr
        self.session = ort.InferenceSession(self.model_path,
                                            providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.last_latency_ms = 0.0

    def detect(self, image: np.ndarray) -> list[YoloDetection]:
        """Detect objects in an RGB/RGBA frame. Records ``last_latency_ms``."""
        t0 = time.perf_counter()
        blob, ratio = letterbox(to_bgr(image), self.input_size)
        raw = self.session.run(None, {self.input_name: blob[None]})[0]
        dets = postprocess(raw, self.input_size, ratio, self.score_thr, self.nms_thr)
        self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
        return dets


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_weights(model: str, cache_dir: str | Path, download: bool = False) -> Path | None:
    """Path to verified weights for ``model`` in ``cache_dir`` (None if unavailable)."""
    spec = YOLOX_WEIGHTS.get(model)
    if spec is None:
        logger.warning("Unknown YOLOX model %r (have %s).", model, ", ".join(YOLOX_WEIGHTS))
        return None
    path = Path(cache_dir).expanduser() / f"{model}.onnx"
    if not path.is_file():
        if not download:
            return None
        import urllib.request

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        logger.info("Downloading %s -> %s", spec.url, path)
        urllib.request.urlretrieve(spec.url, tmp)  # noqa: S310 (pinned https URL)
        tmp.replace(path)
    digest = _sha256(path)
    if digest != spec.sha256:
        logger.warning("YOLOX weights %s have SHA-256 %s, expected %s; not using them.",
                       path, digest, spec.sha256)
        return None
    return path


def make_detector(config=None) -> YoloxDetector | None:
    """The configured detector, or None if disabled or onnxruntime/weights are missing."""
    if config is None:
        from pantrysort.config import CONFIG as config
    cfg = getattr(config, "yolo", None)
    if cfg is None or not cfg.enabled:
        return None
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        logger.info("YOLO shadow detector off: onnxruntime not installed (pip install .[yolo]).")
        return None
    path = ensure_weights(cfg.model, cfg.cache_dir, cfg.download)
    if path is None:
        logger.info("YOLO shadow detector off: no verified %s weights in %s.",
                    cfg.model, cfg.cache_dir)
        return None
    try:
        return YoloxDetector(path, YOLOX_WEIGHTS[cfg.model].input_size,
                             cfg.score_thr, cfg.nms_thr, name=cfg.model)
    except Exception as exc:  # a broken model must never stop the sorter
        logger.warning("YOLO shadow detector failed to load (%s).", exc)
        return None


# --------------------------------------------------------------------------- shadow tracker

Locate = Callable[[float, float], object]  # (u, v) -> world point (3,) or None


@dataclass
class YoloObservation:
    """What YOLO saw at one identified item, versus the QR ground truth."""

    label: str                 # QR-identified item (ground truth)
    sku: str | None
    camera: str
    source: str                # "camera" (passive) or "camera-active"
    expected: str | None       # COCO class a correct detection would have
    detected: bool             # any detection back-projected onto this item
    top_class: str | None      # highest-scoring detection at the item
    top_score: float | None
    correct: bool | None       # top_class == expected (False if undetected; None if unmappable)
    latency_ms: float
    num_detections: int        # all detections in the frame

    @property
    def unmappable(self) -> bool:
        return self.expected is None


@dataclass
class YoloShadowTracker:
    """Runs a detector on identifying frames and scores it against the QR labels.

    Detections are matched to an item by back-projecting the box center with
    ``locate`` and taking the nearest item within ``match_tol`` (m). Only records;
    callers must never feed anything from here into routing.
    """

    detector: object  # anything with .detect(image) and .last_latency_ms
    match_tol: float = 0.08
    observations: list[YoloObservation] = field(default_factory=list)

    def observe(self, label: str, sku: str | None, camera: str, image: np.ndarray,
                locate: Locate, positions: Mapping[str, np.ndarray],
                source: str = "camera") -> YoloObservation:
        dets = self.detector.detect(image)
        latency = float(getattr(self.detector, "last_latency_ms", 0.0))
        at_item = [d for d in dets if self._match(d, locate, positions) == label]
        top = max(at_item, key=lambda d: d.score) if at_item else None
        expected = expected_coco_class(sku, label)
        correct = None
        if expected is not None and top is not None:
            correct = top.cls_name == expected
        elif expected is not None:
            correct = False
        obs = YoloObservation(
            label=label, sku=sku, camera=camera, source=source, expected=expected,
            detected=top is not None,
            top_class=top.cls_name if top else None,
            top_score=round(top.score, 4) if top else None,
            correct=correct, latency_ms=round(latency, 2), num_detections=len(dets),
        )
        self.observations.append(obs)
        return obs

    def _match(self, det: YoloDetection, locate: Locate,
               positions: Mapping[str, np.ndarray]) -> str | None:
        p = locate(*det.center_px)
        if p is None:
            return None
        p = np.asarray(p, dtype=float)
        best, best_d = None, self.match_tol
        for name, pos in positions.items():
            d = float(np.linalg.norm(p[:2] - np.asarray(pos, dtype=float)[:2]))
            if d <= best_d:
                best, best_d = name, d
        return best

    def summary(self) -> dict:
        obs = self.observations
        mappable = [o for o in obs if not o.unmappable]
        n_correct = sum(1 for o in mappable if o.correct)
        n_detected = sum(1 for o in obs if o.detected)
        lat = [o.latency_ms for o in obs]
        return {
            "model": getattr(self.detector, "name", type(self.detector).__name__),
            "observations": len(obs),
            "detected": n_detected,
            "detection_rate": n_detected / len(obs) if obs else 0.0,
            "mappable": len(mappable),
            "correct": n_correct,
            "accuracy_mappable": n_correct / len(mappable) if mappable else 0.0,
            "unmappable": len(obs) - len(mappable),
            "mean_latency_ms": float(np.mean(lat)) if lat else 0.0,
        }

    def summary_line(self) -> str:
        s = self.summary()
        return (f"YOLO shadow ({s['model']}): detected {s['detected']}/{s['observations']} "
                f"items, class correct {s['correct']}/{s['mappable']} mappable, "
                f"{s['unmappable']} unmappable, {s['mean_latency_ms']:.0f} ms/frame")

    def write(self, out_dir: str | Path) -> Path:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        with (out / "observations.jsonl").open("w", encoding="utf-8") as f:
            for o in self.observations:
                f.write(json.dumps({**asdict(o), "unmappable": o.unmappable}) + "\n")
        (out / "summary.json").write_text(json.dumps(self.summary(), indent=2),
                                          encoding="utf-8")
        return out
