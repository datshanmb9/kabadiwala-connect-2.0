# Paper Revision Log

- **Input (unchanged):** `Kabadiwala_Connect_Research_Paper_Rough_Draft.docx` (MD5 `6b5e4346ad9b502a87f7726588d71ee3`, the same before and after this revision)
- **Output:** `Kabadiwala_Connect_Research_Paper_Revised.docx` (6 pages, 18 references, 4 figures, 5 tables)
- **Date:** 12 October 2026

The revised file was built on the rough draft itself: its title section, author section, IEEE styles, column layout, footer and automatic heading, figure, table and reference numbering were kept, and only the body text was replaced. Evidence files are in `evidence/` and `privacy_fix_proposal/`.

## A. Factual corrections

| # | Rough-draft statement | Problem found | Revised statement | Evidence |
|---|---|---|---|---|
| A1 | "104 images that appeared in more than one split were removed …, leaving 7,163 images" | Arithmetic did not fit: the original export had 7,210 images, so only 47 files were removed. A hash check also showed duplicates remain. | The project notes report 104 cross-split duplicates. Our MD5 check: no test image identical to a training image, 5 test images identical to validation images, 83 duplicate files overall (71 within train). Near-duplicates not checked. | `evidence/dataset_audit_2026-10-12.txt`, `ewaste_ml/README.md`, `results/dataset_inspection_report.json` |
| A2 | "mice are small in most photographs" | False: the median mouse box is 34.4% of the image, above the 29.2% median of all boxes | Lamps (10.6%, ratio 2.0) and boilers (16.4%) are small; mouse low recall is not explained by size, and its cause is not studied | `evidence/dataset_audit_2026-10-12.txt` |
| A3 | "Every state-changing request must carry an idempotency key" | Only 17 of 45 state-changing operations require it | The 17 workflow operations require it; registration, profile updates, approvals and notification reads do not | `evidence/idempotency_coverage_2026-10-12.txt` |
| A4 | "Every attempt, automatic or manual, is stored" | Detections at photo upload (`/ai/classify-photo`) are not stored | Upload-time detections are returned but not stored; RRR-side AI attempts and manual decisions are stored append-only | `classification/service.py` (`classify_photo` vs `classify_with_ai`) |
| A5 | "no endpoint writes a status field directly" | Too broad: approval and reward statuses are written directly | Item, lot, bid and complaint state changes use allow-listed transitions; approval and reward statuses are set directly | `recyclers/service.py`, `rrr_centres/service.py`, `rewards/service.py` |
| A6 | "Linear regression had more than twice the error of the tree ensembles" | False for Gradient Boosting (1.7×) | 2.4× the selected model, 1.7× the weakest ensemble; speculation about "interactions" removed | `price_ml(working)/outputs/model_comparison.csv` |
| A7 | "inference took about 59 ms per image" | Measurement conditions not stated | 2.2 / 59.1 / 0.8 ms (pre-processing / model / post-processing) per image, batch 16, laptop CPU; excludes upload and the per-request model load; end-to-end time not measured | `evidence/yolo_test_split_eval_2026-10-12.txt` |
| A8 | Test results presented without date or tool version | The held-out evaluation was run during document preparation | States 12 Oct 2026, Ultralytics 8.4.157, CPU, default validation settings | same |
| A9 | "AP@0.5 ranged from 0.64 to 0.99" | Rounding hid the exact values | 0.637 to 0.995, with 849 test boxes | `evidence/yolo_test_split_metrics_2026-10-12.json` |
| A10 | Training table: "single GPU, about 58 min [TO FILL: GPU model]"; no optimizer or software version | Incomplete | Optimizer "auto"; mosaic switched off in the last 10 epochs (`close_mosaic: 10`); seed 0; Ultralytics 8.3.40 and PyTorch 2.11 (CUDA); RTX 3050 Laptop GPU (4 GB); 57.7 min | `runs/detect/ewaste_yolov8n5/args.yaml`, `results.csv`, `evidence/training_hardware_2026-10-12.txt` |
| A11 | YOLOv8n architecture not described | Requested; previously only "3.01 M parameters" | C2f backbone with SPPF, upsample/concatenate neck, anchor-free head at strides 8/16/32; 3,012,863 parameters; 8.1 GFLOPs | installed `ultralytics/cfg/models/v8/yolov8.yaml`; evaluation log model summary |
| A12 | Web tests "14 Sep 2026" | That date was not verifiable | "Recorded by 15 Sep 2026" (`PROJECT_STATUS.md` last modified 15 Sep), not re-run because of Node.js 20; current code has 48 and 42 test cases | `PROJECT_STATUS.md`, `evidence/web_vitest_attempt_2026-10-12.txt` |
| A13 | "The door-to-door kabadiwala … is already the channel most households use" | 45% is not "most" | "a common channel"; 45% preference and >90% informal share, both cited to [4] | Sengupta et al. 2023 abstract (Monash research portal) |
| A14 | Voskergian & Ishaq "inside an Internet-of-Things smart bin" | "Smart bin" not supported by the abstract | "within an Internet-of-Things management system"; their best result of 72% mAP@50 (YOLOv8s) added, with a note that it is not comparable | Semantic Scholar abstract |
| A15 | Kumar et al. "note that developing countries depend heavily on informal processing" | The abstract could not be accessed to confirm this | Restricted to what the title and scope support | Crossref/OpenAlex metadata |
| A16 | HistGradientBoosting described via the 2011 scikit-learn paper | That paper predates the estimator (added in v0.21) | New reference [14]: scikit-learn User Guide (inspired by LightGBM; features binned to at most 256 bins) | scikit-learn documentation |
| A17 | Fig. 1 showed a NEEDS_REVIEW state at the photo step | No submission or state exists at that step | Figure redrawn: "flagged: user confirms category"; note that auto-listing needs a category | `classification/service.py::classify_photo`, `ewaste/service.py::auto_progress_to_listed_lot` |
| A18 | "At month end the administrator computes rewards" | Implies automatic scheduling | "the administrator triggers reward computation for a calendar month" | `rewards/router.py` (`POST /admin/rewards/compute`) |
| A19 | Bid deadline and cancel rules not fully described | Incomplete | Bids after the 7-day deadline are rejected; cancellation is allowed only within 24 h and before logistics/payment | `bids/service.py` |
| A20 | Handover timestamp described as evidence | The timestamp is device-supplied | Coordinates and timestamp come from the device (server clock used only if none is sent), so this is verification, not proof | `ewaste/service.py::handover` |
| A21 | Prediction interval vs app band not clearly separated | Requested distinction | The ±10% band is a configuration value, not a statistical interval; the 90% interval covered 93.1% (val) and 86.9% (final test, below target) and is not used by the app | `config.py`, `outputs/calibration_evaluation_report.csv` |
| A22 | Translation mentioned only in the literature review | The actual status was missing | Backend endpoints lazily load IndicTrans2 (25 target languages); mobile uses a static Kannada table; model replaced by a stub in tests; quality not measured | `translation/service.py`, `mobile/lib/features/translation/*` |
| A23 | Price features described loosely | Needed for the integration findings | 20 materials, 4 conditions (listed), 11 cities, dates 1 Jan 2024 – 1 Sep 2026, 3,593/1,228/1,179 rows | dataset CSV, `train.py` |
| A24 | Integration probe numbers without inputs | Not reproducible as written | Inputs stated (1 item, 2 kg, Bengaluru); the city-name mismatch added | `evidence/price_model_input_probe_2026-10-12.txt` |

