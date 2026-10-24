"""Describe the pantry sorting scene independently of Drake.

The scene definition (bins, storage bins, and the items to be sorted) is pure
Python data so it can be authored, tested, and reasoned about without importing
pydrake. ``build_station`` in ``station.py`` turns it into a Drake diagram.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from pantrysort.inventory.models import (
    FoodCategory,
    StorageLocation,
    StorageType,
)
from pantrysort.perception.classifier import Detection


@dataclass
class SceneItem:
    """An item physically present in the scene's intake bin."""

    label: str
    category: FoodCategory
    position: tuple[float, float, float]      # world-frame grasp point (m)
    unit_calories: int | None = None
    shelf_life_days: int | None = None        # days from "today" until expiry
    allergens: tuple[str, ...] = ()
    barcode: str | None = None

    def to_detection(self, today: date | None = None) -> Detection:
        today = today or date.today()
        exp = today + timedelta(days=self.shelf_life_days) if self.shelf_life_days else None
        return Detection(
            label=self.label,
            category=self.category,
            confidence=1.0,
            position=self.position,
            unit_calories=self.unit_calories,
            expiration_date=exp,
            allergens=self.allergens,
            barcode=self.barcode,
        )


@dataclass
class PantryScene:
    items: list[SceneItem] = field(default_factory=list)
    locations: list[StorageLocation] = field(default_factory=list)

    def detections(self, today: date | None = None) -> list[Detection]:
        return [item.to_detection(today) for item in self.items]


# Default storage layout: one location per storage type / category group.
DEFAULT_LOCATIONS: list[StorageLocation] = [
    StorageLocation(
        id="shelf-canned",
        name="Canned goods shelf",
        storage_type=StorageType.SHELF,
        accepts=(FoodCategory.CANNED, FoodCategory.CONDIMENT),
    ),
    StorageLocation(
        id="shelf-dry",
        name="Dry goods shelf",
        storage_type=StorageType.SHELF,
        accepts=(FoodCategory.DRY_GOODS, FoodCategory.SNACK, FoodCategory.BABY),
    ),
    StorageLocation(
        id="fridge",
        name="Refrigerator",
        storage_type=StorageType.REFRIGERATOR,
        accepts=(FoodCategory.DAIRY, FoodCategory.PRODUCE, FoodCategory.BEVERAGE),
    ),
    StorageLocation(
        id="freezer",
        name="Freezer",
        storage_type=StorageType.FREEZER,
        accepts=(FoodCategory.FROZEN,),
    ),
    StorageLocation(
        id="bin-misc",
        name="Misc / non-food bin",
        storage_type=StorageType.BIN,
        accepts=(FoodCategory.NON_FOOD, FoodCategory.BAKERY, FoodCategory.UNKNOWN),
    ),
]


def default_scene() -> PantryScene:
    """A representative mixed donation bin for demos and tests."""
    items = [
        SceneItem("Black beans (can)", FoodCategory.CANNED, (0.45, -0.10, 0.03),
                  unit_calories=330, shelf_life_days=540),
        SceneItem("Spaghetti (box)", FoodCategory.DRY_GOODS, (0.50, 0.00, 0.03),
                  unit_calories=800, shelf_life_days=365, allergens=("wheat",)),
        SceneItem("Peanut butter (jar)", FoodCategory.CONDIMENT, (0.55, 0.12, 0.03),
                  unit_calories=2500, shelf_life_days=300, allergens=("peanut",)),
        SceneItem("Milk (carton)", FoodCategory.DAIRY, (0.42, 0.14, 0.04),
                  unit_calories=600, shelf_life_days=10, allergens=("milk",)),
        SceneItem("Frozen peas (bag)", FoodCategory.FROZEN, (0.48, -0.16, 0.03),
                  unit_calories=350, shelf_life_days=200),
        SceneItem("Infant formula (can)", FoodCategory.BABY, (0.58, -0.04, 0.03),
                  unit_calories=2600, shelf_life_days=120, allergens=("milk",)),
    ]
    return PantryScene(items=items, locations=list(DEFAULT_LOCATIONS))


# Approximate world-frame drop points for each storage location (m).
LOCATION_DROP_POINTS: dict[str, tuple[float, float, float]] = {
    "shelf-canned": (0.0, 0.55, 0.20),
    "shelf-dry": (0.0, 0.70, 0.20),
    "fridge": (-0.55, 0.30, 0.20),
    "freezer": (-0.55, -0.30, 0.20),
    "bin-misc": (0.0, -0.60, 0.15),
}
