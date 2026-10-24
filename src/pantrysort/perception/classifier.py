"""Item classification.

For simulation we know the ground-truth item identity from the Drake scene, so
the default classifier is a lookup. A real deployment would swap in a vision
model (barcode scan + fine-grained classifier) behind the same interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol

from pantrysort.inventory.models import FoodCategory, InventoryItem


@dataclass
class Detection:
    """A single perceived object with a pose (sim frame) and identity guess."""

    label: str
    category: FoodCategory
    confidence: float
    # World-frame position of the object's grasp point, in meters.
    position: tuple[float, float, float]
    unit_calories: Optional[int] = None
    expiration_date: Optional[date] = None
    allergens: tuple[str, ...] = ()
    barcode: Optional[str] = None

    def to_item(self, quantity: int = 1) -> InventoryItem:
        return InventoryItem(
            name=self.label,
            category=self.category,
            quantity=quantity,
            unit_calories=self.unit_calories,
            expiration_date=self.expiration_date,
            allergens=self.allergens,
            barcode=self.barcode,
        )


class ClassifierBackend(Protocol):
    def detect(self, observation: object) -> list[Detection]: ...


class ItemClassifier:
    """Thin wrapper so the pipeline depends on a stable interface.

    Pass a `backend` implementing `detect(observation) -> list[Detection]`.
    In sim, the scene provides a ground-truth backend.
    """

    def __init__(self, backend: ClassifierBackend) -> None:
        self._backend = backend

    def detect(self, observation: object) -> list[Detection]:
        return self._backend.detect(observation)
