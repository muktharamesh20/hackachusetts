"""QR code generation, decoding, and a QR-based classifier backend.

Flow::

    FoodQrPayload --make_qr_image--> image on the item
    camera image  --decode_qr_codes--> [DecodedQr]
    DecodedQr     --QrClassifierBackend--> Detection (via the FoodCatalog)

Everything here works on plain numpy images, so it can be tested without Drake.
In the sim, the observation is the RGB image from the overhead camera.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from pantrysort.inventory.models import FoodCategory
from pantrysort.perception.catalog import FoodCatalog
from pantrysort.perception.classifier import Detection
from pantrysort.perception.qr_payload import FoodQrPayload, PayloadError

logger = logging.getLogger("pantrysort.perception.qr")

# Error correction "M" recovers ~15% damage: a good balance of density vs. robustness.
DEFAULT_ERROR = "m"
DEFAULT_BORDER = 4  # quiet zone in modules; the QR spec minimum, needed for detection


# --------------------------------------------------------------------------- generation


def make_qr_image(
    payload: FoodQrPayload | str,
    scale: int = 10,
    border: int = DEFAULT_BORDER,
    error: str = DEFAULT_ERROR,
) -> np.ndarray:
    """Render a payload to a grayscale uint8 image (0 = black module, 255 = white).

    ``scale`` is pixels per module. ``border`` is the quiet zone in modules.
    """
    import segno

    text = payload.encode() if isinstance(payload, FoodQrPayload) else payload
    qr = segno.make(text, error=error, micro=False)
    modules = np.array([list(row) for row in qr.matrix], dtype=bool)  # True = dark
    modules = np.pad(modules, border, constant_values=False)
    img = np.where(modules, 0, 255).astype(np.uint8)
    return np.kron(img, np.ones((scale, scale), dtype=np.uint8))


def save_qr_png(payload: FoodQrPayload | str, path: str | Path, scale: int = 10) -> Path:
    """Write the QR for ``payload`` as a PNG (usable as a Drake mesh texture)."""
    import cv2

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), make_qr_image(payload, scale=scale)):
        raise OSError(f"failed to write QR image to {path}")
    return path


# --------------------------------------------------------------------------- decoding


@dataclass(frozen=True)
class DecodedQr:
    text: str
    # 4x2 array of (x, y) pixel corners, in OpenCV's order.
    corners: np.ndarray

    @property
    def center_px(self) -> tuple[float, float]:
        cx, cy = self.corners.mean(axis=0)
        return float(cx), float(cy)


def decode_qr_codes(image: np.ndarray) -> list[DecodedQr]:
    """Find and decode every QR code in an image.

    Accepts grayscale (HxW), RGB (HxWx3), or RGBA (HxWx4) uint8 images. Drake's
    camera produces RGBA, so that is handled directly.
    """
    import cv2

    gray = _to_gray(image)
    results = _decode_with(cv2.QRCodeDetector(), gray)
    if not results:
        # Rendered camera frames give only ~4 px per module, which the default
        # detector often can't sample. Upscaling fixes most of those cases.
        up = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        results = [DecodedQr(r.text, r.corners / 2) for r in _decode_with(cv2.QRCodeDetector(), up)]
    if not results and hasattr(cv2, "QRCodeDetectorAruco"):
        results = _decode_with(cv2.QRCodeDetectorAruco(), gray)
    if not results:
        # Oblique / perspective views: detect the QR quad (its finder squares make
        # the quad recoverable), warp it flat, then decode the rectified patch.
        results = _decode_rectified(gray)
    return results


def _decode_rectified(gray: np.ndarray, out_side: int = 240) -> list[DecodedQr]:
    """Rectify each detected QR quad to a flat square and decode it.

    Uses the QR's own corner geometry to undo perspective/lens warp so we can
    read codes the detector can locate but not sample head-on. Corners are
    reported in the original image coordinates.
    """
    import cv2

    det = cv2.QRCodeDetector()
    ok, quads = det.detectMulti(gray)
    if not ok or quads is None:
        found, q = det.detect(gray)
        quads = q.reshape(1, 4, 2) if (found and q is not None) else None
    if quads is None:
        return []

    results: list[DecodedQr] = []
    dst = np.array([[0, 0], [out_side, 0], [out_side, out_side], [0, out_side]],
                   dtype=np.float32)
    for quad in np.asarray(quads, dtype=np.float32).reshape(-1, 4, 2):
        Hm = cv2.getPerspectiveTransform(quad, dst)
        rect = cv2.warpPerspective(gray, Hm, (out_side, out_side))
        rect = cv2.copyMakeBorder(rect, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
        text, _, _ = cv2.QRCodeDetector().detectAndDecode(rect)
        if text:
            results.append(DecodedQr(text=text, corners=quad.astype(float)))
    return results


def _decode_with(detector, gray: np.ndarray) -> list[DecodedQr]:
    results: list[DecodedQr] = []
    ok, texts, points, _ = detector.detectAndDecodeMulti(gray)
    if ok and points is not None:
        for text, pts in zip(texts, points, strict=True):
            if text:  # detected-but-undecodable codes come back as ""
                results.append(DecodedQr(text=text, corners=np.asarray(pts, dtype=float)))

    if not results:
        # The multi detector occasionally misses a lone code the single one finds.
        text, pts, _ = detector.detectAndDecode(gray)
        if text and pts is not None:
            results.append(DecodedQr(text=text, corners=np.asarray(pts, dtype=float).reshape(4, 2)))
    return results


def _to_gray(image: np.ndarray) -> np.ndarray:
    import cv2

    img = np.asarray(image)
    if img.dtype != np.uint8:
        raise TypeError(f"expected a uint8 image, got {img.dtype}")
    if img.ndim == 2:
        return img
    if img.ndim == 3 and img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    if img.ndim == 3 and img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
    raise ValueError(f"unsupported image shape {img.shape}")


# --------------------------------------------------------------------------- classifier


@dataclass
class QrObservation:
    """What the QR backend consumes: one camera frame."""

    image: np.ndarray
    today: date | None = None


# Maps a decoded QR (pixel corners) to a world-frame grasp point. In the sim this
# will use the depth image + camera intrinsics/pose; until then a fixed intake
# point is used.
Locator = Callable[[DecodedQr], tuple[float, float, float]]


class QrClassifierBackend:
    """``ClassifierBackend`` that identifies items by their PantrySort QR label.

    * Non-PantrySort QR codes are ignored.
    * A valid payload with an unknown sku yields an UNKNOWN detection (routed to the
      misc bin) with reduced confidence, so the item is still cleared from intake.
    * Expiry comes from the QR; if absent, from the catalog's ``shelf_life_days``.
    """

    UNKNOWN_SKU_CONFIDENCE = 0.5

    def __init__(
        self,
        catalog: FoodCatalog,
        locator: Locator | None = None,
        intake_position: tuple[float, float, float] = (0.50, 0.0, 0.03),
    ) -> None:
        self.catalog = catalog
        self._locator = locator or (lambda _qr: intake_position)

    def detect(self, observation: QrObservation | np.ndarray) -> list[Detection]:
        if isinstance(observation, QrObservation):
            image, today = observation.image, observation.today
        else:
            image, today = observation, None
        today = today or date.today()

        detections: list[Detection] = []
        for qr in decode_qr_codes(image):
            try:
                payload = FoodQrPayload.parse(qr.text)
            except PayloadError as exc:
                logger.debug("Ignoring non-PantrySort QR %r: %s", qr.text, exc)
                continue
            detections.append(self._to_detection(payload, qr, today))
        return detections

    def _to_detection(self, payload: FoodQrPayload, qr: DecodedQr, today: date) -> Detection:
        return detection_from_payload(payload, self.catalog, self._locator(qr), today,
                                      self.UNKNOWN_SKU_CONFIDENCE)


def _label_category(payload: FoodQrPayload) -> FoodCategory | None:
    if payload.category is None:
        return None
    try:
        return FoodCategory(payload.category)
    except ValueError:
        logger.warning("QR %s has unknown category %r; ignoring it.", payload.sku, payload.category)
        return None


def detection_from_payload(
    payload: FoodQrPayload,
    catalog: FoodCatalog,
    position: tuple[float, float, float],
    today: date | None = None,
    unknown_confidence: float = QrClassifierBackend.UNKNOWN_SKU_CONFIDENCE,
) -> Detection:
    """Turn a decoded label into a Detection.

    Facts printed on the label (category, calories, allergens, expiry) win; the
    catalog fills in whatever the label leaves out, plus the display name. An
    unknown sku with no category on the label is UNKNOWN (routed to the misc bin).
    """
    today = today or date.today()
    position = tuple(float(v) for v in position)
    entry = catalog.get(payload.sku)
    label_cat = _label_category(payload)

    if entry is None:
        logger.warning("QR sku %r not in catalog; using label data only.", payload.sku)
        return Detection(
            label=f"Unknown item ({payload.sku})",
            category=label_cat or FoodCategory.UNKNOWN,
            confidence=unknown_confidence,
            position=position,
            unit_calories=payload.unit_calories,
            expiration_date=payload.expiration_date,
            allergens=payload.allergens or (),
            barcode=payload.sku,
        )

    exp = payload.expiration_date
    if exp is None and entry.shelf_life_days is not None:
        exp = today + timedelta(days=entry.shelf_life_days)
    return Detection(
        label=entry.name,
        category=label_cat or entry.category,
        confidence=1.0,
        position=position,
        unit_calories=payload.unit_calories if payload.unit_calories is not None
        else entry.unit_calories,
        expiration_date=exp,
        allergens=payload.allergens if payload.allergens is not None else entry.allergens,
        barcode=payload.sku,
    )


def payload_for_entry(entry, expiration_date: date | None = None,
                      lot: str | None = None) -> FoodQrPayload:
    """Full self-contained label for a catalog entry (expiry, category, nutrition)."""
    return FoodQrPayload(
        sku=entry.sku,
        expiration_date=expiration_date,
        lot=lot,
        category=entry.category.value,
        unit_calories=entry.unit_calories,
        allergens=tuple(entry.allergens),
    )
