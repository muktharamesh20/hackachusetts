# PantrySort / Stash mobile app

The Expo/React Native app for the pantry system. The repository and robot
simulation use the PantrySort name; the current app UI and Supabase-facing data
layer use Stash. The final release name, scheme, bundle identifier, and icon
must be made consistent before production release.

The app currently supports three role experiences:

- **Pantry staff** — inventory, camera scanning, lot/expiry review, FEFO handout,
  discard, activity, and donor drop-off acceptance.
- **Donors** — needs, donations, scanned donation bags, and handoff slips.
- **Neighbors** — pantry discovery, available resources, and saved pantries.

## Current data contract

The app uses the latest migration-backed Supabase schema under
`../supabase/migrations/`. The current contract is pantry-scoped and lot-aware:

- `inventory_items` — product aggregate currently on hand.
- `inventory_lots` — quantities grouped by expiration date and source.
- `inventory_transactions` — intake, distribute, and discard history.
- `app_categories` and `catalog_items` — canonical categories and product facts.
- `pantries`, `profiles`, drop-off, resource, and goal tables.

The app service boundary is [`lib/stash.ts`](lib/stash.ts). Do not build new
business-critical writes against the legacy three-table `../db/schema.sql`
contract. See [`../.kiro/specs/pantry-app-integration/`](../.kiro/specs/pantry-app-integration/)
for the integration requirements and migration plan.

## Setup

Prerequisites:

- Node 18+ and npm.
- A Supabase project with the migration chain applied in order.
- Xcode and CocoaPods for native iOS builds.

```bash
cd app
npm install
cp .env.example .env
```

Fill `app/.env` with the **anon** key only:

```text
EXPO_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

Never put `SUPABASE_SERVICE_ROLE_KEY` in the app. The bundle ships to a device;
RLS and authenticated roles protect its requests. The app client persists
sessions with SecureStore and has an AsyncStorage/web fallback.

Enable Supabase Authentication → Providers → Email. For local testing, you can
disable email confirmation; enable it for a real deployment.

## Native iOS Release build

A Release build embeds the JavaScript bundle and does not need Metro after it is
installed. Configure signing in Xcode with your Apple Developer team.

```bash
cd app
npx expo prebuild --platform ios
npx expo run:ios --device --configuration Release
```

Or open the generated workspace in Xcode:

```bash
open ios/pantrysort.xcworkspace
```

Select a physical iPhone, enable automatic signing, choose the team, select the
Release configuration, and run. Verify authentication, SecureStore session
persistence, camera scanning, Supabase reads, and one authorized inventory
operation on the device. Keep `.env`, signing assets, provisioning profiles,
and native secrets out of git.

For a development preview, `npx expo start` / Expo Go may be useful, but it is
not the production acceptance path and requires Metro.

## Structure

```text
app/
├── app/                 # Expo Router routes and role layouts
│   ├── (auth)/          # sign-in/sign-up
│   ├── (onboarding)/    # profile and role setup
│   ├── (pantry)/        # pantry staff flows
│   ├── (donor)/         # donor flows
│   └── (neighbor)/      # neighbor flows
├── components/          # shared scan and UI components
├── context/             # auth/profile state
├── lib/
│   ├── supabase.ts      # Supabase client + SecureStore session
│   ├── stash.ts         # typed app data service
│   └── qr.ts            # PS1/barcode parsing and mapping
└── theme/               # app colors, typography, and view modes
```

## Validation

```bash
npx tsc --noEmit
npx expo install --check
npx expo run:ios --device --configuration Release
```

The full robot/app/backend acceptance checklist is tracked in
`.kiro/specs/pantry-app-integration/tasks.md`.
