"""Perception: identify pantry items from observations."""

from pantrysort.perception.catalog import CatalogEntry, FoodCatalog
from pantrysort.perception.classifier import Detection, ItemClassifier
from pantrysort.perception.qr_payload import FoodQrPayload, PayloadError

# qr.py (QrClassifierBackend, make_qr_image, decode_qr_codes) is imported directly
# from pantrysort.perception.qr so this package doesn't require OpenCV/segno.

__all__ = [
    "CatalogEntry",
    "Detection",
    "FoodCatalog",
    "FoodQrPayload",
    "ItemClassifier",
    "PayloadError",
]
