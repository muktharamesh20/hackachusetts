"""Procedural pantry objects: cans, boxes, bottles, bags, and essentials.

Every object is built from one primitive, a *loft*: a stack of rounded-rectangle
cross-sections joined into a closed, watertight surface. A rounded rectangle
with ``half_x == half_y == corner`` is a circle, so the same code makes cans and
bottles (round sections), boxes and cartons (sharp-ish rectangles), and bags,
soap, and tubes (very rounded sections).

Objects are *miniatures* sized for the SO-101 gripper (jaws open to ~8 cm) and
for quick 3D printing, roughly the size of the printable apples (~4.5 cm). By
convention every object's grip width is along **y** and is <= 6 cm; the sim
yaws items so the jaws close along their y axis.

Dimensions below are in centimeters for readability; meshes come out in meters.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from pantrysort.sim.mesh_io import MeshData, check_watertight, signed_volume

CM = 0.01
MAX_GRIP_WIDTH = 0.06  # m, along y

Section = tuple[float, float, float, float]  # (z, half_x, half_y, corner_radius) in cm


# --------------------------------------------------------------------------- primitives


def rounded_rect(hx: float, hy: float, rc: float, k: int) -> np.ndarray:
    """(4k, 2) points CCW around a rounded rectangle, starting in the +x+y corner."""
    rc = float(np.clip(rc, 0.03, min(hx, hy)))  # keep corners non-degenerate (>= 0.3 mm)
    pts = []
    centers = [(hx - rc, hy - rc), (-(hx - rc), hy - rc), (-(hx - rc), -(hy - rc)),
               (hx - rc, -(hy - rc))]
    for q, (cx, cy) in enumerate(centers):
        for t in np.linspace(0.0, np.pi / 2, k):
            a = q * np.pi / 2 + t
            pts.append((cx + rc * np.cos(a), cy + rc * np.sin(a)))
    return np.asarray(pts)


def loft(sections: list[Section], k: int = 8, cap_bottom: bool = True,
         cap_top: bool = True, closed_loop: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Join sections (bottom to top) into a closed mesh. Returns (vertices_cm, faces)."""
    rings = []
    for z, hx, hy, rc in sections:
        xy = rounded_rect(hx, hy, rc, k)
        rings.append(np.column_stack([xy, np.full(len(xy), z)]))
    n = len(rings[0])
    verts = np.vstack(rings)
    faces = []
    count = len(rings) if closed_loop else len(rings) - 1
    for i in range(count):
        i2 = (i + 1) % len(rings)
        for j in range(n):
            j2 = (j + 1) % n
            a, b, c, d = i * n + j, i * n + j2, i2 * n + j, i2 * n + j2
            faces += [(a, b, d), (a, d, c)]
    if not closed_loop:
        extra = []
        if cap_bottom:
            ci = len(verts) + len(extra)
            extra.append(rings[0].mean(axis=0))
            faces += [(ci, (j + 1) % n, j) for j in range(n)]
        if cap_top:
            ci = len(verts) + len(extra)
            extra.append(rings[-1].mean(axis=0))
            base = (len(rings) - 1) * n
            faces += [(ci, base + j, base + (j + 1) % n) for j in range(n)]
        if extra:
            verts = np.vstack([verts, extra])
    faces = np.asarray(faces, dtype=np.int64)
    if signed_volume(verts, faces) < 0:  # make normals point outward
        faces = faces[:, ::-1]
    return verts, faces


def circle(z: float, r: float) -> Section:
    return (z, r, r, r)


def rounded_box(sx: float, sy: float, sz: float, edge: float, corner: float | None = None,
                steps: int = 5) -> list[Section]:
    """Box sections with rounded vertical corners (``corner``) and top/bottom edges (``edge``)."""
    corner = edge if corner is None else corner
    hx, hy = sx / 2, sy / 2
    out: list[Section] = []
    for phi in np.linspace(-np.pi / 2, 0, steps):  # bottom rounding
        inset = edge * (1 - np.cos(phi))
        out.append((edge + edge * np.sin(phi), hx - inset, hy - inset, corner - inset))
    for phi in np.linspace(0, np.pi / 2, steps):   # top rounding
        inset = edge * (1 - np.cos(phi))
        out.append((sz - edge + edge * np.sin(phi), hx - inset, hy - inset, corner - inset))
    return out


