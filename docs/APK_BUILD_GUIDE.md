# APK Build Guide — Kabadiwala Connect 2.0 (Phase 12)

Covers building and installing the Flutter mobile app (Home User +
Collector) as an Android APK for local demo purposes. This is a
**local-demo build**, not a Play Store release — see "Known
limitations" at the end before treating it as anything more.

## 1. The two ways to run this app against the backend

The backend has no TLS (mock-payment/mock-AI architecture, HTTP only)
and normally only listens on `127.0.0.1`. Which of these two setups you
use determines both the `API_BASE_URL` you build with and whether the
backend needs an extra flag.

### A. Android emulator (what this phase actually built and tested)

The emulator has a fixed special alias, `10.0.2.2`, that always routes
to the **host machine's own loopback address** — this works even
though the backend is started with no `--host` flag at all (i.e. bound
only to `127.0.0.1`), because the emulator's virtual router, not the
backend, does the address translation.

```bash
cd mobile
flutter build apk --release --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

No backend changes needed for this path.

### B. A real physical Android device on the same Wi-Fi/LAN

A physical device is not the emulator — `10.0.2.2` means nothing to
it. It must reach the backend at the **host machine's real LAN IPv4
address** instead. Find it with:

```powershell
ipconfig          # look for "IPv4 Address" under your active adapter (Wi-Fi/Ethernet)
```

(For this development machine at the time of Phase 12, that address
was `10.74.38.76` — yours will very likely be different, and it can
change whenever your machine reconnects to a network. Always re-check
with `ipconfig` rather than assuming a value from this document is
still correct.)

```bash
cd mobile
flutter build apk --release --dart-define=API_BASE_URL=http://<your-LAN-IP>:8000
```

This path additionally requires:
1. **Backend bound to all interfaces, not just loopback** — start it
   with `--host 0.0.0.0` (see `DEPLOYMENT_GUIDE.md`). Without this, the
   backend process refuses connections from anywhere but the host
   machine itself, regardless of what the phone sends.
2. **A Windows Firewall inbound rule for port 8000** — Windows blocks
   unsolicited inbound connections to a listening port by default.
   Either accept the "Allow this app through Windows Defender
   Firewall" prompt the first time you start the backend with
   `--host 0.0.0.0`, or add a rule manually:
   ```powershell
   New-NetFirewallRule -DisplayName "Kabadiwala backend (demo)" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
   ```
3. **Both devices on the same network** — a phone on mobile data, a
   guest Wi-Fi network, or a different VLAN than the host machine will
   not be able to reach it no matter how the backend or firewall are
   configured.

**This session did not have a physical Android device available. The
physical-device path above is fully documented and was reasoned
through during the Phase 12 audit, but it has not actually been built
or tested end-to-end — do not treat it as verified until you've run it
yourself.**

## 2. Why this needs a network-security-config, not just the right URL

Android 9+ (API 28+) blocks all cleartext (plain `http://`) network
traffic by default, app-wide, regardless of what URL you point the app
at. Since this backend has no TLS, a release build would have every
single API call silently blocked by the OS without an explicit
exception.

`mobile/android/app/src/main/res/xml/network_security_config.xml`
grants that exception, but **only** for the two specific hosts this
guide documents (`10.0.2.2` and this machine's current LAN IP) — not a
blanket cleartext allowance for every domain. It's wired in via
`android:networkSecurityConfig="@xml/network_security_config"` on the
`<application>` tag in `AndroidManifest.xml`. If your LAN IP changes,
add the new one to that file's `<domain>` list before building for a
physical device — the build will otherwise succeed but every network
call will fail silently on-device.

## 3. Build commands

```bash
cd mobile
flutter clean          # optional, only if you suspect a stale build
flutter pub get
flutter build apk --release --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Output: `mobile/build/app/outputs/flutter-apk/app-release.apk` (also
mirrored at `mobile/build/app/outputs/apk/release/app-release.apk`).
Both paths are gitignored — this is a build artifact, never committed.

## 4. Installing on the emulator

```bash
flutter emulators --launch <emulator-id>     # if not already running
adb install -r mobile/build/app/outputs/flutter-apk/app-release.apk
```

If `adb install` reports `cmd: Can't find service: package` even
though `adb devices` shows the emulator as `device` (not `offline`),
the emulator's Android framework (`system_server`) hasn't actually
finished starting despite `sys.boot_completed=1` — this was
encountered during this exact phase. `adb -s <id> reboot` and waiting
for the device to reattach resolves it; there is nothing wrong with
the APK or the build in that case.

## 5. Known limitations (read before assuming this is production-ready)

- **This is a debug-signed release build**, not a properly
  keystore-signed one. `android/app/build.gradle.kts`'s `release`
  build type explicitly uses `signingConfigs.getByName("debug")` (with
  its own `// TODO: Add your own signing config` comment, unchanged
  this phase) so that `flutter build apk --release` works without
  requiring you to generate and manage a real keystore. This is
  appropriate for a local/judged demo, not for Play Store distribution
  — a real release needs its own upload keystore.
- **`API_BASE_URL` is baked in at build time**, not configurable after
  install. Building for the emulator and expecting it to work on a
  physical device on your LAN (or vice versa) will fail — rebuild with
  the correct value for whichever device you're targeting.
- **No HTTPS anywhere.** Acceptable for a local demo; a real internet
  deployment would need a TLS-terminating backend and the
  network-security-config override could then be removed entirely.
