"""Describe the pantry sorting scene independently of Drake.

The scene definition (bins, storage bins, and the items to be sorted) is pure
Python data so it can be authored, tested, and reasoned about without importing
pydrake. ``build_station`` in ``station.py`` turns it into a Drake diagram.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from pantrysort.inventory.models import (
    FoodCategory,
    StorageLocation,
    StorageType,
)
from pantrysort.perception.catalog import FoodCatalog
from pantrysort.perception.classifier import Detection
from pantrysort.perception.qr_payload import FoodQrPayload

ITEMS_DIR = Path(__file__).resolve().parents[3] / "assets" / "items"
SHAPES_MANIFEST = ITEMS_DIR / "shapes.yaml"

# SO-101 shoulder_pan axis in the world (the arm base sits at the origin facing +x).
PAN_AXIS_XY = (0.0388, 0.0)


@dataclass(frozen=True)
class ItemShape:
    """Geometry for an item body. ``mesh`` None means a plain box of ``native_size``.

    Meshes live in ``assets/items`` (see ``scripts/prepare_items.py`` and
    ``scripts/generate_printables.py``), are in meters, and are centered on their
    bounding box. By convention the grip width is along the shape's y axis.
    """

    name: str
    native_size: tuple[float, float, float]  # bounding box at scale 1 (m)
    mesh: str | None = None                   # file name under assets/items
    scale: float = 1.0
    color: tuple[float, float, float, float] | None = None

    @property
    def size(self) -> tuple[float, float, float]:
        return tuple(s * self.scale for s in self.native_size)  # type: ignore[return-value]

    @property
    def grip_width(self) -> float:
        return self.size[1]

    def scaled(self, scale: float) -> ItemShape:
        return replace(self, scale=scale)


BOX = ItemShape("box", (0.035, 0.035, 0.05))


@lru_cache(maxsize=1)
def load_shapes(path: Path = SHAPES_MANIFEST) -> dict[str, ItemShape]:
    """All shapes listed in ``assets/items/shapes.yaml``, plus the plain ``box``."""
    import yaml

    shapes = {"box": BOX}
    if path.is_file():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name, raw in data.items():
            color = raw.get("color")
            shapes[name] = ItemShape(name, tuple(raw["size"]), mesh=raw.get("mesh"),
                                     color=tuple(color) if color else None)
    return shapes


def get_shape(name: str | None, scale: float = 1.0) -> ItemShape:
    shapes = load_shapes()
    if name not in shapes:
        raise KeyError(
            f"unknown item shape {name!r}; run scripts/generate_printables.py "
            f"(known: {', '.join(sorted(shapes))})"
        )
    return shapes[name].scaled(scale)


def facing_yaw(x: float, y: float) -> float:
    """Yaw that points an item's x axis at the arm, so the jaws close along its y."""
    return math.atan2(y - PAN_AXIS_XY[1], x - PAN_AXIS_XY[0])


@dataclass
class SceneItem:
    """An item physically present in the scene's intake bin."""

    label: str
    category: FoodCategory
    position: tuple[float, float, float]      # world-frame grasp point (m)
    unit_calories: int | None = None
    shelf_life_days: int | None = None        # days from "today" until expiry
    allergens: tuple[str, ...] = ()
    barcode: str | None = None
    shape: ItemShape = BOX
    yaw: float = 0.0  # rotation about z on the intake mat (rad)
    # What's printed on the QR sticker on top of the item (None = no sticker).
    qr: FoodQrPayload | None = None
    # Index into PantryScene.boxes if the item arrives in a donation box. Then
    # ``position``/``yaw`` are its pose once the box is at the pick station.
    box: int | None = None

    def to_detection(self, today: date | None = None,
                     catalog: FoodCatalog | None = None) -> Detection:
        """Ground-truth detection: what a perfect scan of this item's label yields."""
        today = today or date.today()
        if self.qr is not None:
            from pantrysort.perception.qr import detection_from_payload

            return detection_from_payload(self.qr, catalog or FoodCatalog.load(),
                                          self.position, today)
        exp = today + timedelta(days=self.shelf_life_days) if self.shelf_life_days else None
        return Detection(
            label=self.label,
            category=self.category,
            confidence=1.0,
            position=self.position,
            unit_calories=self.unit_calories,
            expiration_date=exp,
            allergens=self.allergens,
            barcode=self.barcode,
        )


@dataclass(frozen=True)
class DonationBox:
    """An open cardboard box of mixed donations that rides the conveyor."""

    label: str
    lot: str


