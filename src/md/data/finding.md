# Finding

The schema is in `src/spec/schema.json`.

## Locator Design

A locator must identify the same element in both engines, so each form uses a value that both parsers can compute.

| Format | Form | Example |
| --- | --- | --- |
| HTML | CSS path after spec parsing | `html > body > img:nth-of-type(1)` |
| DOCX | part name and indexed XPath | `word/document.xml#(//w:p)[2]` |
| PPTX | slide, shape ID, run index | `slide:1/shape:3/run:1` |
| XLSX | sheet and cell, or sheet and shape | `Data!A1`, `Data!shape:7` |
| PDF | page, or struct element in tree order | `page:1`, `struct:3:Figure` |

## Subtleties

- HTML parsing must follow the HTML spec in both engines, or implied elements such as `tbody` change the path. Python uses `html5lib`. The web tool uses `parse5` with scripting off.
- The web tool adds a `colors` field to contrast findings for the fix panel. Conformance tests do not compare it.
