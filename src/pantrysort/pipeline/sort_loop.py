"""The end-to-end pantry sort loop.

For each detected item:
  1. classify it (category, calories, expiry, allergens),
  2. decide its storage location from the inventory store's routing,
  3. drive the robot (scripted or LeRobot policy) to pick it from the bin and
     place it at that location's drop point, and
  4. record it in the inventory (intake transaction).

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
from typing import Optional

import numpy as np

from pantrysort.config import CONFIG, Config
from pantrysort.inventory.models import InventoryItem
from pantrysort.inventory.base import InventoryStoreProtocol
from pantrysort.inventory.factory import make_store
from pantrysort.perception.classifier import Detection
from pantrysort.policy.lerobot_policy import Policy, make_policy
from pantrysort.sim.pantry_scene import (
    PadLayout,
    PantryScene,
    default_scene,
)

logger = logging.getLogger("pantrysort.sort_loop")


@dataclass
class SortResult:
    sorted_items: list[InventoryItem] = field(default_factory=list)
    unresolved: list[Detection] = field(default_factory=list)

    @property
    def num_sorted(self) -> int:
        return len(self.sorted_items)


class SortLoop:
    def __init__(
        self,
        scene: Optional[PantryScene] = None,
        store: Optional[InventoryStoreProtocol] = None,
        policy: Optional[Policy] = None,
        config: Config = CONFIG,
        use_sim: bool = True,
    ) -> None:
        self.config = config
        self.scene = scene or default_scene()
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

    def run(self, today: Optional[date] = None) -> SortResult:
        today = today or date.today()
        result = SortResult()
        station = self._maybe_build_station()
        self._pads = PadLayout()
        if station is not None:
            station.start_recording()

        for detection in self.scene.detections(today):
            location = self.store.location_for_category(detection.category)
            if location is None:
                logger.warning("No storage location for %s; skipping.", detection.label)
                result.unresolved.append(detection)
                continue

            # Drive the robot to move the item, if a station is available.
            if station is not None:
                self._pick_and_place(station, detection, location.id)

            item = detection.to_item()
            item.location_id = location.id
            self.store.intake(item)
            result.sorted_items.append(item)
            logger.info(
                "Sorted %-24s -> %-18s (cal=%s, exp=%s)",
                detection.label,
                location.name,
                item.total_calories,
                item.expiration_date,
            )

        if station is not None:
            station.finish_recording()
        self._log_report()
        return result

    def _pick_and_place(self, station, detection: Detection, location_id: str) -> None:
        from pantrysort.sim.pantry_scene import BOX
        from pantrysort.sim.pick_and_place import execute_pick_and_place

        shapes = {it.label: it.shape for it in self.scene.items}
        shape = shapes.get(detection.label, BOX)
        # Items sharing a location fill the pad's slots, then stack.
        drop, yaw = self._pads.place(location_id, shape.size[2])
        execute_pick_and_place(
            station,
            self.policy,
            grasp_position=np.asarray(detection.position, dtype=float),
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
