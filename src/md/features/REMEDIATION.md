# Feature: Remediation

Fixes are minimal XML patches on the original parts, never a re-serialization through a high-level library. OOXML fixes keep all untouched parts byte for byte. Web HTML fixes keep all other bytes. Python HTML fixes serialize the document again. Each fix is a pure function `(doc, finding, input) -> patch`, recorded in an undo stack of document snapshots.

| Fix | HTML | DOCX | PPTX | XLSX | PDF |
| --- | --- | --- | --- | --- | --- |
| Alt text | `alt` attr | `wp:docPr/@descr` | `p:cNvPr/@descr` | `xdr:cNvPr/@descr` | `/Alt` on Figure struct elem (tagged only) |
| Mark decorative | `alt=""` | `adec:decorative` ext | `adec:decorative` ext | same | `/Artifact` (tagged only) |
| Title | n/a | `dc:title` in core.xml | `dc:title` | `dc:title` | Info `/Title` + XMP + `/DisplayDocTitle` |
| Language | `lang` attr | `w:lang` in styles defaults | `a:defRPr/@lang` + runs | n/a | catalog `/Lang` |
| Table header | `<th scope>` | `w:tblHeader` on row 1 | `a:tblPr/@firstRow` | named Table header row | No |
| Heading level | retag `<hN>` | swap `w:pStyle` | n/a | n/a | No |
| Link text | edit anchor text | edit `w:hyperlink` runs | edit run text | edit cell text | No |
| Font too small | n/a | raise `w:sz` to threshold | raise `@sz` | raise font size | No |
| Justified text | n/a | `w:jc` both -> left | n/a | n/a | n/a |
| Contrast | suggest color, set style | set `w:color` | set `a:srgbClr` | set font color | No |
| Reading order | n/a | n/a | reorder `p:spTree` | n/a | No |
| A1 empty | n/a | n/a | n/a | write sheet title to A1 | n/a |

Contrast suggestions keep the hue and move lightness until the ratio passes, so the author's palette survives. PDF fixes write through pdf-lib, which rewrites the file; check for dropped form fields or signatures and warn before download. Python ships the same fix functions behind `panocheck fix FILE --apply fixes.json` for batch use.
