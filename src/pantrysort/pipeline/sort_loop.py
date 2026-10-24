"""The end-to-end pantry sort loop.

Donation boxes ride the conveyor to the pick station one at a time. For each
item in the box at the station (or on the intake mat, for box-less scenes):
  1. scan its QR sticker with the fixed camera rig and decode it (category,
     calories, expiry, allergens, lot), showing the result in Meshcat,
  2. decide its storage location: expired items go to the discard bin,
     everything else by category via the inventory store's routing,
  3. drive the robot (scripted or LeRobot policy) to pick it from the bin and
     place it at that location's drop point, and
  4. record it in the inventory (intake, plus a discard transaction if expired).

When a box is empty the belt brings the next one; the empties ride on downstream.

The loop is designed to run with or without Drake. If the station can be built
it executes real pick-and-place motions; otherwise it still runs the full
perception -> routing -> inventory flow (useful for CI and demos on machines
without the robotics stack). This separation is what makes the business logic
testable and the robot layer swappable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from pantrysort.config import CONFIG, Config
from pantrysort.inventory.base import InventoryStoreProtocol
from pantrysort.inventory.factory import make_store
from pantrysort.inventory.models import (
    FoodCategory,
    InventoryItem,
    StorageLocation,
    TransactionType,
)
from pantrysort.perception.catalog import FoodCatalog
from pantrysort.perception.classifier import Detection
from pantrysort.perception.qr_payload import FoodQrPayload, PayloadError
from pantrysort.policy.lerobot_policy import Policy, make_policy
from pantrysort.sim.pantry_scene import (
    DISCARD_LOCATION_ID,
    PadLayout,
    PantryScene,
    SceneItem,
    scene_for_mode,
)

logger = logging.getLogger("pantrysort.sort_loop")


@dataclass
class ScanOutcome:
    """Result of identifying one item: the detection plus what the scan saw."""

    detection: Detection
    payload: FoodQrPayload | None = None
    raw_text: str | None = None
    image: np.ndarray | None = None
    corners: np.ndarray | None = None
    source: str = "ground-truth"  # "camera" when decoded from the rendered frame


@dataclass
class SortResult:
    sorted_items: list[InventoryItem] = field(default_factory=list)
    unresolved: list[Detection] = field(default_factory=list)
    discarded: list[InventoryItem] = field(default_factory=list)  # expired on arrival
    scans: list[ScanOutcome] = field(default_factory=list)
    # Per donation box: (label, {destination location id: item count}).
    boxes: list[tuple[str, dict[str, int]]] = field(default_factory=list)

    @property
    def num_sorted(self) -> int:
        return len(self.sorted_items)


class SortLoop:
    def __init__(
        self,
        scene: PantryScene | None = None,
        store: InventoryStoreProtocol | None = None,
        policy: Policy | None = None,
        config: Config = CONFIG,
        use_sim: bool = True,
    ) -> None:
        self.config = config
        self.scene = scene or scene_for_mode(getattr(config.sim, "scene_mode", "flat_grid"))
        self.store = store or make_store(locations=self.scene.locations, config=config)
        self.policy = policy or make_policy(
            config.policy.backend,
            policy_path=config.policy.lerobot_policy_path,
            device=config.policy.device,
        )
        self.use_sim = use_sim
        self._station = None

    def _maybe_build_station(self):
        if not self.use_sim:
            return None
        if self._station is not None:
            return self._station
        try:
            from pantrysort.sim.station import build_station

            self._station = build_station(self.scene, self.config.sim)
            logger.info("Drake station built; running with simulation.")
        except ImportError as exc:
            logger.warning("Simulation unavailable (%s). Running logic-only.", exc)
            self._station = None
        return self._station

    def run(self, today: date | None = None) -> SortResult:
        today = today or date.today()
        result = SortResult()
        station = self._maybe_build_station()
        self._pads = PadLayout()
        self._catalog = FoodCatalog.load()
        if station is not None:
            station.start_recording()

        # Identify every item once up front by fusing QR reads across all rig
        # cameras (match each decoded QR to the nearest item, vote across views).
        self._identifications = {}
        if station is not None and getattr(station, "cameras", None):
            self._identifications = station.identify_items()
            logger.info("Camera rig identified %d/%d items.",
                        len(self._identifications), len(self.scene.items))

        if self.scene.boxes:
            for k, box in enumerate(self.scene.boxes):
                if station is not None:
                    station.convey_box_to_station(k)
                contents = self.scene.box_items(k)
                logger.info("%s (lot %s) at the pick station: %d item(s).",
                            box.label, box.lot, len(contents))
                counts: dict[str, int] = {}
                for scene_item in contents:
                    loc_id = self._process(station, scene_item, today, result)
                    if loc_id is not None:
                        counts[loc_id] = counts.get(loc_id, 0) + 1
                result.boxes.append((box.label, counts))
                logger.info("%s empty: %s", box.label,
                            ", ".join(f"{n} -> {loc}" for loc, n in counts.items()) or "nothing")
            if station is not None:
                station.run_out()
            loose = [it for it in self.scene.items if it.box is None]
        else:
            loose = list(self.scene.items)
        for scene_item in loose:
            self._process(station, scene_item, today, result)

        if station is not None:
            station.finish_recording()
        self._log_report()
        return result

    def _process(self, station, scene_item: SceneItem, today: date,
                 result: SortResult) -> str | None:
        """Scan, route, move, and record one item. Returns its destination id."""
        scan = self._identify(station, scene_item, today)
        result.scans.append(scan)
        detection = scan.detection
        location = self.route(detection, today)
        self._show_scan(station, scan, location, today)
        if location is None:
            logger.warning("No storage location for %s; skipping.", detection.label)
            result.unresolved.append(detection)
            return None

        # Drive the robot to move the item, if a station is available.
        if station is not None:
            self._pick_and_place(station, scene_item, detection, location.id)

        item = detection.to_item()
        item.location_id = location.id
        self.store.intake(item)
        result.sorted_items.append(item)
        logger.info(
            "Sorted %-24s -> %-22s (cal=%s, exp=%s)",
            detection.label,
            location.name,
            item.total_calories,
            item.expiration_date,
        )
        if location.id == DISCARD_LOCATION_ID:
            self.store.discard(item.id, item.quantity,
                               note=f"expired {item.expiration_date} on arrival")
            result.discarded.append(item)
        return location.id

    # ------------------------------------------------------------------ routing

    def route(self, detection: Detection, today: date) -> StorageLocation | None:
        """Expired -> discard bin; otherwise the first location accepting the category."""
        exp = detection.expiration_date
        if exp is not None and exp < today:
            for loc in self.store.locations():
                if loc.id == DISCARD_LOCATION_ID:
                    return loc
        return self.store.location_for_category(detection.category)

    # ------------------------------------------------------------------ scanning

    def _identify(self, station, scene_item: SceneItem, today: date) -> ScanOutcome:
        """Read the item's QR sticker from the fixed camera rig, if present.

        Without a rendering station (logic-only runs, CI) the sticker's payload is
        used directly, which is what a perfect scan would return. With a station,
        every rig camera is scanned once (cached) and QR reads are matched to this
        item by world position and fused across cameras.
        """
        from pantrysort.perception.qr import detection_from_payload

        if station is None or not getattr(station, "cameras", None):
            det = scene_item.to_detection(today, self._catalog)
            text = scene_item.qr.encode() if scene_item.qr else None
            return ScanOutcome(det, scene_item.qr, text)

        ident = self._identifications.get(scene_item.label)
        if ident is not None:
            try:
                payload = FoodQrPayload.parse(ident.text)
            except PayloadError as exc:
                logger.warning("QR matched to %s isn't a PantrySort label (%s).",
                               scene_item.label, exc)
            else:
                det = detection_from_payload(payload, self._catalog, scene_item.position, today)
                logger.info("Identified %-22s via %s (votes %d/%d)", scene_item.label,
                            ",".join(ident.cameras), ident.votes, ident.total_reads)
                image = station.camera_rgb(ident.cameras[0]) if ident.cameras else None
                return ScanOutcome(det, payload, ident.text, image, source="camera")

        # Passive fusion missed this item: actively present it to a camera. The
        # arm lifts the item to a reachable lens, where its QR is large and
        # head-on; the read is accepted only if it back-projects to where the
        # held item is (so a different item's sticker can't be misattributed).
        from pantrysort.sim.active_scan import present_and_read

        active = present_and_read(station, scene_item.label)
        if active is not None:
            text, image, cam = active
            try:
                payload = FoodQrPayload.parse(text)
            except PayloadError as exc:
                logger.warning("Active scan of %s isn't a PantrySort label (%s).",
                               scene_item.label, exc)
            else:
                det = detection_from_payload(payload, self._catalog, scene_item.position, today)
                logger.info("Identified %-22s by presenting to %s", scene_item.label, cam)
                return ScanOutcome(det, payload, text, image, source="camera-active")

        logger.warning("No camera read a QR for %s; sending to the misc bin.",
                       scene_item.label)
        det = Detection(label="Unlabeled item", category=FoodCategory.UNKNOWN, confidence=0.0,
                        position=scene_item.position)
        return ScanOutcome(det, source="camera")

    def _show_scan(self, station, scan: ScanOutcome, location: StorageLocation | None,
                   today: date) -> None:
        det = scan.detection
        warn = self.config.inventory.expiry_warn_days
        dest = location.name if location is not None else "no storage location"
        if scan.payload is not None:
            from pantrysort.sim.scan_display import expiry_status

            status, _ = expiry_status(det.expiration_date, today, warn)
            logger.info(
                "Scanned [%s] %s | %s | %s kcal | allergens: %s | exp %s (%s) -> %s",
                scan.source, det.label, det.category.value,
                det.unit_calories if det.unit_calories is not None else "-",
                ", ".join(det.allergens) or "none", det.expiration_date or "-", status, dest,
            )
        display = getattr(station, "scan_display", None)
        if display is None:
            return
        from pantrysort.sim.scan_display import ScanInfo, render_scan_card

        card = render_scan_card(
            ScanInfo(
                detection=det if scan.payload is not None else None,
                destination=dest,
                raw_text=scan.raw_text,
                lot=scan.payload.lot if scan.payload else None,
                camera_view=scan.image,
                qr_corners=scan.corners,
            ),
            today, warn,
        )
        display.show(card, station.context.get_time())

    # ------------------------------------------------------------------ motion

    def _pick_and_place(self, station, scene_item: SceneItem, detection: Detection,
                        location_id: str) -> None:
        from pantrysort.sim.pick_and_place import execute_pick_and_place

        shape = scene_item.shape
        # Items sharing a location fill the pad's slots, then stack.
        drop, yaw = self._pads.place(location_id, shape.size[2])
        execute_pick_and_place(
            station,
            self.policy,
            grasp_position=np.asarray(scene_item.position, dtype=float),
            drop_position=np.asarray(drop, dtype=float),
            grasp_width=shape.grip_width,
            drop_yaw=yaw,
        )

    def _log_report(self) -> None:
        summary = self.store.summary()
        warn = self.config.inventory.expiry_warn_days
        soon = self.store.expiring_soon(warn)
        logger.info("--- Inventory summary ---")
        logger.info(
            "items=%d units=%d total_calories=%d (~%.1f day-servings @2000kcal)",
            summary.total_items,
            summary.total_units,
            summary.total_calories,
            summary.total_calories / 2000 if summary.total_calories else 0.0,
        )
        txs = self.store.transactions()
        names = {t.item_id: t.note for t in txs if t.transaction_type is TransactionType.INTAKE}
        for t in txs:
            if t.transaction_type is TransactionType.DISCARD:
                logger.info("Discarded: %s (%s)", names.get(t.item_id, t.item_id), t.note)
        if soon:
            logger.info("Expiring within %d days (distribute first):", warn)
            for item in self.store.distribution_queue():
                d = item.days_until_expiry()
                if d is not None and d <= warn:
                    logger.info("  %-24s in %d days", item.name, d)


def main() -> None:
    """Console-script entry point (`pantrysort-sim`)."""
    from rich.logging import RichHandler

    logging.basicConfig(
        level=CONFIG.log_level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )
    loop = SortLoop()
    result = loop.run()
    logger.info("Done. Sorted %d item(s).", result.num_sorted)


if __name__ == "__main__":
    main()
