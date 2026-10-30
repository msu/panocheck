# Data: Finding

Every finding uses one schema (`src/spec/schema.json`): `{check_id, severity, format, locator, message, fixable}`.

## Locators

Locators are format-specific.

| Format | Form | Example |
| --- | --- | --- |
| HTML | CSS path | `html > body > img:nth-of-type(1)` |
| DOCX | part name + XPath | `word/document.xml#(//w:p)[2]` |
| PPTX | slide index + shape ID + run index | `slide:1/shape:3/run:1` |
| XLSX | sheet and cell, or sheet and shape | `Data!A1`, `Data!shape:7` |
| PDF | page, or struct element in tree order | `page:1`, `struct:3:Figure` |
| Document level | part and element, or `document` | `docProps/core.xml#dc:title` |
