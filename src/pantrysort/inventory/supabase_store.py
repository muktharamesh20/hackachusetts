"""Supabase (Postgres) implementation of the inventory store.

Persists items, storage locations, and the intake/distribute/discard
transaction log in Supabase tables via the official ``supabase-py`` client.
FEFO/expiry/nutrition reporting reuses the same pure-Python helpers as the
in-memory store, so results are identical regardless of backend.

The ``supabase`` import is lazy so the package stays importable without the SDK
or network access. See ``db/schema.sql`` for the table definitions.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Optional

from pantrysort.inventory.models import (
    FoodCategory,
    InventoryItem,
    StorageLocation,
    Transaction,
    TransactionType,
)
from pantrysort.inventory.nutrition import NutritionSummary, fefo_order, summarize
from pantrysort.inventory.serde import (
    item_to_row,
    location_to_row,
    row_to_item,
    row_to_location,
    transaction_to_row,
)

ITEMS_TABLE = "inventory_items"
LOCATIONS_TABLE = "storage_locations"
TRANSACTIONS_TABLE = "inventory_transactions"


class SupabaseInventoryStore:
    """Inventory store backed by Supabase Postgres.

    Parameters
    ----------
    url, key:
        Supabase project URL and API key. If omitted, read from
        ``SUPABASE_URL`` / ``SUPABASE_KEY`` (or service-role key) via config.
    client:
        An existing supabase Client may be injected (useful for tests).
    seed_locations:
        Optional locations to upsert on construction.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        client: Any = None,
        seed_locations: Optional[Iterable[StorageLocation]] = None,
    ) -> None:
        self._client = client or self._make_client(url, key)
        if seed_locations:
            for loc in seed_locations:
                self.add_location(loc)

    @staticmethod
    def _make_client(url: Optional[str], key: Optional[str]) -> Any:
        try:
            from supabase import create_client
        except Exception as exc:  # pragma: no cover - env dependent
            raise ImportError(
                "supabase-py is required for the Supabase backend. "
                "Install with `pip install supabase`. "
                f"Underlying import error: {exc}"
            ) from exc

        if not url or not key:
            from pantrysort.config import CONFIG

            url = url or CONFIG.inventory.supabase_url
            key = key or CONFIG.inventory.supabase_key
        if not url or not key:
            raise ValueError(
                "Supabase URL and key are required. Set SUPABASE_URL and "
                "SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY) in your environment."
            )
        return create_client(url, key)

    # --- locations ---

    def add_location(self, location: StorageLocation) -> None:
        self._client.table(LOCATIONS_TABLE).upsert(location_to_row(location)).execute()

    def locations(self) -> list[StorageLocation]:
        resp = self._client.table(LOCATIONS_TABLE).select("*").execute()
        return [row_to_location(r) for r in (resp.data or [])]

    def location_for_category(
        self, category: FoodCategory
    ) -> Optional[StorageLocation]:
        # PostgREST array containment: accepts @> {category}
        resp = (
            self._client.table(LOCATIONS_TABLE)
            .select("*")
            .contains("accepts", [category.value])
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return row_to_location(rows[0]) if rows else None

    # --- intake / outflow ---

    def intake(self, item: InventoryItem) -> InventoryItem:
        if item.location_id is None:
            loc = self.location_for_category(item.category)
            if loc is not None:
                item.location_id = loc.id
        self._client.table(ITEMS_TABLE).upsert(item_to_row(item)).execute()
        self._log(Transaction(item.id, TransactionType.INTAKE, item.quantity, note=item.name))
        return item

    def distribute(self, item_id: str, quantity: int = 1, note: str = "") -> None:
        self._remove(item_id, quantity, TransactionType.DISTRIBUTE, note)

    def discard(self, item_id: str, quantity: int = 1, note: str = "") -> None:
        self._remove(item_id, quantity, TransactionType.DISCARD, note)

    def _remove(
        self, item_id: str, quantity: int, ttype: TransactionType, note: str
    ) -> None:
        item = self.get(item_id)
        if item is None:
            raise KeyError(f"No item with id {item_id!r}")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if quantity > item.quantity:
            raise ValueError(
                f"Cannot remove {quantity} of {item.name}; only {item.quantity} on hand"
            )
        remaining = item.quantity - quantity
        if remaining == 0:
            self._client.table(ITEMS_TABLE).delete().eq("id", item_id).execute()
        else:
            self._client.table(ITEMS_TABLE).update({"quantity": remaining}).eq(
                "id", item_id
            ).execute()
        self._log(Transaction(item_id, ttype, quantity, note=note))

    def _log(self, txn: Transaction) -> None:
        self._client.table(TRANSACTIONS_TABLE).insert(transaction_to_row(txn)).execute()

    # --- queries ---

    def get(self, item_id: str) -> Optional[InventoryItem]:
        resp = (
            self._client.table(ITEMS_TABLE).select("*").eq("id", item_id).limit(1).execute()
        )
        rows = resp.data or []
        return row_to_item(rows[0]) if rows else None

    def all_items(self) -> list[InventoryItem]:
        resp = self._client.table(ITEMS_TABLE).select("*").execute()
        return [row_to_item(r) for r in (resp.data or [])]

    def items_in(self, location_id: str) -> list[InventoryItem]:
        resp = (
            self._client.table(ITEMS_TABLE)
            .select("*")
            .eq("location_id", location_id)
            .execute()
        )
        return [row_to_item(r) for r in (resp.data or [])]

    def expired(self, today: Optional[date] = None) -> list[InventoryItem]:
        return [i for i in self.all_items() if i.is_expired(today)]

    def expiring_soon(
        self, warn_days: int, today: Optional[date] = None
    ) -> list[InventoryItem]:
        return [i for i in self.all_items() if i.is_expiring_soon(warn_days, today)]

    def distribution_queue(self, today: Optional[date] = None) -> list[InventoryItem]:
        fresh = [i for i in self.all_items() if not i.is_expired(today)]
        return fefo_order(fresh, today)

    def summary(self) -> NutritionSummary:
        return summarize(self.all_items())

    def transactions(self) -> list[Transaction]:
        from pantrysort.inventory.serde import row_to_transaction

        resp = self._client.table(TRANSACTIONS_TABLE).select("*").execute()
        return [row_to_transaction(r) for r in (resp.data or [])]
