"""In-memory inventory store with a lifecycle transaction log.

Tracks everything coming in (intake) and going out (distribute/discard) and
answers the operational questions a pantry cares about: what's expiring, how
many calories/servings are on hand, and what to distribute first (FEFO).

The store is intentionally backend-agnostic. It keeps state in memory and
exposes a clean API; a SQLAlchemy-backed implementation can subclass or wrap
this later without changing callers.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from pantrysort.inventory.models import (
    FoodCategory,
    InventoryItem,
    StorageLocation,
    Transaction,
    TransactionType,
)
from pantrysort.inventory.nutrition import NutritionSummary, fefo_order, summarize


class InMemoryInventoryStore:
    def __init__(self, locations: Optional[Iterable[StorageLocation]] = None) -> None:
        self._items: dict[str, InventoryItem] = {}
        self._transactions: list[Transaction] = []
        self._locations: dict[str, StorageLocation] = {
            loc.id: loc for loc in (locations or [])
        }

    # --- locations ---

    def add_location(self, location: StorageLocation) -> None:
        self._locations[location.id] = location

    def locations(self) -> list[StorageLocation]:
        return list(self._locations.values())

    def location_for_category(self, category: FoodCategory) -> Optional[StorageLocation]:
        """Pick the first storage location that accepts this category."""
        for loc in self._locations.values():
            if loc.accepts_category(category):
                return loc
        return None

    # --- intake / outflow ---

    def intake(self, item: InventoryItem) -> InventoryItem:
        """Record a newly received item and auto-assign a storage location."""
        if item.location_id is None:
            loc = self.location_for_category(item.category)
            if loc is not None:
                item.location_id = loc.id
        self._items[item.id] = item
        self._transactions.append(
            Transaction(item.id, TransactionType.INTAKE, item.quantity, note=item.name)
        )
        return item

    def distribute(self, item_id: str, quantity: int = 1, note: str = "") -> None:
        self._remove(item_id, quantity, TransactionType.DISTRIBUTE, note)

    def discard(self, item_id: str, quantity: int = 1, note: str = "") -> None:
        self._remove(item_id, quantity, TransactionType.DISCARD, note)

    def _remove(
        self, item_id: str, quantity: int, ttype: TransactionType, note: str
    ) -> None:
        item = self._items.get(item_id)
        if item is None:
            raise KeyError(f"No item with id {item_id!r}")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if quantity > item.quantity:
            raise ValueError(
                f"Cannot remove {quantity} of {item.name}; only {item.quantity} on hand"
            )
        item.quantity -= quantity
        self._transactions.append(Transaction(item_id, ttype, quantity, note=note))
        if item.quantity == 0:
            del self._items[item_id]

    # --- queries ---

    def get(self, item_id: str) -> Optional[InventoryItem]:
        return self._items.get(item_id)

    def all_items(self) -> list[InventoryItem]:
        return list(self._items.values())

    def items_in(self, location_id: str) -> list[InventoryItem]:
        return [i for i in self._items.values() if i.location_id == location_id]

    def expired(self, today: Optional[date] = None) -> list[InventoryItem]:
        return [i for i in self._items.values() if i.is_expired(today)]

    def expiring_soon(
        self, warn_days: int, today: Optional[date] = None
    ) -> list[InventoryItem]:
        return [
            i for i in self._items.values() if i.is_expiring_soon(warn_days, today)
        ]

    def distribution_queue(self, today: Optional[date] = None) -> list[InventoryItem]:
        """Items ordered First-Expired-First-Out, excluding already-expired."""
        fresh = [i for i in self._items.values() if not i.is_expired(today)]
        return fefo_order(fresh, today)

    def summary(self) -> NutritionSummary:
        return summarize(self._items.values())

    def transactions(self) -> list[Transaction]:
        return list(self._transactions)


# Backward-compatible alias (the original class name).
InventoryStore = InMemoryInventoryStore
