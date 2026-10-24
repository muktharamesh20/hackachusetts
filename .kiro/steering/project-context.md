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


## Current app/backend integration context

The repository now contains a substantially implemented Expo/React Native app
under `app/` with role-aware Pantry/Donor/Neighbor flows. The app data boundary
is `app/lib/stash.ts`; the Supabase client is `app/lib/supabase.ts`. The app
uses the anon key and RLS, with sessions persisted through SecureStore and an
AsyncStorage/web fallback. Do not place a service-role key in the mobile app.

The current production database contract is the latest migration chain under
`supabase/migrations/`, especially the lot-aware/app-data migration. It includes
pantry-scoped `inventory_items`, per-expiry `inventory_lots`,
`inventory_transactions`, `app_categories`, `catalog_items`, roles, drop-offs,
and RPCs. The older `db/schema.sql` three-table contract is legacy and must not
be used for new production integration work.

Inventory changes must be lot-aware, FEFO-ordered, pantry-authorized, and
atomic with their audit transaction. The robot/Python layer currently has
legacy category values and a separate Supabase adapter; use the
`pantry-app-integration` spec to reconcile it rather than adding another
parallel schema.

QR/catalog rules:

- `PS1` payloads are shared between Python and the app.
- SKU/catalog facts take precedence over broad legacy category labels.
- A generic `canned` value is ambiguous and must not blindly become `protein`.
- Expiry provenance must distinguish package-confirmed, OCR-derived,
  catalog-estimated, and missing dates.
- Fixtures live under `assets/qr/`; the broader source catalog is
  `assets/catalog.yaml` and `assets/barcodes/`.

## Native app build conventions

For a physical iPhone production-style test, configure `app/.env` with only
`EXPO_PUBLIC_SUPABASE_URL` and `EXPO_PUBLIC_SUPABASE_ANON_KEY`, generate/update
the native workspace when app config changes, configure Xcode automatic signing,
and build the Release configuration. A Release build must embed the JavaScript
bundle and run without Metro. Never commit `.env`, signing assets, provisioning
profiles, or service-role credentials.

The app currently has PantrySort repository/native naming and Stash UI/data
naming. Choose and document one canonical release name before final native
release; do not silently rename bundle identifiers or schemes in unrelated
feature work.

## Documentation source of truth

- Camera/vision behavior: `.kiro/specs/camera-vision/`.
- Robot/app/backend integration: `.kiro/specs/pantry-app-integration/`.
- Current database contract: `supabase/migrations/`.
- Current mobile service contract: `app/lib/stash.ts`.
- Current robot sort entry point: `src/pantrysort/pipeline/sort_loop.py`.
- Generated camera/video diagnostics belong under `outputs/`.
