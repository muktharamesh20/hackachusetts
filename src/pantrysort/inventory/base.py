"""Shared InventoryStore interface.

Both the in-memory store and the Supabase-backed store implement this Protocol,
so callers (the sort loop, an app, tests) depend only on the interface. Swap
backends by constructing a different implementation; nothing else changes.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Protocol, runtime_checkable

from pantrysort.inventory.models import (
    FoodCategory,
    InventoryItem,
    StorageLocation,
)
from pantrysort.inventory.nutrition import NutritionSummary


@runtime_checkable
class InventoryStoreProtocol(Protocol):
    # locations
    def add_location(self, location: StorageLocation) -> None: ...
    def locations(self) -> list[StorageLocation]: ...
    def location_for_category(
        self, category: FoodCategory
    ) -> Optional[StorageLocation]: ...

    # intake / outflow
    def intake(self, item: InventoryItem) -> InventoryItem: ...
    def distribute(self, item_id: str, quantity: int = 1, note: str = "") -> None: ...
    def discard(self, item_id: str, quantity: int = 1, note: str = "") -> None: ...

    # queries
    def get(self, item_id: str) -> Optional[InventoryItem]: ...
    def all_items(self) -> list[InventoryItem]: ...
    def items_in(self, location_id: str) -> list[InventoryItem]: ...
    def expired(self, today: Optional[date] = None) -> list[InventoryItem]: ...
    def expiring_soon(
        self, warn_days: int, today: Optional[date] = None
    ) -> list[InventoryItem]: ...
    def distribution_queue(
        self, today: Optional[date] = None
    ) -> list[InventoryItem]: ...
    def summary(self) -> NutritionSummary: ...
