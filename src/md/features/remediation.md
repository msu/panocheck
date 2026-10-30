# Remediation

## Intent

A fix must not damage what it does not touch.

- OOXML fixes change only the parts they touch. All other parts keep their bytes.
- Web HTML fixes splice the source text at parser offsets.
- Python HTML fixes serialize the document again, because `html5lib` gives no offsets. This is a known gap.
- The original upload stays unchanged in the undo stack.

## Decisions

- A fix is a function of the document, the finding and the user input. The undo stack holds document snapshots.
- Contrast suggestions keep the hue and move the lightness, so the palette of the author survives.
- PDF fixes rewrite the file, so the tool checks for forms and signatures and warns.
- The web PDF title fix does not write XMP. Python does.
- PDF has no fixes for headings, tables, contrast or font size, because these need content stream edits.
