"""Domain models for pantry inventory.

These are plain, dependency-light dataclasses/enums so the inventory logic is
fully unit-testable without Drake, LeRobot, or a database.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class FoodCategory(str, Enum):
    """Coarse categories used for sorting into storage areas."""

    CANNED = "canned"
    DRY_GOODS = "dry_goods"          # pasta, rice, beans, cereal
    BAKERY = "bakery"
    PRODUCE = "produce"
    DAIRY = "dairy"
    FROZEN = "frozen"
    BEVERAGE = "beverage"
    SNACK = "snack"
    CONDIMENT = "condiment"
    BABY = "baby"                    # formula, baby food
    NON_FOOD = "non_food"            # hygiene, pet, etc.
    UNKNOWN = "unknown"


class StorageType(str, Enum):
    SHELF = "shelf"
    REFRIGERATOR = "refrigerator"
    FREEZER = "freezer"
    BIN = "bin"


class TransactionType(str, Enum):
    INTAKE = "intake"        # item received / donated
    DISTRIBUTE = "distribute"  # item given out
    DISCARD = "discard"      # item expired/damaged, removed


@dataclass(frozen=True)
class StorageLocation:
    """A physical place an item can be sorted into."""

    id: str
    name: str
    storage_type: StorageType
    accepts: tuple[FoodCategory, ...]

    def accepts_category(self, category: FoodCategory) -> bool:
        return category in self.accepts


@dataclass
class InventoryItem:
    """A single tracked food item (one physical unit or a counted group)."""

    name: str
    category: FoodCategory
    quantity: int = 1
    unit_calories: Optional[int] = None          # kcal per unit
    weight_grams: Optional[float] = None
    expiration_date: Optional[date] = None
    allergens: tuple[str, ...] = ()
    barcode: Optional[str] = None
    location_id: Optional[str] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    received_at: datetime = field(default_factory=datetime.now)

    # --- derived / helper properties ---

    @property
    def total_calories(self) -> Optional[int]:
        if self.unit_calories is None:
            return None
        return self.unit_calories * self.quantity

    def days_until_expiry(self, today: Optional[date] = None) -> Optional[int]:
        if self.expiration_date is None:
            return None
        today = today or date.today()
        return (self.expiration_date - today).days

    def is_expired(self, today: Optional[date] = None) -> bool:
        days = self.days_until_expiry(today)
        return days is not None and days < 0

    def is_expiring_soon(self, warn_days: int, today: Optional[date] = None) -> bool:
        days = self.days_until_expiry(today)
        return days is not None and 0 <= days <= warn_days


@dataclass(frozen=True)
class Transaction:
    """A lifecycle event recording items moving in or out of the pantry."""

    item_id: str
    transaction_type: TransactionType
    quantity: int
    timestamp: datetime = field(default_factory=datetime.now)
    note: str = ""
