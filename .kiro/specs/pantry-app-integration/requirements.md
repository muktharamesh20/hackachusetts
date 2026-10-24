# Pantry App Integration — Requirements

## Status

Requirements phase — proposed for review.

This spec integrates the existing Drake/SO-101 simulation, QR/catalog pipeline,
Supabase lot-aware backend, and Expo/React Native Stash app. It is not a
new-app specification: substantial implementations already exist and must be
reconciled without breaking the current simulation or mobile flows.

## Introduction

PantrySort is a food-pantry automation system. A kinematic SO-101 robot in
Drake receives donated food, identifies products using camera-visible QR labels,
sorts them into storage destinations, and records the resulting inventory. The
mobile app lets pantry staff, donors, and neighbors interact with the same
inventory and pantry data.

The current repository contains two partially divergent contracts:

- The robot/Python layer uses legacy item rows and categories such as `canned`,
  `dry_goods`, `condiment`, and `frozen`.
- The current Supabase/app layer uses pantry-scoped inventory lots and app
  categories such as `protein`, `grains`, `cooking_basics`, and `fruit_veg`.

This spec establishes the behavior needed to make those implementations one
system. Existing camera-vision behavior remains governed by
`.kiro/specs/camera-vision/`.

## Goals

1. Make the latest Supabase migration contract the source of truth for shared
   inventory data.
2. Preserve the existing in-memory backend for tests and offline simulation.
3. Make robot intake and mobile intake produce equivalent, auditable lot data.
4. Preserve QR-driven simulation behavior and the existing Expo role flows.
5. Make FEFO distribution correct at lot level and safe under concurrent use.
6. Produce a reproducible native iOS Release build that runs on a physical
   iPhone without Metro.

## Non-goals

- Replacing the existing SO-101 camera-vision pipeline.
- Adding contact-dynamics grasp simulation.
- Building a public marketplace or payment settlement system.
- Shipping the Supabase service-role key in the mobile app.
- Treating the older three-table schema as a second production contract.

## Glossary

- **Pantry**: A food pantry represented by a Supabase `pantries` row.
- **Item**: A product aggregate shown in inventory; its quantity is derived from
  its lots.
- **Lot**: Units received together with a shared expiration date, source, and
  optional lot code.
- **FEFO**: First Expired, First Out; consume the eligible lot with the nearest
  expiration date first, with undated lots last.
- **PS1 payload**: PantrySort's versioned QR payload containing SKU, expiry, lot,
  category, calories, and allergens.
- **Robot intake**: Inventory received through the Drake/robot pipeline and
  attributed to source `robot`.
- **Scan intake**: Inventory entered through the mobile scanner and attributed
  to source `scan`.
- **Estimated expiry**: A date inferred from catalog shelf life or OCR rather
  than confirmed from package text.
- **Canonical category**: One of the current app/Supabase category keys, not a
  legacy Python-only category string.
- **Release build**: A native iOS build with the JavaScript bundle embedded,
  installable on a physical device without a Metro server.

## Requirements

### Requirement 1: Canonical data contract

**User Story:** As a robot and app developer, I want one shared data contract,
so that inventory created by the robot appears correctly in the app.

#### Acceptance Criteria

1. THE system SHALL treat the latest Supabase migration chain, including
   `inventory_lots`, `app_categories`, `catalog_items`, pantry scoping, RLS,
   triggers, and RPCs, as the production schema source of truth.
2. THE system SHALL define one canonical category mapping from every legacy
   robot category to an app category before robot-to-Supabase integration is
   enabled.
3. WHEN a robot or app writes an item THEN the persisted row SHALL include a
   pantry identity, canonical category, product identity when known, quantity,
   source, and expiration information appropriate to the intake path.
4. THE system SHALL either remove the legacy `db/schema.sql` contract or label
   it explicitly as legacy and prevent new production code from using it.
