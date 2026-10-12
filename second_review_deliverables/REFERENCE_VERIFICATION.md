# Reference Verification Log

Paper: `Kabadiwala_Connect_Research_Paper_Revised.docx`. Checks were run on 12 October 2026. Numbering follows the revised paper, where references are numbered in order of first citation.

Status key:

- **Verified** – bibliographic details confirmed from the publisher, an indexing service or the source itself, and the cited claim confirmed from the abstract or full text.
- **Verified (metadata)** – bibliographic details confirmed, but the full text or abstract was not accessible. The claim was kept narrow.
- **Manual check** – details or support could not be fully confirmed; please check before final submission.

| # | Reference | Claim it supports in the paper | Status | How it was checked |
|---|---|---|---|---|
| [1] | Baldé et al., *The Global E-waste Monitor 2024*, ITU/UNITAR | 62 Mt in 2022; generation outpacing documented recycling | Verified | Author list from the report PDF (ewastemonitor.info / ITU) and the Stichting OPEN record; figures from the UNITAR press release. The ITU copy is "Edition 2, Nov 2024". No ISBN was given because none was found on an official page. |
| [2] | Wath, Dutt, Chakrabarti, *Environ. Monit. Assess.* 172:249–262 (2011) | Informal/unorganised sector handles most collection and recycling; open burning, acid dumping | Verified | Semantic Scholar metadata; full text (NEERI open-access PDF) contains "unorganized or informal sectors" and "open burning … dumping of acids" |
| [3] | MoEFCC, E-Waste (Management) Rules, 2022, G.S.R. 801(E), 2 Nov 2022 | Replaced the 2016 rules; producer recycling targets met through recyclers' certificates | Verified (secondary copies) | Gazette copy hosted by MP Pollution Control Board, CPCB SOP and the PIB parliamentary answer agree. **Manual check:** the official e-Gazette page was not accessed. |
| [4] | Sengupta et al., *Minerals Engineering* 200, 108154 (2023), Part II | ~45% prefer kabadiwalas; informal sector >90%; GPS route tracking; 20–30 km/day | Verified | Crossref metadata; abstract on the Monash research portal |
| [5] | Sengupta et al., *Minerals Engineering* 184, 107661 (2022), Part I | Proposes a modified EPR model including informal collectors | Verified (metadata) + **manual check** | Crossref/OpenAlex metadata confirmed. The "modified EPR model" description comes from secondary summaries; the abstract (ScienceDirect) could not be opened. |
| [6] | Kumar, Holuszko, Espinosa, *Resour. Conserv. Recycl.* 122:32–42 (2017) | Reviews generation, collection, legislation and recycling | Verified (metadata) | Crossref and OpenAlex. The abstract was not accessible, so the claim was reduced to the paper's stated scope (its title). |
| [7] | Redmon et al., CVPR 2016, pp. 779–788 | YOLO as single-pass regression | Verified | CVF Open Access page |
| [8] | Jocher, Chaurasia, Qiu, "Ultralytics YOLOv8", v8.0.0, 2023 | Five sizes n–x; anchor-free head; architecture description | Verified | Ultralytics docs (recommended citation; no formal paper exists, DOI pending). The architecture details were also read from the installed `yolov8.yaml`. Note: training used package version 8.3.40 (stated in Table II). |
| [9] | Lin et al., "Microsoft COCO", ECCV 2014, LNCS 8693, pp. 740–755 | COCO pre-training; mAP@0.5 and 0.5:0.95 definitions | Verified | Springer/CMU records |
| [10] | Majchrowska et al., *Waste Management* 138:274–284 (2022) | EfficientDet-D2 + EfficientNet-B2 litter detection and classification | Verified | Semantic Scholar abstract (indexed under the arXiv title "Waste detection in Pomerania…"); journal title and pages confirmed via ResearchGate and citing records |
| [11] | Voskergian & Ishaq, *J. Smart Cities and Society* 2(2):77–98 (2023) | Compared YOLOv5s / v7-tiny / v8s within an IoT system; YOLOv8s best at 72% mAP@50 | Verified | Crossref metadata; Semantic Scholar abstract |
| [12] | Friedman, *Ann. Statist.* 29(5):1189–1232 (2001) | Gradient boosting as an additive model of trees | Verified | Project Euclid / JSTOR records |
| [13] | Ke et al., "LightGBM", NeurIPS 2017, pp. 3146–3154 | Histogram-based split finding, gradient-based sampling, feature bundling | Verified (metadata) + **manual check** | NeurIPS proceedings record. Sampling and bundling (GOSS, EFB) are in the abstract; histogram-based split finding is described in the paper body, which was not opened in this session. Some indexes list pages as 3149–3157; NeurIPS BibTeX gives 3146–3154. |
| [14] | scikit-learn developers, User Guide, "Ensembles …", histogram-based gradient boosting section | HGB inspired by LightGBM; bins features into ≤256 bins | Verified | Read on scikit-learn.org on 12 Oct 2026 (the page says "typically 256 bins"; `max_bins` defaults to 255 plus one bin for missing values). **Note:** the page title used in the reference was taken from the documentation section name; confirm it matches the version you cite. |
| [15] | Pedregosa et al., *JMLR* 12:2825–2830 (2011) | scikit-learn library used for preprocessing and comparison | Verified | scikit-learn citation page; Bibsonomy record |
| [16] | Gala et al., IndicTrans2, *TMLR* (Dec. 2023), arXiv:2305.16307 | Open translation models for 22 scheduled languages | Verified | arXiv record; OpenReview/TMLR listing |
| [17] | Roboflow Universe, "Balanced E-Waste Dataset", v3, CC BY 4.0 | Dataset source and licence | Verified (project file) + **manual check** | Workspace, project, version, licence and URL come from `dataset/data.yaml` and `README.roboflow.txt` in the project. The v3 web page returned HTTP 403 (the v2 page was reachable). Open the URL once in a browser. |
| [18] | Sinnott, "Virtues of the haversine", *Sky and Telescope* 68(2), 1984 | Haversine distance formula | **Manual check** | Exists according to multiple catalogues, but the start page differs between sources (p. 158 vs p. 159). The paper uses p. 159 (Springer citation). The original was not accessible. |

## Consistency checks (automated)

- 18 references are listed and all 18 are cited; there are no citations without an entry.
- Numbering follows the order of first appearance.
- The abstract contains no citations.
- No reference from the rough draft was removed. One reference was added ([14], scikit-learn User Guide), and [1] gained its URL.

## Not done

- No external plagiarism or similarity checker was run, and no similarity score is claimed. Use your university's approved checker.
- References were checked for existence and for support of the specific sentence that cites them, not for every statement each source makes.
