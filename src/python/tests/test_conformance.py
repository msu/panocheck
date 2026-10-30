import json, pathlib, re, subprocess, sys
import pytest
import yaml
import panocheck

ROOT = pathlib.Path(__file__).resolve().parents[2]
FX = ROOT.parent / "fixtures"
EXPECTED = json.loads((FX / "expected.json").read_text())


def norm(findings):
    return sorted(({"check_id": f.check_id, "severity": f.severity, "locator": f.locator} for f in findings),
                  key=lambda x: (x["check_id"], x["locator"]))


@pytest.mark.parametrize("path", sorted(EXPECTED))
def test_fixture(path):
    entry = EXPECTED[path]
    probe = (lambda url: entry["probe"][url]) if "probe" in entry else None
    assert norm(panocheck.scan(FX / path, media_probe=probe).findings) == entry["findings"]


def test_every_check_has_pass_and_fail_fixture():
    seen = {}
    for path in EXPECTED:
        _, check, name = path.split("/")
        seen.setdefault(check, set()).add(name.split("-")[0])
    for c in panocheck.SPEC["checks"]:
        assert seen.get(c["id"]) == {"pass", "fail"}, c["id"]


def test_fail_fixtures_contain_their_check():
    for path, entry in EXPECTED.items():
        _, check, name = path.split("/")
        ids = {f["check_id"] for f in entry["findings"]}
        assert (check in ids) == name.startswith("fail"), path


def test_embedded_spec_matches_yaml():
    assert panocheck.SPEC == yaml.safe_load((ROOT / "spec/checks.yaml").read_text())


def test_no_deps_needed_to_import():
    code = "import sys; import panocheck; assert not {'lxml','html5lib','pikepdf','pymupdf'} & set(sys.modules)"
    subprocess.run([sys.executable, "-c", code], check=True, cwd=ROOT / "python")


def test_xxe_is_not_expanded(tmp_path):
    import zipfile, io
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("word/document.xml", '<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>')
    assert [f.check_id for f in panocheck.scan(b.getvalue(), name="x.docx").findings] == ["doc.malformed"]


def test_sarif_and_score(tmp_path):
    r = panocheck.scan(FX / "html/img.alt.missing/fail-1.html")
    doc = json.loads(r.to_sarif(tmp_path / "o.sarif"))
    assert doc["runs"][0]["results"][0]["ruleId"] == "img.alt.missing"
    assert r.score == 90


def test_cli_fail_on(tmp_path):
    path = str(FX / "html/img.alt.missing/fail-1.html")
    assert panocheck.main(["scan", path, "--fail-on", "severe"]) == 1
    assert panocheck.main(["scan", path, "--fail-on", "severe", "--min-severity", "major", "--format", "json"]) == 1
    assert panocheck.main(["scan", str(FX / "html/img.alt.missing/pass-1.html"), "--fail-on", "minor"]) == 0
