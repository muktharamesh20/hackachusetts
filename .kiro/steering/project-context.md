---
inclusion: always
---

# PantrySort — project context & conventions (for Kiro)

Steering notes so future sessions pick up the project's constraints and the
conventions established so far. Keep this current when the architecture shifts.

## Environment: Drake needs WSL on Windows

Drake publishes **no Windows wheels**. On this machine the sim runs in **WSL
Ubuntu** using a **Python 3.12** venv at `~/.venvs/pantrysort` (uv-managed).
Edit files on Windows; run/test in WSL:

    wsl -d Ubuntu --cd "/mnt/c/.../hackachusetts" -- ~/.venvs/pantrysort/bin/python ...

Use Python 3.10-3.12 everywhere (3.13/3.14 are too new for Drake). See the
root `DEV_NOTES.md` for full setup. `pydrake` has no `__version__`; check an
actual import instead.

## Simulation architecture

- **Kinematic** station (`src/pantrysort/sim/station.py`): joint angles come
  from IK and are written to the plant context; held items follow the gripper.
  No contact dynamics. Good for perception + camera-driven positioning.
- **Arm**: TheRobotStudio **SO-101** (5 arm DoF + gripper), base welded at the
  origin facing +x. EE frame `gripper_frame_link`.
- **Camera rig** (`src/pantrysort/sim/camera.py`): a **base** 160-deg wide-angle
  camera on `shoulder_link` (low on the limb, pans with the base) plus **external
  iPhone-style ground cameras** at the front corners. Declarative `CameraSpec` /
  `default_rig` / `load_rig`; add cameras via config, not code.
- **Identification** (`src/pantrysort/perception/identify.py`): QR decoded per
  camera, back-projected to world via depth, matched to the nearest item, fused
  by majority vote, with per-camera "watch regions". When passive decode misses,
  the arm actively presents the item to a camera (`sim/active_scan.py`).
- **Do NOT reintroduce the gripper scanner** as the scan path. It is legacy
  (`qr_scanner` defaults False); we identify via the rig.
- **Scenes** (`PANTRYSORT_SCENE_MODE`): `flat_grid` (experimental default),
  `belt_bare` (conveyor, no boxes - closest to near-term real), `belt_boxes`
  (full conveyor + donation boxes - basis for future robustness work).

## Conventions

- Motion is velocity/acceleration-limited (`move_ee_to_smooth`, `_ramp_to`) and
  per-call joint-step clamped; avoid snapping joints.
- Prefer vision/depth-derived decisions over hardcoded clearances, so sim and
  real differences are tolerated (see `sim/vision_path.py`).
- Outputs (camera frames, videos, diagnostics) go under `outputs/` (gitignored),
  in timestamped run folders.
- Branch per feature; keep `main` as the integration line. Verify with
  `pytest tests/ -p no:cacheprovider` and `ruff check` before committing.