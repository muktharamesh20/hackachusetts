# PantrySort App (Expo / React Native)

A mobile app for pantry volunteers: sign in, view inventory, and work the
First-Expired-First-Out (FEFO) distribution queue. It reads the same Supabase
tables the robot/sorter writes to (`inventory_items`, `storage_locations`, and
the `distribution_queue` view — see `../db/schema.sql`).

Built with Expo Router + Supabase Auth (email/password), with sessions stored
in the device keychain via expo-secure-store.

## Prerequisites
- Node 18+ (you have 22) and the Expo tooling (`npx expo`).
- A Supabase project with `../db/schema.sql` applied.
- Xcode (for running on an iPhone / simulator).

## Setup

```bash
cd app
npm install
cp .env.example .env
# edit .env:
#   EXPO_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
#   EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key   # ANON key (not service_role!)
```

> Use the **anon** key here, never the service_role key — this bundle ships to
> the device. Row Level Security protects the data (see db/schema.sql).

## Enable email auth in Supabase
Dashboard → Authentication → Providers → Email: enable it. For quick testing you
can turn OFF "Confirm email" so new sign-ups log in immediately.

## Run on your iPhone with Xcode

```bash
npx expo run:ios            # builds a dev client and installs to the simulator
# For a physical iPhone:
#   open the generated ios/ project in Xcode, pick your device + signing team,
#   then Run. Or use: npx expo run:ios --device
```

For a distributable build later, use EAS: `npx eas build -p ios`.

Quick JS-only preview (no native build): `npx expo start`, then scan the QR with
Expo Go. Note: secure-store/native features work best in a dev build.

## Structure
```
app/
├── app/
│   ├── _layout.tsx         # AuthProvider + session route guard
│   ├── (auth)/             # sign-in, sign-up
│   └── (tabs)/             # inventory, distribute (FEFO), settings
├── context/AuthContext.tsx # Supabase auth state
├── lib/supabase.ts         # Supabase client (SecureStore session)
├── lib/inventory.ts        # typed queries against the pantry tables
└── theme/colors.ts
```
