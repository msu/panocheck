#!/usr/bin/env python3
"""Write spec/checks.yaml into python/panocheck.py and web/site/engine/spec.js. Use --check to test sync."""
import json, pathlib, re, sys
import yaml

root = pathlib.Path(__file__).resolve().parent.parent
spec = yaml.safe_load((root / "spec/checks.yaml").read_text())
target = root / "python/panocheck.py"
text = target.read_text()
block = "# BEGIN SPEC\nSPEC = json.loads(r'''" + json.dumps(spec, ensure_ascii=True, separators=(",", ":")) + "''')\n# END SPEC"
new = re.sub(r"# BEGIN SPEC.*?# END SPEC", lambda m: block, text, flags=re.S)
web = root / "web/site/engine/spec.js"
web_new = "// Generated from src/spec/checks.yaml by src/tools/sync_spec.py.\nexport default " + json.dumps(spec, ensure_ascii=True, indent=1) + "\n"
if "--check" in sys.argv:
    stale = new != text or not web.exists() or web.read_text() != web_new
    sys.exit("The spec copies are stale. Run src/tools/sync_spec.py." if stale else 0)
target.write_text(new)
web.write_text(web_new)