def lathe(profile: list[tuple[float, float]]) -> list[Section]:
    """Round sections from an (r, z) profile, bottom to top."""
    return [circle(z, r) for r, z in profile]


# --------------------------------------------------------------------------- objects


@dataclass(frozen=True)
class Printable:
    name: str
    title: str
    color: tuple[float, float, float, float]
    build: Callable[[], tuple[np.ndarray, np.ndarray]]  # -> (verts_cm, faces)

    def mesh(self) -> MeshData:
        verts_cm, faces = self.build()
        return MeshData(self.name, verts_cm * CM, faces, self.color)


def _soup_can():
    r, h = 2.6, 6.4
    return loft(lathe([
        (r - 0.25, 0.0), (r, 0.2), (r, 0.45), (r - 0.06, 0.6),
        (r - 0.06, 1.2), (r, 1.3), (r, h - 1.3), (r - 0.06, h - 1.2),  # label ribs
        (r - 0.06, h - 0.6), (r, h - 0.45), (r, h - 0.1), (r - 0.12, h),
        (r - 0.3, h), (r - 0.35, h - 0.12),  # lid seam step
    ]), k=16)


def _tuna_can():
    r, h = 2.8, 2.3
    return loft(lathe([(r - 0.2, 0.0), (r, 0.15), (r, h - 0.2), (r - 0.1, h),
                       (r - 0.3, h), (r - 0.35, h - 0.1)]), k=16)


def _cereal_box():
    return loft(rounded_box(5.2, 2.4, 7.6, edge=0.12, corner=0.15), k=4)


def _pasta_box():
    return loft(rounded_box(6.0, 2.6, 3.4, edge=0.12, corner=0.15), k=4)


def _rice_bag():
    # Soft bag that narrows into a folded, sealed top.
    body = rounded_box(5.4, 3.4, 5.6, edge=0.9, corner=1.2)[:6]
    top = [(5.8, 2.6, 1.3, 0.8), (6.3, 2.6, 0.5, 0.45), (6.7, 2.6, 0.12, 0.1)]
    return loft(body + top, k=6)


def _flour_bag():
    body = rounded_box(5.0, 3.2, 6.0, edge=0.5, corner=0.9)[:6]
    top = [(6.2, 2.45, 1.4, 0.7), (6.6, 2.4, 0.6, 0.5), (7.0, 2.3, 0.15, 0.12)]
    return loft(body + top, k=6)


def _olive_oil_bottle():
    return loft(lathe([
        (1.6, 0.0), (1.9, 0.15), (1.95, 0.4), (1.95, 5.2),   # body
        (1.8, 5.9), (1.3, 6.6), (0.8, 7.1), (0.62, 7.4),      # shoulder
        (0.62, 7.9), (0.85, 7.95), (0.85, 9.0), (0.6, 9.1),   # neck + cap
    ]), k=14)


def _salt_shaker():
    return loft(lathe([
        (1.5, 0.0), (1.7, 0.15), (1.7, 4.2), (1.62, 4.35),
        (1.62, 4.9), (1.45, 5.35), (1.0, 5.65), (0.4, 5.8),   # domed pour cap
    ]), k=14)


def _peanut_butter_jar():
    return loft(lathe([
        (2.2, 0.0), (2.45, 0.15), (2.5, 0.5), (2.5, 4.6), (2.3, 4.9),  # jar
        (2.3, 5.05), (2.45, 5.1), (2.45, 6.1), (2.3, 6.2),            # lid
    ]), k=16)


def _milk_carton():
    w, d, h_wall = 4.0, 4.0, 5.6
    walls = rounded_box(w, d, h_wall, edge=0.08, corner=0.12)[:-1]
    gable = [(h_wall + 0.6, w / 2, d / 2 * 0.6, 0.1), (h_wall + 1.2, w / 2, 0.15, 0.1),
             (h_wall + 1.9, w / 2, 0.1, 0.08)]  # sloped roof + sealed fin
    return loft(walls + gable, k=4)


def _frozen_peas_bag():
    # Flat pillow bag lying on the table.
    return loft(rounded_box(6.0, 4.6, 2.0, edge=0.9, corner=1.6, steps=7), k=8)


