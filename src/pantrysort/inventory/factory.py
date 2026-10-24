"""Construct an inventory store from configuration.

Backend selection (``PANTRYSORT_INVENTORY_BACKEND``):
  * ``memory``   -> InMemoryInventoryStore (default; no network, great for tests)
  * ``supabase`` -> SupabaseInventoryStore (persistent Postgres via supabase-py)
"""

from __future__ import annotations

from typing import Iterable, Optional

from pantrysort.config import CONFIG, Config
from pantrysort.inventory.base import InventoryStoreProtocol
from pantrysort.inventory.models import StorageLocation
from pantrysort.inventory.store import InMemoryInventoryStore


def make_store(
    locations: Optional[Iterable[StorageLocation]] = None,
    config: Config = CONFIG,
) -> InventoryStoreProtocol:
    backend = config.inventory.backend.lower()
    locations = list(locations or [])

    if backend == "memory":
        return InMemoryInventoryStore(locations=locations)

    if backend == "supabase":
        from pantrysort.inventory.supabase_store import SupabaseInventoryStore

        return SupabaseInventoryStore(
            url=config.inventory.supabase_url,
            key=config.inventory.supabase_key,
            seed_locations=locations,
        )

    raise ValueError(
        f"Unknown inventory backend {backend!r} (use 'memory' or 'supabase')."
    )
