# PantrySort / Stash 🥫🤖

A food-pantry automation system combining:

- **Drake + SO-101** — kinematic simulation, camera-based QR identification,
  active item presentation, safe motion, and sorting.
- **QR/catalog perception** — PS1 labels, standard barcode lookup, item facts,
  expiration provenance, and category routing.
- **Supabase Postgres** — pantry-scoped inventory, expiration lots, FEFO
  distribution, lifecycle transactions, catalog data, roles, and drop-offs.
- **Expo / React Native** — the current mobile app with pantry staff, donor, and
  neighbor experiences.
- **LeRobot integration seams** — learned policy support alongside the scripted
  simulation policy.

The repository contains a working robotics simulation and a substantially
implemented mobile app. The current integration work is about reconciling their
shared catalog, category, lot, authorization, and atomic-operation contracts.

## Start here

- [`DEV_NOTES.md`](DEV_NOTES.md) — robotics environment notes.
- [`.kiro/steering/project-context.md`](.kiro/steering/project-context.md) —
  current architecture and contributor conventions.
- [`.kiro/specs/camera-vision/`](.kiro/specs/camera-vision/) — camera rig, QR
  identification, active scan, motion, and obstacle-avoidance specification.
- [`.kiro/specs/pantry-app-integration/`](.kiro/specs/pantry-app-integration/) —
  robot/Supabase/mobile integration requirements, design, and tasks.
- [`docs/PROBLEM_AND_SOLUTION.md`](docs/PROBLEM_AND_SOLUTION.md) — problem and
  solution overview.
- [`docs/SUPABASE_SETUP.md`](docs/SUPABASE_SETUP.md) — current Supabase setup.
- [`app/README.md`](app/README.md) — mobile app and native iOS Release setup.

## Repository layout

```text
hackachusetts/
├── .kiro/
│   ├── steering/                         # project-wide architecture guidance
│   └── specs/
│       ├── camera-vision/                # current simulation spec
│       └── pantry-app-integration/       # robot/backend/app contract
├── app/                                  # Expo Router React Native app
├── assets/
│   ├── catalog.yaml                      # source product catalog
│   ├── barcodes/                         # generated barcode fixtures
│   └── qr/                               # QR fixtures and printable labels
├── db/                                   # legacy three-table schema reference
├── docs/                                 # setup and problem/solution docs
├── src/pantrysort/
│   ├── inventory/                        # domain + memory/Supabase adapters
│   ├── perception/                       # QR, catalog, and identification
│   ├── sim/                              # Drake station, cameras, scenes, motion
│   ├── policy/                            # scripted and LeRobot policies
│   └── pipeline/                         # end-to-end sort loop
├── supabase/migrations/                  # current production schema source
├── scripts/                              # simulation, recording, diagnostics
└── tests/                                # pure Python and simulation tests
```

## Robotics environment

Use Python 3.10–3.12. Drake does not publish wheels for newer Python versions.
On Windows, run Drake under the WSL environment documented in `DEV_NOTES.md`.
On macOS, use a supported Python/Drake installation and verify `pydrake`
imports before running the station.

```bash
make install-dev
make test
make lint
python scripts/run_sim.py
```

The simulation supports `flat_grid`, `belt_bare`, and `belt_boxes` scene modes.
Camera/video diagnostics write to timestamped `outputs/` folders. The existing
camera-vision spec tracks the remaining belt-scene and approach/inter-item
obstacle-validation work.

## Supabase and mobile app

The current Supabase contract is the migration chain under
[`supabase/migrations/`](supabase/migrations/), not the older `db/schema.sql`.
It models pantry-scoped items, per-expiration lots, catalog facts, roles, and
transactions. See [`docs/SUPABASE_SETUP.md`](docs/SUPABASE_SETUP.md).

The app uses the Supabase anon key and RLS. Never put a service-role key in
`app/.env` or a mobile bundle. To build a native Release version for a physical
iPhone without Metro:

```bash
cd app
npm install
cp .env.example .env
# fill EXPO_PUBLIC_SUPABASE_URL and EXPO_PUBLIC_SUPABASE_ANON_KEY
npx expo prebuild --platform ios
npx expo run:ios --device --configuration Release
```

See [`app/README.md`](app/README.md) for Xcode signing and acceptance checks.

## Project status

The simulation and app are functional but the shared contract is still being
reconciled. The next implementation work is tracked in
`.kiro/specs/pantry-app-integration/tasks.md`: canonical catalog/category data,
atomic inventory operations, Python/app adapters, RLS hardening, integration
tests, and physical-device Release acceptance.

## License

MIT (see `LICENSE`).
