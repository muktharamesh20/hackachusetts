"""A configurable multi-camera rig for the pantry station.

Cameras localize and (close enough) identify items from several viewpoints.
None are overhead or on the gripper. Two kinds of mount are supported:

  * ``world``        - a static camera fixed in the world at a chosen pose.
  * a body frame     - a camera that rides a robot link (e.g. ``shoulder_link``,
                       the rotation base: upright, yaws with ``shoulder_pan``).

Each camera is declared by a :class:`CameraSpec` (position + look-at target +
FOV + resolution). The default rig has the robot camera on ``shoulder_link`` and
one static camera viewing from the opposite side; add more by extending the
list or loading one from YAML (:func:`load_rig`).

Drake's ``RgbdSensor`` is a pinhole camera; we approximate a fisheye by
rendering wide-FOV and distorting the RGB with OpenCV (``apply_fisheye``).
Localization uses the clean pinhole model + rendered depth
(``CameraModel.pixel_to_world``), so object positions stay accurate even though
the cosmetic RGB is distorted.

``apply_fisheye`` / intrinsics / homography math are pure numpy+OpenCV and are
unit-tested without a simulator; pydrake imports stay inside functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

RENDERER_NAME = "rig_cam"

# OpenCV fisheye distortion coefficients (k1, k2, k3, k4); positive k1 = barrel.
DEFAULT_FISHEYE_D = (0.55, 0.15, 0.03, 0.0)  # ~160 deg USB wide-angle base lens

# iPhone back (main) camera: ~26mm-equiv, roughly 70 deg horizontal / ~55 deg
# vertical FOV on 4:3, and well-corrected optics (near-zero fisheye distortion).
IPHONE_FOV_Y = np.radians(55.0)
IPHONE_FISHEYE_D = (0.02, 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class CameraSpec:
    """Declarative placement of one camera.

    ``mount`` is ``"world"`` for a static camera, or a body-frame name
    (e.g. ``"shoulder_link"``) to ride a robot link. ``xyz`` / ``look_at`` are
    expressed in the mount frame (world coordinates for a static camera, the
    body frame for a mounted one). ``fov_y`` is the vertical field of view (rad).
    """

    name: str
    xyz: tuple[float, float, float]
    look_at: tuple[float, float, float]
    mount: str = "world"
    width: int = 640
    height: int = 480
    fov_y: float = np.radians(90.0)
    fisheye: tuple[float, float, float, float] = DEFAULT_FISHEYE_D


def default_rig() -> list[CameraSpec]:
    """Robot camera on the rotation base + one static camera from the far side.

    The arm base sits near the origin facing +x; the intake grid is in front
    (x in ~[0.15, 0.30]). The robot camera rides ``shoulder_link`` looking
    forward and slightly down; the static camera sits past the intake area
    looking back toward the arm, so the two views are roughly opposed and an
    item occluded in one is visible in the other.
    """
    return [
        CameraSpec(
            name="robot_cam",
            mount="shoulder_link",
            # Real lens: 8MP USB wide-angle, 160 deg FOV, back plate flush to the
            # limb. WORLD pose at rest: clear of the arm body, looking out over
            # the intake grid; it then rides shoulder_link (upright, yaws with
            # shoulder_pan). On a 4:3 sensor 160 deg horizontal ~ 125 deg vertical.
            xyz=(0.12, 0.0, 0.22),
            look_at=(0.25, 0.0, 0.02),
            width=1280,
            height=960,
            fov_y=np.radians(125.0),
        ),
        # External iPhone back cameras (main ~26mm-equiv, 4:3, low distortion)
        # at the front corners of the intake grid, ~0.30 m out and angled inward:
        # close enough to decode side stickers (and for the arm to lift an item
        # up to), but off to the corners so they do not block the arm's forward
        # or side swing. look_at is also the world point each is meant to watch.
        CameraSpec(
            name="iphone_left",
            mount="world",
            xyz=(0.34, -0.26, 0.18),
            look_at=(0.22, 0.0, 0.03),
            width=1280,
            height=960,
            fov_y=IPHONE_FOV_Y,
            fisheye=IPHONE_FISHEYE_D,
        ),
        CameraSpec(
            name="iphone_right",
            mount="world",
            xyz=(0.34, 0.26, 0.18),
            look_at=(0.22, 0.0, 0.03),
            width=1280,
            height=960,
            fov_y=IPHONE_FOV_Y,
            fisheye=IPHONE_FISHEYE_D,
        ),
    ]


# --------------------------------------------------------------- geometry / model


def look_at_rotation(eye, target, up=(0.0, 0.0, 1.0)) -> np.ndarray:
    """3x3 rotation for a camera at ``eye`` looking at ``target`` using Drake's
    camera convention (+z forward into the scene, +x right, +y down)."""
    eye = np.asarray(eye, dtype=float)
    target = np.asarray(target, dtype=float)
    forward = target - eye
    n = np.linalg.norm(forward)
    if n < 1e-9:
        raise ValueError("camera eye and look_at coincide")
    forward /= n
    up = np.asarray(up, dtype=float)
    right = np.cross(forward, up)
    nr = np.linalg.norm(right)
    if nr < 1e-6:  # looking straight up/down: pick another up
        up = np.array([0.0, 1.0, 0.0])
        right = np.cross(forward, up)
        nr = np.linalg.norm(right)
    right /= nr
    down = np.cross(forward, right)
    return np.column_stack([right, down, forward])


@dataclass
class CameraModel:
    """Pinhole intrinsics + world pose; enough to back-project pixels to world.

    ``X_WC`` is the 4x4 camera-to-world transform (camera: +z fwd, +x right,
    +y down).
    """

    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    X_WC: np.ndarray

    @property
    def K(self) -> np.ndarray:
        return np.array([[self.fx, 0.0, self.cx],
                         [0.0, self.fy, self.cy],
                         [0.0, 0.0, 1.0]])

    def pixel_to_world(self, u: float, v: float, depth: float) -> np.ndarray:
        x = (u - self.cx) / self.fx * depth
        y = (v - self.cy) / self.fy * depth
        return (self.X_WC @ np.array([x, y, depth, 1.0]))[:3]

    def world_to_pixel(self, p_world) -> tuple[float, float, float]:
        p = np.asarray(p_world, dtype=float)
        pc = np.linalg.inv(self.X_WC) @ np.array([p[0], p[1], p[2], 1.0])
        depth = pc[2]
        return (float(self.fx * pc[0] / depth + self.cx),
                float(self.fy * pc[1] / depth + self.cy),
                float(depth))


def apply_fisheye(rgb: np.ndarray, model: CameraModel, D=DEFAULT_FISHEYE_D) -> np.ndarray:
    """Fisheye-distorted copy of ``rgb`` (HxWx3 or HxWx4 uint8). Cosmetic only."""
    import cv2

    img = np.asarray(rgb)
    if img.dtype != np.uint8:
        raise TypeError(f"expected uint8 image, got {img.dtype}")
    K = model.K
    Dv = np.asarray(D, dtype=float).reshape(4, 1)
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(
        K, Dv, np.eye(3), K, (model.width, model.height), cv2.CV_16SC2
    )
    if img.ndim == 3 and img.shape[2] == 4:
        rgb3 = cv2.remap(img[:, :, :3], map1, map2, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        a = cv2.remap(img[:, :, 3], map1, map2, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT)
        return np.dstack([rgb3, a])
    return cv2.remap(img, map1, map2, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


# --------------------------------------------------------------- homography helper


def homography_from_points(image_pts: np.ndarray, world_pts_xy: np.ndarray) -> np.ndarray:
    """3x3 homography mapping world ground-plane (x, y, 1) -> image (u, v, 1).

    A simple way to configure a static camera's ground mapping from >= 4 known
    correspondences (e.g. tape marks on the table seen in the image), without a
    full pose. ``image_pts`` is Nx2 pixels; ``world_pts_xy`` is Nx2 world x,y on
    z=0. Use :func:`ground_pixel_to_world` to invert it for localization.
    """
    import cv2

    image_pts = np.asarray(image_pts, dtype=np.float64)
    world_pts_xy = np.asarray(world_pts_xy, dtype=np.float64)
    if len(image_pts) < 4:
        raise ValueError("need >= 4 point correspondences for a homography")
    H, _ = cv2.findHomography(world_pts_xy, image_pts)
    return H


def ground_pixel_to_world(H: np.ndarray, u: float, v: float) -> tuple[float, float]:
    """Invert a ground homography: image (u, v) -> world (x, y) on z=0."""
    Hinv = np.linalg.inv(np.asarray(H, dtype=float))
    p = Hinv @ np.array([u, v, 1.0])
    return float(p[0] / p[2]), float(p[1] / p[2])


# --------------------------------------------------------------- Drake wiring


def _ensure_renderer(scene_graph) -> bool:
    from pydrake.geometry import MakeRenderEngineVtk, RenderEngineVtkParams

    if scene_graph.HasRenderer(RENDERER_NAME):
        return True
    try:
        scene_graph.AddRenderer(RENDERER_NAME, MakeRenderEngineVtk(RenderEngineVtkParams()))
        return True
    except Exception:
        return False


def add_camera(builder: Any, plant: Any, scene_graph: Any, spec: CameraSpec):
    """Add one :class:`CameraSpec` to the station. Returns the ``RgbdSensor`` or
    ``None`` if VTK is unavailable."""
    from pydrake.geometry import (
        ClippingRange,
        ColorRenderCamera,
        DepthRange,
        DepthRenderCamera,
        RenderCameraCore,
    )
    from pydrake.math import RigidTransform, RotationMatrix
    from pydrake.systems.sensors import CameraInfo, RgbdSensor

    if not _ensure_renderer(scene_graph):
        return None

    # spec.xyz / spec.look_at are always WORLD coordinates: the pose the camera
    # should have when the arm is at rest. For a mounted camera we convert that
    # world pose into the parent body frame (X_PC = X_WP^-1 . X_WC) so it then
    # rides the body; for a static camera the world pose is used directly.
    R_WC = RotationMatrix(look_at_rotation(spec.xyz, spec.look_at))
    X_WC = RigidTransform(R_WC, list(spec.xyz))

    core = RenderCameraCore(
        RENDERER_NAME, CameraInfo(spec.width, spec.height, spec.fov_y),
        ClippingRange(0.01, 6.0), RigidTransform(),
    )
    color_cam = ColorRenderCamera(core, show_window=False)
    depth_cam = DepthRenderCamera(core, DepthRange(0.03, 5.0))

    if spec.mount == "world":
        parent_id = scene_graph.world_frame_id()
        X_PC = X_WC
    else:
        body = plant.GetFrameByName(spec.mount).body()
        parent_id = plant.GetBodyFrameIdOrThrow(body.index())
        # Convert the world camera pose into the parent body frame at rest.
        plant_ctx = plant.CreateDefaultContext()
        X_WP = plant.GetFrameByName(spec.mount).CalcPoseInWorld(plant_ctx)
        X_PC = X_WP.inverse().multiply(X_WC)

    sensor = builder.AddSystem(RgbdSensor(parent_id, X_PC, color_cam, depth_cam))
    sensor.set_name(f"cam_{spec.name}")
    builder.Connect(scene_graph.get_query_output_port(), sensor.query_object_input_port())
    return sensor


def add_rig(builder, plant, scene_graph, specs: list[CameraSpec]) -> dict[str, Any]:
    """Add every camera in ``specs``. Returns {name: RgbdSensor} (skips any that
    fail to create)."""
    cams: dict[str, Any] = {}
    for spec in specs:
        sensor = add_camera(builder, plant, scene_graph, spec)
        if sensor is not None:
            cams[spec.name] = sensor
    return cams


def camera_model_from_sensor(sensor: Any, context: Any) -> CameraModel:
    """Live intrinsics + world pose for a sensor (reflects any parent motion)."""
    core = sensor.default_color_render_camera().core()
    info = core.intrinsics()
    sensor_ctx = sensor.GetMyContextFromRoot(context)
    X_WC = sensor.body_pose_in_world_output_port().Eval(sensor_ctx)
    return CameraModel(
        width=info.width(), height=info.height(),
        fx=info.focal_x(), fy=info.focal_y(),
        cx=info.center_x(), cy=info.center_y(),
        X_WC=X_WC.GetAsMatrix4(),
    )


def load_rig(path) -> list[CameraSpec]:
    """Load a camera rig from a YAML file. Each entry maps to a CameraSpec; any
    omitted field uses the CameraSpec default. Degrees are accepted for fov via
    ``fov_deg``."""
    import yaml

    with open(path) as f:
        data = yaml.safe_load(f) or []
    specs: list[CameraSpec] = []
    for entry in data:
        e = dict(entry)
        if "fov_deg" in e:
            e["fov_y"] = np.radians(e.pop("fov_deg"))
        for key in ("xyz", "look_at"):
            if key in e:
                e[key] = tuple(float(v) for v in e[key])
        if "fisheye" in e:
            e["fisheye"] = tuple(float(v) for v in e["fisheye"])
        specs.append(CameraSpec(**e))
    return specs
