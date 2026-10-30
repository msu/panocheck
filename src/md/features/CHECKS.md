# Feature: Checks

The catalog mirrors Panorama's published per-format checklist; severities are provisional defaults until calibrated (see Testing). Panorama uses three tiers: severe (blocks access), major (needs a workaround), minor (best practice). Thresholds are parameters in the spec, not constants: Panorama admins can change the font-size threshold.

| Check ID | Formats | Default severity | Web auto-fix |
| --- | --- | --- | --- |
| `pdf.scanned` | PDF | Severe | No (detect) |
| `pdf.untagged` | PDF | Severe | No (detect) |
| `doc.encrypted` | PDF | Severe | No |
| `doc.malformed` | PDF, DOCX, PPTX, XLSX | Severe | No |
| `img.alt.missing` | All | Severe | Yes |
| `media.captions.missing` | HTML | Severe | No (Python only) |
| `media.captions.auto` | HTML | Major | No (Python only) |
| `media.private` | HTML | Major | No (Python only) |
| `doc.title.missing` | PDF, DOCX, PPTX, XLSX | Major | Yes |
| `doc.lang.missing` | PDF, DOCX, PPTX | Major | Yes |
| `doc.lang.wrong` | DOCX, PPTX | Major | Yes |
| `heading.none` | HTML, PDF, DOCX | Major | Guided |
| `heading.start` | PDF, DOCX | Major | Guided (not PDF) |
| `heading.nesting` | HTML, PDF, DOCX | Major | Guided (not PDF) |
| `heading.depth` | HTML, PDF, DOCX | Minor | Guided (not PDF) |
| `table.header.missing` | All | Major | Yes (not PDF) |
| `table.header.scope` | HTML | Minor | Yes |
| `table.caption.missing` | HTML, DOCX | Minor | Yes |
| `table.empty` | HTML | Minor | Yes (remove) |
| `contrast.insufficient` | All (PDF: Python only) | Major | Suggest color (not PDF) |
| `reading_order` | PDF, PPTX | Major | PPTX only |
| `slide.title.missing` | PPTX | Major | Yes |
| `link.text.generic` | All but PDF | Major | Yes |
| `link.adjacent.duplicate` | HTML | Minor | Yes (merge) |
| `link.iframe.title` | HTML | Minor | Yes |
| `font.too_small` | All | Minor | Yes (bump, not PDF) |
| `text.justified` | DOCX | Minor | Yes |
| `list.not_marked` | HTML, DOCX | Minor | Guided |
| `img.alt.too_long` | HTML | Minor | Yes |
| `img.alt.filename` | HTML | Major | Yes |
| `img.alt.meaningless` | HTML | Major | Yes |
| `img.decorative.interactive` | HTML | Major | Yes |
| `img.not_inline` | DOCX | Minor | No (manual) |
| `heading.too_long` | HTML | Minor | Yes |
| `content.too_long` | HTML | Minor | No |
| `target.too_small` | HTML | Minor | No |
| `xlsx.a1.empty` | XLSX | Minor | Yes |

Parameter defaults: font minimum 9 pt; alt and heading length 120 characters; page length 3,000 words; contrast 4.5:1 normal text and 3:1 large text (WCAG AA, assumed; Panorama does not publish its ratio).

Static limits: HTML contrast and target size read inline styles only. PDF contrast assumes a white page. `doc.lang.wrong` uses the stopword table in the spec, so both engines give the same result.
