# Requirements Document

## Introduction

Vision for the SO-101 pantry sorter: the system must locate and identify donated
items from cameras and move the arm safely to sort them. The arm is a kinematic
SO-101 in Drake with a multi-camera rig (a base wide-angle camera on the
rotation-base limb plus configurable external ground cameras). This document
captures the requirements the camera/vision work satisfies. It is written
retrospectively to anchor future changes.

## Glossary

- **Rig**: the set of cameras — one base camera on the arm plus external cameras.
- **Base camera**: a 160-degree fisheye mounted on `shoulder_link`; upright, pans with the base.
- **External camera**: a ground-mounted, iPhone-style camera at a configurable pose.
- **Watch region**: the world area a camera is expected to observe; reads outside it are rejected.
- **Active present**: the arm lifts an item to a camera to read its QR up close.
- **Obstacle map**: world points above the table inferred from camera depth.

## Requirements

### Requirement 1: Multi-camera rig

**User Story:** As an operator, I want several cameras covering the workspace, so that every item's QR is visible to at least one camera even with imprecise placement.

#### Acceptance Criteria
1. WHEN the station is built THEN the system SHALL provide a base camera on the rotation-base limb that stays upright and pans with the base.
2. WHEN external cameras are configured THEN the system SHALL place them at ground level at configurable poses (direct pose or homography).
3. WHERE a camera is added THEN the system SHALL allow it via configuration without code changes.

### Requirement 2: Item identification

**User Story:** As the sorter, I want each decoded QR matched to the specific item it is on, so that items are labeled and routed correctly.

#### Acceptance Criteria
1. WHEN a QR is decoded THEN the system SHALL back-project it to a world point via depth and match it to the nearest known item within a tolerance.
2. WHEN multiple cameras read the same item THEN the system SHALL fuse the reads by majority vote.
3. IF a stray QR appears in a frame outside the camera's watch region THEN the system SHALL reject it.
4. WHEN passive decoding fails for an item THEN the arm SHALL actively present that item to a camera and accept the read only if it back-projects to the held item.
5. WHERE identification runs THEN the system SHALL NOT rely on a gripper-mounted scanner.

### Requirement 3: Safe motion and placement

**User Story:** As an operator, I want smooth, safe arm motion, so that items are not flung, dropped from height, or clipped through obstacles.

#### Acceptance Criteria
1. WHEN the arm moves THEN the system SHALL limit joint velocity and acceleration and avoid snapping or teleporting items.
2. WHEN an item is placed THEN the arm SHALL lower it close to the surface before release and settle it without a mid-air spin.
3. WHEN the arm carries an item THEN the system SHALL avoid obstacles detected from camera depth and keep a margin above the ground.
4. WHERE clearances are decided THEN the system SHALL derive them from vision rather than hardcoded values.

### Requirement 4: Testability

**User Story:** As a developer, I want to inspect what the cameras see and run different scenes, so that I can verify behavior.

#### Acceptance Criteria
1. WHEN a diagnostic runs THEN the system SHALL save camera frames and videos under `outputs/` in per-run folders, excluded from version control.
2. WHERE a scene is selected THEN the system SHALL support `flat_grid`, `belt_bare`, and `belt_boxes` modes.


## Integration boundary with the pantry app

The camera-vision spec owns perception and motion decisions; it does not own
Supabase authorization, lot accounting, or mobile UI behavior. Once a QR label
is identified, the integration layer must convert the result into the canonical
catalog/category and lot-aware event defined by
`.kiro/specs/pantry-app-integration/requirements.md`.

The camera pipeline SHALL preserve the following handoff facts when available:

- PS1 raw payload and decoded SKU.
- Observed item identity and confidence/source of the read.
- Package expiration and whether it is confirmed or estimated.
- Lot code, calories, allergens, quantity, and physical destination.
- Simulation run identifier when the result came from Drake.

A successful physical placement must precede robot intake recording. If the
backend call fails after placement, the integration layer must retry with an
idempotency key rather than silently dropping the inventory event.
