"""Tests for the overhead fisheye camera (localization).

Two layers:
  * pure math (CameraModel back-projection, apply_fisheye) with no Drake, and
  * a Drake-gated integration test that renders the real scene and checks that
    a known item back-projects near its true world position.
"""

from __future__ import annotations

import numpy as np
import pytest

from pantrysort.sim.camera import CameraModel, apply_fisheye, look_at_rotation


def _down_camera(z: float = 0.45) -> CameraModel:
    R = look_at_rotation([0, 0, z], [0, 0, 0])
    X = np.eye(4)
    X[:3, :3] = R
    X[:3, 3] = [0, 0, z]
    return CameraModel(width=640, height=480, fx=400, fy=400, cx=319.5, cy=239.5, X_WC=X)


def test_center_projects_to_principal_point():
    cm = _down_camera()
    u, v, d = cm.world_to_pixel([0, 0, 0])
    assert abs(u - cm.cx) < 1e-6
    assert abs(v - cm.cy) < 1e-6
    assert abs(d - 0.45) < 1e-6


@pytest.mark.parametrize("p", [(0, 0, 0), (0.05, -0.03, 0.02), (-0.04, 0.06, 0.0)])
def test_pixel_world_roundtrip(p):
    cm = _down_camera()
    u, v, d = cm.world_to_pixel(p)
    back = cm.pixel_to_world(u, v, d)
    assert np.allclose(back, p, atol=1e-6), f"{back} != {p}"


def test_apply_fisheye_preserves_shape_and_dtype():
    cm = _down_camera()
    rgba = (np.random.default_rng(0).random((480, 640, 4)) * 255).astype(np.uint8)
    out = apply_fisheye(rgba, cm)
    assert out.shape == rgba.shape
    assert out.dtype == np.uint8

    rgb = (np.random.default_rng(1).random((480, 640, 3)) * 255).astype(np.uint8)
    out3 = apply_fisheye(rgb, cm)
    assert out3.shape == rgb.shape


def test_apply_fisheye_rejects_non_uint8():
    cm = _down_camera()
    with pytest.raises(TypeError):
        apply_fisheye(np.zeros((480, 640, 3), dtype=np.float32), cm)


# --------------------------------------------------------------- Drake integration

pytest.importorskip("pydrake", reason="pydrake not installed")


def _station():
    from pantrysort.config import SimConfig
    from pantrysort.sim.station import build_station

    return build_station(
        config=SimConfig(meshcat=False, qr_scanner=False, overhead_camera=True)
    )


def test_rig_has_cameras():
    st = _station()
    if not st.cameras:
        pytest.skip("VTK renderer unavailable in this environment")
    assert "robot_cam" in st.camera_names()


def test_camera_renders_frames():
    st = _station()
    if not st.cameras:
        pytest.skip("VTK renderer unavailable in this environment")
    rgb = st.camera_rgb("robot_cam")
    depth = st.camera_depth("robot_cam")
    fe = st.camera_fisheye("robot_cam")
    assert rgb.shape[2] == 4 and rgb.dtype == np.uint8
    assert depth.dtype == np.float32
    assert fe.shape == rgb.shape


def test_item_localizes_near_truth():
    st = _station()
    if not st.cameras:
        pytest.skip("VTK renderer unavailable in this environment")
    cm = st.camera_model("robot_cam")
    # Find any in-frame item the base camera can localize, assert it is close.
    localized = 0
    for item in st.scene.items:
        p_true = np.array(item.position, dtype=float)
        u, v, d = cm.world_to_pixel(p_true)
        if not (0 <= u < cm.width and 0 <= v < cm.height and d > 0):
            continue
        p_est = st.locate_pixel(u, v, "robot_cam")
        if p_est is None:
            continue
        if (abs(p_est[0] - p_true[0]) < 0.03 and abs(p_est[1] - p_true[1]) < 0.03):
            localized += 1
    assert localized >= 1, "base camera localized no item near truth"
