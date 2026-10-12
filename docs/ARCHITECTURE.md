# Kabadiwala Connect 2.0 — System Architecture & Design

Status: **Phase 0 — Design only. No implementation yet.** This document is the baseline all 12 build phases will refer back to. Nothing here is built; it is submitted for your approval before Phase 1 (backend foundation) begins.

---

## 1. System Architecture Overview

**Pattern:** Modular monolith backend + independently deployable frontends. No microservices, no event bus, no Kubernetes, no blockchain — deliberately, per your anti-overengineering constraint.

```
                              ┌─────────────────────────┐
                              │   MongoDB (single DB)    │
                              │  logically separated      │
                              │  by collection, not by DB │
                              └────────────▲─────────────┘
                                           │
                              ┌────────────┴─────────────┐
                              │   Backend API (FastAPI)   │
                              │   Modular monolith,        │
                              │   domain-organized routers │
                              │   + services + repositories│
                              └────────────▲─────────────┘
        ┌───────────────┬──────────────────┼──────────────────┬───────────────┐
        │               │                  │                  │               │
  ┌─────┴─────┐   ┌─────┴──────┐   ┌───────┴───────┐   ┌──────┴──────┐  ┌─────┴─────┐
  │  Mobile    │   │ RRR Centre │   │   Recycler     │   │   Admin      │  │ AI/ML      │
  │  (Flutter) │   │  Website   │   │   Website      │   │   Website    │  │ Classifier │
  │ Home User+ │   │  (web)     │   │   (web)        │   │   (web)      │  │ (internal  │
  │ Collector  │   │            │   │                │   │              │  │  service)  │
  └───────────┘   └────────────┘   └───────────────┘   └─────────────┘  └───────────┘
```

**Why one backend, not four:** all four frontends share the same domain rules (state machine, RBAC, idempotency, audit log). Splitting the backend by frontend would recreate the "frontend/backend mismatch" bug class explicitly called out as a Kabadiwala Connect 1.0 failure. The backend is organized internally by **domain module** (auth, ewaste, lots, bids, payments, rewards, complaints, admin, ai, notifications), each with its own router/service/repository layer, so it stays maintainable without being physically split.

**Why the frontends are still physically separate apps:** RRR, Recycler, and Admin serve different roles with different authorization boundaries. Keeping them as separate deployable web apps (not tabs of one app) means a bug in the Recycler UI can never accidentally expose an Admin route, and each can be deployed/updated independently.

**Layers inside the backend:**
1. **Router layer** — HTTP concerns only (FastAPI path operations, request/response models).
2. **Service layer** — business rules, state machine transitions, authorization checks beyond basic role gate.
3. **Repository layer** — MongoDB access (Motor), one repository per collection, no business logic.
4. **Shared core** — auth/JWT, RBAC dependency injection, config, logging, audit writer, idempotency middleware, geo-distance util, money (Decimal) util.

This layering is the direct fix for "inconsistent state transitions" and "authorization issues" in 1.0: state transitions live in exactly one place per entity (the service layer), and every router depends on an RBAC guard — there is no code path that skips it.

---

## 2. Folder Structure

```
/backend
  /app
    /core
      config.py            # env-driven settings (pydantic BaseSettings)
      security.py          # password hashing, JWT issue/verify
      rbac.py              # role dependency injection (require_role(...))
      idempotency.py        # idempotency key middleware/decorator
      geo.py                # haversine distance, tolerance checks
      money.py              # Decimal-based money helpers
      audit.py              # audit log writer
      errors.py             # structured error responses + error codes
    /modules
      auth/            (router.py, service.py, schemas.py)
      home_users/
      collectors/
      rrr_centres/
      recyclers/
      wards/
      ewaste/            # submission + handover + geo verification
      classification/    # AI classification integration
      lots/
      bids/
      logistics/
      payments/
      rewards/
      complaints/
      admin/
      notifications/
      audit_logs/        # read-only query endpoints for admin
    /db
      mongo.py            # Motor client, index creation on startup
      repositories/       # one file per collection
    /state_machines
      ewaste_states.py
      bid_states.py
      lot_states.py
    main.py                # app factory, router registration, middleware
  /tests
    /unit
    /integration
  /scripts
    seed_admin.py
    seed_demo_data.py
  .env.example
  requirements.txt
  Dockerfile (optional, documented but not required for demo)

/mobile                     # Flutter — Home User + Collector apps (one app, role-based nav)
  /lib
    /core (api_client, auth_storage, config)
    /features
      auth/
      home_user/
      collector/
    /shared (widgets, theme)
  pubspec.yaml

/recycler-web                # separate SPA, talks only to /api/v1
/admin-web                   # separate SPA
# rrr-centre-web removed — RRR-centre lot creation/publishing is API-only now.

/docs
  README.md
  SETUP_GUIDE.md
  ARCHITECTURE.md            # this document, refined
  API_DOCUMENTATION.md
  DATABASE_SCHEMA.md
  TESTING_GUIDE.md
  SECURITY.md
  DEPLOYMENT_GUIDE.md
  APK_BUILD_GUIDE.md
  DEMO_GUIDE.md
```

