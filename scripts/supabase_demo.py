"""Verify the Supabase inventory backend end-to-end.

Seeds the default storage locations, takes in the default scene's items, then
reads back the FEFO distribution queue and a nutrition summary FROM Supabase.

Prereqs:
  * A Supabase project with db/schema.sql applied (see docs/SUPABASE_SETUP.md).
  * SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY) in your .env.
  * `pip install supabase`

Usage:
    PANTRYSORT_INVENTORY_BACKEND=supabase python scripts/supabase_demo.py
"""

from __future__ import annotations

from pantrysort.config import CONFIG
from pantrysort.inventory.supabase_store import SupabaseInventoryStore
from pantrysort.sim.pantry_scene import default_scene


def main() -> None:
    if not CONFIG.inventory.supabase_url or not CONFIG.inventory.supabase_key:
        raise SystemExit(
            "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_KEY "
            "(or SUPABASE_SERVICE_ROLE_KEY) in your .env. "
            "See docs/SUPABASE_SETUP.md."
        )

    scene = default_scene()
    store = SupabaseInventoryStore(seed_locations=scene.locations)

    print("Seeding storage locations + taking in sample items...")
    for detection in scene.detections():
        store.intake(detection.to_item())

    print("\nStorage locations:")
    for loc in store.locations():
        print(f"  - {loc.id:<14} {loc.name}")

    print("\nFEFO distribution queue (soonest expiry first):")
    for item in store.distribution_queue():
        days = item.days_until_expiry()
        when = f"{days} days" if days is not None else "no expiry"
        print(f"  - {item.name:<26} ({when})")

    summary = store.summary()
    print("\nNutrition summary (read back from Supabase):")
    print(f"  items={summary.total_items} units={summary.total_units} "
          f"total_calories={summary.total_calories}")
    for cat, cal in sorted(summary.by_category_calories.items(), key=lambda x: x[0].value):
        print(f"    {cat.value:<12} {cal} kcal")

    print("\nConnected to Supabase successfully.")


if __name__ == "__main__":
    main()
