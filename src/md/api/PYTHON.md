# API: Python

A single file, `src/python/panocheck.py`, so that a project can vendor it by copy. It embeds the spec. It imports each heavy dependency only when needed. Target Python 3.11+, packaged with `pyproject.toml` (hatchling).

## Public API

```python
from panocheck import scan, fix, Params

report = scan("syllabus.docx", params=Params(min_font_pt=9))
for f in report.findings:
    print(f.check_id, f.severity, f.locator, f.message)
report.to_sarif("out.sarif")
```

## CLI

- `panocheck scan FILE... [--format text|json|sarif] [--min-severity major] [--min-font 9] [--fail-on major] [--probe-media]`
- `panocheck canvas COURSE_ID [--token-env CANVAS_TOKEN] [--base-url https://montana.instructure.com]`: crawls pages, assignments, discussions, quizzes and files; reports per item.
- `panocheck score REPORT.json`: estimated course score.
- `panocheck fix FILE --apply fixes.json [-o OUT]`: batch fixes. `fixes.json` is a list of `{check_id, locator, value, decorative}`.
- Exit code non-zero when findings at or above `--fail-on` exist, for CI use.

## Dependencies

| Install | Packages | Used for |
| --- | --- | --- |
| core | `lxml`, `html5lib`, `pikepdf`, `pymupdf` | All structural checks |
| `[canvas]` | `canvasapi` | Course crawl |
| `[media]` | `yt-dlp` | Caption checks |
| external | LibreOffice | Legacy and ODF conversion |

OOXML checks read raw part XML through `lxml`. The Canvas base URL for MSU is an assumption; confirm it.