5. THE system SHALL keep `assets/catalog.yaml`, `catalog_items`, and the mobile
   catalog behavior synchronized for SKU, name, category, calories, allergens,
   and shelf-life facts.
6. IF a catalog fact differs between sources THEN CI or a documented sync check
   SHALL report the mismatch before release.

### Requirement 2: Pantry identity and authorization

**User Story:** As a pantry operator, I want inventory isolated by pantry and
role, so that one pantry cannot modify another pantry's data.

#### Acceptance Criteria

1. WHEN a user accesses inventory, lots, transactions, drop-offs, or goals THEN
   the query SHALL be scoped to a pantry the user is authorized to access.
2. THE system SHALL distinguish at least neighbor, donor, pantry staff, and
   pantry owner capabilities.
3. Pantry staff SHALL be able to intake, review, distribute, and discard stock
   only for authorized pantries.
4. Donors SHALL be able to submit their own drop-off bags but SHALL NOT directly
   alter accepted pantry inventory.
5. Neighbors SHALL be able to view public pantry information and eligible stock
   without receiving staff write access.
6. THE mobile app SHALL use only the Supabase anon key and authenticated RLS;
   the service-role key SHALL never be bundled or exposed to a device.
7. IF a user lacks authorization THEN the API/app SHALL return a clear error and
   SHALL not partially write inventory or transaction data.

### Requirement 3: Lot-aware inventory lifecycle

**User Story:** As pantry staff, I want every intake and outflow tied to lots,
so that expiration, quantity, and audit history remain accurate.

#### Acceptance Criteria

1. WHEN stock is received THEN the system SHALL create or update an item
   aggregate and create a distinct lot containing quantity, expiration date,
   source, received time, and optional lot code.
2. THE item aggregate quantity SHALL equal the sum of its positive lot
   quantities.
3. THE item aggregate expiration date SHALL equal the earliest non-null lot
   expiration date, or null when no lot has a date.
4. WHEN stock is distributed or discarded THEN the system SHALL consume lots in
   FEFO order and append one auditable transaction containing pantry, item,
   quantity, source, actor, and reason/note.
5. WHEN the final units of an item leave inventory THEN the system SHALL retain
   its transaction history even if the current aggregate row is removed or
   reaches zero.
6. THE system SHALL distinguish confirmed expiration dates from estimated dates
   and allow authorized staff to confirm or correct an estimated date.
7. IF an intake contains an already-expired lot THEN the system SHALL route it to
   the discard workflow or an explicitly configured quarantine destination and
   SHALL not present it as distributable stock.
8. IF a lot mutation or transaction append fails THEN the operation SHALL be
   atomic from the caller's perspective and SHALL not leave quantity and audit
   history inconsistent.

### Requirement 4: Atomic inventory operations

**User Story:** As a pantry operator, I want inventory actions to be safe when
multiple people or robot processes act at once.

#### Acceptance Criteria

1. THE backend SHALL expose atomic operations or RPCs for robot intake, scan
   intake, distribution, discard, and drop-off acceptance.
2. WHEN two clients distribute the same item concurrently THEN the backend SHALL
   prevent the total distributed quantity from exceeding available lot stock.
3. WHEN an operation succeeds THEN its item/lot changes and transaction record
   SHALL commit together.
4. WHEN an operation fails THEN no partial item, lot, or transaction mutation
   SHALL remain.
5. THE Python store, mobile service layer, and SQL/RPC contract SHALL use the
   same operation semantics and transaction type values.
6. The in-memory implementation SHALL preserve equivalent validation and FEFO
   behavior so tests do not silently pass cases the database rejects.

### Requirement 5: Robot-to-Supabase intake

**User Story:** As the sorter, I want a successfully identified and sorted item
to appear in the correct pantry inventory automatically.

#### Acceptance Criteria

1. WHEN the camera/QR pipeline identifies an item THEN the robot integration
   SHALL send SKU, item name, canonical category, quantity, calories, allergens,
   physical expiration, lot code when available, and destination pantry.
