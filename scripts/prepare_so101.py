"""Prepare the SO-101 model for Drake.

Drake's SceneGraph can't use .stl meshes for collision geometry, so this converts
every STL in ``assets/so101/assets`` to OBJ and writes ``so101_drake.urdf`` (a copy
of ``so101_new_calib.urdf`` that references the OBJ files). The original URDF from
TheRobotStudio/SO-ARM100 is left untouched.

Usage:
    PYTHONPATH=src python scripts/prepare_so101.py
"""

from __future__ import annotations

import re
from pathlib import Path

from pantrysort.sim.mesh_io import read_stl, write_obj

SO101_DIR = Path(__file__).resolve().parents[1] / "assets" / "so101"
SRC_URDF = SO101_DIR / "so101_new_calib.urdf"
DST_URDF = SO101_DIR / "so101_drake.urdf"


def main() -> int:
    stls = sorted((SO101_DIR / "assets").glob("*.stl"))
    for stl in stls:
        mesh = read_stl(stl)
        write_obj(stl.with_suffix(".obj"), mesh.vertices, mesh.faces)
    urdf = SRC_URDF.read_text(encoding="utf-8")
    DST_URDF.write_text(re.sub(r'(filename="[^"]+)\.stl"', r'\1.obj"', urdf), encoding="utf-8")
    print(f"Converted {len(stls)} meshes; wrote {DST_URDF.relative_to(SO101_DIR.parents[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
