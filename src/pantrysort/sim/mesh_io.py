"""Small mesh I/O helpers for preparing sim assets (no Drake dependency).

* ``read_stl``  - binary or ASCII STL
* ``read_3mf``  - every mesh object in a 3MF archive (e.g. a Bambu/Prusa project),
  including its display color if the file has one
* ``write_3mf`` - a minimal, spec-compliant 3MF (core spec) with one color per object
* ``write_obj`` - OBJ with per-face normals (Drake's renderers require normals)
* ``check_watertight`` / ``signed_volume`` - sanity checks for generated meshes
"""

from __future__ import annotations

import re
import struct
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_3MF_URI = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
_3MF_NS = "{" + _3MF_URI + "}"


@dataclass
class MeshData:
    name: str
    vertices: np.ndarray  # (N, 3) float
    faces: np.ndarray     # (M, 3) int, 0-indexed
    color: tuple[float, float, float, float] | None = None  # RGBA in [0, 1]

    @property
    def size(self) -> np.ndarray:
        return self.vertices.max(axis=0) - self.vertices.min(axis=0)


# --------------------------------------------------------------------------- STL


def read_stl(path: Path) -> MeshData:
    """Read an STL, merging duplicate vertices."""
    data = Path(path).read_bytes()
    n = struct.unpack("<I", data[80:84])[0] if len(data) >= 84 else 0
    if len(data) == 84 + 50 * n:  # binary
        rec = np.frombuffer(data[84:], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
        tri = rec["v"].reshape(-1, 3).astype(np.float64)
    else:  # ASCII
        tri = np.array(re.findall(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", data), dtype=np.float64)
    verts, inverse = np.unique(np.round(tri, 7), axis=0, return_inverse=True)
    return MeshData(Path(path).stem, verts, inverse.reshape(-1, 3))


# --------------------------------------------------------------------------- 3MF

_UNIT_SCALE = {"micron": 1e-6, "millimeter": 1e-3, "centimeter": 1e-2,
               "inch": 0.0254, "foot": 0.3048, "meter": 1.0}


def _parse_color(text: str | None) -> tuple[float, float, float, float] | None:
    if not text or not text.startswith("#") or len(text) not in (7, 9):
        return None
    vals = [int(text[i:i + 2], 16) / 255 for i in range(1, len(text), 2)]
    return tuple(vals + [1.0] * (4 - len(vals)))  # type: ignore[return-value]


def read_3mf(path: Path) -> list[MeshData]:
    """Return every ``<object>`` with a ``<mesh>`` in a 3MF archive, in file order.

    Coordinates are converted to meters using the model's ``unit`` attribute.
    Objects in Bambu/Prusa projects often live in ``3D/Objects/*.model``; those
    are included too. Build-plate transforms are ignored (meshes keep their own
    local frame). Colors come from ``<basematerials>`` when present.
    """
    meshes: list[MeshData] = []
    with zipfile.ZipFile(path) as zf:
        model_files = sorted(n for n in zf.namelist() if n.lower().endswith(".model"))
        for name in model_files:
            root = ET.fromstring(zf.read(name))
            unit = _UNIT_SCALE.get(root.get("unit", "millimeter"), 1e-3)
            materials: dict[str, list] = {}
            for group in root.iter(f"{_3MF_NS}basematerials"):
                materials[group.get("id")] = [
                    _parse_color(b.get("displaycolor")) for b in group.iter(f"{_3MF_NS}base")
                ]
            for obj in root.iter(f"{_3MF_NS}object"):
                mesh = obj.find(f"{_3MF_NS}mesh")
                if mesh is None:
                    continue
                v = np.array([[float(e.get("x")), float(e.get("y")), float(e.get("z"))]
                              for e in mesh.iter(f"{_3MF_NS}vertex")])
                f = np.array([[int(e.get("v1")), int(e.get("v2")), int(e.get("v3"))]
                              for e in mesh.iter(f"{_3MF_NS}triangle")])
                color = None
                pid, pindex = obj.get("pid"), obj.get("pindex")
                if pid in materials and pindex is not None:
                    color = materials[pid][int(pindex)]
                label = obj.get("name") or f"{Path(name).stem}_{obj.get('id')}"
                meshes.append(MeshData(label, v * unit, f, color))
    return meshes


_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""
_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def write_3mf(path: Path, mesh: MeshData, title: str | None = None) -> None:
    """Write one mesh (vertices in meters) as a 3MF in millimeters, sitting on z = 0."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    v = mesh.vertices * 1000.0
    v = v - np.array([0.0, 0.0, v[:, 2].min()])  # rest on the print bed
    color = mesh.color or (0.8, 0.8, 0.8, 1.0)
    hexcolor = "#" + "".join(f"{round(c * 255):02X}" for c in color[:3])

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{_3MF_URI}">',
        f' <metadata name="Title">{title or mesh.name}</metadata>',
        ' <metadata name="Application">pantrysort generate_printables</metadata>',
        " <resources>",
        f'  <basematerials id="1"><base name="{mesh.name}" displaycolor="{hexcolor}"/></basematerials>',
        f'  <object id="2" name="{mesh.name}" type="model" pid="1" pindex="0">',
        "   <mesh>",
        "    <vertices>",
    ]
    lines += [f'     <vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in v]
    lines += ["    </vertices>", "    <triangles>"]
    lines += [f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in mesh.faces]
    lines += ["    </triangles>", "   </mesh>", "  </object>", " </resources>",
              ' <build><item objectid="2"/></build>', "</model>", ""]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("3D/3dmodel.model", "\n".join(lines))


# --------------------------------------------------------------------------- OBJ


def write_obj(path: Path, verts: np.ndarray, faces: np.ndarray) -> None:
    """Write an OBJ with one flat normal per face, dropping degenerate triangles."""
    path = Path(path)
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2])
                  & (faces[:, 0] != faces[:, 2])]
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    normals = np.cross(b - a, c - a)
    lengths = np.linalg.norm(normals, axis=1)
    keep = lengths > 1e-15
    faces, normals = faces[keep], normals[keep] / lengths[keep, None]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii") as fh:
        fh.write(f"# {path.stem} (generated for Drake)\n")
        for v in verts:
            fh.write(f"v {v[0]:.7g} {v[1]:.7g} {v[2]:.7g}\n")
        for n in normals:
            fh.write(f"vn {n[0]:.5f} {n[1]:.5f} {n[2]:.5f}\n")
        for i, f in enumerate(faces + 1, start=1):  # OBJ is 1-indexed
            fh.write(f"f {f[0]}//{i} {f[1]}//{i} {f[2]}//{i}\n")


# --------------------------------------------------------------------------- checks


def signed_volume(verts: np.ndarray, faces: np.ndarray) -> float:
    """Enclosed volume; positive when faces wind counter-clockwise seen from outside."""
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def check_watertight(faces: np.ndarray) -> list[str]:
    """Return problems found (empty list = closed, consistently oriented 2-manifold)."""
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    directed, counts = np.unique(edges, axis=0, return_counts=True)
    problems = []
    if (counts > 1).any():
        problems.append(f"{int((counts > 1).sum())} edges used twice in the same direction")
    fwd = {tuple(e) for e in directed}
    missing = sum(1 for a, b in directed if (b, a) not in fwd)
    if missing:
        problems.append(f"{missing} edges without a matching opposite edge (holes)")
    return problems
