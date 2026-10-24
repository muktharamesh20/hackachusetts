"""Tests for vision-based obstacle mapping and collision-aware stepping.

Pure numpy (no Drake): build a synthetic ObstacleMap and check plan_step /
lift_over_obstacles avoid it and respect the ground margin.
"""

from __future__ import annotations

import numpy as np

from pantrysort.sim.vision_path import (
    ObstacleMap,
    lift_over_obstacles,
    plan_step,
)


def _box_obstacle(center, half=0.03, n=5, ground_z=0.006):
    xs = np.linspace(center[0] - half, center[0] + half, n)
    ys = np.linspace(center[1] - half, center[1] + half, n)
    zs = np.linspace(center[2] - half, center[2] + half, n)
    pts = np.array([[x, y, z] for x in xs for y in ys for z in zs])
    return ObstacleMap(points=pts, ground_z=ground_z)


def test_hits_and_clearance():
    omap = _box_obstacle([0.2, 0.0, 0.05])
    assert omap.hits([0.2, 0.0, 0.05], radius=0.02)
    assert not omap.hits([0.2, 0.0, 0.30], radius=0.02)
    # below ground is always a hit
    assert omap.hits([0.2, 0.0, -0.01], radius=0.02)
    assert omap.min_clearance([0.2, 0.0, 0.30]) > 0.2


def test_empty_map_never_hits_above_ground():
    omap = ObstacleMap()
    assert not omap.hits([0.2, 0.0, 0.1], radius=0.05)
    assert omap.min_clearance([0.2, 0.0, 0.1]) == float("inf")


def test_plan_step_respects_ground_margin():
    omap = ObstacleMap(ground_z=0.006)
    ee = np.array([0.2, 0.0, 0.2])
    target = np.array([0.2, 0.0, -0.1])  # aim below ground
    step = plan_step(ee, target, omap, ground_margin=0.02)
    assert step[2] >= 0.006 + 0.02 - 1e-9


def test_plan_step_lifts_over_obstacle():
    omap = _box_obstacle([0.2, 0.0, 0.05])
    # Move straight through the obstacle at its height.
    ee = np.array([0.10, 0.0, 0.05])
    target = np.array([0.30, 0.0, 0.05])
    # Several steps; the planner should raise z above the obstacle top.
    heights = []
    for _ in range(10):
        ee = plan_step(ee, target, omap, ee_radius=0.05)
        heights.append(ee[2])
    assert max(heights) > 0.08, f"did not lift over obstacle: max z {max(heights):.3f}"


def test_lift_over_obstacles_keeps_xy():
    omap = _box_obstacle([0.2, 0.0, 0.05])
    ee = np.array([0.10, 0.0, 0.05])
    step = np.array([0.20, 0.0, 0.05])  # lands in the obstacle
    out = lift_over_obstacles(ee, step, omap, ee_radius=0.05)
    assert out[0] == step[0] and out[1] == step[1]  # x,y preserved
    assert out[2] > step[2]  # z raised to clear
