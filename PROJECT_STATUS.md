# PROJECT_STATUS — Kabadiwala Connect 2.0

Last updated: 2026-09-14, end of Phase 10 sprint (Integration — a real
cross-app audit found and fixed four genuine integration defects (a
Flutter-web loopback bug, a broken recycler-web navigation path, and
two stale admin-web status mappings), closed the one real end-to-end
gap by adding the admin-controlled `SOLD/PAID → COMPLETED` step, and
added true multi-module tests — one full chain from home-user
registration to a redeemed reward, cross-role isolation against shared
live data, and combined edge cases spanning two modules at once — on
top of the unchanged Phase 1–9 test suite).

This file documents the **actual, verified** implementation state. Nothing
here is claimed complete unless it is implemented and its tests have
actually been run and passed, per project rules.

---

## Phase 1 — Backend Foundation + Authentication: COMPLETE, VERIFIED

- Auth (`login`, `refresh`, `logout`, `/me`), RBAC (`require_role`, DB-sourced
  role/status re-check on every request), audit logging, structured error
  contract, Swagger BearerAuth.
- Git checkpoint: `3e799c5`.
- 32/32 tests passing (re-verified independently at the start of this sprint).

## Phase 2 — First Backend Vertical Slice: COMPLETE, VERIFIED

**Goal:** wards → home-user registration → admin-created collector →
e-waste submission → geo-verified handover, as one real, working, tested
slice — not a stub.

### What was built

| Module | Endpoints | Notes |
|---|---|---|
| `state_machines/ewaste_states.py` | — | Pure, dependency-free allow-listed transition table covering the full `CREATED → … → COMPLETED` chain plus the `FLAGGED_FOR_REVIEW` side branch and its admin-recovery transitions (`→ HANDOVER_PENDING` retry, `→ REJECTED` terminal). No endpoint writes `status` directly. |
| `core/geo.py` | — | Pure haversine distance + GPS validity (null/out-of-range/`(0,0)` sentinel rejection). |
| `wards` | `POST /api/v1/wards` (admin), `GET /api/v1/wards` (any authenticated) | Reference data. `rrr_centre_id` intentionally omitted — no `rrr_centres` module yet (Phase 5). |
| `home_users` | `POST /api/v1/home-users/register` (public), `GET /api/v1/home-users/me` (HOME_USER) | Self-registration creates both the `users` account and the `home_users` profile. |
| `collectors` | `POST /api/v1/admin/collectors` (GOVERNMENT_ADMIN only), `GET /api/v1/collectors/me` (COLLECTOR, read-only) | **No self-registration endpoint exists anywhere.** `employee_id` = login username, issued only by admin. |
| `ewaste` | `POST /api/v1/ewaste/submissions` (HOME_USER, `Idempotency-Key` required), `GET /api/v1/ewaste/submissions` + `/{id}` (own / admin), `POST /api/v1/ewaste/submissions/{id}/handover` (COLLECTOR, `Idempotency-Key` required) | Full geo verification: GPS validity, timestamp sanity (window from `MAX_HANDOVER_WINDOW_HOURS`), haversine distance (`MAX_HANDOVER_DISTANCE_METERS`), ward/assignment match, duplicate-handover prevention (DB unique index + pre-check). Failure routes to `FLAGGED_FOR_REVIEW`, not silent success. |

Audit logging (`audit.record()`, reused unchanged from Phase 1) fires on:
`WARD_CREATED`, `HOME_USER_REGISTERED`, `COLLECTOR_CREATED`,
`EWASTE_SUBMISSION_CREATED`, `EWASTE_HANDOVER_RECORDED`.

New Mongo indexes (added in `db/mongo.py`, additive only — no existing
index touched): unique `wards.ward_id`, unique `home_users.user_id`,
unique `collectors.user_id` + `collectors.employee_id`, unique
`e_waste_submissions.submission_id` + compound `(home_user_id, status)`,
unique `collection_handovers.submission_id`, and unique
`(idempotency_key, scope)` on `idempotency_keys` — this last one was
defined but **not yet created** by Phase 1 (its own docstring said the
first idempotent module owns it); Phase 2 is that module.

### Deliberate scoping decisions (flagged, not silent)

1. **No separate `e_waste_items` collection yet.** The item's lifecycle
   `status` lives directly on the `e_waste_submissions` document. The
   architecture's `e_waste_items` collection exists specifically to carry
   the immutable `reward_eligible_at` stamp, which has no consumer until
   the Phase 9 reward batch job exists — creating the collection now would
   be an empty shell. **Action needed in Phase 9:** introduce
   `e_waste_items`, migrate/derive from `e_waste_submissions`, and add the
   `reward_eligible_at` set-once write at the `COLLECTED` transition.
2. **"Collector assignment" and "assignment/ward validation" are one check**,
   performed at handover time (collector's `ward_id` must equal the
   submission's `ward_id`) rather than a separate dispatch/assignment
   endpoint — no such endpoint was in Phase 2's explicit scope.
3. **Collector "must change password on first login" is deferred** — admin
   sets the initial password directly at creation. Not yet enforced.
4. **No admin `PATCH /api/v1/admin/collectors/{id}`** yet (update
   employee_id/rrr_id/ward_id/assigned_area) — Phase 2 scope was creation
   only. Needed before Phase 5+ if a collector's ward assignment ever needs
   correcting post-creation.
5. **Idempotency race gap inherited from Phase 1's shared helper, not
   introduced here:** `idempotency.py`'s `get_cached_response` /
   `store_response` guarantee correctness for **sequential** replay
   (verified by tests) but not a true concurrent race — two simultaneous
   requests with the same key can both pass the cache-miss check and both
   execute before the second one's `store_response` hits the duplicate-key
   error, by which point its side effect (e.g. a second submission) has
   already happened. Closing this needs a "reserve-before-execute" redesign
   of the shared helper — out of scope for this sprint, flagged for
   whoever picks up Phase 9 payments (where this actually matters).
6. **Verified only against `mongomock-motor`, not real MongoDB this
   session.** Real MongoDB was confirmed reachable (v8.2.2) at the start of
   the assessment, but running the automated suite against it wasn't done
   this sprint (all of Phase 2's new indexes are simple top-level unique
   indexes, not the partial-unique-index case the Phase 1 docs specifically
   flagged as mongomock-risky — that case doesn't arrive until Phase 9's
   bid-acceptance index). Recommended before trusting this in a live demo:
   point `tests/conftest.py`'s `test_db` fixture at a real
   `AsyncIOMotorClient` against a disposable test database and re-run.

### Tests — actually executed, this session

Ran `pytest -v` in the project's own `.venv` (Python 3.10, real bcrypt/JWT,
`mongomock-motor` in-memory DB — same setup Phase 1 used).

**Result: 83 passed, 0 failed.** (32 Phase 1 + 51 new Phase 2)

New test breakdown:
- `tests/unit/test_geo.py` — 7 (haversine known distances, GPS validity: null/out-of-range/null-island)
- `tests/unit/test_ewaste_states.py` — 10 (full happy-path chain, FLAGGED_FOR_REVIEW branch + recovery, arbitrary/backward/terminal-state rejection)
- `tests/integration/test_wards_api.py` — 5 (admin create, non-admin 403, duplicate ward_id 409, list, auth-required)
- `tests/integration/test_home_users_api.py` — 5 (register+login, unknown ward 404, duplicate username 409, `/me`, RBAC on `/me`)
- `tests/integration/test_collectors_api.py` — 7 (admin create, employee_id login, **no self-registration endpoint exists (404)**, non-admin 403, duplicate employee_id 409, `/me`, RBAC isolation vs. home-user token)
- `tests/integration/test_ewaste_api.py` — 17 (submission create, idempotency-key-required, idempotency replay dedup, distinct-key non-dedup, RBAC, unknown ward, valid handover → COLLECTED, invalid GPS → FLAGGED, excessive distance → FLAGGED, invalid timestamp → FLAGGED, duplicate handover → 409, handover idempotency replay, out-of-ward collector → 403, non-collector RBAC, audit log entries, cross-home-user ownership isolation, admin can view any)

One real bug was caught and fixed by this test suite before it passed: the
handover service originally checked submission status *before* checking
for an existing handover record, so a second handover attempt on an
already-handled submission returned a generic 400 instead of the specific
`DUPLICATE_HANDOVER` 409 the architecture calls for. Reordered; now covered
by `test_duplicate_handover_rejected`.

### Known limitations / honestly unverified

- Not run against real MongoDB this session (see point 6 above).
- No concurrency test yet for the handover duplicate-key race (Phase 1's
  concurrency-test pattern — `asyncio.gather` firing two requests at once —
  exists in the architecture doc for bid-acceptance; the same pattern
  should be applied to handover once real-Mongo verification happens).
- `on_event("startup")` deprecation warning (FastAPI) is pre-existing from
  Phase 1, not addressed this sprint — cosmetic, not a test failure.

---

## Phase 3 — Home User Mobile App: COMPLETE, VERIFIED

**Goal:** a working Flutter Home User app wired to the real Phase 1+2
backend — register/login → dashboard → submit e-waste with photo+GPS →
see the actual returned status. No mocked backend responses anywhere in
the app; every screen calls the real API contract.

### Pre-work verification (done before writing any code)

- Flutter 3.47.3 (stable) / Dart 3.13.3 confirmed installed and working.
  `flutter doctor`: Android toolchain ✅, Chrome/Edge web ✅, Windows
  desktop ❌ (no Visual Studio C++ workload — not installed this sprint;
  demo target is Android emulator/device or Chrome/Edge web instead).
- No pre-existing Flutter project in the repo.
- Re-read the actual Phase 1/2 router/schema code (not assumption) to pin
  down exact contracts: login returns `{access_token, refresh_token,
  role}` only (no identity fields — `/me` is a required follow-up call);
  submission create requires role `HOME_USER` + header `Idempotency-Key` +
  body `{ward_id, photo_file_id, home_lat, home_lng, home_ts?}`.

### One backend change made, disclosed (not silent)

`GET /api/v1/wards` was authenticated-only in Phase 2. The registration
screen needs a ward picker *before* the user has an account/token, and
there was no way to get one. Fix: made **only the list route** public
(`backend/app/modules/wards/router.py`); ward creation is still
`GOVERNMENT_ADMIN`-only, completely unchanged. Updated the one test that
asserted 401-without-token (`test_list_wards_requires_auth` →
`test_list_wards_is_public`, in `backend/tests/integration/test_wards_api.py`)
to match the new, deliberate contract. Full backend suite re-run after
this change: **83/83 still passing.**

### Also disclosed: no real photo upload

The Phase 2 backend's `POST /ewaste/submissions` only ever accepted an
opaque `photo_file_id` *string* — there is no file-upload/storage endpoint,
and building one was out of Phase 3's scope (and not something the mobile
client should invent on its own). The app genuinely captures/picks a photo
on-device (proves the camera/gallery integration works) and computes bytes
in memory for the on-screen preview, but sends only a locally-generated
reference id (`local-photo:<uuid>`) as `photo_file_id` — it never claims
the image was uploaded anywhere it wasn't. This is stated directly in the
Submit E-Waste screen's UI copy, not hidden.

### What was built (`/mobile`, Flutter project root per the architecture doc)

```
lib/
  core/            config.dart, api_client.dart, api_exception.dart,
                   auth_storage.dart, location_service.dart,
                   photo_picker_service.dart, idempotency_key_generator.dart
  features/
    auth/          AuthSession model, AuthRepository, AuthController
    home_user/     Ward + HomeUserProfile models, HomeUserRepository
    ewaste/        Submission + SubmissionCreateResult models, EwasteRepository
  screens/         auth_gate, login, register, home (dashboard),
                   submit_ewaste, submissions_list, submission_detail
  shared/          validators.dart, submission_status.dart (backend-status →
                   label/color map), state_views.dart (loading/empty/error), theme.dart
main.dart          Provider-based DI wiring
```

Covers every item in the Phase 3 scope list:
- **Auth:** login against the real backend, tokens persisted as one JSON
  unit in `flutter_secure_storage`, session restore on app start (re-checks
  `/me`, attempts one `/auth/refresh` on an expired token, clears storage
  and falls back to the login screen on any failure), logout (best-effort
  server call + unconditional local clear).
- **Registration/profile:** full name, address, ward (dropdown fed by the
  now-public `GET /wards`), household lat/lng via device GPS
  (`geolocator`), optional UPI ID, auto-login immediately after successful
  registration, profile shown on the dashboard.
- **Home dashboard:** profile summary, Submit E-Waste entry point, My
  Submissions entry point, logout.
- **E-waste submission:** camera/gallery photo capture (`image_picker`),
  live GPS capture, `Idempotency-Key` generated once per submission
  attempt and reused across retries of that same attempt (a fresh key
  only on a genuinely new attempt), real API call, explicit success/failure
  UI — never a fabricated success.
- **Submission tracking:** list + detail screens driven entirely by the
  actual `status` string the backend returns; the status→label/color map
  covers the full backend state-machine allow-list generically (so an
  unrecognized value still renders instead of crashing), but only
  `WAITING_FOR_COLLECTION` / `COLLECTED` / `FLAGGED_FOR_REVIEW` are
  actually reachable from this app's own flow in Phase 2's current
  backend scope (handover is a Collector action — Phase 4).
- **API layer:** single `ApiClient` used by every repository — attaches
  Bearer tokens, parses the `{success:false,error_code,message}` contract,
  separately handles FastAPI's differently-shaped 422 validation errors,
  network errors (`SocketException`), and timeouts, all surfaced as one
  `ApiException` type. No secrets in source; `AppConfig.apiBaseUrl`
  defaults per-platform (`10.0.2.2` for Android emulator, `localhost` for
  web) and is overridable via `--dart-define=API_BASE_URL=...`.
- **Role isolation:** `AuthRepository.login()` throws `WrongRoleException`
  and refuses to persist a session if the authenticated account's role
  isn't `HOME_USER` — even though backend RBAC is what actually enforces
  this on every API call regardless of what the client does. No collector
  screens exist anywhere in this app.
- **UI:** Material 3, one plain theme, explicit loading/empty/error widgets
  reused across every data-driven screen, inline form validation, no
  animations beyond Flutter's defaults.

### Tests — actually executed, this session

`flutter analyze`: **No issues found.**

`flutter test`: **59/59 passed.** Breakdown: `ApiClient` error handling (9
— structured errors, FastAPI 422 shape, non-JSON 500, `SocketException`,
timeout with an injectable duration so the test doesn't block for the real
15s), idempotency key generation/uniqueness (2), `AuthController` state
transitions (5 — login success/failure/wrong-role, restore, logout),
`AuthRepository` (8 — login incl. persistence, wrong-role rejection,
restore incl. the refresh-token fallback path and its own failure path,
logout), model serialization round-trips (`AuthSession`,
`HomeUserProfile`, `Ward`, `Submission` in both its list- and
detail-endpoint shapes) (9), `HomeUserRepository` (5 — ward list is
tokenless, registration request-body construction incl. conditional
`upi_id`, error propagation), `EwasteRepository` (6 — submission request
construction, idempotency-key reuse across a retry, error propagation for
both submission and detail-fetch), form validators (9), status-label
mapping incl. every state in the backend's own allow-list plus an unknown
fallback (3), and two `LoginScreen` widget tests (error banner rendering,
client-side validation blocking the API call, navigation to Register) (3).

One real test-writing mistake was caught and fixed here too: the status
label test asserted `'Flagged for Review'` (lowercase "for") but the
actual, correct, simpler title-casing implementation produces `'Flagged
For Review'` — fixed the test expectation rather than adding minor-word
special-casing the app doesn't need.

Backend: **83/83 pytest still passing** after the wards-router change
(re-run in full, not assumed).

### Live smoke test & manual end-to-end verification (done after the above)

Beyond `flutter analyze`/`flutter test`/pytest, the app was actually run
against the real running backend and manually driven through the full
demo flow in a browser — this is demo-verified, not just test-verified.

