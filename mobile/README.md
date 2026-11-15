# KinLAN mobile app

The Android app (and its web build) for KinLAN: Expo SDK 58, Expo Router, TypeScript. Plan: `docs/KinLAN_Technical_Plan.md`, Section 6. Design: `docs/design/direction.md` (tokens and rules) and the interactive prototype in `docs/design/prototype/`.

## Run it

```bash
npm install
npx expo start
```

Press `w` for the web build or `a` for an Android emulator. Expo Go can't load the embedded Manrope font or the native tabs exactly as built; for a phone, use a development build (`npx eas-cli@latest build --profile development`, issue #63). Telemetry: set `EXPO_NO_TELEMETRY=1`.

The app talks to the live API by default. To use a local server instead:

```bash
EXPO_PUBLIC_API_URL=http://192.168.1.13:8000 npx expo start
```

## Checks (also run by CI)

```bash
npx tsc --noEmit
npx eslint .
npx expo-doctor
```

## Structure

| Path | What |
|---|---|
| `src/app/` | Routes only (Expo Router). `(tabs)/_layout.tsx` is the native Material tab bar on Android; `_layout.web.tsx` is the web tab bar |
| `src/theme/` | Colours, the nine type roles, spacing, radii and motion from `direction.md`. Never hard-code colours or sizes |
| `src/components/ui/` | The design system (`Text`, `Screen`, `Card`, `SectionLabel`). Screens import from here, not from `react-native` |
| `src/api/` | The API client (errors, token refresh), session storage (keystore on Android, `localStorage` on web) and TanStack Query |
| `assets/images/` | App icon, adaptive icon, splash and favicon, made from the KinLAN mark |

## Web build and CORS

`npx expo export --platform web` writes a static single-page app to `dist/`. The API only accepts browser requests from origins in its `CORS_ORIGINS` setting (`http://localhost:8081`, Expo's dev port, for now). When the web build gets a public address, add it to `CORS_ORIGINS` on Render.
