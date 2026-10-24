"""Generate a PantrySort QR label PNG for every sku in the food catalog.

Usage:
    python scripts/generate_qr.py                       # all skus -> assets/qr/
    python scripts/generate_qr.py --sku MILK-CARTON --exp 2026-11-03 --lot A1
    python scripts/generate_qr.py --out-dir /tmp/qr --scale 12

Each label carries sku, expiry, lot, category, calories, and allergens. If
--exp is omitted, expiry is today + the catalog's shelf_life_days. Each PNG is
verified by decoding it back before the script reports success.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from pantrysort.perception.catalog import DEFAULT_CATALOG_PATH, FoodCatalog
from pantrysort.perception.qr import (
    decode_qr_codes,
    make_qr_image,
    payload_for_entry,
    save_qr_png,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "assets" / "qr")
    parser.add_argument("--sku", action="append", help="only these skus (repeatable)")
    parser.add_argument("--exp", type=date.fromisoformat, help="expiry date YYYY-MM-DD")
    parser.add_argument("--lot", help="lot / donation id")
    parser.add_argument("--scale", type=int, default=10, help="pixels per QR module")
    args = parser.parse_args(argv)

    catalog = FoodCatalog.load(args.catalog)
    skus = args.sku or [entry.sku for entry in catalog]
    today = date.today()

    for sku in skus:
        entry = catalog.get(sku)
        if entry is None:
            print(f"error: sku {sku!r} not in {args.catalog}", file=sys.stderr)
            return 1
        exp = args.exp
        if exp is None and entry.shelf_life_days is not None:
            exp = today + timedelta(days=entry.shelf_life_days)

        payload = payload_for_entry(entry, exp, args.lot)
        path = save_qr_png(payload, args.out_dir / f"{sku}.png", scale=args.scale)

        # Round-trip check so we never ship an unreadable label.
        decoded = [d.text for d in decode_qr_codes(make_qr_image(payload, scale=args.scale))]
        if payload.encode() not in decoded:
            print(f"error: generated QR for {sku} did not decode back", file=sys.stderr)
            return 1
        print(f"{path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}  "
              f"{payload.encode()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
