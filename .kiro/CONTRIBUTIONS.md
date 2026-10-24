# Kiro contributions log

A running record of what Kiro has built on PantrySort, so contributions are easy
to trace. Newest first. Each entry lists the branch and the key commits.

---

## Obstacle-avoidance rollout (Tasks 6-7)
Branch: eature/obstacle-avoidance-rollout
- Extended vision obstacle avoidance from the carry phase to the policy-driven
  approach/transport in execute_pick_and_place, and validated on all scenes.
- _build_obstacles builds the map excluding the grasp-target item (so the arm
  can reach it); steps lift over obstacles except during the final straight-down
  descent onto the target. Verified: flat_grid 9/9, belt_bare 9/9, belt_boxes
  13/13 sorted; EE rises to ~0.23 m over box walls.

## Vision-based obstacle avoidance (Task D, in progress)
Branch: `feature/vision-obstacle-pathing`
- `7802faf` feat: vision-based obstacle avoidance for the carry path (v1)
- `src/pantrysort/sim/vision_path.py` (new): `ObstacleMap.from_station` builds an
  obstacle point cloud from the cameras' depth (ground + arm + held item
  filtered, voxel-downsampled); `plan_step` / `lift_over_obstacles` raise the EE
  over obstacles while holding a ground margin. Not hardcoded.
- Wired into the transport carry so the arm goes OVER clutter (EE rises to
  ~0.15 m while carrying). `tests/test_vision_path.py` (5 pure-numpy tests).
- TODO: extend/validate on `belt_bare` and `belt_boxes`; tune radii.

## Motion & placement fixes (Tasks B, C)
Branch: `integrate/conveyor-env` -> merged to `main` (PR #4)
- `029683f` fix: no teleport after scan; gentle set-down instead of high drop
- Active-scan keeps the item grasped and hands it to pick-and-place (skips the
  redundant grasp); no `SetFreeBodyPose` snap-back. Arm lowers to ~1.5 cm before
  release; `drop_held_onto` settles in <=1.5 cm steps. Per-item max step jump
  dropped from ~0.25 m (teleport) to <=0.057 m.

## Conveyor environment integration (Task A)
Branch: `integrate/conveyor-env` -> merged to `main` (PR #4)
- `26f6614` merge of `feature/conveyor-donation-boxes`, resolved with OUR camera
  rig winning and the gripper-scanner path rejected; kept the conveyor scene,
  walled bins, wrist-turn-during-transport drop, and SO-101 tooling scripts.
- Added `PANTRYSORT_SCENE_MODE` (flat_grid | belt_bare | belt_boxes) and a
  `belt_bare` scene (belt, no boxes).

## Camera rig, identification, recording (merged to `main`, PRs #1-#3)
Branch: `feature/fisheye-camera` -> `main`
- `abdcd35` record separate base + external camera videos (`sim/recording.py`,
  `scripts/run_sim_record.py`).
- `639ef83` mount base camera low on the shoulder limb looking outward.
- `22ee654` smooth motion limits, ground cameras, multiview camera diagnostic
  (`scripts/camera_diagnostic.py`).
- `7b0400e` robust multi-camera QR identification: passive fusion + active
  present-to-camera (`perception/identify.py`, `sim/active_scan.py`), QR corner
  rectification, per-camera watch regions.
- `a644217` scan QR from the camera rig (not a gripper camera); QR stickers moved
  to item sides.
- `889484e` configurable camera rig with the fisheye base camera
  (`sim/camera.py`, `assets` fetch + STL->OBJ for Drake collisions).

## Docs / environment
Branch: `docs/wsl-drake-setup-notes` -> `main` (PR #2)
- `DEV_NOTES.md`: known-good WSL + Python 3.12 + Drake setup (no Windows wheels);
  notes the kinematic sim and the camera-rig direction.
- `src/pantrysort/sim/README.md`: arm API + run instructions.