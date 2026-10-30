# panocheck

Document accessibility checker and fixer for HTML, DOCX, PPTX, XLSX and PDF.

- Web tool: https://msu.github.io/panocheck/ . Your file stays in your browser.
- Python: one file, `src/python/panocheck.py`. Copy it into your project to vendor it.

## Layout

```
src/md/       specification and design, start at src/md/README.md
src/spec/     check IDs, severities, thresholds, messages
src/python/   single-file library and CLI, plus tests
src/web/      Vite + Preact app for GitHub Pages
src/tools/    fixture generator, spec sync
fixtures/     generated test documents and expected.json
```

Both engines must produce the same findings for each fixture.

## Python

```
pip install ./src/python
panocheck scan syllabus.docx --format json --fail-on major
panocheck fix syllabus.docx --apply fixes.json
panocheck canvas 12345 --token-env CANVAS_TOKEN
```

```python
from panocheck import scan, Params

report = scan("syllabus.docx", params=Params(min_font_pt=9))
for f in report.findings:
    print(f.check_id, f.severity, f.locator, f.message)
```

To vendor, copy `panocheck.py` and install the packages for your formats:
`lxml` (OOXML), `html5lib` (HTML), `pikepdf` and `pymupdf` (PDF). Optional packages are
`canvasapi` and `yt-dlp`. The file imports each package only when needed.

Legacy and ODF files need LibreOffice on the path.

## Develop

Change `src/md` first, then derive code and tests from it.

```
cd src/python && uv venv && uv pip install -e '.[dev]' && .venv/bin/pytest
cd src/web && npm ci && npm test && npm run build && npx playwright test
```

After you edit `src/spec/checks.yaml`, run `src/tools/sync_spec.py`.
After you edit `src/tools/gen_fixtures.py`, run it again to rebuild `fixtures/`.

## Limits

- The score is an estimate with provisional weights.
- HTML contrast and target size use inline styles only. The tool does not render the page.
- Contrast for PDF runs in Python only and assumes a white page.
- Language detection uses a stopword table for English, Spanish, French and German.
- Caption checks run in Python only.
- Python HTML fixes serialize the document again. Web HTML fixes keep all other bytes.
- Web PDF title fixes write the Info dictionary only. Python also writes XMP.
- The tool detects untagged and scanned PDFs but does not repair them.

## License

0BSD
