# Checks

The catalog is in `src/spec/checks.yaml`. It mirrors the published Panorama checklist.

## Severity

Panorama uses three tiers. Severe blocks access. Major needs a workaround. Minor is best practice. The severities in the spec are provisional until calibration.

## Decisions

- Thresholds are parameters because Panorama admins can change the font-size threshold.
- The 4.5:1 and 3:1 contrast ratios are WCAG AA. This is an assumption, because Panorama does not publish its ratio.
- `doc.lang.wrong` uses a stopword table in the spec, not a language library. Two different libraries cannot give the same result in both engines. The cost is support for only four languages.
- The score is separate from findings, because its weights are a guess.

## PDF Tags

- `reading_order` compares marked content that shows text and has one reference. Chrome tagged PDFs number background boxes in paint order, and they reference a page-wide wrapper MCID from several tags. Neither is a reorder. A decrease is only a heuristic, because MCID numbers follow paint order and the struct tree defines the reading order. It has not been compared with a screen reader or with Panorama.
- `tag.empty` covers the text tags P, H, H1 to H6, LI, Lbl and LBody. Chrome makes such tags for boxes that draw only a background. A tag that holds a figure is not empty. Text inside a form XObject counts as text. The fix retags as Div, because the removal of a tag breaks the parent tree.
- `doc.title.hidden` runs only when the title exists, so that one missing title gives one finding.

## Static Limits

- HTML contrast and target size read inline styles only. The tool does not render the page.
- PDF contrast runs only in Python, because pdf.js text content has no color. A PDF does not record the background behind text, so the check renders the page and takes the most common color in the text box. A gradient or a photo can give a wrong result.
- Caption checks run only in Python, because they need network access.
