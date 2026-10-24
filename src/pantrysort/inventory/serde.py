"""Serialization between domain models and plain dict rows.

These helpers convert InventoryItem / StorageLocation / Transaction to and from
JSON-friendly dicts that map directly onto Supabase (Postgres) table columns.
Keeping this in one place means both the Supabase backend and any app you build
can rely on the same row shape.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pantrysort.inventory.models import (
    FoodCategory,
    InventoryItem,
    StorageLocation,
    StorageType,
    Transaction,
    TransactionType,
    app_category,
)


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])


def _parse_datetime(value: Any) -> datetime:
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    # Supabase returns ISO strings, often with a trailing 'Z'.
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


# --- StorageLocation ---

def location_to_row(loc: StorageLocation) -> dict[str, Any]:
    return {
        "id": loc.id,
        "name": loc.name,
        "storage_type": loc.storage_type.value,
        "accepts": [c.value for c in loc.accepts],
    }


def row_to_location(row: dict[str, Any]) -> StorageLocation:
    return StorageLocation(
        id=row["id"],
        name=row["name"],
        storage_type=StorageType(row["storage_type"]),
        accepts=tuple(FoodCategory(c) for c in (row.get("accepts") or [])),
    )


# --- InventoryItem ---

def item_to_row(item: InventoryItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        # The app groups shelves by its own categories; see models.app_category.
        "category": app_category(item.category, item.name).value,
        "quantity": item.quantity,
        "unit_calories": item.unit_calories,
        "weight_grams": item.weight_grams,
        "expiration_date": item.expiration_date.isoformat()
        if item.expiration_date
        else None,
        "allergens": list(item.allergens),
        "barcode": item.barcode,
        "location_id": item.location_id,
        "received_at": item.received_at.isoformat(),
    }


def row_to_item(row: dict[str, Any]) -> InventoryItem:
    return InventoryItem(
        id=row["id"],
        name=row["name"],
        category=FoodCategory(row["category"]),
        quantity=int(row.get("quantity", 1)),
        unit_calories=row.get("unit_calories"),
        weight_grams=row.get("weight_grams"),
        expiration_date=_parse_date(row.get("expiration_date")),
        allergens=tuple(row.get("allergens") or []),
        barcode=row.get("barcode"),
        location_id=row.get("location_id"),
        received_at=_parse_datetime(row.get("received_at")),
    )


# --- Transaction ---

def transaction_to_row(txn: Transaction) -> dict[str, Any]:
    return {
        "item_id": txn.item_id,
        "transaction_type": txn.transaction_type.value,
        "quantity": txn.quantity,
        "timestamp": txn.timestamp.isoformat(),
        "note": txn.note,
        "item_name": txn.note or None,
    }


def row_to_transaction(row: dict[str, Any]) -> Transaction:
    return Transaction(
        item_id=row["item_id"],
        transaction_type=TransactionType(row["transaction_type"]),
        quantity=int(row["quantity"]),
        timestamp=_parse_datetime(row.get("timestamp")),
        note=row.get("note", ""),
    )
