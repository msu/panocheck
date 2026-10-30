# Infrastructure: Testing

One fixture corpus drives both engines; a check is done when Python and JS produce identical findings for every fixture.

- **Fixtures:** `fixtures/<format>/<check_id>/{pass,fail}-*.ext` plus `expected.json`. Each check gets at least one minimal passing and one failing file, built by script where possible so they are reproducible.
- **Conformance:** pytest and Vitest both load `expected.json` and compare normalized findings (check ID, severity, locator). Vitest skips checks that the spec marks as Python only.
- **Fix round-trip:** apply each fix, rescan, assert the finding is gone and no new one appears. CI also fixes files from real writers and opens the output in headless LibreOffice (`src/tools/lo_smoke.py`).
- **Real-world set:** 20 to 50 anonymized course files from your own Canvas courses, kept out of the public repo.
- **Calibration against Panorama:** for each real-world file, record Panorama's score and issue list (manually, or through its REST API if ECAT grants a key). Diff findings to find missed or extra checks, then fit severity weights so the estimated score tracks Panorama's. Report the mean absolute error with each release.
- **The tool's own accessibility:** `axe-core` and keyboard-only Playwright tests on the web app in CI.