**Note on the mobile app — approved: one Flutter codebase, strictly role-isolated.** Home User and Collector share one Flutter codebase (avoiding duplicated camera/GPS/upload code) but are strictly separated at every layer, not just by which nav item is shown:

- **Navigation isolation:** two entirely separate navigation graphs (`home_user_router` vs `collector_router`), selected once at login based on the role returned by the backend in the login response — never based on a locally-stored or user-editable flag. There is no shared route table where a Home User route and a Collector route could both resolve; the non-matching graph is never even constructed for the logged-in session.
- **Storage isolation:** the JWT and role are written to secure storage (`flutter_secure_storage`) together, as a single unit, immediately after login. The app never reads a separately-stored "role" value to decide what to show — it decodes the role from the verified JWT itself each time, so editing local storage can't detach the displayed role from the token's actual claim.
- **API isolation:** the API client only exposes the request-builder methods relevant to the session's role (e.g. a `HomeUserApi` class vs a `CollectorApi` class); the Collector build of the client has no method that even knows how to call a Home User endpoint, and vice versa. This is a defense-in-depth/UX measure, not the security boundary.
- **Backend is authoritative, always:** none of the above is trusted as the actual security control. Every backend endpoint independently re-verifies the JWT and re-checks the caller's role and ownership server-side (see Section 5 and Section 7) regardless of which client or client state sent the request. So even if someone manually crafted a raw HTTP request claiming to be a Collector call with a Home User's token, or modified the token/local storage/request parameters, the backend rejects it — the Flutter-side isolation only prevents an honest user from *accidentally* landing on the wrong screen; it is not what stops a malicious request.

---

## 3. Database / Entity Design (MongoDB)

All collections use `_id` (ObjectId) plus a human-facing business ID where the spec requires one (e.g. `submission_id`, `lot_id`). Timestamps `created_at`/`updated_at` (UTC) on every collection.

| Collection | Purpose | Key fields | Indexes / uniqueness |
|---|---|---|---|
| `users` | Auth identity for every role | phone/username, password_hash, role, status | unique(phone) or unique(username) per role type |
| `home_users` | Home user profile | user_id, full_name, address, upi_id, household_location {lat,lng} | unique(user_id) |
| `collectors` | Collector profile | user_id, **employee_id (= login username)**, rrr_id, ward_id, assigned_area (radius), created_by_admin_id | unique(employee_id) |
| `rrr_centres` | RRR centre profile | rrr_id, tender_id, ward_id, licence_docs, status(PENDING/APPROVED/REJECTED) | unique(rrr_id), unique(tender_id) |
| `recyclers` | Recycler profile | license_id (=username), company_name, status(PENDING/APPROVED/REJECTED) | unique(license_id) |
| `wards` | Municipal ward reference data | ward_id, name, rrr_centre_id | unique(ward_id), unique(rrr_centre_id) — one RRR per ward |
| `e_waste_submissions` | Home user's initial submission | submission_id, home_user_id, photo_file_id, home_lat, home_lng, home_ts, status | unique(submission_id), index(home_user_id, status) |
| `collection_handovers` | Collector's handover event | submission_id, collector_id, rrr_id, photo_file_id, collector_lat, collector_lng, collector_ts, distance_m, verification_result | unique(submission_id) — one handover per submission |
| `e_waste_items` | Post-verification canonical item record (feeds classification + lots **and independently feeds citizen rewards**) | item_id, submission_id, home_user_id, current_state, **reward_eligible_at (immutable, set-once timestamp written exactly once when state first reaches `COLLECTED`; never updated/cleared by later transitions)** | unique(item_id), index(home_user_id, reward_eligible_at) |
| `ai_classifications` | Every classification attempt (AI or manual) | item_id, predicted_category, confidence, model_version, confirmed_category, confirmed_by, source(AI/MANUAL) | index(item_id) |
| `lots` | RRR-created sellable lot | lot_id, rrr_id, ward_id, category, item_ids[], status, bid_deadline | unique(lot_id), index(rrr_id, status) |
| `bids` | Recycler bid on a lot | bid_id, lot_id, recycler_id, amount, status(PLACED/CANCELLED/ACCEPTED/REJECTED) | unique(bid_id), index(lot_id, status), **partial unique index on `{lot_id: 1}` where `status: "ACCEPTED"` — keyed on `lot_id` only, not `(lot_id, recycler_id)`, so it is physically impossible for any two documents (from the same or different recyclers) to hold `status: ACCEPTED` for the same lot** |
| `logistics_bookings` | Recycler's collection slot | booking_id, lot_id, recycler_id, slot_time, status | unique(booking_id), unique(lot_id) — one active booking per lot |
| `payments` | Payment records (recycler → mock gateway) | payment_id, lot_id, recycler_id, amount, idempotency_key, status | unique(payment_id), unique(idempotency_key) |
| `rewards` | Computed monthly reward per home user | reward_id, home_user_id, period(YYYY-MM), points, amount, status | unique(home_user_id, period) — prevents double reward for same month |
| `reward_transactions` | Individual credit/redemption ledger entries | txn_id, home_user_id, type(CREDIT/REDEMPTION), amount, idempotency_key | unique(txn_id), unique(idempotency_key) |
| `complaints` | All actor complaints | complaint_id, reporter_id, reporter_role, target_type, target_id, category, status | unique(complaint_id), index(status) |
| `notifications` | In-app notifications | notification_id, user_id, type, read | index(user_id, read) |
| `audit_logs` | Immutable event log | log_id, actor_id, actor_role, action, entity_type, entity_id, before/after snapshot, timestamp | index(entity_type, entity_id), index(timestamp) — write-only from app code, no update/delete endpoint exists |
| `government_actions` | Admin-specific privileged actions (approvals, overrides, **and eligibility invalidations — see note below**) | action_id, admin_id, action_type, target_id, reason | index(target_id) |

