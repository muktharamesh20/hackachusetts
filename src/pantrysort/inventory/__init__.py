"""Inventory domain: items, lifecycle events, nutrition, and FEFO logic.

Backends:
  * InMemoryInventoryStore  - in-process, no dependencies (default; for tests/demos)
  * SupabaseInventoryStore  - persistent Postgres via supabase-py

Both satisfy InventoryStoreProtocol. Use `make_store()` to pick one from config.
"""

from pantrysort.inventory.base import InventoryStoreProtocol
from pantrysort.inventory.factory import make_store
from pantrysort.inventory.models import (
    FoodCategory,
    InventoryItem,
    StorageLocation,
    StorageType,
    Transaction,
    TransactionType,
)
from pantrysort.inventory.store import InMemoryInventoryStore, InventoryStore

__all__ = [
    "FoodCategory",
    "InventoryItem",
    "StorageLocation",
    "StorageType",
    "Transaction",
    "TransactionType",
    "InventoryStoreProtocol",
    "InMemoryInventoryStore",
    "InventoryStore",
    "make_store",
]
