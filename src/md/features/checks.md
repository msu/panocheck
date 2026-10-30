# Checks

The catalog is in `src/spec/checks.yaml`. It mirrors the published Panorama checklist.

## Severity

Panorama uses three tiers. Severe blocks access. Major needs a workaround. Minor is best practice. The severities in the spec are provisional until calibration.

## Decisions

- Thresholds are parameters because Panorama admins can change the font-size threshold.
- The 4.5:1 and 3:1 contrast ratios are WCAG AA. This is an assumption, because Panorama does not publish its ratio.
- `doc.lang.wrong` uses a stopword table in the spec, not a language library. Two different libraries cannot give the same result in both engines. The cost is support for only four languages.
- The score is separate from findings, because its weights are a guess.

## Static Limits

- HTML contrast and target size read inline styles only. The tool does not render the page.
- PDF contrast runs only in Python, because pdf.js text content has no color. It assumes a white page.
- Caption checks run only in Python, because they need network access.
