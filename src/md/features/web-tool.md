# Web Tool

## Privacy

The CSP has `connect-src 'none'`, so the page cannot send a file anywhere. The landing page states this. HTML previews use an iframe with an empty `sandbox`, so document scripts do not run.

## Parser Choices

- Workers have no `DOMParser`, so XML uses `@xmldom/xmldom` and HTML uses `parse5`.
- `parse5` gives source offsets. These offsets let HTML fixes keep all other bytes.
- `fflate` replaces JSZip, because its `originalSize` value gives a zip bomb check before decompression.
- `pdf-lib` reads the catalog and struct tree. pdf.js reads text and draws pages.

## Subtleties

- pdf.js posts its own messages on the app worker. The RPC layer tags its messages and ignores all others.
- The app must render a fix panel with its initial value in `useState`. An effect that sets the value can erase fast input.

## Preview Limits

- PPTX and XLSX show an outline. A faithful browser render is not worth the cost in v1.
- DOCX previews have no finding anchors.
- PDF previews open the page of a page-level finding, with no overlays.