**Android attempt, then Chrome fallback:** `flutter emulators --launch
Pixel_8` booted `emulator-5554` (`sys.boot_completed=1`), but its package
manager service never came up after ~100s of polling (`pm path android`
kept failing with "Can't find service: package") — an emulator/tooling
environment issue on this machine, not an app or code defect. Per
instructions, fell back to the explicitly-sanctioned alternative: `flutter
run -d chrome --web-port=8765 --dart-define=API_BASE_URL=http://localhost:8000`.
Chrome launch succeeded cleanly (no code changes needed for this target).

**Bug #1 found live, root-caused, fixed — CORS.** The registration screen
loaded but ward-list fetch failed with "Could not reach the server."
Root cause, confirmed (not assumed) via direct evidence: `grep` for
CORS/Middleware across `app/` returned nothing — the backend had no
`CORSMiddleware` at all. Simulating the browser's preflight
(`OPTIONS /api/v1/wards` with `Origin: http://localhost:8765`) reproduced
it exactly: `405 Method Not Allowed`, no `Access-Control-Allow-Origin`
header. Since `ApiClient` sends `Content-Type: application/json` (a
non-"simple" header), every browser call requires a preflight, and the
browser blocks the whole request when that preflight fails — surfacing to
Dart as a generic `http.ClientException` → our `NETWORK_ERROR`, which
matched the reported symptom precisely. **Fix:** added `CORSMiddleware`
in `backend/app/main.py`, origin-restricted via a new
`Settings.cors_allowed_origin_regex` (`backend/app/core/config.py`,
documented in `.env.example`) defaulting to loopback-only
(`^https?://(localhost|127\.0\.0\.1)(:\d+)?$`) — **not**
`allow_origins=["*"]`. `allow_credentials=False` (auth is Bearer-header,
not cookies, so browser "credentials" mode was never relevant).
Verified: a non-loopback `Origin: http://evil.example.com` gets no
`Access-Control-Allow-Origin` back; `http://localhost:8765` does. Backend
pytest re-run after this change: 83/83. No Flutter code touched for this
fix — Android is unaffected (mobile HTTP clients aren't subject to
browser CORS).

**Bug #2 found live — pre-existing unrelated data in the default local
Mongo database.** The real local `kabadiwala_connect` database already
had 22 `collectors` documents (and collections like `gov_payments`,
`zone_offices`, `otp_codes`) from an unrelated prior project, using a
different schema (`collector_id`/`phone`/`pin_hash`, not our
`user_id`/`employee_id`/`password_hash`) — our Phase 2
`collectors.user_id` unique index build failed on startup against it
(duplicate `null` keys, since none of those legacy docs have `user_id`).
**Fix, environment-only, no data touched:** created `backend/.env`
(git-ignored, not committed) pointing `DATABASE_NAME` at an isolated
`kabadiwala_connect_2_0`. The legacy `kabadiwala_connect` database was
never modified — verified its `wards` collection count stayed `0`
throughout.

**Demo reference data — exactly one ward, created through the real API,
not a direct DB write.** The isolated database started with zero users
and zero wards (confirmed by direct read before touching anything). Used
the *existing* seed script (`python -m scripts.seed_admin` — idempotent,
env-driven, never resets) to provision the demo `GOVERNMENT_ADMIN`
account in the isolated DB only, then called the real
`POST /api/v1/wards` (not a Mongo insert) to create exactly one ward:
**`ward_id: "SIH-DEMO-01"`, `name: "SIH Demo Ward - Koramangala"`**.
Verified afterward: `GET /api/v1/wards` returns exactly this one ward;
unauthenticated `POST /api/v1/wards` still `401`; exactly one ward
document exists (no duplicates); backend pytest 83/83.

**Full manual demo flow, verified live in Chrome, by the user:**
Home User registration → login → dashboard (loaded real backend profile
data) → e-waste submission screen → real photo selected via the
browser's file/camera picker → real browser GPS captured → submission
sent to the backend → backend returned a real `submission_id` → final
displayed status: `WAITING_FOR_COLLECTION`. Every step hit the actual
running backend; nothing was mocked or faked for this run.

### Known limitations / honestly unverified

- **Android was not actually verified live this session** — only Chrome
  web. The emulator's package-manager service never came up (see above);
  this is an environment/tooling gap on this machine, not a known app
  defect, but Android-specific behavior (camera/GPS permission prompts,
  `10.0.2.2` base URL routing, secure storage on Android's Keystore) is
  therefore still test-verified only, not demo-verified, and should be
  retried once the emulator issue is resolved or on a physical device.
- **Local dev setup is not yet zero-config from a fresh clone.** Getting
  the backend running standalone against this machine's MongoDB currently
  requires manually creating `backend/.env` with a non-default
  `DATABASE_NAME` (because of the unrelated legacy data noted above) and
  running the seed script — neither step is unique to this machine's
  history, but neither is automated or documented in `SETUP_GUIDE.md` yet.
- Session-restore/refresh logic, wrong-role rejection, and idempotency-key
  reuse are covered by repository/controller-level tests against a mocked
  HTTP layer (`http.testing.MockClient`), not by driving the actual UI
  end-to-end in an integration test — no `integration_test` package/driver
  was set up (out of the 3-hour budget).
- No widget tests for `RegisterScreen`, `HomeScreen`, or
  `SubmitEwasteScreen` — only `LoginScreen` got widget-level coverage;
  the underlying repositories/controllers those screens call are
  thoroughly tested, but the screens' own widget trees are not.
- `flutter pub get` reported 18 packages with newer versions available
  beyond the pinned constraints — not upgraded this session (stability
  over latest-version chasing, consistent with "prefer stable, well-
  supported packages").
- Collector app, RRR/Recycler/Admin websites, AI classification,
  payments/rewards, and the remaining backend modules
  (`lots`/`bids`/`logistics`/`payments`/`rewards`/`complaints`/`notifications`)
  do not exist yet.

---

## Phase 4 — Collector Mobile Role: COMPLETE, VERIFIED

**Goal:** add the Collector role to the same Flutter codebase and continue
the real e-waste lifecycle from `WAITING_FOR_COLLECTION` — pending-queue
discovery → confirm handover — using the existing Phase 2 state machine
and geo-verification exactly as-is, with strict role isolation.

### Inspection finding that shaped this phase

The Phase 2 handover endpoint (`POST /ewaste/submissions/{id}/handover`)
was already fully built and tested — full geo-verification, state machine,
idempotency, audit logging. But there was no way for a collector to
*discover* a `submission_id` to hand over: `GET /ewaste/submissions` is
Home-User-own-only, and `GET /ewaste/submissions/{id}` requires either
home-user ownership or admin. This was a genuine, disclosed gap, not an
assumption — confirmed by reading the actual router code before writing
anything.

### One backend extension, disclosed (not silent)

Added `GET /api/v1/ewaste/submissions/pending` (`COLLECTOR`-only) to the
*existing* `ewaste` module — no new module, no new collection. The ward
is derived server-side from the collector's own profile (never a
client-supplied parameter), mirroring the same ownership pattern already
used by `handover`'s `COLLECTOR_OUTSIDE_ASSIGNED_AREA` check — a
collector cannot browse another ward's queue by passing a different id.
One additive compound index, `e_waste_submissions.(ward_id, status)`
(`backend/app/db/mongo.py`) — no existing index touched, no document
shape changed. The handover endpoint itself was **not modified at all**;
Phase 4 only adds a way to find work for it.

### What was built

**Backend** (`backend/app/modules/ewaste/`, `db/repositories/submissions_repo.py`,
`db/mongo.py`): `list_pending_by_ward` repo function, `list_pending_for_collector`
service function, the new router endpoint (registered before
`/submissions/{submission_id}` deliberately, so the static path wins the
route match).

**Mobile** (`mobile/lib/`):
- `features/collector/` — `CollectorProfile` model, `CollectorRepository`
  (wraps the existing `GET /collectors/me`).
- `features/ewaste/` — extended `EwasteRepository` with
  `listPendingForCollector` and `handover`; new `HandoverResult` model
  mirroring the backend's `HandoverResponse` exactly (never a
  client-fabricated verification outcome).
- `screens/collector/` — `CollectorHomeScreen` (dashboard, no route to
  any Home User screen), `CollectorPendingQueueScreen`,
  `CollectorHandoverScreen` (photo + live GPS capture, reusing the same
  `LocationService`/`PhotoPickerService`/idempotency-key-per-attempt
  pattern as the Home User submission screen; displays the real returned
  `verification_result`/`status`, never assumes success).
- `features/auth/auth_repository.dart` — widened the accepted-role set
  from `{HOME_USER}` to `{HOME_USER, COLLECTOR}`; any other role
  (`GOVERNMENT_ADMIN`, `RECYCLER`, `RRR_CENTER`) is still refused
  client-side, same as before.
- `screens/auth_gate.dart` — the one place that now branches on
  `session.role` to select `CollectorHomeScreen` vs `HomeScreen`, per the
  architecture's "two entirely separate navigation graphs, selected once
  at login from the verified role" requirement. No existing Home User
  screen was renamed, moved, or altered.

No collector self-registration path exists anywhere — `POST
/api/v1/admin/collectors` (admin-only, unchanged since Phase 2) remains
the only account-creation path, on both backend and client.

### Tests — actually executed, this session

Backend `pytest`: **88/88 passed** (83 existing + 5 new: collector sees
own-ward pending submissions; empty queue when none; collector does
**not** see another ward's queue — verified with a second collector in a
second ward; non-collector role → 403; an already-`COLLECTED` submission
is excluded from the queue). Full existing suite re-run unchanged
alongside — zero regressions.

`flutter analyze`: **No issues found.**

`flutter test`: **80/80 passed** (59 existing + 21 new/updated, including
4 for the login-portal-selector fix described below):
`CollectorProfile` model round-trip incl. null optional fields (2),
`CollectorRepository.getProfile` incl. error propagation (2),
`HandoverResult` model for VERIFIED/FLAGGED/null-distance shapes (3),
`EwasteRepository.listPendingForCollector` incl. error propagation (2),
`EwasteRepository.handover` incl. exact request-body/header construction,
idempotency-key reuse across a retry, and error propagation (3), and an
`AuthGate` widget test proving the actual role-branch: a `COLLECTOR`
session renders `CollectorHomeScreen` and never `HomeScreen` (and vice
versa for `HOME_USER`) (3). Two pre-existing tests were corrected in
place rather than left wrong: one `AuthRepository` and one
`AuthController` test had used `role: 'COLLECTOR'` as their example of a
*rejected* role (accurate for Phase 3, stale after this phase) — fixed to
assert collector login now succeeds, with a `RECYCLER` role substituted
as the still-rejected example.

### Live verification — real backend, real isolated DB, no reset

Restarted the backend against the **same** `kabadiwala_connect_2_0`
database used since Phase 3 — confirmed the existing demo ward
(`SIH-DEMO-01`) and the one real submission from the Phase 3 live manual
test survived untouched. Created exactly one demo collector through the
real API (`POST /admin/collectors`, using the existing seeded admin):
**`employee_id: "SIH-DEMO-COL-01"`, `ward_id: "SIH-DEMO-01"`**.

To exercise the full write path without consuming the one submission
left for manual UI testing, registered a second, clearly-labeled demo
home user (`sih-demo-home-02`) and its own submission purely through the
real registration/submission APIs, then drove a real handover through it
via curl: pending queue correctly showed 2 items → handover call
returned `{"status": "COLLECTED", "verification_result": "VERIFIED",
"distance_m": 7.76...}` (genuinely computed, not asserted) → pending
queue correctly dropped back to 1 → the home user's own `GET
/submissions` correctly reflected the new `COLLECTED` status. This proves
the full `WAITING_FOR_COLLECTION → COLLECTED` continuation end-to-end
through the real API surface the Flutter app calls.

**Role isolation verified live, both directions:** a collector token
gets `403 FORBIDDEN_ROLE` on `GET /home-users/me` and `POST
/ewaste/submissions`; a home-user token gets `403 FORBIDDEN_ROLE` on
`GET /ewaste/submissions/pending` and `GET /collectors/me`.

Relaunched the Flutter web app (`flutter run -d chrome --web-port=8765
--dart-define=API_BASE_URL=http://localhost:8000`) against this backend —
clean startup, no runtime errors, serving `200`. The original real
submission from the Phase 3 manual test was left sitting in
`WAITING_FOR_COLLECTION` in the demo ward specifically so a manual
click-through of the Collector UI had a real item to act on.

### Manual UI click-through, by the user — including a negative-path proof

The user then manually drove the actual Collector UI end-to-end in
Chrome (login as `SIH-DEMO-COL-01` → Pending Collections → tap the real
item → Confirm Handover) and confirmed it works.

**One UI-level bug was found and fixed first:** the shared login screen
statically read "Home User Login" even when logging in as a Collector.
Fixed with a purely cosmetic portal selector (`SegmentedButton` — "Home
User" / "Collector") in `login_screen.dart` that only changes displayed
strings (heading, username-field label "Username"↔"Employee ID", and
hides the Home-User-only "Register" link in Collector mode). It does
**not** gate or influence the actual login call — proven by a dedicated
test that selects the Collector portal, logs in with `HOME_USER`
credentials, and asserts login still succeeds correctly on the backend's
actual returned role. 4 new widget tests added
(`test/screens/login_screen_test.dart`); `AuthController`, `AuthGate`,
and the real login/RBAC path were not touched.

**Then a real negative-path handover, live, through the actual UI —
proving the geo-verification is genuine and not bypassed by the
client:** using the Collector UI's own captured browser GPS (not a
fixture, not a stub), the handover attempt was **995.9 m** from the
submission's recorded location. The 150 m server-side limit
(`Settings.max_handover_distance_meters`, unchanged — see the diff
confirmation below) correctly rejected it: the backend returned
`status: "FLAGGED_FOR_REVIEW"`, `verification_result: "FLAGGED"`,
`reasons: ["DISTANCE_EXCEEDED"]`, and the Collector UI displayed exactly
that real, server-computed result — not a fabricated success. This is
the negative-path counterpart to Phase 2's original distance-check test
and Phase 3's own live CORS/ward findings: the demo now has a
**verified-live positive path** (Phase 4's earlier curl-driven
`VERIFIED`/`COLLECTED` run) **and a verified-live negative path**
(`FLAGGED`/`FLAGGED_FOR_REVIEW`), both through the real backend, neither
mocked.

**Explicitly confirmed not weakened:** `git diff` on
`backend/app/modules/ewaste/service.py` for this whole phase shows only
the new, additive `list_pending_for_collector` function — the `handover`
function and every line of its geo-verification logic (GPS validity,
timestamp sanity, haversine distance, the 150 m comparison itself) are
byte-for-byte unchanged from Phase 2. `grep` confirms
`max_handover_distance_meters: float = 150.0` in `config.py` is still
the only definition of that limit, referenced from exactly the same one
call site.

### Known limitations / honestly unverified

- Same Android caveat as Phase 3 carries forward unchanged — only Chrome
  web has been live-verified; the emulator package-manager issue from
  Phase 3 was not revisited this session.
- No widget tests for `CollectorHomeScreen`, `CollectorPendingQueueScreen`,
  or `CollectorHandoverScreen` themselves — only `AuthGate`'s routing
  decision and the login portal selector got widget-level coverage this
  phase; the manual click-through covered the rest, but there's no
  automated regression guard for those three screens' own widget trees.
- The optional extension considered in the pre-implementation plan
  (widening `GET /ewaste/submissions/{id}` to collectors for a separate
  detail view) was **not** built — the pending-queue list's full raw
  documents were sufficient for the handover confirm screen, so it wasn't
  needed.
- Collector account creation still has no forced password-change-on-first-login
  flow (same deferral noted in Phase 2/3).
- A collector who gets a `FLAGGED_FOR_REVIEW` result today has no
  in-app way to see it move to admin review/retry — that's the
  `FLAGGED_FOR_REVIEW → HANDOVER_PENDING`/`→ REJECTED` admin-recovery
  path from the state machine, which has no admin UI yet (no Admin
  website exists until a later phase).

