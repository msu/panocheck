# panocheck

`panocheck` is a document accessibility checker and fixer for HTML, DOCX, PPTX, XLSX and PDF.

If is available as

- A web tool: https://msu.github.io/panocheck/
- A python tool for command line/library work: `src/python/panocheck.py`


## Web

The web tool is online and doesn't require any installation.  Simply navigate to https://msu.github.io/panocheck/ and begin using it.

It keeps all files client side and thus is FERPA compliant

## Python

The python library can be used as a stand-alone command line tool (e.g. for agents) or as a library in a larger workflow.

To install it:

```
pip install "git+https://github.com/msu/panocheck.git#subdirectory=src/python"
```

To run it:

```
panocheck scan syllabus.docx
```

To vendor it, copy `src/python/panocheck.py` into your project.


## Project Layout

```
src/md/       intent and design decisions, start at src/md/README.md
src/spec/     check IDs, severities, thresholds, messages
src/python/   single-file library and CLI, plus tests
src/web/      plain HTML and JavaScript for GitHub Pages (src/web/site)
```

## Developing

This project follows the [/src/md](https://srcmd.org) standard.

To run the tests:

```
cd src/python && uv venv && uv pip install -e '.[dev]' && .venv/bin/pytest
cd src/web && npm ci && npm test && npx playwright test
cd src/web && npm run serve    # http://localhost:5173/
```

* After you edit `src/spec/checks.yaml`, run `src/tools/sync_spec.py`.
* After you update a web library, run `npm run vendor` in `src/web`.
* After you edit `src/tools/gen_fixtures.py`, run it again to rebuild `fixtures/`.

## Panocheck Limits

- The score is an estimate with provisional weights.
- HTML contrast and target size use inline styles only. The tool does not render the page.
- Contrast for PDF runs in Python only and assumes a white page.
- Language detection uses a stopword table for English, Spanish, French and German.
- Caption checks run in Python only.
- Python HTML fixes serialize the document again. Web HTML fixes keep all other bytes.
- Web PDF title fixes write the Info dictionary only. Python also writes XMP.
- The tool detects untagged and scanned PDFs but does not repair them.

## License

[0BSD](LICENSE)