@dataclass
class PantryScene:
    items: list[SceneItem] = field(default_factory=list)
    locations: list[StorageLocation] = field(default_factory=list)
    # Donation boxes on the conveyor, in arrival order. Empty = items sit on a
    # flat intake mat instead (no conveyor).
    boxes: list[DonationBox] = field(default_factory=list)

    def detections(self, today: date | None = None) -> list[Detection]:
        catalog = FoodCatalog.load() if any(it.qr for it in self.items) else None
        return [item.to_detection(today, catalog) for item in self.items]

    def box_items(self, box: int) -> list[SceneItem]:
        """Items packed in donation box ``box``, in unpacking order."""
        return [it for it in self.items if it.box == box]


# Expired items aren't stocked: they go to this bin and are logged as discarded.
DISCARD_LOCATION_ID = "discard"


# Default storage layout: one location per storage type / category group.
DEFAULT_LOCATIONS: list[StorageLocation] = [
    StorageLocation(
        id="shelf-canned",
        name="Canned goods shelf",
        storage_type=StorageType.SHELF,
        accepts=(FoodCategory.CANNED, FoodCategory.CONDIMENT),
    ),
    StorageLocation(
        id="shelf-dry",
        name="Dry goods shelf",
        storage_type=StorageType.SHELF,
        accepts=(FoodCategory.DRY_GOODS, FoodCategory.SNACK, FoodCategory.BABY),
    ),
    StorageLocation(
        id="fridge",
        name="Refrigerator",
        storage_type=StorageType.REFRIGERATOR,
        accepts=(FoodCategory.DAIRY, FoodCategory.PRODUCE, FoodCategory.BEVERAGE),
    ),
    StorageLocation(
        id="freezer",
        name="Freezer",
        storage_type=StorageType.FREEZER,
        accepts=(FoodCategory.FROZEN,),
    ),
    StorageLocation(
        id="bin-misc",
        name="Misc / non-food bin",
        storage_type=StorageType.BIN,
        accepts=(FoodCategory.NON_FOOD, FoodCategory.BAKERY, FoodCategory.UNKNOWN),
    ),
    StorageLocation(
        id=DISCARD_LOCATION_ID,
        name="Expired / discard bin",
        storage_type=StorageType.BIN,
        accepts=(),  # never chosen by category; the sort loop sends expired items here
    ),
]


# Intake grid in front of the arm: 3 rows (near -> far) x 3 columns.
INTAKE_ROWS_X = (0.15, 0.225, 0.30)
INTAKE_COLS_Y = (-0.08, 0.0, 0.08)

# Default donation bin: a mix of canned, dry, cooking basics, fresh/cold, and
# non-food essentials. Listed near row first, so the arm clears the front first;
# tall items sit in the far row where the SO-101 has the most reach above them.
DEFAULT_SKUS: tuple[str, ...] = (
    "TOOTHPASTE", "APPLE", "SPAGHETTI-BOX",
    "BEANS-BLK-CAN", "PEAS-FROZEN-BAG", "TOILET-PAPER",
    "CEREAL-BOX", "OLIVE-OIL", "MILK-CARTON",
)

# Days from "today" to the expiry printed on a demo label, where it differs from
# the catalog's shelf life: one donation is already past its date and one is
# about to expire, so the demo exercises the discard bin and the FEFO warning.
DEFAULT_EXPIRY_OFFSETS: dict[str, int] = {"MILK-CARTON": -3, "APPLE": 5}


def scene_from_skus(skus: list[str] | tuple[str, ...],
                    catalog: FoodCatalog | None = None,
                    today: date | None = None,
                    expiry_offsets: dict[str, int] | None = None,
                    lot: str | None = None) -> PantryScene:
    """Lay out catalog products on the intake grid (row by row, up to 9).

    Each item gets a QR sticker carrying its sku, expiry (today + catalog shelf
    life, or ``expiry_offsets[sku]`` days), lot, category, calories, and
    allergens. ``barcode`` holds the sku and each item looks like its catalog
    ``shape``.
    """
    from pantrysort.perception.qr import payload_for_entry

    catalog = catalog or FoodCatalog.load()
    today = today or date.today()
    offsets = expiry_offsets or {}
    lot = lot or f"D{today:%y%m%d}"
    slots = [(x, y) for x in INTAKE_ROWS_X for y in INTAKE_COLS_Y]
    if len(skus) > len(slots):
        raise ValueError(f"intake grid holds {len(slots)} items, got {len(skus)}")
    items = []
    for sku, (x, y) in zip(skus, slots, strict=False):
        entry = catalog.get(sku)
        if entry is None:
            raise KeyError(f"sku {sku!r} not in catalog")
        shape = get_shape(entry.shape or "box")
        days = offsets.get(sku, entry.shelf_life_days)
        exp = today + timedelta(days=days) if days is not None else None
        # Body origin is the bounding-box center, so a resting item sits at h/2.
        items.append(SceneItem(
            label=entry.name,
            category=entry.category,
            position=(x, y, shape.size[2] / 2),
            unit_calories=entry.unit_calories,
            shelf_life_days=days,
            allergens=entry.allergens,
            barcode=sku,
            shape=shape,
            yaw=facing_yaw(x, y),
            qr=payload_for_entry(entry, exp, lot),
        ))
    return PantryScene(items=items, locations=list(DEFAULT_LOCATIONS))


