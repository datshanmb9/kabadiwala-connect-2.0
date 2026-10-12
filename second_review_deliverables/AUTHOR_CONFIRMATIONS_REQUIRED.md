# Author Confirmations Required

File: `Kabadiwala_Connect_Research_Paper_Revised.docx`

These items cannot be verified from the repository. They are marked in the paper with yellow `[TO FILL: …]` text (search for "TO FILL" in Word). Nothing below has been guessed.

## 1. Must be supplied before submission

| # | Item | Where in the paper | What to provide |
|---|---|---|---|
| 1 | Student author name | Author block, left column | Full name as registered |
| 2 | Student department | Author block, left column | e.g. Department of Computer Applications (confirm exact name) |
| 3 | Student institution | Author block, left column | Full institution name |
| 4 | Student city | Author block, left column | City, India |
| 5 | Student email or ORCID | Author block, left column | Institutional email preferred |
| 6 | Project guide name and designation | Author block, right column | Full name |
| 7 | Guide department | Author block, right column | — |
| 8 | Guide institution | Author block, right column | — |
| 9 | Guide city | Author block, right column | — |
| 10 | Guide email or ORCID | Author block, right column | Ask the guide for permission to list it |
| 11 | Acknowledgment | "Acknowledgment" section | Whom to thank (guide, department, institution), or delete the section |
| 12 | Observation on the 11 real photographs | Section VI-A, end of first results paragraph | One sentence on what the detector got right or wrong on the photos in `ewaste_ml/runs/detect/test_predictions/results/`, or delete the sentence. Only the count "boxes on 8 of 11" was verified. |

If the paper has a single author (no guide), change the author section from two columns to one (Layout → Columns → One, with the cursor in the author block) and delete the right-hand block.

## 2. Filled from evidence — please confirm

| Item | Value used | Evidence | Why confirmation is needed |
|---|---|---|---|
| Training GPU | NVIDIA GeForce RTX 3050 Laptop GPU (4 GB) | The training run's event file was written on host `WIN-J3URQFPVSP3`, the same host name as this machine, and `nvidia-smi` on this machine reports this GPU (`evidence/training_hardware_2026-10-12.txt`) | Assumes the GPU did not change between training and today |
| Version 1.0 faults | Three faults listed in the Introduction | `docs/ARCHITECTURE.md` (Section 1 and Section 17) | This is the project's own design note, not an external source; be ready to explain it in the viva |

## 3. Not used in the paper (not available)

- **First Review status and supervisor feedback:** a research paper does not normally include these, so no marker was added. They belong in your review presentation.
- **Personal name in the file metadata:** Word had recorded a user name in the document's "last modified by" property during template conversion. It was cleared and was not used as the author name.

## 4. Decisions you may want to revisit

- **Title:** unchanged from the rough draft. Confirm it with your guide.
- **Length:** the revised paper is 6 pages (the rough draft was 5), mainly because of the role table, dataset audit, privacy subsection and more precise test reporting. If your department sets a page limit, the role table (Table I) and Section IV-E (translation) are the easiest to shorten.
