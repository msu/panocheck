# Testing

## Conformance

A check is done when Python and the web engine give the same findings for every fixture.

- `src/tools/gen_fixtures.py` builds the fixtures and states the expected findings by hand. The engines do not generate the expected findings.
- Each check has at least one passing and one failing fixture. A test enforces this.
- Conformance compares check ID, severity and locator.
- Fixtures are minimal, so they do not prove that real files work. `src/tools/lo_smoke.py` fixes files from real writers and opens them in LibreOffice.

## Fix Round Trip

After each fix, a rescan must show that the finding is gone and that no new finding appears.

## Calibration

The fixtures cannot show whether the tool agrees with Panorama. For this, use 20 to 50 anonymized course files, kept out of the public repo. Record the Panorama score and issues for each file, compare the findings, and fit the severity weights. Report the mean absolute error with each release.

## The Tool Itself

An inaccessible accessibility checker is not shippable. CI runs axe and a keyboard-only flow on the app.
