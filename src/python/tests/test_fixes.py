import json, pathlib
import pytest
import panocheck

FX = pathlib.Path(__file__).resolve().parents[3] / "fixtures"
EXPECTED = json.loads((FX / "expected.json").read_text())
VALUES = {"img.": "A description", "doc.title": "A title", "doc.lang": "en-US", "table.caption": "A caption",
          "link.text": "Course syllabus", "link.iframe": "A title", "contrast": "111111", "heading.too_long": "Short",
          "slide.title": "A title", "heading.": 1}
NO_FIX = {"img.not_inline", "heading.none", "list.not_marked", "content.too_long", "target.too_small",
          "pdf.scanned", "pdf.untagged", "doc.encrypted", "doc.malformed", "media.captions.missing",
          "media.captions.auto", "media.private"}


def value(check, path):
    if check == "doc.lang.wrong":
        return "es"
    if check == "contrast.insufficient" and "fail-2" in path:
        return "ffffff"
    if check in ("heading.nesting",):
        return 2
    if check == "heading.depth":
        return 4
    return next((v for k, v in VALUES.items() if check.startswith(k)), None)


CASES = [p for p, e in EXPECTED.items() if p.split("/")[1] not in NO_FIX and "fail" in p and e["findings"]
         and not (p.startswith("pdf/") and p.split("/")[1] not in ("doc.title.missing", "doc.title.hidden", "tag.empty", "doc.lang.missing", "img.alt.missing"))]


@pytest.mark.parametrize("path", CASES)
def test_round_trip(path):
    entry = EXPECTED[path]
    fixes = [{"check_id": f["check_id"], "locator": f["locator"], "value": value(f["check_id"], path)}
             for f in entry["findings"]]
    out = panocheck.fix((FX / path).read_bytes(), fixes, name=path)
    assert panocheck.scan(out, name=path).findings == []


def test_decorative_docx():
    path = "docx/img.alt.missing/fail-1.docx"
    f = EXPECTED[path]["findings"][0]
    out = panocheck.fix((FX / path).read_bytes(), [{**f, "decorative": True}], name=path)
    assert panocheck.scan(out, name=path).findings == []


def test_untouched_parts_keep_bytes():
    import io, zipfile
    path = "docx/doc.title.missing/fail-1.docx"
    data = (FX / path).read_bytes()
    out = panocheck.fix(data, [{"check_id": "doc.title.missing", "locator": "x", "value": "T"}], name=path)
    a, b = zipfile.ZipFile(io.BytesIO(data)), zipfile.ZipFile(io.BytesIO(out))
    assert a.read("word/document.xml") == b.read("word/document.xml")


def test_empty_value_fails():
    path = "docx/doc.title.missing/fail-1.docx"
    with pytest.raises(panocheck.FixError):
        panocheck.fix((FX / path).read_bytes(), [{"check_id": "doc.title.missing", "locator": "x"}], name=path)
