#!/usr/bin/env python3
"""Embed spec/checks.yaml in python/panocheck.py. Run with --check to test sync."""
import json, pathlib, re, sys
import yaml

root = pathlib.Path(__file__).resolve().parent.parent
spec = yaml.safe_load((root / "spec/checks.yaml").read_text())
target = root / "python/panocheck.py"
text = target.read_text()
block = "# BEGIN SPEC\nSPEC = json.loads(r'''" + json.dumps(spec, ensure_ascii=True, separators=(",", ":")) + "''')\n# END SPEC"
new = re.sub(r"# BEGIN SPEC.*?# END SPEC", lambda m: block, text, flags=re.S)
if "--check" in sys.argv:
    sys.exit(0 if new == text else "python/panocheck.py spec is stale. Run tools/sync_spec.py.")
target.write_text(new)