def _toothpaste():
    # Tube lying along x: round cap end, flattening to a crimped seal.
    sections: list[Section] = [circle(0.0, 0.75), circle(1.0, 0.8)]  # cap
    for t in np.linspace(0.0, 1.0, 10):
        hy = 1.35 + 0.55 * t                # widens toward the crimp
        hz = 1.15 * (1 - t) ** 0.8 + 0.12   # flattens toward the crimp
        sections.append((1.1 + 6.4 * t, hy, hz, hz))
    sections.append((8.2, 1.95, 0.12, 0.1))  # crimp
    v, f = loft(sections, k=8)
    # Loft axis (z) -> world x, section x -> world y (grip width), section y -> world z.
    v = v[:, [2, 0, 1]]
    return v, f[:, ::-1] if signed_volume(v, f) < 0 else f


def _soap_bar():
    return loft(rounded_box(6.0, 3.8, 2.0, edge=0.7, corner=1.2, steps=6), k=8)


def _toilet_paper():
    r_out, r_in, h = 2.8, 0.9, 5.0
    ring = [circle(0.0, r_in), circle(0.0, r_out - 0.15), circle(0.1, r_out),
            circle(h - 0.1, r_out), circle(h, r_out - 0.15), circle(h, r_in)]
    return loft(ring, k=16, closed_loop=True)  # hollow core


def _shampoo_bottle():
    return loft([
        (0.0, 2.0, 1.1, 1.0), (0.15, 2.2, 1.3, 1.2), (5.8, 2.2, 1.3, 1.25),
        (6.6, 1.6, 1.1, 1.05), (7.1, 0.9, 0.9, 0.9),        # shoulder
        (7.15, 1.05, 0.95, 0.95), (8.6, 1.05, 0.95, 0.95),  # flip cap
        (8.8, 0.8, 0.7, 0.7),
    ], k=10)


PRINTABLES: dict[str, Printable] = {p.name: p for p in [
    Printable("soup_can", "Soup can", (0.78, 0.12, 0.12, 1.0), _soup_can),
    Printable("tuna_can", "Tuna can", (0.25, 0.45, 0.70, 1.0), _tuna_can),
    Printable("cereal_box", "Cereal box", (0.95, 0.55, 0.10, 1.0), _cereal_box),
    Printable("pasta_box", "Pasta box", (0.15, 0.35, 0.75, 1.0), _pasta_box),
    Printable("rice_bag", "Rice bag", (0.95, 0.93, 0.85, 1.0), _rice_bag),
    Printable("flour_bag", "Flour bag", (0.85, 0.80, 0.70, 1.0), _flour_bag),
    Printable("olive_oil_bottle", "Olive oil bottle", (0.30, 0.42, 0.10, 1.0), _olive_oil_bottle),
    Printable("salt_shaker", "Salt shaker", (0.92, 0.92, 0.95, 1.0), _salt_shaker),
    Printable("peanut_butter_jar", "Peanut butter jar", (0.72, 0.48, 0.25, 1.0),
              _peanut_butter_jar),
    Printable("milk_carton", "Milk carton", (0.97, 0.97, 0.97, 1.0), _milk_carton),
    Printable("frozen_peas_bag", "Frozen peas bag", (0.25, 0.65, 0.30, 1.0), _frozen_peas_bag),
    Printable("toothpaste", "Toothpaste tube", (0.20, 0.55, 0.85, 1.0), _toothpaste),
    Printable("soap_bar", "Soap bar", (0.95, 0.70, 0.78, 1.0), _soap_bar),
    Printable("toilet_paper", "Toilet paper roll", (0.98, 0.98, 0.98, 1.0), _toilet_paper),
    Printable("shampoo_bottle", "Shampoo bottle", (0.10, 0.62, 0.62, 1.0), _shampoo_bottle),
]}


def validate(mesh: MeshData) -> list[str]:
    """Problems that would make an object unprintable or ungrippable."""
    problems = check_watertight(mesh.faces)
    if signed_volume(mesh.vertices, mesh.faces) <= 0:
        problems.append("non-positive volume (inside-out)")
    width = mesh.size[1]
    if width > MAX_GRIP_WIDTH:
        problems.append(f"grip width {width * 100:.1f} cm exceeds {MAX_GRIP_WIDTH * 100:.0f} cm")
    return problems