---

## Phase 5 — RRR Centre Website: COMPLETE, VERIFIED

**Goal:** the real continuation of the e-waste lifecycle past collection —
RRR registration → government approval → receive → manual classification
→ lot creation → publish for bidding — in a new, physically separate
web app, per the architecture's frontend-isolation decision. Recycler
bidding itself stays out of scope (Phase 6); this phase gets a lot to
`LISTED_FOR_BIDDING` and stops there.

### Inspection findings that shaped this phase

- The item-level state machine (`ewaste_states.py`, written in Phase 2)
  already had every transition this phase needed
  (`COLLECTED→AT_RRR→CLASSIFIED→LOT_CREATED→LISTED_FOR_BIDDING`), fully
  defined and completely unused until now — zero changes needed to it.
- The architecture defines a **separate** lot-level state machine
  (`DRAFT→LISTED_FOR_BIDDING→...`, Section 6.3) that didn't exist yet —
  `state_machines/lot_states.py` was a planned-but-missing file. Built it
  now, matching the same pure/dependency-free pattern as
  `ewaste_states.py`; only `DRAFT→LISTED_FOR_BIDDING` is actually
  reachable this phase, the rest of the table is defined for later
  phases to extend.
- `wards` had no `rrr_centre_id` field yet — deliberately deferred in
  Phase 2 and documented at the time as "Phase 5's problem."

### Deliberate scoping decisions (flagged, not silent)

1. **Classification is manual-only.** Every classification this phase
   writes `source: "MANUAL"`, `confidence: null`,
   `model_version: "unavailable"` — this is the architecture's own
   documented AI-fallback path, not a shortcut. The real classifier is
   Phase 8's job, in order.
2. **RRR self-registers, unlike collectors.** The permission matrix's
   "Approve RRR / recycler registration" (admin action) implies something
   is submitted to approve — so `rrr_centres` follows the `home_users`
   self-registration pattern (public endpoint) rather than the
   admin-only-creation pattern used for `collectors`. A PENDING account
   can log in (it's ACTIVE at the `users` level) but every privileged
   action is gated by a separate `require_approved_rrr()` service-layer
   check — role alone is never sufficient, same principle as every other
   ownership check in this codebase.
3. **Ward↔RRR linking happens at approval, not registration.** An RRR
   claims a ward when it registers; `wards.rrr_centre_id` is only written
   when an admin approves — enforced by a **partial** unique index
   (`{rrr_centre_id: {$exists: true}}`), not a plain one, specifically to
   avoid the exact "many docs missing a field collide as duplicate nulls"
   failure already hit for real with unrelated legacy data in Phase 3.
4. **No licence-document upload.** `licence_doc_ref` is an opaque,
   optional string — same "no real file storage exists yet" honesty
   already established for e-waste/handover photos in Phase 3/4.
5. **No admin website UI for RRR approval** (`GET/POST
   /api/v1/admin/rrr-centres/...`) — used via curl for this phase's live
   verification, same precedent as Phase 2's collector creation before
   an Admin website existed.

### What was built

**Backend — three new modules, same router→service→repository layering
as every existing module:**
- `rrr_centres`: self-register, `GET /me`, admin list/approve/reject.
- Extends the existing `ewaste` module (not a new one):
  `GET .../awaiting-receipt`, `POST .../{id}/receive`,
  `GET .../awaiting-classification`, `POST .../{id}/classify`,
  `GET .../classified` — all `RRR_CENTER`-only, all ward-scoped from the
  caller's own profile (never a client-supplied ward filter), all
  `Idempotency-Key`-gated and audit-logged, same pattern as Collector's
  handover in Phase 4.
- `lots`: create (validates every item is the caller's own, `CLASSIFIED`,
  same category), publish (`DRAFT→LISTED_FOR_BIDDING`, sets
  `bid_deadline` from the new `Settings.lot_bid_window_days`), list, and
  owner-scoped detail (RRR-own or `GOVERNMENT_ADMIN`).
- `state_machines/lot_states.py` (new) drives the lot's own status in
  parallel with each contained item's status via the unchanged
  `ewaste_states.py` — two state machines advanced together per write,
  matching the architecture's explicit separation of lot vs. item
  lifecycles.
- Additive-only DB changes: `rrr_centres`, `ai_classifications`, `lots`
  collections; `e_waste_submissions.category` field;
  `wards.rrr_centre_id` field with its partial unique index. No existing
  collection, index, or document shape touched.

**Frontend — new `rrr-centre-web`** (Vite + React + TypeScript, at the
repo root per the architecture's folder structure — a genuinely separate
SPA, not a route inside the Flutter app or any existing frontend):
`api/apiClient.ts` mirrors the Flutter app's `ApiClient` design exactly
(Bearer tokens, the `{success:false,error_code,message}` contract,
distinct handling for FastAPI's 422 shape vs. network/timeout failures);
`features/{auth,wards,rrrCentre,ewaste,lots}/` repositories; pages for
Login (RRR-only, same client-side wrong-role refusal pattern as the
Flutter app), Register, Dashboard (shows approval status; action links
only render once `APPROVED`), Receive Items, Classify Items, Build a Lot
(groups classified items by category, multi-select), My Lots, and Lot
Detail (Publish button). No component library, no state-management
package beyond React Context — matches "avoid unnecessary packages."
Session storage: browser `localStorage` (see limitations below — this is
a disclosed simplification relative to the architecture's stated
web-frontend preference, not a silent deviation).

### Tests — actually executed, this session

Backend `pytest`: **122/122 passed** (88 existing + 34 new: 7 lot-state
transition tests, 10 `rrr_centres` tests incl. the one-RRR-per-ward
conflict and the pending/approved/rejected gate, 8 receive/classify
tests incl. cross-ward rejection, 9 `lots` tests incl. category-mismatch
rejection and owner-scoped list/detail isolation). Full existing suite
re-run alongside, unchanged — zero regressions.

`rrr-centre-web`: `npm run build` (TypeScript project build +
production bundle) — clean. `npm run lint` (oxlint) — zero errors, 8
non-blocking `react-hooks/exhaustive-deps` warnings for the intentional
"load once on mount" pattern (equivalent to the Flutter app's
`initState`-driven loads), left as-is. `npm test` (Vitest): **35/35
passed** — `ApiClient` error handling (9, mirroring the Flutter
`ApiClient` test depth: structured errors, FastAPI 422 shape, non-JSON
500, network failure, timeout with an injectable duration),
`AuthRepository` (8: login incl. persistence and wrong-role rejection,
restore incl. the refresh-token fallback path, logout), `WardsRepository`/
`RrrCentreRepository`/`EwasteRepository`/`LotsRepository` (15: request
shape/headers/body construction, error propagation), and one
`LoginPage` component test (3: error banner rendering, wrong-role
message, registration link) using Testing Library + user-event.

### Live verification — real backend, same isolated DB, no reset

Restarted the backend against the same `kabadiwala_connect_2_0` database
used since Phase 3 — confirmed the demo ward (`SIH-DEMO-01`) and both
submissions left from Phase 4 (one `FLAGGED_FOR_REVIEW`, one real
`COLLECTED` item) survived untouched.

Drove the **complete** workflow through the real API, reusing that
existing `COLLECTED` item rather than fabricating new data:
1. Registered `SIH-DEMO-RRR-01` for ward `SIH-DEMO-01` through the real
   `POST /rrr-centres/register` → `PENDING`.
2. Approved it via the existing seeded admin through the real
   `POST /admin/rrr-centres/{id}/approve` → confirmed live that
   `GET /wards` now shows `"rrr_centre_id": "SIH-DEMO-RRR-01"` on that
   ward.
3. `GET .../awaiting-receipt` correctly showed the real `COLLECTED`
   item → `POST .../receive` → `AT_RRR`.
4. `POST .../classify` with category `e-waste-small-appliances` →
   `CLASSIFIED`; confirmed the item now appears in
   `GET .../classified`.
5. `POST /lots` with that one item → `DRAFT`; confirmed the item
   immediately dropped out of the classified queue.
6. `POST /lots/{id}/publish` → `LISTED_FOR_BIDDING`, with a genuinely
   computed `bid_deadline` (`created_at + 7 days`, from
   `Settings.lot_bid_window_days`) — not a fixed/stubbed value.
7. Confirmed via admin `GET /ewaste/submissions/{id}` that the
   underlying item's own status also reads `LISTED_FOR_BIDDING`, and via
   `GET /lots` that the lot appears in the RRR's own list.

**RBAC verified live:** unauthenticated `GET /admin/rrr-centres` →
`401 INVALID_TOKEN`; the existing Phase 4 demo collector's token on
`GET /lots` → `403 FORBIDDEN_ROLE`.

**CORS verified live for the new frontend with zero backend change:**
preflight from `Origin: http://localhost:5173` (the `rrr-centre-web` dev
server) → `200` with a correct `access-control-allow-origin` header —
the Phase 3 loopback-regex CORS policy covered this new frontend/port
automatically, exactly as it was designed to.

Backend (`:8000`) and `rrr-centre-web` (`:5173`) are both left running.

### Manual browser verification — two real bugs found and fixed

The curl-driven live verification above proved the backend end-to-end,
but the first actual browser click-through (login as
`sih-demo-rrr-01` / `demoRrrPass1`) failed with "Could not reach the
server" — a genuinely new finding curl could never have caught, since
curl doesn't enforce anything browser-specific. Both root causes were
confirmed by reproduction before any fix was applied, not guessed:

1. **IPv4/IPv6 loopback mismatch** (partial fix, real but not the full
   story): the Vite dev server bound to the IPv6 loopback (`[::1]`),
   while the backend (`--host 0.0.0.0`) is IPv4-only — `curl -6
   http://localhost:8000/...` reproduced the exact same connection
   failure. Fixed by changing `apiClient.ts`'s `DEFAULT_BASE_URL` from
   `http://localhost:8000` to the literal `http://127.0.0.1:8000`
   (never subject to DNS/hosts resolution ambiguity). This alone did
   **not** fix the browser — proving it wasn't the real (or at least not
   the only) cause.
2. **The actual root cause: `TypeError: Illegal invocation`.** Chrome
   DevTools showed *zero* network requests were ever generated on
   submit and no uncaught console error — meaning an exception was
   thrown before `fetch()` was ever dispatched, and silently caught.
   `apiClient.ts` stored native `fetch` as a bare instance property
   (`this.fetchImpl = fetch`) and later invoked it as
   `this.fetchImpl(...)` — method-call syntax that sets fetch's internal
   receiver to the `ApiClient` instance instead of `window`. Real
   browser engines enforce a strict WebIDL receiver brand-check on
   `Window.prototype.fetch` and throw synchronously for this, before any
   HTTP activity starts; our own `try/catch` silently converted that
   `TypeError` into a generic `NETWORK_ERROR`. This is why every
   networking/CORS hypothesis was correctly ruled out by the user's own
   DevTools evidence (backend independently reachable from the same
   Chrome instance) and why no test caught it: every Vitest test injects
   a mock `fetchImpl`, which has no receiver brand-check, so the failure
   mode is specific to real browser `fetch` and unreachable from
   jsdom/Node. Fixed with one line: `fetch.bind(globalThis)`.

**Confirmed fixed by the user's own manual click-through** (not
self-reported): login authenticates the real `APPROVED` demo RRR;
dashboard shows the correct RRR/tender/ward/status; Receive and Classify
queues correctly render empty (the one demo item was already carried
through to `LISTED_FOR_BIDDING` by the earlier curl verification); My
Lots shows the real demo lot (`e-waste-small-appliances`, 1 item,
`LISTED_FOR_BIDDING`); navigation between pages works. This is now
genuinely demo-verified, not just test-verified.

Re-ran after each fix: `npm test` 35/35, `npm run build` clean, backend
`pytest` 122/122 (untouched both times — neither bug nor either fix
touched the backend).

### Known limitations / honestly unverified

- **Session storage uses `localStorage`, not httpOnly cookies.** The
  architecture's Section 5 states web frontends should prefer
  server-managed/httpOnly-cookie refresh-token storage. The backend's
  actual `/auth/login` contract returns tokens as a JSON body (matching
  what the Flutter app already consumes) — it has no cookie-issuing path,
  and adding one now would be a cross-cutting backend auth change
  affecting every client, well beyond this phase's scope. `localStorage`
  is the closest web-native equivalent to what the backend already
  provides, consistent with the actual (not aspirational) contract — but
  it is a real, disclosed gap versus the architecture's stated
  preference, not a silent one.
- No widget/component tests for `RegisterPage`, `DashboardPage`,
  `ReceiveItemsPage`, `ClassifyItemsPage`, `BuildLotPage`, `LotsPage`, or
  `LotDetailPage` — only `LoginPage` got component-level coverage this
  phase (matching the same scope decision made for the Flutter app's
  screens in Phase 3/4); the repositories and API client those pages
  call are thoroughly tested.
- No RRR-facing detail endpoint extension for a single submission
  (`GET /ewaste/submissions/{id}` still excludes `RRR_CENTER` from its
  allow-list, unchanged from Phase 2) — considered in the pre-approval
  plan, not built, because the queue endpoints already return full raw
  documents, making a separate detail fetch unnecessary for this phase's
  screens.
- Lot creation's per-item validation loop raises on the *first* invalid
  item rather than collecting and reporting all failures at once — fine
  for this phase's single-category-at-a-time UI flow (which only offers
  already-filtered, same-category items to select from), but would need
  richer batch-error reporting if a future UI ever let users mix
  mismatched selections more freely.
- 8 non-blocking oxlint warnings (`react-hooks/exhaustive-deps` ×7 for
  the intentional mount-only load pattern, ×1 `react-refresh/
  only-export-components` in `AuthContext.tsx`) — left as-is, none
  represent a functional bug.

---

## Phase 6 — Recycler Website + Bidding: COMPLETE, VERIFIED

**Goal:** the real continuation of the marketplace from `LISTED_FOR_BIDDING`
— recycler registration → government approval → browse/bid → RRR accepts
→ sibling bids rejected → lot/item sync to `BID_SELECTED` — in a new,
physically separate web app. Logistics/payments themselves stay out of
scope (later phases); this phase gets a bid to `ACCEPTED` and a lot to
`BID_SELECTED` and stops there, exactly as planned.

### Inspection findings that shaped this phase

- `lot_states.py` (Phase 5) already had `LISTED_FOR_BIDDING→BID_SELECTED`
  and the reopen transition `BID_SELECTED→LISTED_FOR_BIDDING` fully
  defined, unused until now — zero changes needed.
- `ewaste_states.py` (item state machine, unchanged since Phase 2) had the
  forward transition but was **missing** the reverse
  `BID_SELECTED→LISTED_FOR_BIDDING` needed for cancel-acceptance to
  reopen an item — one small, disclosed, additive line added to an
  already-shipped file (does not change any existing transition).
- `state_machines/bid_states.py` was a planned-but-missing file (same
  situation `lot_states.py` was in before Phase 5) — built now.

### Deliberate scoping decisions (flagged, not silent)

1. **Bid acceptance is `RRR_CENTER`'s job, not Government Admin's** — per
   the architecture's own permission matrix ("Accept bid / cancel
   acceptance — RRR_CENTER, own lots only"). This meant the full
   accept/cancel-acceptance workflow was testable and live-verifiable
   *this* phase through the real API, with no need to wait for or fake
   an Admin website.
2. **The "and before payment" half of the 24h cancel-acceptance guard is
   a no-op today** — no `payments` module exists until Phase 9. The
   time-based half (24h) is fully enforced now; the payment half will
   start actually gating once real payment records exist.
3. **Recyclers are not ward-scoped**, unlike RRR/Collector — confirmed
   from the architecture's own schema (`recyclers` has no `ward_id`
   field). `GET /lots/listed` is genuinely marketplace-wide.
