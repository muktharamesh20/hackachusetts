"""Food catalog: maps a QR ``sku`` to the static facts about that product.

The catalog is a YAML file (default ``assets/catalog.yaml``, override with the
``PANTRYSORT_CATALOG_PATH`` env var). Each entry looks like::

    BEANS-BLK-CAN:
      name: Black beans (can)
      category: canned            # a FoodCategory value
      unit_calories: 330
      shelf_life_days: 540        # fallback if the QR has no exp date
      allergens: []
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pantrysort.inventory.models import FoodCategory

# src/pantrysort/perception/catalog.py -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_PATH = _REPO_ROOT / "assets" / "catalog.yaml"


class CatalogError(ValueError):
    """Raised when the catalog file is missing or malformed."""


@dataclass(frozen=True)
class CatalogEntry:
    sku: str
    name: str
    category: FoodCategory
    unit_calories: int | None = None
    shelf_life_days: int | None = None
    allergens: tuple[str, ...] = ()
    shape: str | None = None  # sim mesh name in assets/items/shapes.yaml


class FoodCatalog:
    def __init__(self, entries: dict[str, CatalogEntry]) -> None:
        self._entries = dict(entries)

    def __contains__(self, sku: str) -> bool:
        return sku in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries.values())

    def get(self, sku: str) -> CatalogEntry | None:
        return self._entries.get(sku)

    @classmethod
    def from_dict(cls, data: dict) -> FoodCatalog:
        if not isinstance(data, dict):
            raise CatalogError("catalog root must be a mapping of sku -> entry")
        entries: dict[str, CatalogEntry] = {}
        for sku, raw in data.items():
            if not isinstance(raw, dict):
                raise CatalogError(f"entry {sku!r} must be a mapping")
            try:
                category = FoodCategory(raw.get("category", "unknown"))
            except ValueError as exc:
                raise CatalogError(f"entry {sku!r}: unknown category {raw.get('category')!r}") from exc
            if "name" not in raw:
                raise CatalogError(f"entry {sku!r} is missing 'name'")
            entries[str(sku)] = CatalogEntry(
                sku=str(sku),
                name=str(raw["name"]),
                category=category,
                unit_calories=_opt_int(raw.get("unit_calories")),
                shelf_life_days=_opt_int(raw.get("shelf_life_days")),
                allergens=tuple(str(a) for a in (raw.get("allergens") or ())),
                shape=str(raw["shape"]) if raw.get("shape") else None,
            )
        return cls(entries)

    @classmethod
    def load(cls, path: str | Path | None = None) -> FoodCatalog:
        import yaml

        path = Path(path or os.getenv("PANTRYSORT_CATALOG_PATH") or DEFAULT_CATALOG_PATH)
        if not path.is_file():
            raise CatalogError(f"catalog file not found: {path}")
        with path.open("r", encoding="utf-8") as fh:
            # safe_load: never construct arbitrary Python objects from YAML.
            data = yaml.safe_load(fh) or {}
        return cls.from_dict(data)


def _opt_int(value) -> int | None:
    return None if value is None else int(value)