2. THE robot SHALL attribute its inventory source as `robot`.
3. THE robot SHALL use the QR PS1 payload and catalog as the primary product
   facts, while preserving observed package facts when they are more specific.
4. IF the QR payload is valid but the SKU is not in the catalog THEN the system
   SHALL record the item in an `unknown` or reviewable state rather than silently
   assigning an unrelated product.
5. IF passive camera identification fails THEN existing active present-to-camera
   behavior SHALL remain available and SHALL preserve the held item for the
   subsequent placement.
6. A logic-only simulation run SHALL remain possible without Supabase or Drake,
   using the in-memory backend.
7. A simulated run SHALL be able to use a test backend or fixture without
   writing production pantry data.

### Requirement 6: QR, barcode, and catalog consistency

**User Story:** As a volunteer, I want scanning to identify products reliably and
make uncertainty visible instead of creating bad inventory.

#### Acceptance Criteria

1. THE system SHALL parse versioned PS1 QR payloads consistently in Python and
   the mobile app.
2. WHEN a standard EAN, UPC, or Code128 barcode is scanned THEN the system SHALL
   look it up in the shared catalog before asking for manual details.
3. WHEN a code is unknown THEN the system SHALL allow an authorized user to
   provide product details and SHALL mark the learned mapping as user-created
   until reviewed.
4. THE system SHALL preserve the distinction between package-confirmed expiry,
   OCR-derived expiry, catalog-estimated expiry, and missing expiry.
5. THE system SHALL apply one documented precedence order for category,
   calories, allergens, image, and shelf-life facts from QR, catalog, OCR, and
   manual input.
6. QR assets under `assets/qr/` SHALL remain test fixtures and SHALL map to the
   same SKUs in the Python catalog, Supabase catalog, and mobile scan flow.
7. The scan flow SHALL show the volunteer the resolved product, quantity,
   expiration status, and uncertainty before committing stock when confidence
   is insufficient.

### Requirement 7: Mobile application behavior

**User Story:** As a pantry participant, I want the mobile app to expose the
right inventory actions for my role.

#### Acceptance Criteria

1. THE app SHALL support persisted Supabase authentication with email/password
   and the currently supported sign-in providers.
2. WHEN an unauthenticated user opens the app THEN the app SHALL route them to
   authentication; when an authenticated user lacks a profile or role THEN the
   app SHALL route them through profile/onboarding setup.
3. Pantry staff SHALL have access to inventory, scanning, lot review, FEFO
   handout, discard, activity, and drop-off acceptance flows.
4. Donors SHALL have access to needs, scanning their donation bag, submitting a
   bag, and retrieving its handoff identifier without staff inventory rights.
5. Neighbors SHALL have access to public pantry discovery, available resources,
   and eligible inventory information without staff mutation rights.
6. The app SHALL display lot-level expiry information and identify estimated
   dates clearly.
7. The app SHALL use the shared Supabase views/RPCs and SHALL not duplicate
   business-critical FEFO or authorization logic only in JavaScript.
8. Network, RLS, empty-data, and partial-failure states SHALL show actionable
   user feedback and SHALL not report an inventory action as successful before
   the backend confirms it.

### Requirement 8: Native iOS Release build

**User Story:** As the app developer, I want to install the app on a physical
iPhone from Xcode without Metro, so that the app works as a real native build.

#### Acceptance Criteria

1. THE Expo project SHALL generate a valid native iOS workspace using the
   repository's supported Expo SDK and dependency versions.
2. A Release configuration SHALL embed the JavaScript bundle and SHALL not
   require a running Metro server after installation.
3. THE app SHALL read `EXPO_PUBLIC_SUPABASE_URL` and
   `EXPO_PUBLIC_SUPABASE_ANON_KEY` at build time, and SHALL fail visibly with
   setup guidance when they are absent.