4. **`bids.recycler_id` and `lots.rrr_id` both store the actor's business
   id** (`license_id`/`rrr_id`), not the raw `user_id` — matching the
   precedent already shipped in Phase 5's `lots.rrr_id`, for consistency.
5. **No standalone bid-detail-by-id endpoint** — "My Bids" and "bids on
   my lot" list views already return full bid documents; a separate
   fetch-by-id wasn't needed for any planned screen.

### What was built

**Backend — two new modules, same router→service→repository layering as
every existing module:**
- `recyclers`: self-register, `GET /me`, admin list/approve/reject —
  mirrors `rrr_centres` almost exactly (same architecture permission-
  matrix line covers both), minus ward linkage.
- `bids`: `POST /bids` (place), `POST /bids/{id}/cancel`,
  `GET /bids/mine`, `POST /bids/{id}/accept` (RRR, own lot),
  `POST /bids/{id}/cancel-acceptance` (RRR, own lot, 24h window) — every
  state-changing endpoint `Idempotency-Key`-gated and audit-logged
  (`BID_PLACED`, `BID_CANCELLED`, `BID_ACCEPTED`, `BID_SIBLING_REJECTED`,
  `BID_ACCEPTANCE_CANCELLED`), same pattern as every prior phase.
- Extends the existing `lots` module (not a new one): `GET /lots/listed`
  (new, marketplace-wide), `GET /lots/{id}` widened to also allow
  `RECYCLER` as a read-only viewer (additive; RRR/admin behavior
  unchanged), `GET /lots/{id}/bids` (RRR, own lot — needed to actually
  choose which bid to accept).
- `state_machines/bid_states.py` (new): `PLACED→CANCELLED`,
  `PLACED→ACCEPTED`, `PLACED→REJECTED` (sibling), `ACCEPTED→CANCELLED`.
  `accept_bid()` in `bids/service.py` drives **three** state machines in
  parallel per call — the bid's own, the lot's (Phase 5), and every
  contained item's (Phase 2) — matching the architecture's explicit
  separation of all three lifecycles.
- **Money:** every bid `amount` is a decimal string over the wire
  (`"1250.50"`), parsed server-side to `Decimal`, validated (positive,
  finite, ≤2 decimal places), stored as `bson.Decimal128` — never a
  Python float or a JSON number, anywhere in `bids/service.py`.
- **The actual race guarantee:** a partial unique index on
  `bids.lot_id` where `status: "ACCEPTED"` — keyed on `lot_id` **alone**,
  never `(lot_id, recycler_id)`, exactly the architecture's corrected
  design (Section 3) — makes two accepted bids on one lot structurally
  impossible at the database level, not just in application logic.
- Additive-only DB changes: `recyclers`, `bids` collections; the one new
  index above plus three supporting indexes on `bids`. No existing
  collection, index, or document shape touched.

**Frontend — new `recycler-web`** (Vite + React + TypeScript, same
architecture as `rrr-centre-web`, built with both Phase 5 fixes already
in place from the first commit rather than rediscovered): `api/
apiClient.ts` (127.0.0.1 default + `fetch.bind(globalThis)`, both
documented inline with *why*, not just *what*); `features/{auth,
recycler,lots,bids}/` repositories; pages for Login (Recycler-only, same
client-side wrong-role refusal pattern), Register, Dashboard (approval
status gates action links), Browse Available Lots (marketplace-wide, no
ward filter), Lot Detail with an embedded Place Bid form (decimal-string
amount input, never a JS number), My Bids (with Cancel for still-`PLACED`
bids). No component library, no state-management package beyond React
Context.

### Tests — actually executed, this session

