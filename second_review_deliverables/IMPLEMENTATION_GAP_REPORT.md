# Implementation Gap Report – Kabadiwala Connect 2.0

Prepared on 12 October 2026 for the MCA Mini Project Second Review. All findings below come from read-only inspection of:

- `D:\FSIH\kabadiwala-connect-2.0-SHARE` (main application: backend, mobile, recycler-web, admin-web, docs)
- `D:\FSIH\ewaste_ml\ewaste_ml` (YOLOv8n training project)
- `D:\FSIH\price_ml(working)` (price model training project)

**Update (12 Oct 2026):** the household-privacy defect listed in the first version of this report has since been fixed with the author's approval and verified with four new regression tests (full backend suite 412/412). The sections below have been updated accordingly. A later consistency pass on the same date corrected the idempotency claim (17 of 45 state-changing operations, not all) and relabelled the recorded web test results as unverified historical evidence. All other findings are unchanged.

No secrets from `.env` are reproduced here or in any deliverable. The database URL was checked only for its scheme (`mongodb+srv`, Atlas host).

---

## 1. Features verified as complete

Verified means: the code exists, it is wired into the API or app, and tests that cover it passed in a run on 12 Oct 2026 (Flutter 153/153; backend 408/408 before the privacy fix and 412/412 after it; logs in `evidence/` and `privacy_fix_proposal/`).

| Area | What was verified | Evidence |
|---|---|---|
| Backend foundation | FastAPI app, 19 domain modules, 86 endpoints under `/api/v1`, structured error format | `backend/app/main.py`, `modules/*/router.py` |
| Authentication | bcrypt hashing, JWT HS256 (access 15 min, refresh 7 days), login/refresh/logout/me | `core/security.py`, `test_auth_api.py`, `test_security.py` |
| Role-based access | 5 roles; role and status re-read from DB on every request; ownership checks in services | `core/rbac.py`, `test_security_rbac_matrix.py`, `test_cross_role_isolation.py` |
| Database integration | MongoDB via Motor; 19 collections; indexes created at start-up; configured for Atlas | `db/mongo.py`, `db/repositories/*` |
| State machines | E-waste item (22 states, 26 transitions), lot, bid, complaint | `state_machines/*`, unit tests |
| Idempotency (main workflow only) | `Idempotency-Key` required and cached replay on 17 of the 45 state-changing operations: submission, collector acceptance, handover, receipt, manual and AI classification, lot creation and publishing, bid place/cancel/accept/cancel-acceptance, logistics booking and confirmation, payment, reward redemption and lot completion. Coverage of the other 28 is open (see Section 2). | `core/idempotency.py`, `test_security_idempotency_scoping.py`, `evidence/idempotency_coverage_2026-10-12.txt` |
| Audit log | Append-only `audit_logs`; admin read endpoint only | `core/audit.py`, `audit_logs/router.py` |
| E-waste submission | Photo upload (JPEG/PNG/WebP ≤ 10 MB), submission with GPS, ward queue, accept | `modules/ewaste`, `test_ewaste_api.py` (35 tests), `test_ewaste_photo_upload.py` |
| Geo-tag handover | Haversine ≤ 150 m, timestamp after submission and ≤ 48 h, invalid GPS → FLAGGED_FOR_REVIEW | `ewaste/service.py::handover`, `core/geo.py`, `test_geo.py` |
| Collector auto-lot | Verified handover → single-item lot listed for bidding, owned by collector | `ewaste/service.py::auto_progress_to_listed_lot`, `test_collector_lot_workflow.py` |
| Lots and bidding | Create/publish lots, place/cancel/accept bids, cancel acceptance (24 h, before payment), one ACCEPTED bid per lot via partial unique index | `modules/lots`, `modules/bids`, `test_bids_api.py` |
| Logistics and payment | Slot booking, collection confirmation, deterministic mock gateway | `modules/logistics`, `modules/payments`, tests |
| Rewards | `reward_eligible_at` set once at COLLECTED; monthly compute (10 points/item, ₹0.50/point); mock UPI redemption; no double reward | `modules/rewards`, `test_rewards_api.py`, race test |
| Complaints, notifications | Complaint workflow and admin review; in-app notifications | tests pass |
| End-to-end flow | Registration → submission → handover → lot → bid → payment → reward redemption | `test_end_to_end_flow.py` |
| Image detection integration | YOLOv8n `best.pt` loaded by backend; `/ai/classify-photo` and `/ai/classify/{id}`; threshold 0.6 → NEEDS_REVIEW | `classification/yolo_classifier.py`, `service.py` |
| Detection model accuracy | Test split (758 images): P 0.868, R 0.822, mAP@0.5 0.876, mAP@0.5:0.95 0.653 | `evidence/yolo_test_split_eval_2026-10-12.txt` |
| Deployed = evaluated model | `backend/ai/detection/weights/best.pt` MD5 = `ewaste_ml/runs/detect/ewaste_yolov8n5/weights/best.pt` (ae52a1ae…) | md5sum |
| Price model | HistGradientBoostingRegressor pipeline; chosen from 5 models on a time-ordered split; deployed model identical to training output (MD5 cf6f1fc8…) | `price_ml(working)/outputs/*.csv`, `src/train.py` |
| Price trend | From real accepted bids, 90-day window, ≥ 4 daily points, ±5 % "stable" band | `pricing/service.py::price_trend`, tests |
| Flutter mobile app | Home User + Collector roles, offline queue with idempotent replay, Kannada UI table | `mobile/lib`, Flutter tests 153/153 |
| Household privacy toward recyclers (**fixed 12 Oct 2026**) | `GET /api/v1/lots/listed` and `GET /api/v1/lots/{id}` (recycler role) now pass lots through an allow-list that keeps only `submission_id` and `actual_weight_kg` per item. Before the fix these responses exposed `home_user_id`, `collector_id`, `collector_lat`, `collector_lng`, `collection_ts` and `collection_photo_file_id`. Lot owners and the admin still receive the full handover evidence; the handover verification itself is unchanged. | Fix in `backend/app/modules/lots/service.py` (`_recycler_view`). Tests in `backend/tests/integration/test_lot_recycler_privacy.py` (4): the 2 recycler tests failed before the fix and passed after it; the 2 owner/admin tests pass. Full suite 412/412 (`privacy_fix_proposal/backend_pytest_after_fix_2026-10-12.txt`). |