4. THE app SHALL use one consistent product name, scheme, bundle identifier,
   icon, and native signing configuration before release.
5. A developer SHALL be able to build and install on a physical iPhone using
   Xcode automatic signing or the documented CLI equivalent.
6. Camera permissions, SecureStore session persistence, QR scanning, and
   authenticated Supabase requests SHALL work in the Release build.
7. A reproducible native verification checklist SHALL record Xcode version,
   Expo SDK, device build result, authentication result, scan result, and
   inventory read/write result.
8. The production mobile bundle SHALL not contain a Supabase service-role key,
   Python credentials, or development-only permissive access assumptions.

### Requirement 9: Existing simulation continuity

**User Story:** As a robotics contributor, I want backend/app integration work to
avoid breaking the working simulation.

#### Acceptance Criteria

1. Existing camera-vision behavior SHALL remain governed by the
   `camera-vision` spec and SHALL continue to support camera rig
   identification, active scan, smooth placement, and diagnostics.
2. The existing scene modes `flat_grid`, `belt_bare`, and `belt_boxes` SHALL
   remain selectable through configuration.
3. Existing logic-only tests SHALL run without Drake, Supabase credentials, or a
   network connection.
4. The new inventory adapter SHALL preserve the in-memory store interface for
   unit tests and local demos.
5. Supabase integration tests SHALL use a disposable/test project or mocked
   client and SHALL not mutate a developer's production pantry by default.
6. The unmerged obstacle-avoidance work SHALL not be marked complete on `main`
   until integrated and independently validated against the camera-vision task
   criteria.

### Requirement 10: Documentation and repository consistency

**User Story:** As a contributor, I want the repository documentation to describe
what actually exists, so that new contributors can start without guessing.

#### Acceptance Criteria

1. `.kiro/steering/project-context.md` SHALL describe the current simulation,
   Supabase migration source of truth, app architecture, category/catalog rules,
   RLS constraints, and native iOS build process.
2. `.kiro/CONTRIBUTIONS.md` SHALL record the existing simulation, Supabase, app,
   and relevant branch history without claiming unmerged work is on `main`.
3. The integration spec SHALL contain requirements, design, and tasks that map
   to the actual files and implementation order.
4. App and Supabase setup documentation SHALL identify stale legacy contracts and
   point contributors to the current migration and service-layer files.
5. The project SHALL use one explicit product-name decision and document any
   transition between PantrySort and Stash.
6. Documentation changes SHALL not include secrets, service-role keys, or local
   device provisioning profiles.

## Proposed decisions requiring confirmation

These are intentionally called out before design work:

1. **Canonical product name:** PantrySort is the repository/robot name and Stash
   is the current app/UI name. The release name must be selected and applied
   consistently.
2. **Canonical schema:** the latest migration-backed lot/pantry schema should
   supersede the original three-table schema.
3. **Canonical category set:** the current `app_categories` keys should be the
   persisted contract, with explicit robot-category translation at the Python
   boundary.
4. **Robot write path:** robot intake and outflow should use atomic authenticated
   backend operations rather than independent row writes.
5. **Release policy:** the mobile app uses the anon key with RLS; service-role
   access, if needed for a robot/server process, stays outside the app bundle.

## References

- [[file:.kiro/specs/camera-vision/requirements.md]]
- [[file:.kiro/specs/camera-vision/design.md]]
- [[file:.kiro/specs/camera-vision/tasks.md]]
- [[file:src/pantrysort/pipeline/sort_loop.py]]
- [[file:src/pantrysort/perception/qr_payload.py]]
- [[file:src/pantrysort/inventory/supabase_store.py]]
- [[file:supabase/migrations/20261024140000_lots_and_app_data.sql]]
- [[file:app/lib/stash.ts]]
- [[file:app/lib/supabase.ts]]
- [[file:assets/catalog.yaml]]