Backend `pytest`: **169/169 passed** (132 existing + 37 new: 9
`bid_states` unit tests + 1 new `ewaste_states` transition test, 8
`recyclers` integration tests, 3 new recycler-facing `lots` tests
(marketplace visibility, approval gate, widened detail access), 26
`bids` integration tests covering placement (valid/invalid amount in 5
parametrized shapes, past-deadline, wrong lot status, idempotency
replay), cancellation (owner-only, wrong-status), acceptance
(owner-only, sibling-rejection, lot/item sync), cancel-acceptance
(within window, expired window via a backdated timestamp — not a real
sleep), role isolation, and the architecture's own named concurrency
test. Full existing suite re-run alongside, unchanged — zero
regressions.

**The concurrency test — an honest finding, not a hidden one.**
`test_two_different_recyclers_cannot_both_be_accepted_for_same_lot`
fires two `accept` requests via `asyncio.gather`. On the first run, the
two requests did not genuinely interleave inside `mongomock-motor` +
`httpx.ASGITransport` — the second request's own `PLACED`-status
pre-check caught the conflict (`400 BID_NOT_ACCEPTABLE`, because
sibling-rejection from the first request had already run) rather than
the database index racing (`409 LOT_ALREADY_ACCEPTED`). Both are
legitimate rejections of the loser; the test was rewritten to assert the
actual safety property — **exactly one bid for the lot ever ends up
`ACCEPTED`, verified by querying both recyclers' final bid state**,
rather than assuming a specific HTTP status for the loser. This is the
same category of honest limitation already documented since Phase 2:
mongomock's index/concurrency behavior is not a perfect stand-in for
real MongoDB under real concurrent load; the partial unique index itself
is real, additive defense-in-depth regardless of which path a given test
run exercises.

`recycler-web`: `npm run build` — clean. `npm run lint` (oxlint) — 0
errors, 6 non-blocking warnings (same intentional mount-only-load
pattern as `rrr-centre-web`). `npm test` (Vitest): **31/31 passed** —
`ApiClient` (10, including one explicit regression check that
constructing a client doesn't throw, guarding the Illegal-invocation
fix), `AuthRepository` (6), `RecyclerRepository`/`LotsRepository`/
`BidsRepository` (11, including the decimal-string-not-a-number
assertion on bid amounts and idempotency-key reuse on retry), and one
`LoginPage` component test (3).

### Live verification — real backend, same isolated DB, no reset

Restarted the backend against the same `kabadiwala_connect_2_0`
database used since Phase 3 — confirmed the demo ward, the Phase 5 demo
RRR (still `APPROVED`), and critically **the real Phase 5 lot was still
`LISTED_FOR_BIDDING`** (its 7-day bid deadline hadn't elapsed), so this
phase's verification reused it rather than fabricating new demo data,
per instructions.

Drove the **complete** workflow through the real API:
1. Registered `sih-demo-recycler-01` → `PENDING` → approved via the
   existing seeded admin → `APPROVED`.
2. `GET /lots/listed` correctly showed the real Phase 5 lot.
3. `GET /lots/{id}` (as the recycler) returned its detail.
4. `POST /bids` placed a real bid — `₹1850.75`, preserved exactly as a
   string round-trip (proving `Decimal128` storage/retrieval introduces
   no float drift) → `GET /bids/mine` confirmed it.
5. As `sih-demo-rrr-01` (the real Phase 5 demo RRR): `GET /lots/{id}/bids`
   showed the real bid → `POST /bids/{id}/accept` → bid `ACCEPTED`, lot
   → `BID_SELECTED`, and (confirmed via admin) the underlying item's own
   status also flipped to `BID_SELECTED` — all three state machines
   observed moving together, live, not just in a test.
6. `POST /bids/{id}/cancel-acceptance` (within the 24h window) → bid
   `CANCELLED`, lot reopened to `LISTED_FOR_BIDDING` — confirmed live,
   leaving the real lot open again for a further manual click-through.

**RBAC verified live, both directions:** the recycler's own token on
`POST /bids/{id}/accept` → `403 FORBIDDEN_ROLE`; the existing Phase 4
demo collector's token on `POST /bids` → `403 FORBIDDEN_ROLE`.

**CORS verified live for the new frontend with zero backend change:**
preflight from `Origin: http://localhost:5174` (the `recycler-web` dev
server, a port never explicitly configured for CORS) → `200` with a
correct `access-control-allow-origin` header — the Phase 3 loopback-regex
policy covered it automatically, same as it did for `rrr-centre-web` in
Phase 5.

Backend (`:8000`), `rrr-centre-web` (`:5173`), and `recycler-web`
(`:5174`) are all left running.

### Known limitations / honestly unverified

- **The recycler-web UI itself was not manually clicked through by a
  human this session** — every backend endpoint it calls was verified
  live via curl (above), and the TypeScript code driving them is
  unit/component-tested, but no one has visually confirmed the actual
  pages render and behave correctly in a browser. The real Phase 5 lot
  is deliberately left `LISTED_FOR_BIDDING` again (acceptance was
  cancelled as part of verification) specifically so a manual
  click-through — login as `sih-demo-recycler-01` /
  `demoRecyclerPass1` → Browse Lots → Lot Detail → Place Bid → My Bids —
  has a real item to act on next.
- The concurrency test's actual code path (DB index race vs. service-
  layer pre-check) is scheduler-dependent under mongomock-motor +
  ASGITransport, as documented above — the safety invariant is proven,
  not which specific defense caught a given run.
- No component tests beyond `LoginPage` for the other 4 recycler-web
  pages (repositories/API client they call are fully tested).
- Lot creation/bid validation still reports only the first failure in a
  batch, not a full list — unchanged carry-over note from Phase 5.
- The payment half of the 24h-cancel-acceptance guard has no effect yet
  (disclosed above) — will start gating once Phase 9 adds real payments.
- Same Android/browser-only-verified caveats from Phase 3–5 carry
  forward unchanged.

---

## Phase 7 — Government Admin Website: COMPLETE, VERIFIED

**Goal:** a Government Admin web app that is genuinely authoritative for
administrative actions — RRR/recycler approval (already built in Phase
5/6, reused as-is), plus collector account management, ward oversight,
e-waste/operations oversight, lots/bids oversight, and a new complaints
workflow — with backend RBAC as the real boundary and every
state-changing action audited, exactly matching the pattern every prior
phase established.

### Inspection findings that shaped this phase

- RRR/recycler admin list/approve/reject (`/api/v1/admin/rrr-centres/...`,
  `/api/v1/admin/recyclers/...`) were already fully built in Phase 5/6 —
  zero backend changes needed; only a frontend page each.
- **No admin list endpoint existed at all** for collectors, lots, bids,
  or submissions — only owner-scoped or `/me` views existed anywhere in
  the codebase (confirmed by reading every router, not assumed).
- **No collector update path existed** — `PROJECT_STATUS.md`'s own Phase
  2 entry had flagged this ("Needed before Phase 5+ if a collector's
  ward assignment ever needs correcting") and it was still true.
- **No `complaints` collection or module existed anywhere** — the
  architecture (Section 13) fully specifies its lifecycle, but nothing
  had built it before this phase.
- Geo-verification detail (`distance_m`, `verification_result`) lives
  only in `collection_handovers`, never copied onto the submission
  document — no admin read path reached it before this phase.

### Deliberate scoping decisions (flagged, not silent)

1. **Admin sub-routes stay colocated in their owning domain module**
   (`GET /api/v1/admin/collectors` lives in `collectors/router.py`,
   `GET /api/v1/admin/lots` in `lots/router.py`, etc.) — matching the
   real precedent Phase 5/6 already established
   (`/admin/rrr-centres`, `/admin/recyclers`), not the Phase-0 doc's
   original single-`admin`-module sketch. The one genuinely
   cross-cutting exception is the new dashboard summary
   (`GET /api/v1/admin/dashboard/summary`), which has no single owning
   domain and lives in a new, thin `app/modules/admin/`.
2. **`ewaste`/`lots`/`bids` routers already carry a hardcoded URL
   prefix** (`/api/v1/ewaste`, `/api/v1/lots`, `/api/v1/bids`), so their
   new `/api/v1/admin/...` routes are registered on a second, unprefixed
   `admin_router` defined in the same file and included separately in
   `main.py` — a small mechanical consequence of FastAPI's per-router
   prefix, not a new architectural pattern.
3. **No ward reassignment endpoint was built.** The ward↔RRR link stays
   intentionally one-time-at-approval, protected by the existing partial
   unique index — inventing a reassignment path now would be new
   relationship logic never reviewed. Ward Management is a **read-only**
   relationship view (wards + admin RRR list + admin collector list
   composed client-side) plus the pre-existing create-ward action.
   Collector ward *re*assignment (a distinct, already-anticipated gap)
   is handled by the new collector `PATCH` instead.
4. **No idempotency key on any new admin endpoint** — checked first:
   none of the existing admin state-changing endpoints (ward create,
   collector create, RRR/recycler approve/reject) require one either;
   only the financial/marketplace endpoints (submissions, handovers,
   lots, bids) do. Phase 7 follows that same real precedent rather than
   inventing a new one.
5. **`government_actions` (the architecture's separate collection) is
   still deferred to Phase 9** — its real payload (reward eligibility
   invalidations) doesn't exist until then. The "Government Actions"
   admin-web view instead filters the existing append-only
   `audit_logs` collection to `actor_role=GOVERNMENT_ADMIN`, via two new
   optional query filters (`actor_role`, `entity_type`) added additively
   to the existing `GET /api/v1/audit-logs` endpoint.
6. **Collector "active/inactive" reuses the existing `users.status`
   field**, not a new field on the `collectors` document — this is real
   enforcement, not cosmetic: `get_current_user()` (unchanged since
   Phase 1) already rejects any non-`ACTIVE` account with
   `ACCOUNT_DISABLED` on every request, so disabling a collector locks
   them out immediately. Verified live (see below).
7. **Complaints: a minimal but complete module**, not a stub. Any
   authenticated role may file one (`POST /api/v1/complaints`,
   `reporter_id`/`reporter_role` always from the token, never the
   body); admin reviews through the exact lifecycle the architecture
   specifies (`OPEN→IN_PROGRESS→RESOLVED/REJECTED/ESCALATED`), enforced
   by a new, independent `state_machines/complaint_states.py` (same
   pure allow-list pattern as `bid_states.py`/`lot_states.py`).

### What was built

**Backend:**
- New `complaints` module (repo/service/router) + `complaint_states.py`
  + `complaints` collection (indexes: unique `complaint_id`,
  `(reporter_id, status)`, `status`).
- New thin `admin` module: `GET /api/v1/admin/dashboard/summary` —
  counts by role/status across users, wards, RRR centres, recyclers,
  submissions, lots, bids, complaints, via Mongo `$group` aggregation.
- `collectors` module +: `GET /api/v1/admin/collectors` (list, no
  password/hash ever included), `PATCH /api/v1/admin/collectors/{id}`
  (partial ward/rrr/area reassignment, validates the new ward exists),
  `POST /api/v1/admin/collectors/{id}/status` (ACTIVE/DISABLED).
- `ewaste` module +: `GET /api/v1/admin/submissions` (optional `status`
  filter), `GET /api/v1/admin/handovers` (optional
  `verification_result` filter) — both read-only, system-wide, not
  ward-scoped.
- `lots` module +: `GET /api/v1/admin/lots` (optional `status` filter).
- `bids` module +: `GET /api/v1/admin/bids` (optional `status` filter).
- `audit_logs` +: optional `actor_role`/`entity_type` filters, additive
  to the existing `skip`/`limit` pagination.
- **Every new state-changing action is audited**, per the explicit
  requirement this phase: `COLLECTOR_ASSIGNMENT_UPDATED`,
  `COLLECTOR_STATUS_CHANGED`, `COMPLAINT_FILED`, `COMPLAINT_REVIEWED` —
  each verified in a dedicated test that reads the actual
  `audit_logs` document back (`actor_role`, `entity_type`, `entity_id`,
  `action`, `details`), not just the HTTP response shape.
- Additive-only DB changes: one new collection (`complaints`) and its
  three indexes. No existing collection, index, or document shape
  touched; `ewaste_states.py`/`lot_states.py`/`bid_states.py` all
  byte-for-byte unchanged this phase.

**Frontend — new `admin-web`** (Vite + React + TypeScript, same
architecture as `rrr-centre-web`/`recycler-web`, both Phase 5/6 fixes —
`127.0.0.1` default and `fetch.bind(globalThis)` — present from the
first commit): one consolidated `AdminRepository` (deliberately not
split per-domain like the other two apps' repositories — these are all
thin, mostly-read calls behind one `GOVERNMENT_ADMIN` gate, so one class
covers RRR/recycler approval, collector management, wards, submissions/
handovers, lots/bids, complaints, and audit logs without per-domain
ceremony); one shared `<Table>` component reused by every list page
instead of bespoke markup each time; pages: Login, Dashboard (summary
tiles + status breakdowns), RRR Centres, Recycler Management, Collector
Management (create + list + inline ward-reassign + enable/disable),
Ward Management (create + read-only RRR/collector relationship view),
E-waste/Operations (submissions + handovers, filterable by status),
Lots & Bids, Complaints (file-state-aware review actions), Audit Logs
(with a "Government Actions" checkbox filter), Logout.

### Tests — actually executed, this session

Backend `pytest`: **208/208 passed** (169 existing + 39 new: 10
`complaint_states` unit tests, 13 `complaints` integration tests
(file/list/review, invalid-transition rejection, non-admin rejection,
**and the audit-event-content assertions** for both filing and review),
16 `admin` integration tests (dashboard summary counts, collector list/
patch/status incl. **audit-event-content assertions** and the live
`ACCOUNT_DISABLED` login-lock proof, submissions/handovers oversight
with status filters, lots/bids oversight with status filters, audit-log
actor_role/entity_type filters, and non-admin `403 FORBIDDEN_ROLE`
rejection on every single new admin route). Full existing suite
re-run alongside, unchanged — zero regressions.

`admin-web`: `npm run build` — clean. `npm run lint` (oxlint) — 0
errors, 11 non-blocking warnings (9× the same intentional
mount-only-load `react-hooks/exhaustive-deps` pattern already accepted
in `rrr-centre-web`/`recycler-web`, one per page; 1×
`react/only-export-components` and 1× `react/set-state-in-effect` in
`AuthContext.tsx` — confirmed by directly re-running `recycler-web`'s
own lint that both of those exact warnings already exist there too,
from the byte-identical `AuthContext.tsx` pattern; not new to this
phase). `npm test` (Vitest): **34/34 passed** — `ApiClient` (11,
including the pre-existing 10-test suite plus one new PATCH-method
test, since `admin-web` is the first of the three frontends to need
PATCH), `AuthRepository` (7), `AdminRepository` (13, covering the
dashboard summary, RRR/recycler approval, collector create/patch/
status, wards, submissions/lots/bids filtering, complaint review body
shape, and audit-log query-filter construction), one `LoginPage`
component test (3).

### Live verification — real backend, same isolated DB, no reset

Restarted the backend against the same `kabadiwala_connect_2_0`
database used since Phase 3 (the process running before this session's
context limit was stale Phase-6 code — confirmed via a `404` on the new
dashboard route before restart, `401` after) — confirmed the demo ward,
both demo RRR/recycler accounts, the one `FLAGGED_FOR_REVIEW`
submission, and the one `LISTED_FOR_BIDDING` lot from Phase 5/6 all
survived untouched.

Drove the actual required flow through the real API:
1. **Admin login → dashboard**: `GET /api/v1/admin/dashboard/summary`
   returned real, correct counts (`HOME_USER: 2, COLLECTOR: 1,
   RRR_CENTER: 1, RECYCLER: 1, GOVERNMENT_ADMIN: 1`, 1 ward, 1 flagged
   submission, 1 listed lot) — matching exactly what Phase 5/6 left
   behind.
2. **Inspect pending records**: both existing demo RRR/recycler were
   already `APPROVED` (no `PENDING` records remained from prior
   phases), so — per instructions, reusing first and creating only the
   minimal necessary new record through the real API, never a direct
   DB write — registered one new demo recycler
   (`sih-demo-recycler-02`) and **performed the one safe
   approval action**: `POST /admin/recyclers/{id}/approve` → `APPROVED`,
   then confirmed the resulting `RECYCLER_APPROVED` audit entry via
   `GET /audit-logs?actor_role=GOVERNMENT_ADMIN&entity_type=recycler`.
3. **Collector management, fully exercised without touching the
   existing real demo collector**: created a new ward (`SIH-DEMO-02`),
   created a new demo collector (`SIH-DEMO-COL-02`) via the admin-only
   path, reassigned it to the new ward via `PATCH`, disabled it via
   `POST .../status` and **confirmed its login was immediately rejected
   with `403 ACCOUNT_DISABLED`** (real enforcement, not cosmetic), then
   re-enabled it, leaving the demo in a clean, usable state.
4. **Complaints, full lifecycle**: filed a real complaint as the
   existing `sih-demo-recycler-01` → `OPEN`, reviewed it as admin →
   `IN_PROGRESS` → `RESOLVED` with resolution notes — the complete
   architecture-specified state machine driven live, not just in tests.
5. **Oversight reads, all against real data**: `GET
   /admin/submissions?status=FLAGGED_FOR_REVIEW` (1), `GET
   /admin/handovers?verification_result=FLAGGED` (1), `GET /admin/lots`
   (1), `GET /admin/bids` (1), `GET /admin/complaints` (1) — every
   count matched what the dashboard summary and prior phases' live
   verifications had already established.
6. **RBAC verified live**: the recycler's own token on `GET
   /admin/collectors` → `403 FORBIDDEN_ROLE`.
7. **CORS verified live for the new frontend with zero backend
   change**: preflight from `Origin: http://localhost:5175`
   (`admin-web`'s dev-server port, auto-selected since `:5173`/`:5174`
   were already in use by the other two apps) → `200` with a correct
   `access-control-allow-origin` header — the Phase 3 loopback-regex
   policy covered it automatically, same as every prior new frontend.
8. Confirmed via `curl` that the served dev bundle's `apiClient.ts`
   genuinely contains both baked-in fixes:
   `DEFAULT_BASE_URL = "http://127.0.0.1:8000"` and
   `fetch.bind(globalThis)`.

Backend (`:8000`), `rrr-centre-web` (`:5173`), `recycler-web`
(`:5174`), and `admin-web` (`:5175`) are all left running.

### Known limitations / honestly unverified

- **The admin-web UI itself was not manually clicked through by a human
  this session** — same disclosed gap as `recycler-web` in Phase 6.
  Every backend endpoint it calls was verified live via curl (above),
  and the TypeScript repository code driving them is unit-tested, but
  no one has visually confirmed the actual pages render and behave
  correctly in a browser. The demo data is left in a clean, fully
  populated state (a pending-free but data-rich dashboard, a resolved
  complaint, a reassigned-then-restored collector) specifically so a
  manual click-through has real content on every page next.
- No component tests beyond `LoginPage` for the other 9 admin-web pages
  (the `AdminRepository`/`ApiClient` they call are thoroughly tested).
- Ward Management has no reassignment action by design (see scoping
  decision 3) — this is a deliberate, disclosed gap, not an oversight.
- The dashboard summary issues one Mongo aggregation query per
  collection sequentially (8 small `$group` calls) rather than a single
  combined pipeline — simple and correct for this data volume; would be
  worth consolidating if the collections ever grow large enough for the
  per-call round-trip cost to matter.
- Same Android/browser-only-verified caveats from Phase 3–6 carry
  forward unchanged.

---

## Phase 8 — AI Classification: COMPLETE, VERIFIED

**Goal:** a real, integrated AI-classification layer for e-waste items,
built behind a genuinely swappable `ClassifierService` interface, wired
into the existing `AT_RRR → CLASSIFIED` lifecycle without inventing a
new one — high confidence reaches `CLASSIFIED` directly; low confidence
or a classifier failure never gets silently accepted, routing instead
to a new `NEEDS_REVIEW` state that only the existing Phase 5 manual
classification path can resolve.

### Inspection findings that shaped this phase

- `classifications_repo.py`'s own docstring already forward-referenced
  a not-yet-built `app/modules/classification/service.py` — the same
  "planned but missing" pattern as `bid_states.py`/`lot_states.py`
  before their phases.
- `config.py` already had `classification_confidence_threshold: float =
  0.6` and `ai_model_version = "ewaste-classifier-v1"` pre-declared and
  unused since Phase 5 — reused verbatim, not reinvented.
- **The decisive finding:** confirmed from Phase 3's own disclosed
  limitation that `photo_file_id` has never been a real uploaded file —
  it is an opaque, caller-supplied string, and no backend code path can
  fetch real image bytes for any submission. A real vision-AI provider
  would have nothing genuine to send. This directly justifies (per your
  own instruction) shipping **exactly one** classifier implementation —
  deterministic and offline — rather than a "real provider" class that
  could never actually be exercised.
- `ewaste_states.py`'s `ALL_STATES`/`ALLOWED_TRANSITIONS` had no
  `NEEDS_REVIEW` state at all — architecture Section 9 names this exact
  state; it simply hadn't been built yet.

### Architectural decisions (flagged, not silent)

1. **No second "real provider" classifier class was built.** The swap
   point is `get_classifier()` in `app/modules/classification/
   classifier.py` — a future real-provider integration adds one new
   `ClassifierService` subclass and one branch there; nothing else in
   the codebase changes. Building an unreachable HTTP-provider class
   now (with no real image bytes to ever send it) would be exactly the
   half-finished-implementation pattern this project avoids.
2. **`DeterministicMockClassifier`** derives `(category, confidence)`
   from a SHA-256 hash of `photo_file_id` — pure, offline, no network
   call, fully reproducible. **This validates integration behavior
   only — it proves nothing about real-world classification accuracy**,
   stated explicitly in the module docstring, every test file, and
   here.
3. **`ai_provider_api_key: str | None = None`** was added to `Settings`
   purely to make "the app must work without AI credentials" a real,
   testable, structural fact rather than an assertion: no code path
   reads it in Phase 8, so classification behaves identically whether
   it's set or not — proven by a dedicated test, including that the
   value (when set) never appears in any response or database record.
4. **`NEEDS_REVIEW` is the one minimum additional state**, per your
   explicit instruction — not a parallel review workflow, not a new
   collection. Its only two transitions: `AT_RRR → NEEDS_REVIEW` (low
   confidence or classifier failure) and `NEEDS_REVIEW → CLASSIFIED`
   (via the **same, unmodified-in-spirit** manual `classify()` function
   Phase 5 already shipped — its eligibility check simply widened from
   "status must be `AT_RRR`" to "status must be `AT_RRR` or
   `NEEDS_REVIEW`", and its `transition()` call now passes the actual
   current status instead of a hardcoded `"AT_RRR"`).
5. **`ai_classifications.classification_id`** was added additively (a
   genuine schema change, disclosed) for uniform auditability across
   both AI and manual attempts — protected by a **partial** unique
   index (`{classification_id: {$exists: true}}`), not a plain one,
   because real historical documents from Phase 5/6 live verification
   predate this field entirely; a plain unique index would have
   collided on startup against the real database exactly like
   `wards.rrr_centre_id` did in Phase 5. Caught and fixed before it
   could break anything, not discovered by accident.
6. **No idempotency key was added anywhere it wasn't already required**
   — `POST /api/v1/ai/classify/{id}` requires one (matching every other
   state-changing submission/handover/lot/bid endpoint), consistent
   with the existing pattern, not a new one.
7. **`GOVERNMENT_ADMIN` oversight reuses the existing Phase 7 `GET
   /api/v1/admin/submissions`** (already surfaces every status
   including `NEEDS_REVIEW`) — no new admin endpoint needed.

### What was built

**Backend — new `classification` module** (`classifier.py`,
`service.py`, `schemas.py`, `router.py`): `ClassificationResult`
dataclass (`success`, `predicted_category`, `confidence`,
`model_version`, `failure_reason`, `metadata` — deliberately no
chain-of-thought/free-text-reasoning field, structurally guaranteed by
a test that enumerates the dataclass's own fields), `ClassifierService`
ABC, `DeterministicMockClassifier`, `get_classifier()` factory.
`classify_with_ai()` validates the classifier's response defensively
(malformed confidence/category is treated as a failure, never trusted
blindly — the classifier is a swappable, potentially-untrusted-input
boundary), catches both the classifier's own `ClassifierError` and any
unexpected exception (never lets a classifier bug crash the RRR
workflow), and routes to `CLASSIFIED` or `NEEDS_REVIEW` accordingly.
`POST /api/v1/ai/classify/{submission_id}` (`RRR_CENTER`, own ward
only, `Idempotency-Key` required).

**Extended, not replaced:** `ewaste_states.py` (+`NEEDS_REVIEW` state,
+2 transitions, everything else byte-for-byte unchanged); `ewaste/
service.py`'s manual `classify()` (widened eligibility check only) and
`list_awaiting_classification_for_rrr()` (now also surfaces
`NEEDS_REVIEW` items, so RRR staff can find them to resolve manually —
two existing queries merged, no new repo function); `mongo.py` (+1
partial unique index, disclosed above).

**Frontend — extended the existing `ClassifyItemsPage`**, no new app:
an "AI Classify" button per queued item, showing the predicted category,
confidence percentage, source/model, and — critically — a clear,
honest "manual review required" message (with the classifier's
`failure_reason` when it failed) rather than ever pretending AI
succeeded. The manual category form stays available on every item
regardless of AI outcome. No credential ever reaches the frontend — the
endpoint's response contains only the classification result.

### Tests — actually executed, this session

Backend `pytest`: **235/235 passed** (208 existing + 27 new: 5
`test_classifier.py` unit tests — determinism, well-formedness, no
chain-of-thought field structurally verified, distinct inputs produce
distinct outputs; 4 new `test_ewaste_states.py` transition tests; 18
`test_classification_api.py` integration tests covering high-confidence
success, low-confidence → `NEEDS_REVIEW`, a simulated `ClassifierError`
and a simulated *unexpected* exception both routing to `NEEDS_REVIEW`
without crashing, a malformed classifier response (out-of-range
confidence) being rejected rather than trusted, classification working
identically with `ai_provider_api_key` unset vs. set (and the key never
leaking into any response or the `ai_classifications` document), RBAC
rejection for `HOME_USER`/`COLLECTOR`, wrong-ward RRR rejection,
`AT_RRR`-only eligibility, idempotency replay (no duplicate DB write)
and a missing-header rejection, a documented concurrency test, the
`AI_CLASSIFICATION_ATTEMPTED` audit entry, the untouched manual
`AT_RRR → CLASSIFIED` path, manual resolution of a `NEEDS_REVIEW` item
with the append-only history proving both the AI attempt and the manual
resolution are kept, and the widened awaiting-classification queue).
Full existing suite re-run alongside, unchanged — zero regressions.

**The concurrency test — same honest category of limitation as Phase
6.** `test_concurrent_ai_classify_attempts_do_not_corrupt_state` fires
two AI-classify requests for the same submission via `asyncio.gather`
with different idempotency keys. As documented since Phase 6,
mongomock-motor + `httpx.ASGITransport` don't reliably interleave two
"concurrent" coroutines the way two real MongoDB connections would, so
this doesn't prove a database-level race is closed — the `AT_RRR`-only
status pre-check is the actual defense here. What it does prove: no
unhandled exception, the item always ends in a valid terminal status,
and — because the mock classifier is a pure function of
`photo_file_id` — even if both requests genuinely raced, their computed
results would be byte-identical, never contradictory.

`rrr-centre-web`: `npm run build` — clean. `npm run lint` (oxlint) — 0
errors, 8 non-blocking warnings (same intentional mount-only-load
`react-hooks/exhaustive-deps` pattern as every prior phase, one per
page including the untouched-logic `ClassifyItemsPage` effect; plus 2
on `AuthContext.tsx`, which this phase did not touch at all — a newer
oxlint rule (`set-state-in-effect`) than Phase 5 shipped with, same
tooling-version observation already made for `admin-web` in Phase 7).
`npm test` (Vitest): **41/41 passed** (35 existing + 6 new: 3
`EwasteRepository.classifyWithAi` tests — request shape, a
`needs_review` result surfacing without throwing, no credential field
ever present on the response — and 3 `ClassifyItemsPage` component
tests covering the high-confidence success display, the low-confidence
"manual review required" display with the manual form still present,
and the failure-fallback display with the classifier's failure reason
shown honestly).

**One real frontend testing bug found and fixed, not routed around.**
The first version of the `ClassifyItemsPage` component tests hung on a
permanent loading spinner. Root cause, confirmed by reproduction: this
page (like every other protected page in all three of this project's
web apps) imports the module-level `ewasteRepository` singleton
directly — unlike `AuthRepository`, which `AuthProvider` explicitly
supports injecting, `EwasteRepository` has no such override point. In
the jsdom test environment, Node's real global `fetch` is available, so
the test was silently making REAL network calls to the real backend
running on `127.0.0.1:8000` for this session's own live verification —
and got back a genuine `401 INVALID_TOKEN` for the fake bearer token,
which the page correctly rendered as an error. Fixed with `vi.mock()`
on the `ewasteRepository` module (the standard, non-invasive Vitest
technique for a singleton import) — no production code was changed to
work around this; the page's actual architecture is unchanged.

### Live verification — real backend, same isolated DB, no reset

Restarted the backend against the same `kabadiwala_connect_2_0`
database used since Phase 3 (confirmed clean startup — the new partial
`classification_id` index built successfully against real historical
`ai_classifications` documents that predate the field, proving the
partial-filter design was correct, not just theoretically justified).
Confirmed the existing `LISTED_FOR_BIDDING` lot and `FLAGGED_FOR_REVIEW`
submission from Phase 5–7 survived untouched. No `AT_RRR` item existed
to reuse, so — per instructions — created the minimum new demo flow
through legitimate APIs only (one new collector, one new home user, two
new submissions driven through real submit → handover → receive calls
to reach `AT_RRR`), never a direct DB write.

1. **High-confidence path:** `POST /ai/classify/{id}` on a submission
   whose `photo_file_id` was chosen (via the same pure hash function,
   verified once during development) to land above the 0.6 threshold →
   returned `confidence: 0.7074`, `status: "CLASSIFIED"` — exactly
   matching the value independently derived for the test suite,
   proving genuine determinism, not a coincidence.
2. **Low-confidence path:** the same call on a `photo_file_id` chosen
   to land below threshold → `confidence: 0.239`, `status:
   "NEEDS_REVIEW"`, `category: null` — never silently accepted.
3. **Persistence confirmed independently** via `GET
   /admin/submissions`: both real statuses correct in the database, not
   just in the HTTP response.
4. **Manual resolution of the AI-flagged item:** `POST .../classify`
   with `{"category": "plastics"}` on the `NEEDS_REVIEW` item →
   `CLASSIFIED` — the exact Phase 5 endpoint, now also accepting this
   new starting status. Confirmed the item dropped out of the
   awaiting-classification queue afterward.
5. **Append-only history confirmed directly against the real
   collection:** the low-confidence item's `ai_classifications` history
   shows exactly two records — the original `AI`/`LOW_CONFIDENCE`
   attempt and the later `MANUAL`/`ACCEPTED` resolution — neither
   overwritten.
6. **Audit trail confirmed:** both `AI_CLASSIFICATION_ATTEMPTED` entries
   present with correct `accepted`/`new_status`/`predicted_category`/
   `confidence` details.
7. **RBAC verified live:** the demo home user's token on `POST
   /ai/classify/{id}` → `403 FORBIDDEN_ROLE`.
8. **Idempotency replay verified live:** the same `Idempotency-Key`
   replayed against the already-`CLASSIFIED` high-confidence item
   returned the byte-identical cached response.
9. **The untouched Phase 5 path, verified live on a third, freshly
   created item that never touched AI at all:** submit → handover →
   receive → `POST .../classify` with a manual category → `CLASSIFIED`,
   proving the original manual-only workflow is completely unaffected.
10. Confirmed via `curl` that the running `rrr-centre-web` dev server
    (`:5173`) is serving the updated `ClassifyItemsPage` bundle
    containing the new AI Classify button and `classifyWithAi` call.

Backend (`:8000`), `rrr-centre-web` (`:5173`), `recycler-web` (`:5174`),
and `admin-web` (`:5175`) are all left running.

### Known limitations / honestly unverified

- **`DeterministicMockClassifier` proves integration behavior, not
  model accuracy — stated explicitly and repeatedly** (module
  docstring, every test file's own docstring, this section). It is a
  SHA-256-hash-based rule, not a trained model, and makes no claim
  about how well it would categorize a real photograph — because it
  never sees one.
- **No real AI provider is wired up, on purpose**, for the reason
  disclosed above (no real image storage exists to send anywhere). The
  swap point (`get_classifier()`) is real and unit-tested for its
  current (mock-only) behavior, but a future real-provider class itself
  does not exist yet.
- **The AI-classify UI itself was not manually clicked through by a
  human this session** — same disclosed gap as `recycler-web` (Phase 6)
  and `admin-web` (Phase 7). Every backend call it makes was verified
  live via curl, and the component behavior is tested against a mocked
  repository. The real demo `AT_RRR`/`NEEDS_REVIEW` items created this
  session were all resolved during live verification (none left
  pending) — a future manual click-through would need to run the AI
  Classify button against a fresh item to see live results, exactly as
  this session's curl-driven verification did.
- The concurrency test's actual code path (true DB-level race vs. the
  service-layer `AT_RRR`-only pre-check) is scheduler-dependent under
  mongomock-motor + ASGITransport, as documented above — same category
  of limitation disclosed for the Phase 6 bid-acceptance concurrency
  test.
- `confirmed_by`/`confirmed_category` stay `None` on an AI-accepted
  (not manually reviewed) classification record, by design — no human
  confirmed it. This preserves the architecture's documented distinction
  between `predicted_category` (AI) and `confirmed_category` (human)
  precisely, rather than blurring it by auto-filling a "confirmer" that
  doesn't exist.

---

## Phase 9 — Payments & Rewards: COMPLETE, VERIFIED

**Goal:** complete the LOT → BID → LOGISTICS → PAYMENT → SOLD/COMPLETED
flow with a mock payment gateway, and the reward eligibility/computation
/mock-UPI-redemption flow — both built on the existing, mostly
pre-declared architecture rather than a new one.

### Inspection findings that shaped this phase

- Both `lot_states.py` and `ewaste_states.py` already had the **entire**
  `LOGISTICS_BOOKED → READY_FOR_COLLECTION → PAYMENT_PENDING →
  SOLD/PAID → COMPLETED` chain pre-declared since Phase 2/5, completely
  unused until now — zero new states needed, only one disclosed reverse
  edge (below).
- `config.py` already had `payment_mode = "MOCK_PAYMENT_GATEWAY"`
  pre-declared since **Phase 1**, unused until now.
- `home_users.upi_id` (optional) already existed since Phase 3 —
  reused directly for mock redemption; never a new field.
- **No `logistics` module/endpoint existed anywhere** — nothing drove
  `BID_SELECTED → LOGISTICS_BOOKED`. This was a genuine, undisclosed gap
  in the existing code, not something Phase 6 deferred on purpose.

### Architectural decisions (flagged, not silent)

1. **One disclosed additive state-machine edge**: `PAYMENT_PENDING →
   READY_FOR_COLLECTION` on both `lot_states.py` and `ewaste_states.py`
   — architecture Section 11's own wording ("on FAILED: lot remains
   READY_FOR_COLLECTION, recycler may retry") required a reverse
   transition that didn't exist. Approved explicitly before
   implementation.
2. **A real, previously-latent bug found and fixed**: `bids/service.py`'s
   `cancel_acceptance()` hardcoded the lot's "from" state as
   `BID_SELECTED` regardless of the lot's actual current status —
   harmless in Phase 6 (nothing could move a lot past `BID_SELECTED`
   while its bid stayed `ACCEPTED`), but would have silently reverted an
   already-`LOGISTICS_BOOKED`/`SOLD` lot back to `LISTED_FOR_BIDDING`
   once Phase 9 added further lot progression. Fixed to check
   `lot["status"]` for real; a bid can now only be un-accepted while its
   lot is still exactly `BID_SELECTED` — which also structurally
   satisfies "before payment," since payment can only happen after
   logistics. Covered by a dedicated regression test.
3. **Payment concurrency uses a stronger guard than the bid-acceptance
   precedent**: `lots_repo.transition_status_if_current()` — a single
   conditional write (`READY_FOR_COLLECTION → PAYMENT_PENDING`) that
   only one of two racing requests can ever have matched — rejects the
   loser immediately, before it ever calls the mock gateway or touches
   any item. The partial unique index on `payments.lot_id`
   (status=SUCCEEDED only) remains a second, independent layer.
4. **`reward_eligible_at` lives on `e_waste_submissions`, not a new
   `e_waste_items` collection** — approved deviation from Phase 2's
   literal note. A second collection would need to be kept in sync with
   `e_waste_submissions` forever after — exactly the dual-source-of-truth
   bug class this project exists to avoid.
5. **Reward formula is points-per-item, not points-per-kg** — no item
   weight is ever recorded anywhere in this system. Configurable via
   `reward_points_per_item` (default **10**) and
   `reward_value_per_point_inr` (default **0.50**) — 1 collected item =
   10 points = ₹5.00, exact default documented here per the checkpoint
   requirement.
6. **No clawback code path exists anywhere** — not a single function in
   `rewards/service.py` debits, invalidates, or reverses a reward. The
   "never claw back" guarantee holds structurally; a dedicated test
   enumerates every public function in the module and asserts none of
   their names even suggest one.
7. **Government-Admin reward computation is an explicit, idempotent,
   admin-triggered batch** (`POST /api/v1/admin/rewards/compute`), not a
   scheduler — no cron/job infrastructure exists in this project. Safe
   to re-run: an already-credited home user for a given period is
   skipped, never re-created, enforced structurally by the
   `unique(home_user_id, period)` index.
8. **A genuine, pre-existing (not newly introduced) idempotency+datetime
   characteristic was found, not fixed**: the shared `idempotency.py`
   cache round-trips a raw Python `datetime` through MongoDB's BSON
   datetime type, which has millisecond precision and no tzinfo — a
   cached replay's `created_at` can differ in exact string form from the
   original response. `test_bids_api.py`'s own idempotency-replay test
   already worked around this by comparing specific fields, not full-JSON
   equality; Phase 9's new tests follow the same established precedent
   rather than modifying Phase 1's shared idempotency helper under a
   "no unnecessary changes to previous phases" mandate. Disclosed here,
   not silently routed around.

### What was built

**Backend — two new modules plus one new payments module, all following
the same router→service→repository layering as every existing module:**
- `logistics`: `POST /api/v1/logistics/{lot_id}/book`
  (`BID_SELECTED → LOGISTICS_BOOKED`), `POST /api/v1/logistics/
  {booking_id}/confirm-collection` (`LOGISTICS_BOOKED →
  READY_FOR_COLLECTION`), `GET /api/v1/logistics/lot/{lot_id}`
  (recycler-own booking lookup, needed so the UI can find an
  already-booked lot's `booking_id` across page loads). All
  Recycler-only, own accepted bid only, `Idempotency-Key`-gated,
  audit-logged.
- `payments`: `POST /api/v1/payments/{lot_id}/initiate`
  (`READY_FOR_COLLECTION → PAYMENT_PENDING`, mock gateway call,
  `→ SOLD`/`PAID` on success or `→ READY_FOR_COLLECTION` on failure —
  all synchronous within one request, matching Phase 8's "no unreachable
  async machinery for a mock" precedent), `GET /api/v1/payments/lot/
  {lot_id}` (recycler-own or admin), `GET /api/v1/admin/payments`
  (admin oversight). Amount is read from the accepted bid's own
  `Decimal128` field and never re-parsed from client input at payment
  time — removes an entire bug class by construction.
- `app/modules/payments/gateway.py`: `MOCK_PAYMENT_GATEWAY`, a pure
  SHA-256-hash-based function of the payment amount — deterministic,
  offline, no real network call, no provider credential of any kind.
  **Proves integration correctness, never a real gateway's approval
  rate** — stated in the module docstring, every test file, and here.
- `rewards`: `POST /api/v1/admin/rewards/compute` (admin, idempotent
  per-period batch), `GET /api/v1/admin/rewards`, `GET
  /api/v1/rewards/mine`, `GET /api/v1/rewards/transactions/mine`,
  `POST /api/v1/rewards/{reward_id}/redeem` (home-user-own, mock UPI
  payout via `app/modules/rewards/payout.py` — same deterministic,
  offline, no-credential design as the payment gateway). New
  `reward_eligible_at` set-once write added to `ewaste/service.py`'s
  existing `handover()`, at the exact `COLLECTED` line — one additive
  line, the manual/verification path otherwise byte-for-byte unchanged.
- Additive-only DB changes: `logistics_bookings`, `payments`, `rewards`,
  `reward_transactions` collections and their indexes (including the
  partial unique `payments.lot_id` SUCCEEDED-only index — the actual
  duplicate-payment guarantee); `e_waste_submissions.reward_eligible_at`
  field. No existing collection, index, or document shape touched.

**Frontend:**
- `recycler-web`: `LotDetailPage` extended with a state-conditional
  "next steps" panel (Book Logistics → Confirm Collection → Pay Now),
  visible only when the viewing recycler owns the lot's accepted bid
  (checked via the backend's own `403`, never assumed client-side). New
  `logisticsRepository.ts`/`paymentsRepository.ts`. No credential ever
  reaches the frontend — the payment endpoint's response contains only
  the result.
- `rrr-centre-web`: no new UI — only a one-line `StatusBadge`
  color-mapping addition for the new lot statuses (RRR already sees
  these read-only via existing pages).
- `admin-web`: new "Rewards" page (compute-by-period form + rewards
  table + payments oversight table), reusing the existing `<Table>`
  component and repository pattern.
- **Home User rewards go into the existing Flutter mobile app** (the
  architecture's own, and only, Home User UI surface — not a new web
  app): new `RewardsRepository`, `Reward`/`RewardTransaction` models,
  and a `RewardsScreen` reachable from the dashboard's "My Rewards"
  button, with a per-reward "Redeem to UPI (mock)" action that never
  collects a PIN or password.

### Tests — actually executed, this session

Backend `pytest`: **289/289 passed** (235 existing + 54 new: 2 new
`test_lot_states.py` + 2 new `test_ewaste_states.py` transition tests,
5 `test_payment_gateway.py`, 3 `test_reward_payout.py`, 5
`test_reward_period_bounds.py` unit tests; 10 `test_logistics_api.py`,
12 `test_payments_api.py` — including the concurrency test and the
regression test for the cancel-acceptance bug fix — and 15
`test_rewards_api.py` integration tests covering immutable
`reward_eligible_at`, month-boundary exclusion, one-reward-per-period,
the structural no-clawback proof, and mock redemption
success/failure/no-UPI-on-file/ownership). Full existing suite re-run
alongside, unchanged — zero regressions.

**The payment concurrency test — genuinely stronger than the Phase 6/8
precedent, not just another honestly-limited one.**
`test_concurrent_payment_attempts_never_produce_two_succeeded_payments`
fires two payment-initiate requests for the same lot via
`asyncio.gather`. Unlike the bid-acceptance and AI-classification
concurrency tests (which rely solely on a DB-level unique index and are
honestly documented as not proving mongomock-motor genuinely
interleaves two coroutines), this endpoint has an *additional* guard —
`lots_repo.transition_status_if_current()` — a single conditional write
that structurally can only be matched by one of the two requests
regardless of scheduler interleaving, so this test verifies the real
invariant (exactly one `SUCCEEDED` payment) directly, not hopefully.

`recycler-web`: **42/42** passed (31 existing + 11 new: 3
`LogisticsRepository` + 4 `PaymentsRepository` + 4 more repository edge
cases). `rrr-centre-web`: **41/41** passed, unchanged (cosmetic-only
change). `admin-web`: **38/38** passed (34 existing + 4 new:
`listPayments`/`computeRewards`/`listRewards`/`INVALID_PERIOD`
propagation). All three: `npm run build` clean; `npm run lint` — 0
errors, same pre-existing warning categories as every prior phase (one
new `no-unused-vars` catch was found and fixed in `LotDetailPage.tsx`
during this session, not left in).

Flutter (`mobile`): `flutter analyze` — **No issues found.** `flutter
test` — **89/89 passed** (80 existing + 9 new: 2 `Reward` model tests,
2 `RewardTransaction` model tests, 5 `RewardsRepository` tests
including idempotency-key reuse on retry and a `FAILED` mock payout
surfacing without throwing).

### Live verification — real backend, same isolated DB, no reset

Restarted the backend against the same `kabadiwala_connect_2_0`
database used since Phase 3 — confirmed clean startup, including the
new partial unique `payments.lot_id` index and the new `rewards`/
`logistics_bookings`/`reward_transactions` indexes building successfully
against the real, pre-existing database with zero collisions. Confirmed
the real Phase 6 lot (`fbee937e-...`) had reverted to
`LISTED_FOR_BIDDING` (its earlier bid was cancelled during Phase 6's own
live verification) — reused it for the payment-success path rather than
creating new lot data.

1. **Payment success, full chain, on the real reused lot**: placed a
   real bid (`₹500.00` — independently confirmed via the pure mock
   gateway function to be a deterministic SUCCESS amount) → accepted →
   booked logistics → confirmed collection → initiated payment →
   `SUCCEEDED`, `gateway_reference: "MOCK-d523d89ad8bdc527"` — the exact
   same reference the unit test suite independently derived, proving
   genuine determinism. Confirmed via `GET /lots/{id}`: lot `SOLD`; via
   `GET /admin/submissions`: item `PAID`.
2. **Duplicate-payment prevention, live**: a second payment attempt on
   the now-`SOLD` lot → `409 LOT_ALREADY_PAID`.
3. **Payment failure + retry, on one new minimal demo flow** (created
   only because no second suitable lot existed — one new home user,
   submission driven through the real submit→handover→receive→classify→
   lot→publish chain, using the existing demo collector/RRR): bid placed
   at `₹100.00` (independently confirmed as a deterministic FAILURE
   amount) → accepted → logistics booked/confirmed → payment →
   `FAILED` → confirmed via `GET /lots/{id}` the lot was back at
   `READY_FOR_COLLECTION`, never stuck in `PAYMENT_PENDING` → retried
   with a fresh idempotency key → `FAILED` again (same deterministic
   amount), proving retry works without corrupting state. Left in this
   real, retryable state for a future manual click-through.
4. **`reward_eligible_at` confirmed immutable and status-independent,
   live**: the same new demo item's `reward_eligible_at` was stamped at
   `COLLECTED` and was still present, unchanged, after the item had
   advanced all the way to `READY_FOR_COLLECTION` — read directly from
   the real document, not inferred.
5. **Reward compute, live**: `POST /admin/rewards/compute` for the real
   current period → exactly one reward created (10 points, ₹5.00,
   matching the documented default formula exactly) → **re-running the
   same compute call returned `count: 0`** — proving one-reward-per-
   period holds against the real database, not just in a test.
6. **Mock UPI redemption, live**: the real home user redeemed the
   credited reward → `SUCCEEDED`, reward status → `REDEEMED`.
7. **RBAC verified live**: the recycler's own token on `POST
   /admin/rewards/compute` → `403 FORBIDDEN_ROLE`.
8. **Audit trail confirmed live** for every Phase 9 action:
   `LOGISTICS_BOOKED`, `LOGISTICS_COLLECTION_CONFIRMED`,
   `PAYMENT_ATTEMPTED` (both the real `FAILED` attempts), `REWARD_COMPUTED`,
   `REWARD_REDEMPTION_ATTEMPTED` — all present with correct details.
9. Confirmed via `curl` that the running `recycler-web` (`:5174`) and
   `admin-web` (`:5175`) dev servers are serving the updated bundles
   containing the new Book Logistics/Pay Now and Compute Monthly
   Rewards UI respectively.

Backend (`:8000`) and all three web frontends (`:5173`–`:5175`) are all
left running.

### Known limitations / honestly unverified

- **`MOCK_PAYMENT_GATEWAY` and the mock UPI payout are pure, offline,
  hash-based functions — they prove integration correctness (does the
  SUCCEEDED/FAILED wiring behave correctly?), never anything about a
  real payment provider's or UPI network's true behavior.** No real
  provider integration exists, deliberately — Phase 9's scope was
  explicitly mock-only.
- **The Book Logistics/Pay Now UI (`recycler-web`) and the Rewards page
  (`admin-web`) were not manually clicked through by a human this
  session** — same disclosed gap as every prior phase's new frontend
  surface. Every backend call each makes was verified live via curl,
  and the repository code driving them is unit-tested. The real
  failure-path lot (`b8ef4851-...`) is deliberately left in a
  `READY_FOR_COLLECTION`/previously-`FAILED` state specifically so a
  manual click-through has a real "Pay Now" action to exercise next.
- The idempotency+datetime characteristic disclosed in decision 8 above
  applies to every module in this codebase that caches a raw datetime
  field in an idempotent response, not just Phase 9's new endpoints —
  flagged here as a systemic, pre-existing observation, not a Phase 9
  regression.
- The payment concurrency test's stronger guarantee (point 3 above)
  does not retroactively strengthen the Phase 6 bid-acceptance or Phase
  8 AI-classification concurrency tests — those remain exactly as
  honestly limited as documented in their own phases.
- No admin UI action exists to reverse/invalidate a reward — by design,
  not an oversight (see decision 6).
- Same Android/browser-only-verified caveats from Phase 3–8 carry
  forward unchanged.

---

## Phase 10 — Integration: COMPLETE, VERIFIED

**Goal:** make the already-built Phase 1–9 modules behave as ONE
coherent system — find and fix real integration defects between them,
close the one genuine end-to-end gap (nothing ever drove
`SOLD/PAID → COMPLETED`), and prove the full chain holds together with
tests that exercise multiple modules at once, not just each module in
isolation.

### Integration audit findings (all genuinely inspected, not assumed)

1. **A live latent bug, not yet exploited**: `mobile/lib/core/config.dart`'s
   web/default target still used the literal `'localhost'` — the exact
   IPv4/IPv6 dual-stack loopback bug found and fixed in `rrr-centre-web`
   during Phase 5 had never been propagated to the Flutter web build,
   which has the identical exposure.
2. **A real broken navigation path**: `recycler-web`'s `MyBidsPage` had
   no link anywhere to `/lots/{lot_id}`, and an accepted bid's lot
   disappears from `BrowseLotsPage` (which only lists
   `LISTED_FOR_BIDDING`). Net effect: there was **no discoverable UI
   path** from "My Bids" to Book Logistics/Confirm Collection/Pay Now —
   only a typed URL could reach it.
3. **Stale status-color mapping**: `admin-web/src/components/
   StateViews.tsx`'s `statusTone()` had not been updated since Phase 7;
   every Phase 8/9 status silently rendered as generic `neutral`.
4. **Stale filter dropdown**: `admin-web/src/pages/OperationsPage.tsx`'s
   status filter list stopped at `BID_SELECTED`, making `NEEDS_REVIEW`
   through `COMPLETED` unreachable as a filter even though the backend
   already returns/accepts them.
5. **A confirmed, genuine backend gap**: grepped the entire backend —
   no code path anywhere ever drove `SOLD → COMPLETED` or
   `PAID → COMPLETED`, despite both transitions being pre-declared in
   their state machines since Phase 2/5. You approved adding the
   minimal, admin-controlled completion step (below) to close this.

Everything else audited — auth/RBAC propagation, CORS, idempotency
conventions, audit-action naming, money/Decimal128 handling across
every module — was found **consistent**. No other defects found.

### The `SOLD/PAID → COMPLETED` completion step

`POST /api/v1/admin/lots/{lot_id}/complete` (`GOVERNMENT_ADMIN` only —
no other role appears anywhere in the permission matrix for finalizing
a sale, and a recycler/RRR self-attesting their own sale complete would
be unchecked). Requires the lot to be exactly `SOLD`; a lot that's
already `COMPLETED` and is asked to complete again with a **new**
idempotency key gets `409 LOT_ALREADY_COMPLETED` (same
"prevent-backwards/duplicate-transition-with-a-clear-conflict" pattern
already established by payments' `LOT_ALREADY_PAID`) — a same-key
replay returns the original cached response, unchanged. Drives the
already-existing `SOLD → COMPLETED` / `PAID → COMPLETED` transitions
(no state-machine changes needed — both were pre-declared since
Phase 2/5) and is audit-logged as `LOT_COMPLETED`. **Phase 9's payment
semantics are completely untouched** — this only adds the one step
after a payment has already succeeded.

### What was built

**Backend**: `complete_lot()` in `lots/service.py` +
`POST /api/v1/admin/lots/{lot_id}/complete` in `lots/router.py`'s
existing `admin_router` (Phase 7's pattern) — no new module, this
belongs entirely to the lot lifecycle. New `sold_lot` conftest fixture
(extends the existing `ready_for_collection_lot` fixture chain with a
real, deterministic-success payment).

**Frontend fixes** (all disclosed defects, not new features):
- `recycler-web/MyBidsPage.tsx`: an `ACCEPTED` bid now shows a
  "View Lot — Book Logistics / Pay" link to `/lots/{lot_id}`.
- `admin-web/StateViews.tsx`: `statusTone()` extended to cover every
  status introduced by Phase 8/9.
- `admin-web/OperationsPage.tsx`: the status filter dropdown extended
  to include every reachable status through `COMPLETED`.
- `mobile/lib/core/config.dart`: web and desktop/iOS-simulator defaults
  changed from `localhost` to the literal `127.0.0.1`.

### Tests — actually executed, this session

Backend `pytest`: **311/311 passed** (289
existing + 22 new: 12 `test_lot_completion_api.py`
(success, audited, invalid-state, never-paid, not-found, 3×RBAC,
idempotency replay, repeated-completion conflict, structural
backwards-transition proof, missing-idempotency-key); 1
`test_end_to_end_flow.py` — one real chain through every module since
Phase 2 (register → submit → handover → **AI classify, both a genuine
high-confidence acceptance and a genuine low-confidence
`NEEDS_REVIEW` on a sibling item, manually resolved** → lot → publish →
bid → accept → logistics book/confirm → payment success → admin
complete → reward compute (proving eligibility is keyed on
`reward_eligible_at`, independent of the item's now-`COMPLETED`
status) → mock UPI redemption — asserting every state transition and
the full audit trail exists); 5 `test_cross_role_isolation.py` (two
home users, two wards' collectors, two RRRs, two recyclers, and a
sweep of every admin-only endpoint against every non-admin role, all
against the same live, shared data); 4
`test_combined_edge_cases.py` (a collector disabled mid-session is
rejected on their very next already-issued-token request; a reward
computed before a sale even starts is never touched when that same
sale's payment later genuinely fails; the exact same idempotency-key
string reused across two unrelated endpoint scopes doesn't
cross-contaminate; a complaint filed about a lot never alters the
lot's own state). Full existing suite re-run alongside, unchanged —
zero regressions.

`recycler-web`: **45/45** passed (42 existing + 3 new
`MyBidsPage.test.tsx` tests — the `ACCEPTED`-bid link, its absence for
`REJECTED`/`PLACED`). `admin-web`: **50/50** passed (38 existing + 12
new `StateViews.test.tsx` tone-mapping regression tests). Both:
`npm run build` clean; `npm run lint` — 0 errors, same pre-existing
warning categories as every prior phase, nothing new introduced.

Flutter (`mobile`): `flutter analyze` — **No issues found.** `flutter
test` — **90/90 passed** (89 existing + 1 new `config_test.dart`
regression guard asserting `apiBaseUrl` never defaults to the literal
`"localhost"`).

### Live verification — real backend, same isolated DB, no reset

Restarted the backend against the same `kabadiwala_connect_2_0`
database used since Phase 3. Found the real `SOLD` lot left over from
Phase 9's own live verification (`fbee937e-...`) — reused it directly,
no new demo data created.

1. **Completed the real lot**: `POST /admin/lots/{id}/complete` →
   `COMPLETED`; confirmed independently via `GET /lots/{id}` (lot) and
   `GET /admin/submissions` (item) — both `COMPLETED`.
2. **Repeated completion, live**: a second completion attempt with a
   fresh idempotency key → `409 LOT_ALREADY_COMPLETED`.
3. **RBAC, live**: the real demo recycler's token on the same endpoint
   → `403`.
4. **Audit trail confirmed live**: `LOT_COMPLETED`,
   `actor_role: GOVERNMENT_ADMIN`, correct `item_ids` in `details`.
5. **Served frontend bundles confirmed via curl** to contain each fix:
   `recycler-web`'s `MyBidsPage.tsx` bundle contains the new "View
   Lot — Book Logistics / Pay" link text; `admin-web`'s `StateViews.tsx`
   and `OperationsPage.tsx` bundles contain the new status strings.

**Honest disclosure, per your explicit instruction not to claim
unactually-performed verification**: no browser-automation tool (e.g.
Playwright) is available in this environment, and no human
click-through was requested or performed this session. The frontend
fixes above are verified at the level every prior phase has
consistently used — real backend API calls plus confirmation that the
running dev server is serving the exact fixed source — but **not** an
actual rendered-browser click-through. This is stated plainly, not
implied otherwise.

Backend (`:8000`) and all three web frontends (`:5173`–`:5175`) are
all left running.

### Known limitations / honestly unverified

- **No actual browser/UI click-through was performed this session**
  for any of the three frontend fixes — see the disclosure above. This
  is the same category of gap disclosed in every phase since 6, now
  made explicit rather than left implicit.
- The completion step is a genuinely new capability (not present before
  Phase 10), approved explicitly by you; it has no UI anywhere yet (no
  "Complete Sale" button exists in `admin-web`) — curl/API-verified
  only. Adding that button was not requested this phase.
- The end-to-end test's AI-classification step reuses the exact
  `"search-0"`/`"search-2"` deterministic photo ids already established
  in Phase 8's own test suite — same honest "proves integration, not
  model accuracy" caveat applies here too.
- No new MongoDB index was needed for the completion step (it only
  updates existing `lots`/`e_waste_submissions` documents), so there is
  nothing new to verify there.
- Same Android/browser-only-verified caveats from Phase 3–9 carry
  forward unchanged.

---

## Phase 11 — Security Testing: COMPLETE, VERIFIED

**Goal:** actively try to find real vulnerabilities in the existing
Phase 1–10 implementation (not just re-confirm existing tests pass),
fix the genuine ones found, and prove the fixes hold under real
concurrency and real cross-user attempts — without touching state
machines, RBAC design, Decimal128 handling, `reward_eligible_at`,
audit behavior, the mock AI/payment architecture, or CORS policy.

### Security audit findings (all genuinely inspected, not assumed)

**Verified secure, no action needed:**
- Full RBAC route inventory across all 15 router files: every
  privileged endpoint has an explicit `require_role(...)` gate; the
  only routes without one are the 6 intentionally-public ones
  (register/login/health/refresh).
- IDOR protection confirmed on every ownership-scoped resource
  (submissions, bids, rewards) — role alone is never sufficient
  server-side, a separate owner-id check runs on top of it.
- No NoSQL injection vector — every user input is Pydantic-typed
  before it ever reaches a Mongo filter; no raw dict passthrough
  anywhere.
- No XSS vector — zero `dangerouslySetInnerHTML`/`innerHTML` usage in
  either web frontend.
- `password_hash`/`refresh_token_hash` are never included in any API
  response schema, anywhere.
- `.env` has never been committed; secrets are not in git history.
- bcrypt hashing is correctly applied; JWT access/refresh
  type-confusion is prevented by `decode_token(expected_type=...)`.

**Genuine vulnerabilities found and fixed this phase:**

1. **[High] Reward redemption race / duplicate-payout** —
   `redeem_reward()` did a plain read-then-check with no atomic
   database guard: two concurrent redemption requests for the same
   reward could both pass the `CREDITED` check and both succeed
   against the mock payout. Fixed with
   `rewards_repo.transition_status_if_current(reward_id, "CREDITED",
   "REDEEMING")` — a single conditional `update_one` (mirroring
   `lots_repo`'s Phase 9 payment-race guard) that only one of two
   racing requests can ever match; the loser gets `409
   REWARD_REDEMPTION_ALREADY_IN_PROGRESS` before the mock payout or any
   transaction record is ever created. A failed payout reverts the
   reward to `CREDITED` (not stuck in `REDEEMING`) so it stays
   retryable.
2. **[Medium] Idempotency cache not scoped per-user** — the cache key
   was `(idempotency_key, scope)` only. If two different accounts ever
   used the identical literal idempotency-key string for the same
   scope, the second caller would have received the first caller's
   cached response, short-circuiting past whatever ownership/approval
   check should have run again. Fixed by scoping the key to
   `(user_id, idempotency_key, scope)`; the MongoDB unique index was
   dropped and recreated on the 3-field key as a **partial** unique
   index (`partialFilterExpression: {user_id: {"$exists": true}}`) —
   the same "avoid duplicate-null collisions against historical
   documents" pattern used since Phase 2, since pre-fix idempotency
   documents in the real database have no `user_id` field at all.
3. **[Medium] No server-side password minimum length** — registration
   schemas only relied on frontend `minLength` form validation, which
   is never sufficient on its own. Fixed with `password: str =
   Field(min_length=8)` on all 4 self/admin-registration schemas
   (home users, collectors, RRR centres, recyclers). `auth/schemas.py`'s
   `LoginRequest.password` was deliberately left unconstrained so
   accounts created before this fix are never locked out.
4. **[Medium] Insecure demo defaults with no startup signal** —
   `JWT_SECRET` and `ADMIN_DEFAULT_PASSWORD` silently default to known,
   publicly-visible-in-source values with nothing surfacing that fact.
   Fixed with a non-blocking `logging.warning` at startup
   (`_warn_if_insecure_defaults_active()` in `app/main.py`) naming
   exactly which default(s) are still active — deliberately a warning,
   not a hard failure, since failing startup would break the local
   demo this whole project is built around, and no new
   infrastructure (secret managers, config validators) was introduced.

**Accepted, unfixed (Low severity, explicitly out of scope this
phase):**
- No brute-force/rate-limiting on `/auth/login`. Would require new
  infrastructure (a rate limiter / attempt counter) beyond what was
  approved this phase.
- Android manifest has no explicit cleartext-traffic configuration —
  unmodified Flutter template default; not exercised by the local
  HTTP-only demo backend.

### What was built

**Backend fixes**: `app/core/idempotency.py` (user-scoped cache key),
`app/db/mongo.py` (dropped old 2-field unique index, created new
partial 3-field one), `app/db/repositories/rewards_repo.py`
(`transition_status_if_current`), `app/modules/rewards/service.py`
(atomic claim + payout-failure revert in `redeem_reward()`), 4
registration schemas (`home_users`, `collectors`, `rrr_centres`,
`recyclers`) gaining `Field(min_length=8)`, `app/main.py` (startup
warning). **32 call sites** across 7 service modules
(`bids`, `classification`, `ewaste`, `logistics`, `payments`,
`rewards`, `lots`) updated to pass the acting user's id into both
`idempotency.get_cached_response()` and `idempotency.store_response()`
— verified via grep that all 32 were migrated and none were missed.

No frontend or Flutter changes this phase — nothing found there
required a security fix.

### Tests — actually executed, this session

Backend `pytest`: **337/337 passed** (311 existing + 26 new across 5
files):
- `test_security_reward_redemption_race.py` (3): two genuinely
  concurrent HTTP redeem calls for the same reward never produce two
  `SUCCEEDED` redemption transactions (the real invariant proven
  against the live query, correctly scoped by transaction `type` so it
  isn't confused by the pre-existing `CREDIT` transaction the reward's
  own computation already created); a second attempt after a real
  success gets a clean `400`; a forced payout failure reverts the
  reward to `CREDITED` and a genuine retry then succeeds.
- `test_security_idempotency_scoping.py` (3): two different recyclers
  reusing the identical literal idempotency key get fully independent
  results, not one leaking into the other; the same user replaying
  their own key still gets the correct single cached result (no
  regression on the intended behavior); a structural check that stored
  idempotency documents actually persist `user_id`.
- `test_security_rbac_matrix.py` (4): a systematic sweep of all 5
  authenticated roles against endpoints restricted to a different
  role (not just "non-admin vs admin", every role pairing); no token
  at all is rejected as unauthenticated (401), never treated as a
  default role; malformed/garbage bearer tokens are rejected cleanly;
  a refresh token cannot be used directly as an access token.
- `test_security_input_validation.py` (12): the new password
  minimum-length is enforced server-side on all 4 registration
  schemas and the admin-created-collector path, accepts exactly 8
  characters, and pre-existing shorter passwords still log in;
  Mongo-operator-shaped JSON objects in a `str` field are rejected by
  schema validation (422) before ever reaching a query; a classic
  NoSQL-injection string payload in a login field is treated as a
  literal non-matching string, never as an operator; wrong-typed and
  incomplete payloads are rejected with 422, never a 500.
- `tests/unit/test_startup_security_warnings.py` (4): the startup
  warning function actually logs when defaults are active, names only
  the specific default(s) still active, stays silent when both are
  overridden, and never raises (proving it's genuinely non-blocking).

One genuine debugging finding worth recording: the redemption-race
test initially appeared to show a duplicate payout (2 "SUCCEEDED"
records found), which would have meant the fix didn't work. Direct
diagnostics (isolated repo-layer concurrent-write test, then a
direct service-layer call bypassing HTTP) both showed correct
behavior, narrowing the discrepancy to the test's own assertion —
its query for `SUCCEEDED` records wasn't scoped by transaction `type`,
so it was also matching the unrelated `CREDIT` transaction the reward
computation step had already inserted for the same `reward_id`. The
fix itself was correct throughout; only the test's query needed
correcting. Documented here rather than silently fixed, per this
project's standing honesty discipline around test failures.

A second, separate flakiness bug surfaced on a full-suite re-run
after that fix: `test_second_redemption_attempt_after_success_is_a_
clean_conflict` failed intermittently (~10% of runs) because
`app/modules/rewards/payout.py`'s mock payout is deterministic per
`reward_id`/amount but effectively random *across* different
`reward_id`s (a SHA-256-derived score against a 90% success rate) —
the same behavior `test_rewards_api.py` already documents with its
own "either way no crash" comment. My new test hard-asserted
`status == "SUCCEEDED"` without controlling for this, unlike the
project's existing convention. Fixed by monkeypatching `payout` to a
forced-success result in both this test and the concurrency test —
the same technique `test_failed_payout_reverts_reward_to_credited_
for_retry` already uses for the opposite (forced-failure) case — since
these tests are about proving the concurrency guard, not payout
randomness. Re-ran the file 5 times after the fix with zero failures.

`recycler-web`: **45/45** passed, unchanged (no changes this phase).
`admin-web`: **50/50** passed, unchanged. Flutter (`mobile`):
`flutter analyze` — **No issues found.** `flutter test` — **90/90
passed**, unchanged.

### Live verification — real backend, same isolated DB, no reset

The backend process still running was found to be serving stale
Phase 9 code (`GET /openapi.json` reported `"0.9.0-phase9"`) — it had
never been restarted since Phase 9's own live verification. Stopped
it and restarted against the same real `kabadiwala_connect_2_0`
MongoDB database used since Phase 3 (confirmed via
`GET /openapi.json` → `"0.11.0-phase11"`); no reset, no data deleted.

1. **Startup warning, live**: server log on this real restart shows
   `INSECURE DEMO DEFAULT(S) STILL ACTIVE: ADMIN_DEFAULT_PASSWORD` —
   confirming `.env` already overrides `JWT_SECRET` on this machine
   but not the admin password, and that the new warning function
   actually fires on a genuine startup, not just under test.
2. **Reward redemption race, live**: registered a fresh demo home
   user + collector, drove one real item to `COLLECTED`, computed a
   real reward (`CREDITED`), then fired two genuinely concurrent
   `POST /rewards/{id}/redeem` requests (real OS-level parallel curl
   processes, not `asyncio.gather` against a mock) with different
   idempotency keys. Result: one `200 SUCCEEDED`, one clean `400
   REWARD_NOT_REDEEMABLE`. Queried the real database directly
   afterward — exactly one `REDEMPTION`/`SUCCEEDED` transaction, reward
   status `REDEEMED`, no duplicate payout.
3. **Idempotency scoping, live**: registered a second fresh demo home
   user, then had both submit e-waste using the **identical literal**
   idempotency key string. Both succeeded independently with distinct
   `submission_id`s (no cached-response leak). Queried
   `idempotency_keys` directly — two separate documents, one per real
   `user_id`, same key string, same scope, each carrying its own
   independent response.

Backend (`:8000`) left running against the real database afterward.

### Known limitations / honestly unverified

- No brute-force/rate-limiting on login and no Android
  cleartext-traffic manifest entry — both accepted Low-severity gaps,
  explicitly out of scope this phase (see above).
- No actual browser/UI click-through was performed this session — no
  frontend code changed this phase, so none was needed, but the same
  disclosure standard from every prior phase is repeated here for
  consistency.
- This phase's live-verification demo entities (`PHASE11-LIVE-COL-01`,
  `phase11-live-rrr-01`, `phase11-live-home-01`/`-02`) were added to
  the same real, persistent, never-reset database used since Phase 3 —
  additive only, nothing deleted or altered.

---

## Phase 12 — APK + Deployment: COMPLETE, VERIFIED (minimal local-demo scope)

**Goal:** produce a real, installable release APK and the two
deployment/build docs the architecture doc always earmarked for this
phase, for a **local demo** — no internet/cloud deployment, no
Docker/Kubernetes, no real signing keystore, no business-logic changes
of any kind.

### Audit findings acted on

1. **Android release build blocked HTTP by default.** Android 9+
   blocks cleartext traffic app-wide unless explicitly permitted; this
   backend has no TLS anywhere (deliberate mock-payment/mock-AI
   architecture). Fixed with a **scoped** network-security-config —
   cleartext permitted only for `10.0.2.2` (the Android emulator's
   fixed host-loopback alias) and this development machine's current
   LAN IPv4 address (`10.74.38.76`, needed only for a real physical
   device on the same network) — every other domain still requires
   HTTPS + system certificate validation, per the explicit "no blanket
   cleartext policy" instruction.
2. **`10.0.2.2` is emulator-only.** Already correctly handled entirely
   at the `flutter build` invocation level via the pre-existing
   `--dart-define=API_BASE_URL=...` mechanism (`mobile/lib/core/
   config.dart` was not touched — no LAN IP was ever hardcoded into
   source, per your explicit instruction).
3. **Release build is debug-signed** (`android/app/build.gradle.kts`'s
   `release` build type uses `signingConfigs.getByName("debug")`,
   unchanged this phase) — disclosed in `APK_BUILD_GUIDE.md`, not
   silently treated as a real release signature; no keystore was
   generated, per your explicit instruction.

### What was built

- `mobile/android/app/src/main/res/xml/network_security_config.xml`
  (new) + one line in `AndroidManifest.xml`
  (`android:networkSecurityConfig="@xml/network_security_config"` on
  `<application>`) — the only code/config change this phase. No
  business logic, no Phase 9 payment/reward code, no Phase 11 security
  logic (RBAC, idempotency, password rules, startup warning) touched.
- `docs/APK_BUILD_GUIDE.md` (new): emulator vs. physical-device
  `API_BASE_URL` values, the network-security-config explanation,
  `--host 0.0.0.0` + Windows Firewall requirement for a physical
  device, exact build/install commands, and the debug-signing/
  build-time-URL/no-HTTPS limitations.
- `docs/DEPLOYMENT_GUIDE.md` (new): MongoDB start command, backend
  start command (loopback-only vs. `--host 0.0.0.0` + firewall rule),
  how to start/build all three websites, suggested local-demo run
  order, optional-internet-deployment considerations (explicitly not
  implemented), and known limitations.

### Release APK

Built with:
```
flutter build apk --release --dart-define=API_BASE_URL=http://10.0.2.2:8000
```
— the emulator-appropriate URL, since an Android emulator
(`emulator-5554`, API 37) was the only Android target actually
available this session; **no physical device was available, and the
physical-device path is documented but was not built or tested**.

Output: `mobile/build/app/outputs/flutter-apk/app-release.apk`
(mirrored at `.../apk/release/app-release.apk`) — **52,112,199 bytes
(~49.7 MiB)**. Both paths are gitignored build artifacts, not
committed. Build itself succeeded cleanly (Gradle `assembleRelease`,
~146s).

**APK installation/runtime verification: BLOCKED, not performed.**
`emulator-5554` was reachable (`adb devices` → `device`) immediately
before the build, but partway through the install attempt its Android
framework layer (`system_server` — the process hosting
`PackageManagerService`, `ActivityManagerService`, etc.) was found to
be down despite `sys.boot_completed=1` and `adb devices` still
reporting it as attached — confirmed via `adb shell service list`
returning zero framework services (`package`, `activity`) while native
HAL services were still present, i.e. a genuine emulator-side crash,
not an APK or build defect. A reboot was issued once
(`adb -s emulator-5554 reboot`); the device stayed in `offline` state
during the wait. Per your explicit instruction, no further reboot or
polling was attempted — **this is recorded honestly as blocked
infrastructure, not claimed as tested.** The APK's own build
correctness (Gradle success, correct signing config applied, correct
`--dart-define` baked in) is verified; its actual launch/network
behavior on a device is not.

### Web app builds — fresh, this session

All three built clean via `npm run build` (`tsc -b && vite build`):
- `rrr-centre-web`: 42 modules, `dist/assets/index-nn4ebLHr.js` (283
  kB / 88.5 kB gzip)
- `recycler-web`: 41 modules, `dist/assets/index-DVUZlBS8.js` (279 kB
  / 87.7 kB gzip)
- `admin-web`: 42 modules, `dist/assets/index-B9Ck3DwB.js` (291 kB /
  89.5 kB gzip)

Smoke-verified: each `dist/` served via `vite preview` (ports
4173/4174/4175) and confirmed via `curl` to be serving the **exact**
freshly-built asset hash — not a stale cached bundle.

### Full regression — re-run this session, unchanged

- Backend `pytest`: **337/337 passed** (identical to Phase 11 — no
  backend code touched this phase).
- `recycler-web`: **45/45 passed**. `admin-web`: **50/50 passed**.
- Flutter `flutter test`: **90/90 passed**.
- `flutter analyze`: **No issues found** (confirms the manifest/
  network-security-config XML addition didn't break anything the
  analyzer would catch).

### Known limitations / honestly unverified

- **Physical Android device path is documented but untested** — no
  device was available this session (see above).
- **Emulator install/launch/live-network verification did not
  complete** — blocked by an emulator-side `system_server` crash
  unrelated to this project's code, not attempted further per your
  explicit instruction to stop polling/rebooting.
- Release APK is debug-signed, not a real Play-Store-grade release
  (disclosed in `APK_BUILD_GUIDE.md`).
- `API_BASE_URL` is baked in at build time; the emulator-built APK in
  this repo's build output would need rebuilding with a LAN IP before
  it would work on a physical device.
- No internet/cloud deployment exists or was attempted — explicitly
  out of this phase's approved scope.
- Same `.env`-defaults disclosure from Phase 11 (`JWT_SECRET`/
  `ADMIN_DEFAULT_PASSWORD`) carries forward unchanged.

---

## Not yet started

The `notifications` backend module and any internet/cloud deployment.
Neither exists — nothing here should be assumed implemented.