## 2. Features partially implemented

| Feature | What works | What is missing / wrong |
|---|---|---|
| Price estimation in the app | Endpoint works; ±10 % band shown | Trained on **synthetic** data only. Only 3 of 37 detector labels (Battery, Laptop, Router) match a price-model material; mobile condition options (New, Like New, Good, Used, Damaged, Non-Working) do not match training values (Working, Partially-Working, Non-Working, Damaged); location sent is a place name or ward ID, while the model knows 11 city names. Unknown values are silently ignored by the encoder (see `evidence/price_model_input_probe_2026-10-12.txt`). |
| Calibrated price range | 90 % conformal interval computed in `price_ml(working)` (coverage 0.931 val / 0.869 test) | Not loaded by the backend; app uses a fixed ±10 % band. |
| Detector → lot category | Detection works | Mapping covers only battery and PCB; every other label becomes `e-waste-small-appliances`. |
| Detector performance | Correct results | `get_classifier()` constructs `YOLOClassifier()` (reloads weights) on every request. |
| Household privacy (residual items after the fix) | Fixed and verified; see Section 1 | Verified only against the in-memory test database (mongomock), not a running Atlas deployment. Recyclers still see each lot's ward, category, weights, deadline and the owning collector's internal ID; this is by design and contains no household data. The recycler web app's TypeScript type `LotItemDetail` still declares the removed fields (no runtime effect, since the page only counts items). |
| Translation | Backend IndicTrans2 endpoints (25 target languages), lazy model load | Tests use a fake model; real model never run in this review. Mobile app does not call the API (uses a static Kannada string table). |
| Idempotency coverage | 17 of 45 state-changing operations require an `Idempotency-Key` (verified from the generated OpenAPI schema) | **Partial / open:** the other 28 (e.g. registration, profile updates, approvals, complaint creation, notification reads, photo upload, price estimate, translation) take no key. Whether each is otherwise safe to repeat has not been reviewed. Full list in `evidence/idempotency_coverage_2026-10-12.txt`. |
| Recycler web / Admin web | Built (`dist/` present, 26 Sep 2026); Vitest 45/45 and 50/50 are reported in `PROJECT_STATUS.md` (Phase 10–12 sections) | **Unverified historical test evidence:** no run log exists and no run date is recorded for these counts (the file's header date, 2026-09-14, refers to the end of Phase 10, and the later sections repeating the counts are undated). Could not re-run on 12 Oct: system Node.js 20.19.5 vs jsdom 30/undici needing a newer Node. Code now has 48 and 42 test cases respectively. |
| RRR Centre role | Full workflow in backend (receive, classify, create/publish lots, accept bids) | Web app removed; demonstrable only through Swagger/API. |
| APK | Debug APK built 26 Sep 2026 (`mobile/build/app/outputs/flutter-apk/app-debug.apk`) | Not installed or run on a physical device; earlier release APK (Unverified — date not recorded) is no longer present; release build is debug-signed. |
| Concurrency guarantees | Logic and unique indexes in place | Tests use mongomock; true concurrent behaviour on Atlas not load-tested. |

## 3. Features not implemented or not verified

- **Smart Match** – no code found anywhere in the repository. Collector assignment is a ward-based pull queue.
- **Food rescue / NGO matching** – no code found.
- **RRR-centre web application** – removed (`docs/ARCHITECTURE.md` folder note).
- **Real payment gateway / real UPI payout** – intentionally mocked (`MOCK_PAYMENT_GATEWAY`).
- **Field evaluation of the detector** – 11 real photos were run through the model (`runs/detect/predict`), but there are no ground-truth labels, so accuracy on real household photos is unknown.
- **Real-market price accuracy** – no real price data exists in the repository.
- **User study / usability testing** – no evidence found.
- **Live MongoDB Atlas run** – the configuration points to Atlas, but no test in this review connected to it.

## 4. Missing evidence or information

| Needed for | What is missing | Where to use it |
|---|---|---|
| Report title page, paper author block | Your name, register/USN number, programme/semester, guide name, department, institution, email | Report title table; paper authors |
| "Progress since First Review" | What you presented at the First Review and the feedback received | Report table 1 (left column) |
| Smart Match / food rescue | Whether these were promised at the First Review, and why they were dropped | Report §1.4, viva QA5 |
| Version 1.0 | A concrete example (screenshot/report) of the 1.0 problems | Report §2.1 |
| YOLO training hardware | GPU model used for training (args.yaml only says `device: 0`) | Report Table 10, paper Table I |
| Real-photo observations | Your interpretation of `runs/detect/predict` outputs | Report §4.3.1, paper §VI-A |
| Screenshots | 9 screenshots listed in report §6.4 | Report Figs. 10–18 |
| Target dates | Dates for the pending-work plan | Report Table 17 |
| Acknowledgment | Guide/department acknowledgment text | Paper |

## 5. Manual corrections needed before submission

1. **Fill every yellow `[TO FILL: …]` field** (13 in the paper, 38 in the report; the viva has 3 bracketed reminders). Search for "TO FILL" in Word.
2. **Insert the nine screenshots** in report §6.4 (blur phone numbers/UPI IDs; never show the Atlas connection string).
3. **Re-run the detection evaluation yourself** (`evidence/yolo_test_eval_script.py`) so you can reproduce the test-split numbers live; they were produced during report preparation, not by an earlier project script.
4. **Re-run web tests on Node.js 22 LTS** (`npm test` in `recycler-web` and `admin-web`) and update Table 15 (report) and Table IV (paper) with the new date and counts. Until then, describe the 45/45 and 50/50 results only as unverified historical evidence.
4a. **Idempotency coverage (open):** review the 28 state-changing operations without an `Idempotency-Key` (report §6.2 issue 8, plan item 10).
5. **Privacy issue: resolved.** The fix and its 4 regression tests were applied with your approval on 12 Oct 2026 (full suite 412/412). The report, viva document, revised paper and this file now describe it as fixed; the original rough-draft paper is intentionally unchanged and still describes it as open. Be ready to explain the fix (viva QD10–QD11).
6. **If you fix the vocabulary mismatch** before the review, update report §6.2 and paper §VI-D accordingly.
7. **Confirm the paper title** with your guide; if changed, also change viva QF1.
8. **Check author order and column count** in the paper. The template was set to two author columns (student + guide); add or remove columns if needed.
9. **Update the TOC** in the report after editing (right-click → Update Field → Update entire table).
10. **Reference [1]** (Global E-waste Monitor 2024) has no ISBN; an ISBN appeared only in a secondary copy and could not be verified on an official ITU/UNITAR page, so it was left out on purpose.
11. Read the paper aloud once and change any sentence that does not sound like you. The wording is original, but your examiner will expect you to explain every sentence.

## 6. Notes on references and originality

- All 17 references were checked online on 12 Oct 2026 (publisher, Crossref, CVF, NeurIPS, JMLR, Project Euclid, Monash research portal, Ultralytics docs, Roboflow Universe). Details that could not be confirmed (ISBN of [1], exact start page of Sinnott 1984 – sources give 158 or 159) are noted above or chosen conservatively.
- Every reference in the paper is cited, and citations are numbered in order of first appearance (automated check).
- No text was copied from the template, papers or websites. The text was checked automatically for leftover template text and common filler phrases (none found).
- No plagiarism or AI-detection score is guaranteed; different checkers give different results. Run your university's checker and revise any flagged passage in your own words.

## 7. Integrity of source and inputs

- `research/rules.docx` (MD5 67296a2a…) and `research/Research Paper Template.docx` (MD5 25832046…) are unchanged.
- No file in `ewaste_ml` or `price_ml(working)` was modified.
- In the main project, the additions are `second_review_deliverables/` and, with your explicit approval on 12 Oct 2026, the privacy fix: `backend/app/modules/lots/service.py` (modified) and `backend/tests/integration/test_lot_recycler_privacy.py` (new). A copy of the original service file is at `privacy_fix_proposal/lots_service.py.before_fix`. No other source file was changed. Bytecode caches that tool runs created inside `backend/venv` were removed again.
- Tests and model evaluation were run on temporary copies outside the project folders.