**Enforcing "only one accepted bid per lot" at the database level (corrected):**

```javascript
db.bids.createIndex(
  { lot_id: 1 },
  { unique: true, partialFilterExpression: { status: "ACCEPTED" } }
)
```

The index key is **`lot_id` alone** — `recycler_id` is deliberately **not** part of the key. If `recycler_id` were included (`{lot_id: 1, recycler_id: 1}`), MongoDB would treat `(lot_A, recycler_X, ACCEPTED)` and `(lot_A, recycler_Y, ACCEPTED)` as two distinct index entries and allow both to exist — which would let two different recyclers simultaneously "win" the same lot. Keying on `lot_id` only means the index has exactly one slot per lot for the `ACCEPTED` state, so whichever `accept` request's write reaches MongoDB first succeeds, and the second one — regardless of which recycler it's from — is rejected with a duplicate-key error at the database layer. The service layer catches that duplicate-key error and returns the structured `LOT_ALREADY_ACCEPTED` error code; it does not itself decide who won, MongoDB does.

**Money fields** are stored as strings or `Decimal128` (MongoDB's native decimal type) — never as floats — so backend arithmetic never introduces rounding drift.

---

## 4. API Architecture

Base path: `/api/v1/`

```
/api/v1/auth              login, refresh, logout (per role)
/api/v1/home-users         registration, profile, upi
/api/v1/collectors         profile (read-only view of employee_id/rrr_id/ward/assigned-area)
/api/v1/rrr-centres        registration, profile, approval status
/api/v1/recyclers          registration, profile, approval status
/api/v1/wards              reference data (admin-managed)
/api/v1/ewaste             submission create, list, detail, handover
/api/v1/ai                 classify (internal, called by ewaste/lots flow), review/confirm
/api/v1/lots               create, list, publish ("bid it"), detail
/api/v1/bids               place, cancel, accept, cancel-acceptance
/api/v1/logistics          book slot
/api/v1/payments           initiate, confirm (mock gateway callback)
/api/v1/rewards            summary, redemption request (eligibility computed from COLLECTED items, independent of lot/sale status)
/api/v1/complaints         create, list, admin review
/api/v1/admin              approvals, ward mgmt, **collector account creation & RRR/ward/area assignment**, monitoring, config
/api/v1/audit-logs         admin-only read
/api/v1/notifications      list, mark-read
```

Every state-changing endpoint (submission, handover, bid actions, payment, reward) accepts an `Idempotency-Key` header, per your idempotency requirement.

Every response uses the structured error contract from your spec:
```json
{ "success": false, "error_code": "LOT_ALREADY_ACCEPTED", "message": "..." }
```

---

## 5. Authentication Architecture

- Password hashing: bcrypt (via `passlib`).
- JWT access token (short-lived, ~15 min) + refresh token (longer-lived, stored server-side or as httpOnly cookie for web apps; secure storage on Flutter via `flutter_secure_storage`).
- Every token carries `sub` (user id) and `role`. The **role in the token is never trusted alone** — every protected endpoint's RBAC dependency re-fetches the user's current role/status from the database on each request, so a revoked/downgraded account can't keep acting on a stale token claim.
- Ownership checks are separate from role checks: e.g. "is RRR_CENTER" (role check) is necessary but not sufficient for "can edit lot X" — the service layer additionally checks `lot.rrr_id == current_user.rrr_id`.
- Admin demo credentials (`admin` / `admin1234`) are seeded by `scripts/seed_admin.py` from environment variables (`ADMIN_DEFAULT_USERNAME`, `ADMIN_DEFAULT_PASSWORD`), never hardcoded in application code, so production can override them via secrets without a code change.

**Collector authentication (corrected):**
- **Username = Employee ID.** This is the collector's login identifier, issued by Government Admin — never chosen by the collector.
- **Password = a separate credential**, either set by the administrator at account creation (and required to be changed on first login) or issued through a government-controlled reset flow. It is a normal hashed password like any other role's — not the RRR ID, and not derived from it.
- **RRR ID is relationship data, never a credential.** It lives on the `collectors` document as the collector's assigned organizational link (`collector.rrr_id`), alongside `ward_id` and `assigned_area`. It is never accepted as a login field, never compared against a password hash, and cannot be supplied or changed by the collector through any collector-facing endpoint.
- **Account creation is admin-only.** There is no collector self-registration endpoint. Only `POST /api/v1/admin/collectors` (Government Admin role required) creates a collector account, and only admin-only endpoints (`PATCH /api/v1/admin/collectors/{id}`) can change a collector's `employee_id`, `rrr_id`, `ward_id`, or `assigned_area` afterward. The collector's own profile endpoint (`GET /api/v1/collectors/me`) is **read-only** with respect to these fields — a collector can view their assigned RRR/ward/area but has no endpoint capable of writing to them.
- This closes the "collector self-assigns an arbitrary RRR ID or ward" gap: the write path for that relationship exists in exactly one place (admin module), and the collector-facing API surface for that data is read-only by construction, not just by convention.

---

## 6. State Machines

### 6.1 E-Waste Submission / Item Lifecycle
```
CREATED → PHOTO_CAPTURED → WAITING_FOR_COLLECTION → COLLECTOR_ASSIGNED
→ HANDOVER_PENDING → LOCATION_VERIFIED → COLLECTED → AT_RRR
→ CLASSIFIED → LOT_CREATED → LISTED_FOR_BIDDING → BID_SELECTED
→ LOGISTICS_BOOKED → READY_FOR_COLLECTION → PAYMENT_PENDING → PAID → COMPLETED
```
Side branch: `HANDOVER_PENDING → FLAGGED_FOR_REVIEW` if geo/timestamp verification fails, instead of silently proceeding to `LOCATION_VERIFIED`. An admin action moves `FLAGGED_FOR_REVIEW` back to `HANDOVER_PENDING` (retry) or to `REJECTED` (terminal).

**Reward eligibility (corrected, final):** the item becomes **reward-eligible as soon as it reaches `COLLECTED`** (immediately after successful geo-tag verification of the handover) — it does **not** wait for `AT_RRR`, `CLASSIFIED`, `LOT_CREATED`, `SOLD`, `PAID`, or `COMPLETED`. The rest of the state machine (classification → lot → bidding → sale → payment) continues independently and has no bearing on whether the citizen who contributed the item gets credited.

**Authoritative eligibility event, not derived state (clarification applied):** the monthly reward batch does **not** query "is `current_state` currently `COLLECTED` or later." Instead, the transition function that moves an item into `COLLECTED` writes a single, immutable `reward_eligible_at` timestamp onto the `e_waste_items` document **at that moment, once, and never again** — this field is set-once (the write path enforces "only if currently null/unset") and is never updated or cleared by any later transition, including `CLASSIFIED`, `LOT_CREATED`, or `COMPLETED`. The batch job's query is simply "`reward_eligible_at` falls within this period," which makes eligibility a recorded historical fact rather than a live read of mutable current state — so eligibility can never be silently lost or altered by unrelated downstream lot/bid/payment activity.

**Handling later-discovered fraud/invalidity — no silent rewrite, no clawback:** if an administrator later determines a specific contribution was invalid or fraudulent, the original `reward_eligible_at` timestamp and the historical event that set it are **never erased or rewritten**. Instead the admin action creates a new, separate, explicitly-audited record — an `eligibility_invalidation` entry (stored in `government_actions`, referencing the `item_id`, the admin who acted, a reason, and a timestamp) — which the reward *computation* step consults going forward: an item with an active invalidation record is excluded from any *future* reward computation, but a reward that was already computed and credited for a prior period is left as-is; there is no automatic debit or clawback path from the citizen's UPI, consistent with the one-way Government→UPI rule. Any correction to money already credited is a distinct, explicit, admin-reviewed adjustment process — never an automated reversal.

Each transition is implemented as an explicit function in `state_machines/ewaste_states.py` with an allow-list of valid `(from_state, to_state)` pairs; any call outside the allow-list raises `INVALID_STATE_TRANSITION`. No endpoint writes a `status` field directly — all writes go through this module.

### 6.2 Bid Lifecycle (per bid document)
```
PLACED → CANCELLED         (recycler-initiated, only before acceptance)
PLACED → ACCEPTED          (RRR-initiated, only one bid per lot)
ACCEPTED → CANCELLED       (RRR-initiated, only within 24h AND before payment)
ACCEPTED → (locked)        (once payment succeeds, no further transition possible)
PLACED → REJECTED          (implicit, when a sibling bid is ACCEPTED — optional, for clarity in UI)
```
The 24-hour and "before payment" guards are enforced in the service layer by comparing `now() - acceptance_time` and by checking `payments` collection for a `SUCCEEDED` payment tied to the lot before allowing `ACCEPTED → CANCELLED`.

### 6.3 Lot Lifecycle
```
DRAFT → LISTED_FOR_BIDDING → BID_SELECTED → LOGISTICS_BOOKED
→ READY_FOR_COLLECTION → PAYMENT_PENDING → SOLD → COMPLETED
```
`BID_SELECTED → LISTED_FOR_BIDDING` is an allowed backward transition only when triggered by the "RRR acceptance cancellation within 24h" flow described above.

---

## 7. Role / Permission Matrix

| Action | HOME_USER | COLLECTOR | RRR_CENTER | RECYCLER | GOV_ADMIN |
|---|---|---|---|---|---|
| Submit e-waste | ✅ (own) | ❌ | ❌ | ❌ | ❌ |
| Confirm handover | ❌ | ✅ (own assigned area only) | ❌ | ❌ | ❌ |
| Review/confirm AI classification | ❌ | ❌ | ✅ (own RRR only) | ❌ | ❌ |
| Create/publish lot | ❌ | ❌ | ✅ (own RRR only) | ❌ | ❌ |
| Place/cancel bid | ❌ | ❌ | ❌ | ✅ (own bids only) | ❌ |
| Accept bid / cancel acceptance | ❌ | ❌ | ✅ (own lots only) | ❌ | ❌ |
| Book logistics | ❌ | ❌ | ❌ | ✅ (own accepted lot only) | ❌ |
| Make payment | ❌ | ❌ | ❌ | ✅ (own committed lot only) | ❌ |
| View own reward summary | ✅ (own) | ❌ | ❌ | ❌ | ❌ |
| Request UPI redemption | ✅ (own) | ❌ | ❌ | ❌ | ❌ |
| File complaint | ✅ | ✅ | ✅ | ✅ | n/a |
| Approve RRR / recycler registration | ❌ | ❌ | ❌ | ❌ | ✅ |
| Manage wards, **create/assign collectors (employee_id, RRR ID, ward, area)** | ❌ | ❌ | ❌ | ❌ | ✅ |
| View own assigned RRR ID / ward / area (read-only) | ❌ | ✅ (own, read-only) | ❌ | ❌ | ❌ |
| View audit logs | ❌ | ❌ | ❌ | ❌ | ✅ |
| View system-wide monitoring | ❌ | ❌ | ❌ | ❌ | ✅ |

"(own X only)" is enforced by an ownership check in the service layer on top of the role check — never by the role check alone.

---

## 8. Geo-Tag Verification Design

Terminology used throughout the product and docs: **"geo-tag based verification"** — never a claim that GPS can't be spoofed.

Inputs: `home_lat/lng/ts` (from submission), `collector_lat/lng/ts` (from handover).

Checks performed server-side at handover time:
1. **Distance check** — haversine distance between the two points ≤ `MAX_HANDOVER_DISTANCE_METERS` (env-configurable, default e.g. 150m).
2. **Timestamp sanity** — collector timestamp must be after submission timestamp, and within a configurable max window (e.g. `MAX_HANDOVER_WINDOW_HOURS`) to catch "impossible movement/time" cases.
3. **GPS validity** — reject missing/null coordinates, out-of-range lat/lng, or (0,0) sentinel values; a rejected reading never silently becomes "verified" — it always routes to `FLAGGED_FOR_REVIEW`.
4. **Duplicate detection** — reject a second handover attempt against the same `submission_id` (unique index on `collection_handovers.submission_id`), and flag two submissions with identical photo hash.
5. **Assignment check** — collector's `assigned_area`/ward must match the submission's ward; otherwise reject with `COLLECTOR_OUTSIDE_ASSIGNED_AREA`.

All inputs and the computed distance/result are stored on the `collection_handovers` document as permanent evidence, and a summary is written to `audit_logs`.

---

## 9. AI/ML Classification Design

- A thin internal interface `ClassifierService.classify(photo) -> {category, confidence, model_version}` — the concrete model implementation is swappable behind this interface (starts as a simple image classifier, e.g. a small CNN or a pretrained model fine-tuned on e-waste categories; exact model choice is a Phase 8 decision, not a Phase 0 one).
- Every classification attempt (AI or manual) is stored in `ai_classifications`, never overwritten — so `predicted_category` (AI) and `confirmed_category` (human) are always both visible.
- If `confidence < CLASSIFICATION_CONFIDENCE_THRESHOLD` (env-configurable), the item is marked `NEEDS_REVIEW` and cannot proceed to `LOT_CREATED` until an RRR staff member confirms a category.
- If the AI service is down/errors, the ewaste pipeline does not block: the item is marked `NEEDS_REVIEW` with `model_version: "unavailable"` and routes straight to manual classification — this satisfies "AI must not block the entire application."

---

## 10. Bid Lifecycle (end-to-end)

```
Lot LISTED_FOR_BIDDING
  → Recycler places bid (status PLACED, idempotent via idempotency key)
  → Recycler may cancel (PLACED → CANCELLED) any time before RRR acceptance
  → RRR accepts exactly one bid (PLACED → ACCEPTED; DB partial unique index on `lot_id` alone prevents a race between any two recyclers)
  → RRR may cancel acceptance within 24h (ACCEPTED → CANCELLED, lot reopens to LISTED_FOR_BIDDING)
  → After 24h OR after payment succeeds, acceptance is final and immutable
  → Recycler books logistics (only allowed once bid is ACCEPTED)
  → Recycler reaches collection stage → payment initiated
  → Payment SUCCEEDED → bid/lot locked, recycler cannot cancel, lot → SOLD
```
All cancelled/rejected bids remain visible in history on both the RRR's bid list and audit logs — nothing is deleted.

---

## 11. Payment Lifecycle

```
(bid ACCEPTED) → logistics booked → recycler reaches collection stage
  → PAYMENT_PENDING created (idempotency_key required)
  → mock/sandbox payment gateway called → PAYMENT_SUCCEEDED or PAYMENT_FAILED
  → on SUCCEEDED: payment record finalized, lot marked SOLD, bid locked
  → on FAILED: lot remains READY_FOR_COLLECTION, recycler may retry (same idempotency key returns same result, doesn't double-charge)
```
The mock payment mechanism is clearly labeled `MOCK_PAYMENT_GATEWAY` in both API responses and UI, per your "no fake banking integration" instruction. No card numbers, CVVs, UPI PINs, or bank passwords are ever accepted or stored by the backend.

---

## 12. Reward Lifecycle (Home User) — corrected

**Eligibility is decoupled from the downstream RRR/recycler pipeline.** A citizen's contribution becomes reward-eligible the moment it is officially collected, not when it is later sold to a recycler:

```
Home submission (CREATED)
  → Collector handover
  → Geo-tag verification succeeds
  → item reaches COLLECTED  ───────────►  reward_eligible_at is stamped NOW
                                           (item may continue on to AT_RRR → CLASSIFIED →
                                            LOT_CREATED → ... → COMPLETED independently —
                                            none of that affects the citizen's eligibility)
```

Then, independently, at month-end:

```
Month-end batch job
  → query e_waste_items where home_user_id = X
    AND reward_eligible_at falls within the period          (the authoritative, immutable event —
                                                               not a read of current_state)
    AND item_id has no active `eligibility_invalidation` record in government_actions
  → compute points per configurable formula (points-per-kg or points-per-item, env/config-driven)
  → reward document created: unique(home_user_id, period) prevents double computation for the same month
  → reward_transactions entry: type CREDIT, idempotency_key = f"{home_user_id}:{period}:credit"
  → Home user requests redemption → reward_transactions entry: type REDEMPTION, idempotency_key = f"{reward_id}:redemption"
  → Redemption transfers Government → UPI only; there is no code path that debits a user's UPI — the payments module used for recycler purchases and the rewards module used for citizen credit are separate services with no shared "charge user" function.
```

**Why `reward_eligible_at` is authoritative, not derived:** it is written exactly once, by the `COLLECTED` transition, and never touched again by any later transition (`CLASSIFIED`, `LOT_CREATED`, `SOLD`, `COMPLETED`, or anything else). The batch job trusts this recorded fact rather than re-deriving "is this item currently in state X or later" — so a legitimately collected contribution's eligibility can never be silently lost, delayed, or altered by unrelated downstream marketplace activity (an unsold lot, a cancelled bid, a slow sale).

**Handling later-discovered fraud — invalidation, not rewrite, never a clawback:** if an administrator later determines a contribution was invalid, the system does **not** erase or edit the historical `reward_eligible_at` value. It creates a new, separate, audited `eligibility_invalidation` record (admin_id, item_id, reason, timestamp) in `government_actions`. That record is consulted only by *future* reward computations (excluding the item going forward); a reward already computed and credited for a prior period is left untouched — correcting it, if ever needed, is a distinct, explicit, admin-reviewed adjustment process, never an automatic debit from the citizen's UPI.

---

## 13. Complaint Lifecycle

```
Any actor files complaint → status OPEN (complaint_id generated)
  → Admin reviews → IN_PROGRESS
  → Admin resolves/rejects/escalates → RESOLVED / REJECTED / ESCALATED
```
Every status change writes an `audit_logs` entry with `actor_id`, `before_status`, `after_status`.

---

## 14. Audit Logging Design

- `audit_logs` is **append-only**: the API layer exposes no update or delete route for this collection, for any role including admin.
- Every write to a state-changing collection (submissions, handovers, classifications, lots, bids, payments, rewards, complaints, government approvals) triggers a call to a single shared `audit.record(...)` helper — so logging can't be forgotten in one module and present in another.
- Each entry captures actor, role, action, entity type/id, and a before/after snapshot where relevant, enabling the "Government Admin can see the complete audit trail" demo step.

---

## 15. Testing Strategy

- **Unit tests** — state machine transition tables (valid/invalid pairs), geo-distance calculation, money rounding, idempotency key handling.
- **Integration tests** (API level, against a test MongoDB instance) — one suite per domain module, covering every scenario listed in your Section 41 (auth, home user, collector, RRR centre, recycler, admin, financial).
- **Concurrency tests** — specifically simulate two simultaneous "accept bid" or "confirm payment" requests to verify the DB-level unique index actually prevents double-acceptance/double-payment, not just the application logic. Concretely: **`test_two_different_recyclers_cannot_both_be_accepted_for_same_lot`** — create one lot with bids from two distinct recyclers (Recycler A and Recycler B), fire both "accept" requests concurrently (e.g. via `asyncio.gather` against the running test app), and assert exactly one request returns HTTP success with the bid transitioned to `ACCEPTED`, while the other returns the structured `{"success": false, "error_code": "LOT_ALREADY_ACCEPTED", ...}` response — never both succeeding, never both failing.
- **Idempotency tests** — replay the same request with the same idempotency key and assert no duplicate record is created.
- **Reward eligibility tests:**
  - `test_reward_eligible_on_collected_not_on_sale` — create an item, drive it only to `COLLECTED` (do not classify, lot, or sell it), run the month-end reward batch, and assert the home user receives a reward credit.
  - `test_reward_not_blocked_by_unsold_or_cancelled_lot` — a `COLLECTED` item still earns its reward even if the resulting lot is never listed, never sold, or has all its bids cancelled.
  - `test_reward_eligible_at_is_set_once_and_immutable` — drive an item through `COLLECTED → AT_RRR → CLASSIFIED → LOT_CREATED → ... → COMPLETED` and assert `reward_eligible_at` is written exactly once (at the `COLLECTED` transition) and its value never changes across all subsequent transitions.
  - `test_invalidation_excludes_future_not_past_rewards` — compute and credit a reward for period M, then have an admin invalidate the underlying item; assert the already-issued reward_transactions CREDIT for period M is untouched, the `eligibility_invalidation` record is created and audited, and the item is excluded from any reward computation for a later period M+1.
  - `test_invalidation_never_creates_a_debit` — after an admin invalidation, assert no `reward_transactions` entry of any debit-like type is ever created and no code path exists that could reduce the citizen's UPI balance.
- **Collector account integrity tests** — `test_collector_cannot_self_register`: assert there is no unauthenticated/collector-role-accessible endpoint that creates or edits a `collectors` document. `test_collector_cannot_change_own_rrr_or_ward`: authenticate as a collector, attempt `PATCH` on their own profile with a different `rrr_id`/`ward_id`, and assert it is rejected (403 or field silently ignored, per final endpoint design) while an admin-issued `PATCH /api/v1/admin/collectors/{id}` for the same change succeeds.
- **Role-isolation tests (mobile)** — `test_home_user_token_rejected_on_collector_endpoints` and its reverse: call a Collector-only endpoint with a valid Home User JWT (and vice versa) and assert a 403 from the backend RBAC guard, independent of anything the Flutter client would normally prevent — confirming the backend, not the app's navigation graph, is the actual boundary.
- Tests are run after every phase before moving to the next, per your Section 40 process; failures are fixed before proceeding, and results are reported honestly (executed/passed/failed/limitations) rather than claimed "bug-free."

---

## 16. Development Phases (confirmed plan)

1. Architecture + DB schema + state machines *(this document)*
2. Backend foundation + authentication
3. Home User mobile app
4. Collector mobile app
5. RRR Centre website
6. Recycler website
7. Government Admin website
8. AI classification
9. Payments/rewards
10. Integration testing
11. Security testing
12. APK build + deployment documentation

Each phase will open with the 8-point pre-implementation breakdown you specified (architecture, files, DB changes, endpoints, screens, security considerations, tests, then implementation) before any code is written.

---

## 17. Risks and Mitigation

| Risk | Mitigation |
|---|---|
| GPS spoofing / fake location apps | Framed honestly as "geo-tag based verification," not spoof-proof; flagged (not silently accepted) cases go to human review; distance/time tolerances are configurable so they can be tightened |
| Two recyclers racing for one lot | DB-level partial unique index on `bids.lot_id` (not `lot_id + recycler_id`) for `status: ACCEPTED`, not just UI disabling — guarantees only one recycler, regardless of identity, can hold ACCEPTED for a given lot |
| Duplicate financial operations on retry | Idempotency keys + unique indexes on `payments.idempotency_key` and `reward_transactions.idempotency_key` |
| AI classifier downtime blocking the pipeline | Explicit `NEEDS_REVIEW`/manual fallback path, AI call wrapped in try/except with graceful degradation |
| Frontend/backend state mismatch (1.0's core bug class) | All state transitions centralized in backend state-machine modules; frontends only ever display server-returned status, never compute or assume it |
| Over-permissioned recycler/RRR/collector access (IDOR) | Every service-layer method takes `current_user` and checks ownership, not just role, before reading/writing |
| Household privacy leakage to RRR/recycler | RRR receives only classification-relevant data; recycler receives RRR location, never household location; enforced via separate response schemas per role, not by filtering the same schema client-side |
| Offline mobile submissions duplicating on resync | Client-generated idempotency key persisted with the local draft, sent unchanged on retry |
| Scope creep into microservices/blockchain/etc. | Explicit modular-monolith decision recorded here; revisit only if a specific, demonstrated scaling need arises |
| Home User/Collector role bleed in the shared Flutter codebase | Separate nav graphs selected once at login from the verified JWT role, separate API client surfaces per role, JWT+role stored as one unit — but the real boundary is server-side RBAC re-checked on every request, so even a fully compromised/modified client can't act outside its authenticated role |
| Collector self-assigning RRR ID/ward | No collector-facing write path exists for `rrr_id`/`ward_id`/`assigned_area`; only `Government Admin` endpoints can create or modify a collector's assignment, and collector profile reads are read-only for these fields |

---

**This is the end of Phase 0.** Per your instructions, I'm stopping here for your review and approval before starting Phase 1 (backend foundation + authentication). Flag anything you want changed — in particular the two open design calls: (1) one Flutter codebase with role-gated navigation vs. two separate Flutter projects for Home User and Collector, and (2) the specific AI model/approach for Phase 8 (deferred, but let me know if you have a preference now).
