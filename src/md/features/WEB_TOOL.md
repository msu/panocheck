# Feature: Web Tool

A static single-page app: Vite + TypeScript, Preact for the UI, all parsing in a Web Worker so large PDFs do not freeze the page. A GitHub Actions workflow deploys it to Pages on every tag or on a manual run.

**User flow**

1. Drop or pick a file (HTML, DOCX, PPTX, XLSX, PDF). Format is sniffed from magic bytes.
2. Worker parses and runs checks; findings appear grouped by severity with counts and an estimated score.
3. Selecting a finding highlights it in the preview and opens a fix panel: a text field for alt text, a language picker, a "first row is header" toggle, a heading-level dropdown, a suggested passing color.
4. Applying a fix edits the in-memory document and re-runs all checks.
5. Download writes the edited bytes as `<name>-accessible.<ext>`, with a JSON report alongside on request.

**Libraries**

| Need | Library |
| --- | --- |
| OOXML zip read/write | fflate (gives the zip size cap) |
| XML | `@xmldom/xmldom` (workers have no `DOMParser`) |
| HTML parse | `parse5` (source offsets for byte-preserving fixes) |
| PDF read | pdf-lib (catalog and struct tree), pdf.js (`getTextContent`, render to canvas) |
| PDF write | pdf-lib (catalog `/Lang`, Info and XMP title, `/Alt` on Figure elements) |
| DOCX preview | `docx-preview` |

**Preview by format**

- HTML: sandboxed iframe, scripts disabled.
- DOCX: `docx-preview` render, with no finding anchors.
- PDF: pdf.js page canvas. A page-level finding opens its page.
- PPTX and XLSX: an outline view (slides, shapes, sheets, cells) instead of a visual render; faithful PPTX rendering in the browser is not worth v1.

**Privacy and hardening**

- CSP `connect-src 'none'`: the app cannot send data anywhere. State this on the landing page.
- Parse untrusted XML with external entities off; cap zip expansion size to block zip bombs.
- The tool itself passes `axe-core` in CI; an inaccessible accessibility checker is not shippable.
