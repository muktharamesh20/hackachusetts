"""Drake-gated tests for active presentation: upright holding of a grasped item."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pydrake", reason="pydrake not installed")

DT = 0.05
TILT_MAX = np.deg2rad(5.0)


def _wrap(a: float) -> float:
    return float((a + np.pi) % (2 * np.pi) - np.pi)


def _grasp(station, label: str) -> str | None:
    body = station.item_bodies[label]
    p_item = np.asarray(station._body_pose(body).translation(), dtype=float)
    shape = station.item_shapes.get(label)
    if shape is not None:
        station.prepare_grasp(shape.grip_width)
    station.move_ee_to_smooth(p_item, DT)
    station.set_gripper(1.0)
    got = station.attach_nearest()
    station.publish(DT)
    return got


@pytest.fixture(scope="module")
def held_station():
    from pantrysort.config import SimConfig
    from pantrysort.sim.pantry_scene import scene_for_mode
    from pantrysort.sim.station import build_station

    st = build_station(scene_for_mode("flat_grid"),
                       SimConfig(meshcat=False, realtime_rate=0.0, qr_scanner=False))
    if not st.cameras:
        pytest.skip("VTK renderer unavailable in this environment")
    for item in st.scene.items:
        if _grasp(st, item.label) is not None:
            return st
        st.detach()
        st.set_gripper(0.0)
    pytest.skip("could not grasp any flat_grid item")


def _present_points(st):
    from pantrysort.sim.camera import presentation_cameras

    names = presentation_cameras(list(st.camera_specs.values()))
    assert names, "rig has no presentation cameras"
    assert "robot_cam" not in names
    return [(n, np.asarray(st.camera_specs[n].present_at, dtype=float)) for n in names]


def test_held_item_starts_upright(held_station):
    st = held_station
    assert st.holding
    up = st.held_item_up_in_hand()
    # Item up in hand is the item's own +z through X_HI and maps to ~world +z now.
    R_WH = st._X_WH().rotation().matrix()
    assert np.allclose(R_WH @ up, st._held_up_W, atol=1e-6)
    assert st.held_item_tilt() < TILT_MAX


@pytest.mark.skip(reason="upright IK in progress (task 12)")
def test_present_points_reachable_upright(held_station):
    from pantrysort.sim.active_scan import _reachable

    st = held_station
    up, x = st.held_item_up_in_hand(), st.held_item_x_in_hand()
    yaw = st.held_item_yaw()
    for name, p in _present_points(st):
        assert _reachable(st, p, tol=0.015, item_up_in_hand=up, item_yaw=yaw,
                          item_x_in_hand=x), f"{name} present_at {p} not reachable upright"


@pytest.mark.skip(reason="upright IK in progress (task 12)")
def test_move_held_upright_to_present_points(held_station):
    st = held_station
    for name, p in _present_points(st):
        yaw = st.held_item_yaw()
        assert st.move_held_upright_to(p, yaw, DT), f"upright IK failed for {name}"
        err = np.linalg.norm(st.ee_position() - p)
        tilt = st.held_item_tilt()
        dyaw = abs(_wrap(st.held_item_yaw() - yaw))
        print(f"{name}: pos_err={err * 100:.2f} cm tilt={np.rad2deg(tilt):.2f} deg "
              f"yaw_err={np.rad2deg(dyaw):.2f} deg")
        assert err < 0.015
        assert tilt < TILT_MAX
        assert dyaw < TILT_MAX


@pytest.mark.skip(reason="upright IK in progress (task 12)")
@pytest.mark.parametrize("turn_deg", [90.0, 180.0])
def test_yaw_targets_hit_while_upright(held_station, turn_deg):
    st = held_station
    name, p = _present_points(st)[0]
    assert st.move_held_upright_to(p, st.held_item_yaw(), DT)
    target = _wrap(st.held_item_yaw() + np.deg2rad(turn_deg))
    worst_tilt = 0.0

    def _sample(s):
        nonlocal worst_tilt
        worst_tilt = max(worst_tilt, s.held_item_tilt() or 0.0)

    st.frame_hooks.append(_sample)
    try:
        ok = st.move_held_upright_to(p, target, DT)
    finally:
        st.frame_hooks.remove(_sample)
    assert ok, f"upright IK failed for yaw +{turn_deg} deg at {name}"
    dyaw = abs(_wrap(st.held_item_yaw() - target))
    err = np.linalg.norm(st.ee_position() - p)
    print(f"{name} +{turn_deg:.0f} deg: yaw_err={np.rad2deg(dyaw):.2f} deg "
          f"tilt_end={np.rad2deg(st.held_item_tilt()):.2f} deg "
          f"worst_tilt={np.rad2deg(worst_tilt):.2f} deg pos_err={err * 100:.2f} cm")
    assert dyaw < TILT_MAX
    assert st.held_item_tilt() < TILT_MAX
    assert err < 0.015
