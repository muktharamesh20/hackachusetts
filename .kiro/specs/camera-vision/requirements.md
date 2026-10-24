# Requirements Document

## Introduction

Vision for the SO-101 pantry sorter: the system must locate and identify donated
items from cameras and move the arm safely to sort them. The arm is a kinematic
SO-101 in Drake with a multi-camera rig (a base wide-angle camera on the
rotation-base limb plus configurable external cameras). This document captures
the requirements the camera/vision work satisfies. It was written retrospectively
to anchor future changes, and revised to fix the active-presentation regression
introduced by the collision-reduction work (commits `b855e47`, `ab3c40e`).

## Glossary

- **Rig**: the set of cameras: one base camera on the arm plus external cameras.
- **Base camera**: a 160-degree fisheye mounted on `shoulder_link`; upright, pans with the base.
- **External camera**: an iPhone-style camera at a configurable fixed world pose.
- **Presentation camera**: an external camera flagged `present=True` that the arm holds items in front of.
- **Present point**: a fixed world point (`present_at`) in front of a presentation camera where a held item is read.
- **Watch region**: the world area a camera is expected to observe; reads outside it are rejected.
- **Active present**: the arm lifts an item to a presentation camera to read its QR up close.
- **Upright**: the held item's own up axis stays aligned with the up direction it had before grasping (world +z).
- **Obstacle map**: world points above the table inferred from camera depth.

## Requirements

### Requirement 1: Multi-camera rig

**User Story:** As an operator, I want several well-placed cameras covering the workspace, so that every item's QR is visible to at least one camera and cameras never sit where the arm or belt gets in the way.

#### Acceptance Criteria
1. WHEN the station is built THEN the system SHALL provide a base camera on the rotation-base limb that stays upright and pans with the base.
2. WHEN external cameras are configured THEN the system SHALL place them at configurable fixed poses outside the belt footprint, clear of queued donation-box footprints and bin drop points, and above the box rim height.
3. WHERE a camera is added THEN the system SHALL allow it via configuration without code changes, including its presentation fields.
4. WHERE a camera is a presentation camera THEN its spec SHALL declare a `present_at` point lying on its optical axis (within 1 cm) 0.12 to 0.18 m from the lens, 0.15 to 0.30 m horizontally from the arm's pan axis, at z >= 0.10 m, and projecting near the image center.
5. WHERE active presentation runs THEN the system SHALL NOT use the base camera as a presentation camera.

### Requirement 2: Item identification

**User Story:** As the sorter, I want each decoded QR matched to the specific item it is on, so that items are labeled and routed correctly.

#### Acceptance Criteria
1. WHEN a QR is decoded THEN the system SHALL back-project it to a world point via depth and match it to the nearest known item within a tolerance.
2. WHEN multiple cameras read the same item THEN the system SHALL fuse the reads by majority vote.
3. IF a stray QR appears in a frame outside the camera's watch region THEN the system SHALL reject it.
4. WHEN passive decoding fails for an item THEN the arm SHALL actively present that item (Requirement 5) and accept the read only if it back-projects to within the held item's size-based tolerance (half its largest dimension plus 0.03 m).
5. WHERE identification runs THEN the system SHALL NOT rely on a gripper-mounted scanner.

### Requirement 3: Safe motion and placement

**User Story:** As an operator, I want smooth, safe arm motion, so that items are not flung, dropped from height, or clipped through obstacles.

#### Acceptance Criteria
1. WHEN the arm moves THEN the system SHALL limit joint velocity and acceleration and avoid snapping or teleporting items.
2. WHEN an item is placed THEN the arm SHALL lower it close to the surface before release and settle it without a mid-air spin.
3. WHEN the arm approaches or carries an item THEN the system SHALL follow the base-swing path with a hover over the drop point, without depth-obstacle rerouting (retired), and keep the item above the surface until the gentle set-down.
4. WHERE lift clearances are decided THEN the system SHALL derive them from scene geometry (box walls, neighbour heights) rather than fixed magic offsets.

### Requirement 4: Testability

**User Story:** As a developer, I want to inspect what the cameras see and run different scenes, so that I can verify behavior.

#### Acceptance Criteria
1. WHEN a diagnostic runs THEN the system SHALL save camera frames and videos under `outputs/` in per-run folders, excluded from version control.
2. WHERE a scene is selected THEN the system SHALL support `flat_grid`, `belt_bare`, and `belt_boxes` modes.
3. WHERE behavior depends on Drake THEN the tests SHALL skip cleanly when pydrake or the VTK renderer is unavailable, and pure-numpy tests SHALL always run.

### Requirement 5: Active presentation

**User Story:** As the sorter, I want an unreadable item held still, upright and close in front of a camera, so that its QR decodes on the first try and the arm does not spin it pointlessly.

#### Acceptance Criteria
1. WHEN an item is grasped for presentation AND it is inside a donation box or within 0.08 m of a neighbouring item THEN the arm SHALL lift it straight up just enough to clear the rim or neighbours (at most 0.06 m), reaching the planned height within 1 cm with x,y drift under 1 cm.
2. WHEN an isolated item is grasped for presentation THEN the arm SHALL NOT perform the straight-up lift.
3. WHEN presenting THEN the arm SHALL move the item to each presentation camera's `present_at` point (within 2 cm) and attempt a straight read before any rotation.
4. WHILE an item is held for presentation, rotated, or returned THEN the system SHALL keep its up axis within 5 degrees of its original up direction.
5. IF the straight read fails at every presentation camera THEN the arm SHALL, as a last resort, rotate the item about the vertical axis in 90-degree steps (within 5 degrees) at exactly one presentation camera's `present_at` point (the camera that detected the largest QR), covering at most 4 faces and stopping at the first successful read.
6. WHILE rotating THEN the system SHALL cap wrist motion at about 1.0 rad/s, hold the item still for at least 0.5 s of sim time at each 90-degree stop before reading, keep total rotation at that location to at most 360 degrees (a single-direction sweep of 270 degrees when wrist_roll room allows), and SHALL NOT tilt `wrist_flex` as part of the search.
9. WHILE the arm is grasping, lifting, gliding to a present point, at the base camera, or carrying to a bin THEN the system SHALL NOT rotate the item for QR search; rotation happens only while the item is stationary within 2 cm of the chosen `present_at` point.
7. IF no read succeeds THEN the arm SHALL return the item upright to its original pose and release it, and the sort loop SHALL route it to the misc bin.
8. WHEN a straight read succeeds THEN the system SHALL NOT run the rotation search.