## B. Privacy issue (Phase 3)

| Step | Result |
|---|---|
| Exposure confirmed | `GET /api/v1/lots/listed` and `GET /api/v1/lots/{lot_id}` returned `item_details` with `home_user_id`, `collector_id`, `collector_lat`, `collector_lng`, `collection_ts` and `collection_photo_file_id` to any approved recycler |
| Fix (approved by the author on 12 Oct 2026) | `backend/app/modules/lots/service.py`: an allow-list `_recycler_view()` keeps only `submission_id` and `actual_weight_kg`; applied to the two recycler responses. Owners and the admin are unchanged. |
| Tests added | `backend/tests/integration/test_lot_recycler_privacy.py` (4 tests): 2 failed before the fix and passed after it |
| Regression | Full backend suite on the patched code: 412 passed, 0 failed |
| Rollback copy | `privacy_fix_proposal/lots_service.py.before_fix` |
| Paper | New Section V-D, requirement (vi) in the Problem Statement, the abstract, Table V and the conclusion |
| Not changed | `recycler-web/src/types/domain.ts` still declares the removed fields as types. This has no runtime effect, because the UI only counts the items; tidy it up if you edit the web app. |

## C. Writing changes

- The contribution list no longer praises itself ("honest list of …" removed) and now states what was evaluated.
- The research gap is limited explicitly to the works reviewed: "We do not claim that no such system exists elsewhere."
- Previous research, our implementation, measured findings and future work are kept in separate paragraphs and subsections (VI-A to VI-E).
- Each limitation is stated where its result appears: synthetic price data, untested web suites, device-supplied GPS, mock tests for the AI and translation modules.
- RRR is now defined at first use in the Problem Statement.
- The abstract sentence that Word's grammar checker flagged was rewritten.

## D. Layout and formatting

- The rough-draft template structure was kept (title section, 2-column author section, 2-column body).
- Table text is left-aligned, because the justified `table copy` style created wide gaps.
- Rows are kept together so tables do not split across pages.
- A continuous section break after the references balances the two columns on the last page.
- Metadata: the "last modified by" personal name inserted by Word was cleared.
