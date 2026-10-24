"""QR system tests: payload format, catalog, generate -> decode -> Detection."""

from __future__ import annotations

from datetime import date

import cv2
import numpy as np
import pytest

from pantrysort.inventory.models import FoodCategory
from pantrysort.perception.catalog import CatalogError, FoodCatalog
from pantrysort.perception.classifier import ItemClassifier
from pantrysort.perception.qr import (
    QrClassifierBackend,
    QrObservation,
    decode_qr_codes,
    make_qr_image,
)
from pantrysort.perception.qr_payload import FoodQrPayload, PayloadError
from pantrysort.sim.pantry_scene import default_scene

TODAY = date(2026, 10, 24)


@pytest.fixture(scope="module")
def catalog() -> FoodCatalog:
    return FoodCatalog.load()


# --- payload ---------------------------------------------------------------


def test_payload_roundtrip():
    p = FoodQrPayload(sku="MILK-CARTON", expiration_date=date(2026, 11, 3), lot="A1")
    text = p.encode()
    assert text == "PS1|sku=MILK-CARTON|exp=2026-11-03|lot=A1"
    assert FoodQrPayload.parse(text) == p


def test_payload_minimal_and_extra_fields():
    assert FoodQrPayload.parse("PS1|sku=PB-JAR") == FoodQrPayload(sku="PB-JAR")
    assert FoodQrPayload.parse("PS1|sku=PB-JAR|w=450").extra == {"w": "450"}


@pytest.mark.parametrize(
    "text",
    [
        "",
        "https://example.com",
        "PS2|sku=PB-JAR",
        "PS1|exp=2026-01-01",
        "PS1|sku=PB-JAR|exp=not-a-date",
        "PS1|sku=PB-JAR|sku=MILK-CARTON",
        "PS1|sku",
        "PS1|sku=bad value",
    ],
)
def test_payload_rejects_invalid(text):
    with pytest.raises(PayloadError):
        FoodQrPayload.parse(text)


def test_payload_encode_rejects_unsafe_values():
    with pytest.raises(PayloadError):
        FoodQrPayload(sku="A|B").encode()


# --- catalog ---------------------------------------------------------------


def test_catalog_covers_default_scene(catalog):
    for item in default_scene().items:
        entry = catalog.get(item.barcode)
        assert entry is not None, item.barcode
        assert entry.name == item.label
        assert entry.category == item.category
        assert entry.allergens == item.allergens


def test_catalog_rejects_bad_category():
    with pytest.raises(CatalogError):
        FoodCatalog.from_dict({"X": {"name": "x", "category": "lava"}})


# --- generate -> decode ----------------------------------------------------


@pytest.mark.parametrize("item", default_scene().items, ids=lambda i: i.barcode)
def test_every_scene_item_qr_decodes(item):
    payload = FoodQrPayload(sku=item.barcode, expiration_date=date(2027, 1, 1), lot="T1")
    decoded = decode_qr_codes(make_qr_image(payload))
    assert [d.text for d in decoded] == [payload.encode()]


def _scene_frame(payload_texts: list[str], size=(480, 640)) -> np.ndarray:
    """Fake RGBA camera frame: QR labels pasted on a gray background, slightly rotated."""
    h, w = size
    frame = np.full((h, w, 4), 120, dtype=np.uint8)
    frame[..., 3] = 255
    for i, text in enumerate(payload_texts):
        qr = make_qr_image(text, scale=4)
        rot = cv2.warpAffine(
            qr,
            cv2.getRotationMatrix2D((qr.shape[1] / 2, qr.shape[0] / 2), 12, 1.0),
            (qr.shape[1], qr.shape[0]),
            borderValue=255,
        )
        y, x = 40, 40 + i * (qr.shape[1] + 30)
        frame[y : y + rot.shape[0], x : x + rot.shape[1], :3] = rot[..., None]
    return frame


def test_decode_from_rgba_camera_frame_with_center():
    text = FoodQrPayload(sku="BEANS-BLK-CAN").encode()
    frame = _scene_frame([text])
    (qr,) = decode_qr_codes(frame)
    assert qr.text == text
    cx, cy = qr.center_px
    side = make_qr_image(text, scale=4).shape[0]
    assert abs(cx - (40 + side / 2)) < 6 and abs(cy - (40 + side / 2)) < 6


def test_no_qr_in_blank_frame():
    assert decode_qr_codes(np.full((240, 320, 3), 200, dtype=np.uint8)) == []


# --- classifier backend ----------------------------------------------------


def test_backend_identifies_first_item(catalog):
    exp = date(2026, 11, 3)
    frame = _scene_frame([FoodQrPayload(sku="MILK-CARTON", expiration_date=exp).encode()])
    classifier = ItemClassifier(QrClassifierBackend(catalog, intake_position=(0.5, 0.0, 0.04)))

    (det,) = classifier.detect(QrObservation(frame, today=TODAY))
    assert det.label == "Milk (carton)"
    assert det.category == FoodCategory.DAIRY
    assert det.expiration_date == exp
    assert det.allergens == ("milk",)
    assert det.barcode == "MILK-CARTON"
    assert det.position == (0.5, 0.0, 0.04)
    assert det.confidence == 1.0


def test_backend_falls_back_to_catalog_shelf_life(catalog):
    frame = _scene_frame([FoodQrPayload(sku="PB-JAR").encode()])
    (det,) = QrClassifierBackend(catalog).detect(QrObservation(frame, today=TODAY))
    assert (det.expiration_date - TODAY).days == 300


def test_backend_unknown_sku_and_foreign_qr(catalog):
    frame = _scene_frame(["PS1|sku=MYSTERY-1", "https://example.com"])
    dets = QrClassifierBackend(catalog).detect(QrObservation(frame, today=TODAY))
    assert len(dets) == 1  # foreign QR ignored
    assert dets[0].category == FoodCategory.UNKNOWN
    assert dets[0].confidence < 1.0


def test_backend_uses_locator(catalog):
    frame = _scene_frame([FoodQrPayload(sku="FORMULA-CAN").encode()])
    backend = QrClassifierBackend(catalog, locator=lambda qr: (qr.center_px[0], qr.center_px[1], 0.0))
    (det,) = backend.detect(frame)
    assert det.position[0] > 0 and det.position[1] > 0