# --------------------------------------------------------------------------- conveyor
#
# A belt runs past the front of the arm along y, carrying donation boxes toward
# -y. Each box stops at the pick station (y = STATION_Y) in front of the arm, is
# unpacked, then rides on downstream as the next box comes in. The category
# bins sit beside and behind the arm, clear of the belt (x < 0.11).

BELT_X = 0.235              # belt centerline (m)
BELT_WIDTH = 0.23
BELT_HALF_LENGTH = 1.25     # belt runs y in [-1.25, 1.25]
BELT_TOP = 0.012            # low tabletop conveyor; keeps tall items in the SO-101's reach
STATION_Y = 0.0             # where a box stops to be unpacked
BOX_PITCH = 0.30            # spacing between boxes queued on the belt
DONATION_BOX_SIZE = (0.20, 0.24, 0.035)  # outer (x, y, wall height), open top
BOX_WALL = 0.004            # cardboard thickness (walls and floor)
BOX_FLOOR_TOP = BELT_TOP + BOX_WALL      # items rest here

# Item slots in a box at the pick station: (dx, dy) from the box center.
# Row 0 is nearer the arm; tall items go in row 1, where the arm reaches higher.
BOX_ROWS_DX = (-0.045, 0.045)
BOX_COLS_DY = (-0.075, 0.0, 0.075)

# One spec per donation box: (label, [(sku, row, col), ...]) in unpacking order.
DEFAULT_DONATIONS: tuple[tuple[str, tuple[tuple[str, int, int], ...]], ...] = (
    ("Donation box 1", (
        ("TOOTHPASTE", 0, 0), ("APPLE", 0, 1), ("SPAGHETTI-BOX", 0, 2),
        ("BEANS-BLK-CAN", 1, 0), ("MILK-CARTON", 1, 2),
    )),
    ("Donation box 2", (
        ("SOAP-BAR", 0, 0), ("TUNA-CAN", 0, 1), ("PEAS-FROZEN-BAG", 0, 2),
        ("CEREAL-BOX", 1, 1),
    )),
    ("Donation box 3", (
        ("APPLE", 0, 1),
        ("TOILET-PAPER", 1, 0), ("RICE-BAG", 1, 1), ("PB-JAR", 1, 2),
    )),
)


def box_station_pose(box: int = 0) -> tuple[float, float, float]:
    """Center of a donation box's floor (bottom face) when it's at the pick station."""
    del box  # every box stops at the same place
    return (BELT_X, STATION_Y, BELT_TOP)


def donation_scene(donations=DEFAULT_DONATIONS, catalog: FoodCatalog | None = None,
                   today: date | None = None,
                   expiry_offsets: dict[str, int] | None = None) -> PantryScene:
    """Donation boxes of mixed products arriving on the conveyor.

    Each item gets a QR sticker (sku, expiry, the box's lot, category, calories,
    allergens). ``expiry_offsets[sku]`` overrides the catalog shelf life (days).
    """
    from pantrysort.perception.qr import payload_for_entry

    catalog = catalog or FoodCatalog.load()
    today = today or date.today()
    offsets = expiry_offsets or {}
    bx, by, _ = box_station_pose()
    boxes: list[DonationBox] = []
    items: list[SceneItem] = []
    for k, (label, contents) in enumerate(donations):
        box = DonationBox(label=label, lot=f"D{today:%y%m%d}-{k + 1}")
        boxes.append(box)
        used: set[tuple[int, int]] = set()
        for sku, row, col in contents:
            if (row, col) in used:
                raise ValueError(f"{label}: slot ({row}, {col}) used twice")
            used.add((row, col))
            entry = catalog.get(sku)
            if entry is None:
                raise KeyError(f"sku {sku!r} not in catalog")
            shape = get_shape(entry.shape or "box")
            days = offsets.get(sku, entry.shelf_life_days)
            exp = today + timedelta(days=days) if days is not None else None
            x, y = bx + BOX_ROWS_DX[row], by + BOX_COLS_DY[col]
            items.append(SceneItem(
                label=f"{entry.name} [{k + 1}]",  # unique: the same product can recur
                category=entry.category,
                position=(x, y, BOX_FLOOR_TOP + shape.size[2] / 2),
                unit_calories=entry.unit_calories,
                shelf_life_days=days,
                allergens=entry.allergens,
                barcode=sku,
                shape=shape,
                yaw=facing_yaw(x, y),
                qr=payload_for_entry(entry, exp, box.lot),
                box=k,
            ))
    return PantryScene(items=items, locations=list(DEFAULT_LOCATIONS), boxes=boxes)


