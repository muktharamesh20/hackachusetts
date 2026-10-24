"""QR stickers on sim items, and the scan-result card shown in Meshcat.

* :func:`write_qr_label_mesh` turns a :class:`FoodQrPayload` into a thin textured
  quad (OBJ + MTL + PNG). The station attaches one to the top of every item, so
  the robot's scanner camera (and Meshcat) see a real, decodable QR code.
* :func:`render_scan_card` draws what the robot read from a label: product,
  expiry status, calories, allergens, destination bin, plus the camera's view.
* :class:`ScanDisplay` shows that card floating above the work area in Meshcat,
  one card per scan, with visibility keyed into the Meshcat recording so the
  replay shows each card while its item is being sorted.

Only numpy/Pillow at import time; pydrake is imported lazily.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from pantrysort.perception.classifier import Detection
from pantrysort.perception.qr_payload import FoodQrPayload

LABEL_MAX_SIZE = 0.036   # QR sticker edge (m); big enough to decode from ~9 cm
LABEL_FILL = 0.92        # sticker edge as a fraction of the item's smaller top dimension
LABEL_LIFT = 0.0008      # sticker sits this far above the item's bounding box top (m)


def label_size(item_size: tuple[float, float, float]) -> float:
    return min(LABEL_MAX_SIZE, LABEL_FILL * min(item_size[0], item_size[1]))


# --------------------------------------------------------------------------- meshes


def write_textured_quad(image: np.ndarray, out_dir: Path, name: str,
                        width: float, height: float) -> Path:
    """Write an OBJ quad (``width`` x ``height`` m, in its xy plane, facing +z)
    textured with ``image`` (top row of the image at +y). Returns the OBJ path."""
    import cv2

    out_dir.mkdir(parents=True, exist_ok=True)
    img = np.asarray(image)
    if img.ndim == 3 and img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    if not cv2.imwrite(str(out_dir / f"{name}.png"), img):
        raise OSError(f"failed to write texture {name}.png")
    (out_dir / f"{name}.mtl").write_text(
        f"newmtl {name}\nKa 1 1 1\nKd 1 1 1\nKs 0 0 0\nd 1\nillum 1\nmap_Kd {name}.png\n"
    )
    w, h = width / 2, height / 2
    obj = out_dir / f"{name}.obj"
    obj.write_text(
        f"mtllib {name}.mtl\n"
        f"v {-w} {-h} 0\nv {w} {-h} 0\nv {w} {h} 0\nv {-w} {h} 0\n"
        "vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\n"
        "vn 0 0 1\n"
        f"usemtl {name}\n"
        "f 1/1/1 2/2/1 3/3/1\nf 1/1/1 3/3/1 4/4/1\n"
    )
    return obj


def write_qr_label_mesh(payload: FoodQrPayload, out_dir: Path, name: str,
                        size: float) -> Path:
    """A ``size`` x ``size`` m QR sticker (quiet zone included) as a textured OBJ."""
    from pantrysort.perception.qr import make_qr_image

    return write_textured_quad(make_qr_image(payload, scale=8), out_dir, name, size, size)


# --------------------------------------------------------------------------- card


@dataclass(frozen=True)
class ScanInfo:
    """Everything the card shows about one scan."""

    detection: Detection | None   # None = no readable label
    destination: str              # storage location name
    raw_text: str | None = None   # decoded QR string
    lot: str | None = None
    camera_view: np.ndarray | None = None  # RGB(A) scanner frame
    qr_corners: np.ndarray | None = None   # 4x2 px corners in camera_view


_GREEN, _AMBER, _RED, _GRAY = (46, 160, 67), (230, 150, 20), (205, 45, 45), (110, 110, 120)

CARD_PX = (960, 540)  # (width, height)


def expiry_status(exp: date | None, today: date, warn_days: int) -> tuple[str, tuple]:
    """(text, rgb) describing how close ``exp`` is."""
    if exp is None:
        return "no expiry date", _GRAY
    days = (exp - today).days
    if days < 0:
        return f"EXPIRED {-days} day{'s' if days != -1 else ''} ago", _RED
    if days == 0:
        return "expires TODAY", _AMBER
    if days <= warn_days:
        return f"expires in {days} day{'s' if days != 1 else ''} - distribute first", _AMBER
    return f"good for {days} days", _GREEN


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def render_scan_card(info: ScanInfo, today: date, warn_days: int = 14) -> np.ndarray:
    """Draw the scan result as an RGB uint8 image (``CARD_PX``)."""
    from PIL import Image, ImageDraw

    W, H = CARD_PX
    card = Image.new("RGB", (W, H), (250, 250, 247))
    draw = ImageDraw.Draw(card)
    det = info.detection

    if det is None:
        status, color = "LABEL UNREADABLE", _GRAY
    else:
        status, color = expiry_status(det.expiration_date, today, warn_days)
        if color == _RED:
            status = status.upper()

    # Header bar.
    draw.rectangle([0, 0, W, 74], fill=color)
    draw.text((24, 14), "QR SCAN", font=_font(40, bold=True), fill="white")
    draw.text((230, 22), status, font=_font(32, bold=True), fill="white")

    # Scanner view on the left.
    view_box = (24, 96, 24 + 330, 96 + 330)
    if info.camera_view is not None:
        view = Image.fromarray(np.ascontiguousarray(info.camera_view[..., :3]))
        sx = (view_box[2] - view_box[0]) / view.width
        sy = (view_box[3] - view_box[1]) / view.height
        card.paste(view.resize((view_box[2] - view_box[0], view_box[3] - view_box[1])),
                   view_box[:2])
        if info.qr_corners is not None:
            pts = [(view_box[0] + x * sx, view_box[1] + y * sy) for x, y in info.qr_corners]
            draw.line(pts + pts[:1], fill=_GREEN, width=5)
    else:
        draw.rectangle(view_box, fill=(60, 60, 66))
    draw.rectangle(view_box, outline=(40, 40, 40), width=3)
    draw.text((view_box[0], view_box[3] + 8), "scanner camera", font=_font(22),
              fill=(90, 90, 90))

    # Facts on the right.
    x0, y = 384, 96
    if det is None:
        draw.text((x0, y), "No PantrySort QR code found", font=_font(36, bold=True), fill="black")
        y += 60
    else:
        draw.text((x0, y), det.label, font=_font(42, bold=True), fill="black")
        y += 62
        rows = [
            ("SKU", det.barcode or "-"),
            ("Lot", info.lot or "-"),
            ("Category", det.category.value.replace("_", " ")),
            ("Calories", f"{det.unit_calories} kcal / unit" if det.unit_calories is not None
             else "-"),
            ("Allergens", ", ".join(det.allergens) if det.allergens else "none"),
            ("Expires", det.expiration_date.isoformat() if det.expiration_date else "-"),
        ]
        for key, value in rows:
            draw.text((x0, y), key, font=_font(28), fill=(60, 60, 60))
            draw.text((x0 + 150, y), value, font=_font(28, bold=key in ("Expires", "Allergens")),
                      fill=color if key == "Expires" else "black")
            y += 42

    # Destination.
    y = max(y + 12, 400)
    draw.rounded_rectangle([x0, y, W - 24, y + 64], radius=12, fill=color)
    draw.text((x0 + 18, y + 14), f"-> {info.destination}", font=_font(32, bold=True),
              fill="white")

    if info.raw_text:
        draw.text((24, H - 34), info.raw_text, font=_font(18), fill=(120, 120, 120))
    return np.asarray(card)


# --------------------------------------------------------------------------- meshcat


CARD_WIDTH = 0.46  # m in the Meshcat scene


def card_pose(camera_position: np.ndarray, camera_target: np.ndarray,
              up_offset: float = 0.33, right_offset: float = -0.55):
    """Pose of a card that faces the Meshcat camera, floating in the upper left
    of the default view (clear of the arm and the storage pads).

    Returns a pydrake RigidTransform whose +z points at the camera and +y is
    the view's "up".
    """
    from pydrake.math import RigidTransform, RotationMatrix

    c, t = np.asarray(camera_position, float), np.asarray(camera_target, float)
    back = (c - t) / np.linalg.norm(c - t)               # card normal, toward the camera
    right = np.cross(np.array([0.0, 0.0, 1.0]), back)
    right /= np.linalg.norm(right)
    up = np.cross(back, right)
    R = RotationMatrix(np.column_stack([right, up, back]))
    return RigidTransform(R, t + up_offset * up + right_offset * right)


class ScanDisplay:
    """Shows one scan card at a time in Meshcat, keyed into the recording."""

    ROOT = "/scan_results"

    def __init__(self, meshcat: Any, out_dir: Path, pose: Any) -> None:
        self.meshcat = meshcat
        self.out_dir = Path(out_dir)
        self.pose = pose
        self._count = 0
        self._current: str | None = None

    def show(self, card: np.ndarray, time: float, recording: bool = True) -> None:
        from pydrake.geometry import Mesh

        name = f"card_{self._count:02d}"
        self._count += 1
        h, w = card.shape[:2]
        obj = write_textured_quad(card, self.out_dir / name, name,
                                  CARD_WIDTH, CARD_WIDTH * h / w)
        path = f"{self.ROOT}/{name}"
        self.meshcat.SetObject(path, Mesh(str(obj)))
        self.meshcat.SetTransform(path, self.pose)
        t = time if recording else None
        if recording:
            # Hidden in the replay until this item is scanned.
            self.meshcat.SetProperty(path, "visible", False, 0.0)
        self.meshcat.SetProperty(path, "visible", True, t)
        if self._current is not None:
            self.meshcat.SetProperty(self._current, "visible", False, t)
        self._current = path
