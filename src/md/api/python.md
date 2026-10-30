# Python Engine

## Intent

A project can vendor the engine by copying one file, `src/python/panocheck.py`.

## Decisions

- `tools/sync_spec.py` embeds the spec in the file. A test fails if the embedded copy and the YAML differ.
- The file imports heavy packages only when needed, so a vendored copy needs only the packages for its formats. A test enforces this.
- The CLI uses `argparse`, so the core has no CLI dependency.
- Python is the reference engine, so it was built first and the web engine is tested against the same fixtures.

## Assumptions

- The MSU Canvas base URL `https://montana.instructure.com` is not confirmed.
- `panocheck canvas` and `--probe-media` have not run against real services.
