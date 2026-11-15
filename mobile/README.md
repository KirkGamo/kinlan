# KinLAN mobile app

The Android app (and its web build) for KinLAN: Expo SDK 58, Expo Router, TypeScript. Plan: `docs/KinLAN_Technical_Plan.md`, Section 6. Design: [`DESIGN.md`](../DESIGN.md) (tokens and rules) and the interactive prototype in `docs/design/prototype/`.

## Run it

```bash
npm install
npx expo start
```

Press `w` for the web build. Expo Go can't load the embedded Manrope font or the native tabs exactly as built; on a phone, use the development build below. Telemetry: set `EXPO_NO_TELEMETRY=1`.

The app talks to the live API by default. To use a local server instead:

```bash
EXPO_PUBLIC_API_URL=http://192.168.1.13:8000 npx expo start
```

## Development build on an Android phone (Windows)

The app includes `expo-dev-client`: build the native app once, install it over USB, then load the JavaScript from Metro.

1. On the phone: Developer options > **USB debugging** on, USB mode **File transfer** (USB tethering hides debugging), then accept "Allow USB debugging".
2. Windows paths: the native build writes object files with very long paths, so it fails from a deep folder (such as `...\Network and Communications\kinlan\mobile`) even with Windows long paths enabled. Build from a short copy, with a CMake whose Ninja (1.12+) supports long paths:

   ```bash
   robocopy mobile C:\kb\mobile /E /XD node_modules android .expo dist
   cd C:\kb\mobile && npm ci && npx expo prebuild -p android --no-install
   sdkmanager "cmake;3.31.6"
   ```

   Then point `C:\kb\mobile\android\local.properties` at it: `sdk.dir=...\\Android\\Sdk` and `cmake.dir=...\\Android\\Sdk\\cmake\\3.31.6` (backslashes doubled).
3. Build for the phone's architecture, install, and forward Metro's port:

   ```bash
   cd C:\kb\mobile\android && ./gradlew assembleDebug -PreactNativeArchitectures=arm64-v8a
   adb install -r app/build/outputs/apk/debug/app-debug.apk
   adb reverse tcp:8081 tcp:8081
   ```
4. Start Metro from the repo (`npx expo start --dev-client`) and open KinLAN on the phone.

Rebuild the native app only when native dependencies or `app.json` change; JavaScript changes load through Metro. `android/` is generated and git-ignored.

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
