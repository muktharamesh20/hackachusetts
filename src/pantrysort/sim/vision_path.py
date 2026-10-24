"""Vision-based obstacle awareness and collision-aware end-effector stepping.

Obstacles are discovered from the cameras' depth images (not hardcoded), so the
planner tolerates differences between the sim and the real rig: whatever the
cameras see above the table becomes an obstacle. The arm plans short EE steps
that stay clear of those obstacle points and never dip below a ground margin.

Pipeline:
  * ``ObstacleMap.from_station`` back-projects each camera's depth to world
    points, drops the ground plane and points on/near the arm itself, and voxel-
    downsamples the rest into an obstacle point set.
  * ``plan_step`` takes the current EE position and a desired next position and
    returns a collision-aware step: if the straight step would pass too close to
    an obstacle (or below ``ground_margin``), it lifts/deflects the step to clear
    it. Repeated each control tick, this yields a path that goes over clutter.

Numpy only; pydrake stays in the station. The EE "radius" is a safety bubble
around the gripper/held item.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ObstacleMap:
    """A set of world-frame obstacle points inferred from camera depth."""

    points: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    ground_z: float = 0.006

    @classmethod
    def from_station(
        cls,
        station,
        *,
        stride: int = 10,
        ground_z: float = 0.006,
        max_depth: float = 2.0,
        arm_clearance: float = 0.09,
        voxel: float = 0.015,
        exclude_labels: tuple[str, ...] = (),
    ) -> ObstacleMap:
        """Build an obstacle map from every rig camera's current depth frame.

        Points at/below ``ground_z`` (the table) are dropped, as are points
        within ``arm_clearance`` of the arm's own links (so the arm is not its
        own obstacle). Remaining points are voxel-downsampled at ``voxel`` m.
        ``exclude_labels`` drops points near those item bodies (e.g. the item the
        arm is about to pick).
        """
        arm_pts = _arm_link_points(station)
        exclude_centers = _item_centers(station, exclude_labels)

        kept: list[np.ndarray] = []
        for name in station.camera_names():
            cm = station.camera_model(name)
            depth = station.camera_depth(name)
            if cm is None or depth is None:
                continue
            depth = np.asarray(depth).reshape(cm.height, cm.width)
            for v in range(0, cm.height, stride):
                for u in range(0, cm.width, stride):
                    d = float(depth[v, u])
                    if not np.isfinite(d) or d <= 0.02 or d > max_depth:
                        continue
                    p = cm.pixel_to_world(u, v, d)
                    if p[2] <= ground_z:
                        continue
                    if arm_pts.size and np.min(np.linalg.norm(arm_pts - p, axis=1)) < arm_clearance:
                        continue
                    if exclude_centers.size and np.min(
                        np.linalg.norm(exclude_centers - p, axis=1)) < 0.05:
                        continue
                    kept.append(p)
        pts = np.array(kept) if kept else np.zeros((0, 3))
        return cls(points=_voxel_downsample(pts, voxel), ground_z=ground_z)

    def min_clearance(self, p: np.ndarray) -> float:
        """Distance from ``p`` to the nearest obstacle point (inf if none)."""
        if self.points.shape[0] == 0:
            return float("inf")
        return float(np.min(np.linalg.norm(self.points - np.asarray(p, dtype=float), axis=1)))

    def hits(self, p: np.ndarray, radius: float) -> bool:
        """True if ``p`` is within ``radius`` of any obstacle or below ground."""
        p = np.asarray(p, dtype=float)
        if p[2] < self.ground_z:
            return True
        return self.min_clearance(p) < radius


def plan_step(
    ee: np.ndarray,
    target: np.ndarray,
    obstacles: ObstacleMap,
    *,
    ee_radius: float = 0.05,
    ground_margin: float = 0.02,
    rate: float = 0.25,
    lift: float = 0.04,
) -> np.ndarray:
    """Return a collision-aware next EE position stepping from ``ee`` toward ``target``.

    Takes a normal fraction-of-remaining step; if that candidate (or the segment
    to it) would come within ``ee_radius`` of an obstacle or below the ground
    margin, the step is raised by ``lift`` (and re-checked) so the arm goes over
    the obstacle rather than through it. Purely reactive and local, which keeps
    it robust to an imperfect/real obstacle map.
    """
    ee = np.asarray(ee, dtype=float)
    target = np.asarray(target, dtype=float)
    cand = ee + rate * (target - ee)
    min_z = obstacles.ground_z + ground_margin
    cand[2] = max(cand[2], min_z)

    # If the step is clear, take it.
    if not _segment_blocked(ee, cand, obstacles, ee_radius):
        return cand

    # Otherwise lift progressively until the raised step clears, capped so we
    # don't shoot off upward.
    for extra in (lift, 2 * lift, 3 * lift, 4 * lift):
        raised = cand.copy()
        raised[2] = max(cand[2] + extra, min_z)
        if not _segment_blocked(ee, raised, obstacles, ee_radius):
            return raised
    # Give up on clearing; at least stay above ground and nudge up.
    cand[2] = max(cand[2] + lift, min_z)
    return cand


def lift_over_obstacles(
    ee: np.ndarray,
    step: np.ndarray,
    obstacles: ObstacleMap,
    *,
    ee_radius: float = 0.05,
    ground_margin: float = 0.02,
    lift: float = 0.03,
    max_lift: float = 0.18,
) -> np.ndarray:
    """Keep `step`'s x,y (the swing already routes horizontally) but raise its
    z so the move from `ee` to it clears obstacles and the ground margin.

    Returns a possibly-higher step. Used to layer obstacle avoidance on top of
    the existing base-swing motion without changing its horizontal routing.
    """
    ee = np.asarray(ee, dtype=float)
    step = np.asarray(step, dtype=float).copy()
    min_z = obstacles.ground_z + ground_margin
    step[2] = max(step[2], min_z)
    extra = 0.0
    while extra <= max_lift and _segment_blocked(ee, step, obstacles, ee_radius):
        extra += lift
        step[2] = max(step[2] + lift, min_z)
    return step

def _segment_blocked(a: np.ndarray, b: np.ndarray, obstacles: ObstacleMap,
                     radius: float, samples: int = 4) -> bool:
    """True if the segment a->b passes within ``radius`` of any obstacle."""
    for t in np.linspace(0.0, 1.0, samples + 1):
        if obstacles.hits(a + t * (b - a), radius):
            return True
    return False


def _voxel_downsample(points: np.ndarray, voxel: float) -> np.ndarray:
    if points.shape[0] == 0 or voxel <= 0:
        return points
    keys = np.floor(points / voxel).astype(np.int64)
    _, idx = np.unique(keys, axis=0, return_index=True)
    return points[np.sort(idx)]


def _arm_link_points(station, samples_per_link: int = 4) -> np.ndarray:
    """Approximate world points along the arm's links, to mask the arm out of
    the obstacle cloud. Uses the plant's body origins (cheap and good enough for
    a clearance mask)."""
    try:
        plant = station.plant
        ctx = station.plant_context
        arm = station.arm
        pts = []
        for name in ("base_link", "shoulder_link", "upper_arm_link", "lower_arm_link",
                     "wrist_link", "gripper_link", "moving_jaw_so101_v1_link"):
            try:
                body = plant.GetBodyByName(name, arm)
            except Exception:
                continue
            pts.append(np.asarray(plant.EvalBodyPoseInWorld(ctx, body).translation(), dtype=float))
        # Interpolate between consecutive link origins for a denser mask.
        dense = []
        for i in range(len(pts) - 1):
            for t in np.linspace(0, 1, samples_per_link, endpoint=False):
                dense.append(pts[i] + t * (pts[i + 1] - pts[i]))
        dense.extend(pts)
        return np.array(dense) if dense else np.zeros((0, 3))
    except Exception:
        return np.zeros((0, 3))


def _item_centers(station, labels: tuple[str, ...]) -> np.ndarray:
    centers = []
    for lbl in labels:
        body = getattr(station, "item_bodies", {}).get(lbl)
        if body is not None:
            centers.append(np.asarray(station._body_pose(body).translation(), dtype=float))
    return np.array(centers) if centers else np.zeros((0, 3))
