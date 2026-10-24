"""A wide-FOV camera for the pantry station, with fisheye post-distortion and
pixel -> world back-projection for object localization.

Drake's ``RgbdSensor`` is a pinhole camera; there is no true fisheye intrinsic
model. We approximate a fisheye by rendering with a wide field of view and then
applying an OpenCV fisheye distortion to the RGB frame (``apply_fisheye``). That
distorted image is what a perception policy "sees".

For *localization* we use the clean pinhole model plus the rendered depth image:
``CameraModel.pixel_to_world`` back-projects a pixel + its depth into a
world-frame point. This is deliberately done on the undistorted pinhole frame so
object positions stay accurate even though the cosmetic RGB is distorted.

The camera is mounted on a configurable parent frame (default: the world,
positioned above and behind the arm looking down at the intake area). It can be
re-parented to e.g. the rotation base (``shoulder_link``) by passing a different
``parent_frame`` to :func:`add_camera`.

All pydrake imports are local to functions so this module imports without Drake;
``apply_fisheye`` / intrinsics math are pure numpy+OpenCV and are unit-tested
without a simulator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

# Default overhead camera: above and behind the arm base, tilted down over the
# intake grid (x in ~[0.15, 0.30], y in ~[-0.08, 0.08]).
DEFAULT_CAMERA_XYZ = (-0.15, 0.0, 0.45)
# Look roughly at the center of the intake area from that mount.
DEFAULT_LOOK_AT = (0.22, 0.0, 0.03)
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480
# Wide vertical FOV to emulate a fisheye's broad coverage (radians).
DEFAULT_FOV_Y = np.radians(90.0)
# OpenCV fisheye distortion coefficients (k1, k2, k3, k4). Positive k1 gives the
# characteristic barrel bulge. Cosmetic only; tune to taste.
DEFAULT_FISHEYE_D = (0.35, 0.08, 0.0, 0.0)

RENDERER_NAME = "overhead_cam"


def look_at_rotation(eye: np.ndarray, target: np.ndarray, up=(0.0, 0.0, 1.0)):
    """Rotation matrix (as a 3x3 numpy array) for a camera at ``eye`` looking at
    ``target``, using Drake's camera convention: +z forward (into the scene),
    +x right, +y down.
    """
    eye = np.asarray(eye, dtype=float)
    target = np.asarray(target, dtype=float)
    forward = target - eye
    forward /= np.linalg.norm(forward)
    up = np.asarray(up, dtype=float)
    # Camera +x = right = forward x up_world; guard against degeneracy.
    right = np.cross(forward, up)
    nr = np.linalg.norm(right)
    if nr < 1e-9:
        up = np.array([0.0, 1.0, 0.0])
        right = np.cross(forward, up)
        nr = np.linalg.norm(right)
    right /= nr
    down = np.cross(forward, right)  # +y of a Drake camera points down
    # Columns are the camera axes expressed in world coordinates.
    return np.column_stack([right, down, forward])


@dataclass
class CameraModel:
    """Pinhole intrinsics + world pose, enough to back-project pixels to world.

    ``X_WC`` is the 4x4 camera-to-world homogeneous transform (camera frame:
    +z forward, +x right, +y down).
    """

    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    X_WC: np.ndarray  # 4x4

    @property
    def K(self) -> np.ndarray:
        return np.array([[self.fx, 0.0, self.cx],
                         [0.0, self.fy, self.cy],
                         [0.0, 0.0, 1.0]])

    def pixel_to_world(self, u: float, v: float, depth: float) -> np.ndarray:
        """Back-project pixel ``(u, v)`` at ``depth`` (m along +z) into world xyz."""
        x = (u - self.cx) / self.fx * depth
        y = (v - self.cy) / self.fy * depth
        p_cam = np.array([x, y, depth, 1.0])
        return (self.X_WC @ p_cam)[:3]

    def world_to_pixel(self, p_world) -> tuple[float, float, float]:
        """Project a world point to (u, v, depth). depth is +z in the camera."""
        p = np.asarray(p_world, dtype=float)
        X_CW = np.linalg.inv(self.X_WC)
        pc = X_CW @ np.array([p[0], p[1], p[2], 1.0])
        depth = pc[2]
        u = self.fx * pc[0] / depth + self.cx
        v = self.fy * pc[1] / depth + self.cy
        return float(u), float(v), float(depth)


def apply_fisheye(rgb: np.ndarray, model: CameraModel,
                  D=DEFAULT_FISHEYE_D) -> np.ndarray:
    """Return a fisheye-distorted copy of ``rgb`` using OpenCV's fisheye model.

    ``rgb`` may be HxWx3 or HxWx4 (Drake gives RGBA); the alpha channel, if any,
    is preserved. Distortion is cosmetic (for the perception image); it does not
    affect localization, which uses the undistorted pinhole model.
    """
    import cv2

    img = np.asarray(rgb)
    if img.dtype != np.uint8:
        raise TypeError(f"expected uint8 image, got {img.dtype}")
    K = model.K
    Dv = np.asarray(D, dtype=float).reshape(4, 1)
    # undistortMap for fisheye: build remap tables once per call (fine for a sim).
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(
        K, Dv, np.eye(3), K, (model.width, model.height), cv2.CV_16SC2
    )
    channels = img.shape[2] if img.ndim == 3 else 1
    if channels == 4:
        rgb3 = cv2.remap(img[:, :, :3], map1, map2, interpolation=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT)
        a = cv2.remap(img[:, :, 3], map1, map2, interpolation=cv2.INTER_NEAREST,
                      borderMode=cv2.BORDER_CONSTANT)
        return np.dstack([rgb3, a])
    return cv2.remap(img, map1, map2, interpolation=cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT)


def add_camera(
    builder: Any,
    plant: Any,
    scene_graph: Any,
    *,
    parent_frame: str | None = None,
    camera_xyz: tuple[float, float, float] = DEFAULT_CAMERA_XYZ,
    look_at: tuple[float, float, float] = DEFAULT_LOOK_AT,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fov_y: float = DEFAULT_FOV_Y,
    name: str = "overhead_camera",
):
    """Add a wide-FOV RgbdSensor to the station. Call before ``plant.Finalize``
    is NOT required for the sensor itself, but the parent frame (if any) must
    exist. Returns the ``RgbdSensor`` system, or ``None`` if VTK is unavailable.

    When ``parent_frame`` is None the camera is fixed in the world. Otherwise it
    is mounted on that body frame (e.g. ``shoulder_link``, the rotation base) and
    moves with it.
    """
    from pydrake.geometry import (
        ClippingRange,
        ColorRenderCamera,
        DepthRange,
        DepthRenderCamera,
        MakeRenderEngineVtk,
        RenderCameraCore,
        RenderEngineVtkParams,
    )
    from pydrake.math import RigidTransform, RotationMatrix
    from pydrake.systems.sensors import CameraInfo, RgbdSensor

    if not scene_graph.HasRenderer(RENDERER_NAME):
        try:
            scene_graph.AddRenderer(RENDERER_NAME, MakeRenderEngineVtk(RenderEngineVtkParams()))
        except Exception:
            return None

    R_WC = RotationMatrix(look_at_rotation(camera_xyz, look_at))
    X_WC = RigidTransform(R_WC, list(camera_xyz))

    core = RenderCameraCore(
        RENDERER_NAME, CameraInfo(width, height, fov_y),
        ClippingRange(0.01, 5.0), RigidTransform(),
    )
    color_cam = ColorRenderCamera(core, show_window=False)
    depth_cam = DepthRenderCamera(core, DepthRange(0.05, 4.0))

    if parent_frame is None:
        parent_id = scene_graph.world_frame_id()
        X_PC = X_WC
    else:
        body = plant.GetFrameByName(parent_frame).body()
        parent_id = plant.GetBodyFrameIdOrThrow(body.index())
        X_PC = X_WC  # caller supplies the pose already in the desired frame

    sensor = builder.AddSystem(RgbdSensor(parent_id, X_PC, color_cam, depth_cam))
    sensor.set_name(name)
    builder.Connect(scene_graph.get_query_output_port(), sensor.query_object_input_port())
    return sensor


def camera_model_from_sensor(sensor: Any, context: Any) -> CameraModel:
    """Build a :class:`CameraModel` (intrinsics + world pose) from a live sensor."""
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