def default_scene(today: date | None = None) -> PantryScene:
    """Three mixed donation boxes arriving on the conveyor (demos and tests)."""
    return donation_scene(today=today, expiry_offsets=DEFAULT_EXPIRY_OFFSETS)


def intake_scene(today: date | None = None) -> PantryScene:
    """The earlier layout: nine items on a flat intake mat, no conveyor."""
    return scene_from_skus(DEFAULT_SKUS, today=today, expiry_offsets=DEFAULT_EXPIRY_OFFSETS)


# --------------------------------------------------------------------------- bins
#
# Layout is sized for the SO-101 arm (base at the origin, facing +x, ~0.35 m
# reach, shoulder_pan limited to about +/-110 degrees).
PAD_HEIGHT = 0.004  # bin floor thickness: items placed in a bin rest at this height
BIN_WALL_HEIGHT = 0.03
BIN_WALL = 0.004


def _ring_point(radius: float, angle_deg: float) -> tuple[float, float, float]:
    """Point on a pad's top surface, in polar coordinates about the shoulder_pan axis.

    Keep ``|angle_deg|`` <= ~108: shoulder_pan is limited to about +/-110 degrees.
    """
    a = math.radians(angle_deg)
    return (round(PAN_AXIS_XY[0] + radius * math.cos(a), 4),
            round(PAN_AXIS_XY[1] + radius * math.sin(a), 4), PAD_HEIGHT)


# Center of each category bin's floor (m). Bins sit beside and behind the arm,
# out of the conveyor's way: an outer pair per side at 0.30 m and one inner bin
# per side at 0.175 m. Bins that receive tall items are on the outer ring, where
# the SO-101 reaches highest. An item placed in a bin has its center at floor +
# height/2 (plus whatever is already stacked).
LOCATION_DROP_POINTS: dict[str, tuple[float, float, float]] = {
    "shelf-canned": _ring_point(0.30, 86),
    "shelf-dry": _ring_point(0.30, 108),
    "bin-misc": _ring_point(0.175, 97),
    "fridge": _ring_point(0.30, -86),
    "freezer": _ring_point(0.30, -108),
    DISCARD_LOCATION_ID: _ring_point(0.175, -97),
}

# Each bin has two slots along the radial direction (inner, outer); further items
# stack on the lower slot. Items are placed with their long x axis tangential and
# their grip width (y, <= 6 cm) radial, so two fit side by side.
PAD_SLOT_OFFSETS = (-0.028, 0.028)
PAD_SIZE = (0.11, 0.09)  # bin outer (radial, tangential) in m


def pad_slot(location_id: str, slot: int) -> tuple[float, float, float, float]:
    """(x, y, pad_top_z, yaw) for a slot on a storage pad."""
    x, y, top = LOCATION_DROP_POINTS.get(location_id, (0.0, 0.0, 0.0))
    bearing = math.atan2(y - PAN_AXIS_XY[1], x - PAN_AXIS_XY[0])
    offset = PAD_SLOT_OFFSETS[slot % len(PAD_SLOT_OFFSETS)]
    yaw = bearing + math.pi / 2  # item x tangential, item y radial
    return (x + offset * math.cos(bearing), y + offset * math.sin(bearing), top, yaw)


class PadLayout:
    """Tracks what's in each bin: each item goes on the lower of its two slots."""

    def __init__(self) -> None:
        self._tops: dict[tuple[str, int], float] = {}

    def place(self, location_id: str, item_height: float) -> tuple[tuple[float, float, float], float]:
        """Reserve a spot; returns (item center position, yaw)."""
        floor = LOCATION_DROP_POINTS.get(location_id, (0.0, 0.0, 0.0))[2]
        slot = min(range(len(PAD_SLOT_OFFSETS)),
                   key=lambda s: (self._tops.get((location_id, s), floor), s))
        x, y, pad_top, yaw = pad_slot(location_id, slot)
        bottom = self._tops.get((location_id, slot), pad_top)
        self._tops[(location_id, slot)] = bottom + item_height
        return (x, y, bottom + item_height / 2), yaw
