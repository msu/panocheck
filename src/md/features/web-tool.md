# Web Tool

## Branding

The header shows the logo (`public/panocheck.svg`) and the name Panocheck. It does not name the university or the school. The MSU blue and gold colors stay. The site hosts its own copies of the Outfit (title) and Inter (body) fonts, because the CSP blocks font services and a font request would leave the page.

## Plain HTML and JavaScript

The site has no framework, no TypeScript and no build. `src/web/site` is what the server sends.

- `npm run vendor` writes the third-party libraries to `site/vendor` as ES modules. These files are checked in, because the browser cannot read `node_modules`.
- `src/tools/sync_spec.py` writes the spec to `site/engine/spec.js`, because a browser cannot import YAML.
- npm is for tests and for the vendor step only.

## Privacy

The CSP in `index.html` has `connect-src 'none'`, so the page cannot send a file anywhere. The landing page states this. HTML previews use an iframe with an empty `sandbox`, so document scripts do not run.

## Many Files

- The user can choose or drop many files. The app scans them one at a time in the worker.
- One file opens in the workspace at once. Many files give a summary table, and a click on a row opens that file.
- A file keeps its bytes only while it is open or has fixes. The other files keep their `File` handle, and the app reads them again on demand. This keeps memory low for many large PDFs.
- "Download fixed copies (zip)" holds only the files with fixes. "Download all reports" gives one JSON list in the shape that `panocheck score` reads.
- Each fix needs a value from the user, so there is no fix for all files at once.

## Parser Choices

- Workers have no `DOMParser`, so XML uses `@xmldom/xmldom` and HTML uses `parse5`.
- `parse5` gives source offsets. These offsets let HTML fixes keep all other bytes.
- `fflate` replaces JSZip, because its `originalSize` value gives a zip bomb check before decompression.
- `pdf-lib` reads the catalog and struct tree. pdf.js reads text and draws pages.

## Subtleties

- pdf.js posts its own messages on the app worker. The RPC layer tags its messages and ignores all others.
- `app.js` draws the findings list again on each change, so it must restore the focus by finding key.
- CSS `display` rules override the `hidden` attribute. `style.css` has a rule that prevents this.

## Preview Limits

- PPTX and XLSX show an outline. A faithful browser render is not worth the cost in v1.
- DOCX previews have no finding anchors.
- PDF previews open the page of a page-level finding, with no overlays.
