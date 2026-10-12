# Deployment Guide — Kabadiwala Connect 2.0 (Phase 12)

This covers running the whole system for a **local demo**: one
backend, one MongoDB instance, three websites, and the mobile app —
all on one machine (optionally reachable by a phone on the same
network). There is no internet/cloud deployment in this phase; see
"Optional internet deployment" at the end for what that would require
later, not what exists today.

## 1. MongoDB

Local, single-node, no auth, no TLS — appropriate for a local demo and
unchanged since Phase 1.

```bash
mongod --dbpath /path/to/your/data/dir
```

The backend connects to `kabadiwala_connect_2_0` (see `backend/.env`,
`DATABASE_NAME`) — a database name deliberately different from Mongo's
own default so it never collides with unrelated data that might exist
in a `kabadiwala_connect` database on the same machine. This project's
data has never been reset since Phase 3 and Phase 12 does not change
that.

## 2. Backend

```bash
cd backend
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

**For browser-only demo (web apps and/or the Android emulator, all on
this same machine):**
```bash
uvicorn app.main:app --port 8000
```
Binds to `127.0.0.1` only — sufficient for every web app and the
emulator (see `APK_BUILD_GUIDE.md` for why the emulator works fine
against a loopback-only backend).

**Only if a physical Android device needs to reach it:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
This exposes the backend to your whole local network, not just this
machine — fine for a temporary local demo, not something to leave
running afterward. You'll also need:
```powershell
New-NetFirewallRule -DisplayName "Kabadiwala backend (demo)" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```
(or accept the Windows Firewall prompt the first time a device
connects) — Windows blocks unsolicited inbound connections to a
listening port by default, independent of anything the app does.

Check it's up: `curl http://127.0.0.1:8000/api/v1/health`

## 3. The websites (Recycler, Government Admin)

rrr-centre-web has been removed from the active workflow (Phase "fix the
recycler workflow"); RRR-centre lot creation/publishing is API-only now,
driven directly against `/api/v1/lots` by an authenticated RRR_CENTER
account. Each remaining site is an independent Vite/React SPA. For local
dev with hot reload:
```bash
cd recycler-web && npm run dev       # http://localhost:5173 (or next free port)
cd admin-web && npm run dev          # http://localhost:5174 (or next free port)
```
Vite auto-assigns the next free port starting at 5173 if multiple are
running at once — there is no fixed port mapping between them, and the
backend's CORS policy (`^https?://(localhost|127\.0\.0\.1)(:\d+)?$`)
already allows any port on loopback, so this needs no configuration.

For a production-style build (what a real deploy would actually serve):
```bash
cd recycler-web && npm run build && npm run preview      # serves dist/ on :4173
cd admin-web && npm run build && npm run preview
```
Both read `VITE_API_BASE_URL` at build time (defaulting to
`http://127.0.0.1:8000` if unset) — no code change needed to point a
build at a different backend, only an env var at build time.

## 4. Mobile app (Home User + Collector)

See `APK_BUILD_GUIDE.md` for the full build/install process. Summary:
`flutter run` for development (any connected device/emulator, hot
reload); `flutter build apk --release --dart-define=API_BASE_URL=...`
for the demo-ready release APK, with the URL chosen per
`APK_BUILD_GUIDE.md`'s emulator-vs-physical-device guidance.

## 5. Suggested local-demo run order

1. Start `mongod` (or confirm it's already running).
2. Start the backend (loopback-only unless a physical phone is part of
   the demo).
3. Start whichever of the three websites the demo needs.
4. Launch the emulator (or connect the physical device) and install/
   run the mobile app.

No process manager, reverse proxy, or container runtime is used or
needed for this — matches the project's explicit "no Docker/
Kubernetes/cloud infrastructure" constraint for local-demo scope.

## 6. Optional internet deployment (not implemented — considerations only)

None of this exists today; it is scoped out of Phase 12 deliberately.
If pursued later:
- A git remote (none is currently configured on this repository) and a
  host for it (e.g. GitHub), since most PaaS deploy from a git repo.
- A hosted MongoDB (e.g. Atlas) — only requires overriding
  `DATABASE_URL`/`DATABASE_NAME` in the backend's environment; no code
  change, since the connection string was already externalized since
  Phase 1.
- Real, non-default `JWT_SECRET` and `ADMIN_DEFAULT_PASSWORD` values
  (Phase 11 already warns loudly at startup if these are still at
  their known defaults).
- Widening `CORS_ALLOWED_ORIGIN_REGEX` to the real deployed frontend
  origin(s) — never to a blanket wildcard.
- HTTPS termination in front of the backend (a platform-provided one,
  e.g. from the PaaS, is sufficient) — this would let the Android
  network-security-config's cleartext exception be removed entirely,
  since the app would then be talking to a real `https://` URL.
- Rebuilding all three web apps and the APK against the real public
  backend URL.

## 7. Known limitations

- Local-only: no TLS, no auth on MongoDB, no process supervision/
  restart-on-crash — all correct and sufficient for a local/judged
  demo, none of it appropriate to leave running as a real service.
- The release APK is debug-signed (see `APK_BUILD_GUIDE.md`) — a real
  distribution build would need its own upload keystore.
- `JWT_SECRET`/`ADMIN_DEFAULT_PASSWORD` remain at their known local
  defaults in this environment's `.env`, exactly as Phase 11's startup
  warning already discloses live every time the backend starts.
