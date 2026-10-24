"""Tests for the overhead fisheye camera (localization).

Two layers:
  * pure math (CameraModel back-projection, apply_fisheye) with no Drake, and
  * a Drake-gated integration test that renders the real scene and checks that
    a known item back-projects near its true world position.
"""

from __future__ import annotations

import numpy as np
import pytest

from pantrysort.sim import pantry_scene as ps
from pantrysort.sim.camera import (
    CameraModel,
    CameraSpec,
    apply_fisheye,
    default_rig,
    load_rig,
    look_at_rotation,
    presentation_cameras,
)


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


# --------------------------------------------------------------- rig placement


def _spec_model(spec: CameraSpec) -> CameraModel:
    """Pinhole model matching Drake's CameraInfo(width, height, fov_y)."""
    f = spec.height / 2.0 / np.tan(spec.fov_y / 2.0)
    X = np.eye(4)
    X[:3, :3] = look_at_rotation(spec.xyz, spec.look_at)
    X[:3, 3] = spec.xyz
    return CameraModel(width=spec.width, height=spec.height, fx=f, fy=f,
                       cx=spec.width / 2.0 - 0.5, cy=spec.height / 2.0 - 0.5, X_WC=X)


def _presenters():
    rig = default_rig()
    names = presentation_cameras(rig)
    return [s for s in rig if s.name in names]


def test_default_rig_has_presentation_cameras_but_not_robot_cam():
    names = presentation_cameras(default_rig())
    assert set(names) == {"iphone_left", "iphone_right"}
    assert "robot_cam" not in names


def test_presentation_cameras_requires_present_at():
    specs = [
        CameraSpec(name="a", xyz=(0.4, 0, 0.1), look_at=(0.2, 0, 0.1), present=True),
        CameraSpec(name="b", xyz=(0.4, 0, 0.1), look_at=(0.2, 0, 0.1),
                   present_at=(0.25, 0, 0.1)),
        CameraSpec(name="c", xyz=(0.4, 0, 0.1), look_at=(0.2, 0, 0.1), present=True,
                   present_at=(0.25, 0, 0.1)),
    ]
    assert presentation_cameras(specs) == ["c"]


@pytest.mark.parametrize("spec", _presenters(), ids=lambda s: s.name)
def test_presentation_camera_placement(spec):
    """Property 6: camera clear of belt/boxes/bins and above the rims; present_at
    on the optical axis, at a reachable radius/height, near the image center."""
    cam = np.asarray(spec.xyz, dtype=float)
    at = np.asarray(spec.present_at, dtype=float)
    rim_z = ps.BELT_TOP + ps.DONATION_BOX_SIZE[2]

    # Outside the belt footprint (and so every queued box, which sits on it).
    belt_x = (ps.BELT_X - ps.BELT_WIDTH / 2, ps.BELT_X + ps.BELT_WIDTH / 2)
    assert not (belt_x[0] <= cam[0] <= belt_x[1] and abs(cam[1]) <= ps.BELT_HALF_LENGTH)
    for k in range(-4, 5):  # queued box footprints along the belt line
        bx, by = ps.BELT_X, ps.STATION_Y + k * ps.BOX_PITCH
        inside = (abs(cam[0] - bx) <= ps.DONATION_BOX_SIZE[0] / 2
                  and abs(cam[1] - by) <= ps.DONATION_BOX_SIZE[1] / 2)
        assert not inside, f"camera inside box footprint at y={by}"
    for loc, (x, y, _z) in ps.LOCATION_DROP_POINTS.items():
        assert np.hypot(cam[0] - x, cam[1] - y) > max(ps.PAD_SIZE), f"camera on bin {loc}"
    assert cam[2] > rim_z

    # present_at lies on the optical axis, 0.12-0.18 m from the lens.
    axis = np.asarray(spec.look_at, dtype=float) - cam
    axis /= np.linalg.norm(axis)
    rel = at - cam
    along = float(rel @ axis)
    off_axis = float(np.linalg.norm(rel - along * axis))
    assert off_axis < 0.01
    assert 0.12 <= along <= 0.18

    radius = np.hypot(at[0] - ps.PAN_AXIS_XY[0], at[1] - ps.PAN_AXIS_XY[1])
    assert 0.15 <= radius <= 0.30
    assert at[2] >= 0.10

    m = _spec_model(spec)
    u, v, d = m.world_to_pixel(at)
    assert d > 0
    assert abs(u - m.cx) < 0.05 * m.width and abs(v - m.cy) < 0.05 * m.height

    # Still watches the pick station for the passive identification pass.
    u, v, d = m.world_to_pixel((ps.BELT_X, ps.STATION_Y, ps.BOX_FLOOR_TOP + 0.02))
    assert d > 0 and 0 <= u < m.width and 0 <= v < m.height


def test_load_rig_roundtrips_presentation_fields(tmp_path):
    path = tmp_path / "rig.yaml"
    path.write_text(
        "- name: stand_cam\n"
        "  xyz: [0.37, -0.2, 0.15]\n"
        "  look_at: [0.25, -0.1, 0.13]\n"
        "  fov_deg: 55\n"
        "  present: true\n"
        "  present_at: [0.25, -0.1, 0.13]\n"
        "- name: plain_cam\n"
        "  xyz: [0.4, 0, 0.2]\n"
        "  look_at: [0.2, 0, 0]\n"
    )
    specs = load_rig(path)
    stand, plain = specs
    assert stand.present is True
    assert stand.present_at == (0.25, -0.1, 0.13)
    assert all(isinstance(v, float) for v in stand.present_at)
    assert plain.present is False and plain.present_at is None
    assert presentation_cameras(specs) == ["stand_cam"]


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
