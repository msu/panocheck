# panocheck

panocheck finds and fixes accessibility issues in HTML, DOCX, PPTX, XLSX and PDF files. Its checks follow the published checks of YuJa Panorama. The name and branding do not use the vendor name.

## Goals

- Reproduce the published Panorama checks. ODF and legacy formats go through conversion in Python.
- Give stable findings with a locator that is precise enough to jump to the problem.
- Keep every byte of a file in the browser, so that student data and FERPA stay out of scope for the web tool.
- Give the same findings from both engines for the same input.

## Non-Goals

- An exact match of the Panorama score. Its weights are not published, so the score is an estimate.
- Tagging, OCR and reading-order repair for PDF. The tool detects these issues only.
- Caption checks and legacy formats in the web tool.

## Structure

One check spec drives two engines. `src/spec/checks.yaml` holds the IDs, severities, thresholds and messages, and neither engine hard-codes them.

- `src/python/panocheck.py`: the reference engine, for batch and Canvas scans
- `src/web/`: a static app that checks one file, guides fixes and returns a corrected copy
- `fixtures/`: generated documents and `expected.json`, which both engines must match

## Subtleties

- Panorama rules can change without notice. Findings can differ from what instructors see, so calibration must run again each term.
- The `pdf-lib` rewrite can damage forms, signatures and incremental history. The web tool warns before download.
- The tool cannot judge whether alternative text is meaningful. It uses heuristics only: a word list, a file name pattern and a length limit.
- These risks have no mitigation yet: false contrast findings on gradients and on text over images, and large PDFs in the browser.

## Rules

- Change `src/md` first, then derive code and tests from it.
- Tests are the executable specification for the intent. Keep them in `src/python/tests` and `src/web`.
- Keep plans and TODOs in `tmp/`, which git ignores.
- Use STE (ASD-STE100 Simplified Technical English) for all files in `src/md`.

## File Index

- [features/checks.md](features/checks.md): severity model and check decisions
- [features/web-tool.md](features/web-tool.md): browser privacy, parser choices and preview limits
- [features/remediation.md](features/remediation.md): how fixes keep the original file
- [data/finding.md](data/finding.md): finding shape and locator design
- [api/python.md](api/python.md): why the Python engine is one file
- [infrastructure/testing.md](infrastructure/testing.md): conformance and calibration intent
- [infrastructure/pages.md](infrastructure/pages.md): GitHub Pages constraints
