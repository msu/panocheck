#!/usr/bin/env python3
"""Fix each failing OOXML fixture, then open the output in headless LibreOffice."""
import json, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/python"))
import panocheck

FX = ROOT / "fixtures"
FIXES = {"doc.title.missing": "A title", "doc.lang.missing": "en-US", "img.alt.missing": "A description"}
expected = json.loads((FX / "expected.json").read_text())
with tempfile.TemporaryDirectory() as d:
    for path, entry in expected.items():
        check = path.split("/")[1]
        if "fail" not in path or check not in FIXES or path.split("/")[0] not in ("docx", "pptx", "xlsx"):
            continue
        fixes = [{**f, "value": FIXES[check]} for f in entry["findings"]]
        name = path.replace("/", "_")
        out = pathlib.Path(d) / name
        out.write_bytes(panocheck.fix((FX / path).read_bytes(), fixes, name=path))
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", d, str(out)], check=True, timeout=180)
        pdf = out.with_suffix(".pdf")
        if not pdf.exists():
            sys.exit(f"LibreOffice failed to open {name}. Examine the fix for {check}.")
        print("ok", name)
