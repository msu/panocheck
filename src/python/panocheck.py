#!/usr/bin/env python3
"""panocheck: document accessibility checker and fixer. Single file, safe to vendor.

Scans HTML, DOCX, PPTX, XLSX and PDF. The spec is embedded below and generated
from spec/checks.yaml by tools/sync_spec.py. Do not edit the block by hand.

Runtime packages: lxml (OOXML), html5lib (HTML), pikepdf + pymupdf (PDF).
Optional: canvasapi (canvas command), yt-dlp (--probe-media). Each is imported
only when needed, so a vendored copy needs only the packages for its formats.
"""
from __future__ import annotations

import argparse
import colorsys
import html as html_lib
import io
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable

# BEGIN SPEC
SPEC = json.loads(r'''{"version":1,"params":{"min_font_pt":9,"alt_max_chars":120,"heading_max_chars":120,"heading_max_depth":4,"heading_min_words":20,"page_max_words":3000,"contrast_normal":4.5,"contrast_large":3.0,"large_text_pt":18,"large_bold_text_pt":14,"min_target_px":24,"lang_min_words":30},"severity_weights":{"severe":10,"major":3,"minor":1},"vocab":{"generic_link":["click here","here","read more","more","link","this link","learn more","details","click","go"],"meaningless_alt":["image","picture","photo","graphic","img","icon","logo","spacer","placeholder","untitled","screenshot"],"colors":{"black":"000000","white":"ffffff","gray":"808080","grey":"808080","silver":"c0c0c0","red":"ff0000","green":"008000","blue":"0000ff","yellow":"ffff00","orange":"ffa500"},"stopwords":{"en":["the","and","of","to","in","is","that","for","with","this","are","you",true,"as","be"],"es":["el","la","los","las","de","que","y","en","un","una","por","con","para","es","del"],"fr":["le","la","les","des","et","que","un","une","pour","dans","est","du","avec","sur","au"],"de":["der","die","das","und","ist","nicht","ein","eine","mit","von","zu","den","auf","f\u00fcr","dem"]}},"checks":[{"id":"pdf.scanned","severity":"severe","formats":["pdf"],"web_fix":"none","message":"The PDF has no text layer. Run OCR on the file."},{"id":"pdf.untagged","severity":"severe","formats":["pdf"],"web_fix":"none","message":"The PDF has no tags. Export a tagged PDF from the source file."},{"id":"doc.encrypted","severity":"severe","formats":["pdf"],"web_fix":"none","message":"The PDF is encrypted. Remove the password and scan again."},{"id":"doc.malformed","severity":"severe","formats":["pdf","docx","pptx","xlsx"],"web_fix":"none","message":"The file structure is not valid. Export the file again from the source."},{"id":"img.alt.missing","severity":"severe","formats":["html","pdf","docx","pptx","xlsx"],"web_fix":"yes","message":"The image has no alternative text. Add a description or mark it as decorative."},{"id":"media.captions.missing","severity":"severe","formats":["html"],"web_fix":"none","engines":["python"],"message":"The media has no captions. Add a caption track."},{"id":"media.captions.auto","severity":"major","formats":["html"],"web_fix":"none","engines":["python"],"message":"The media has only automatic captions. Edit the captions and publish them."},{"id":"media.private","severity":"major","formats":["html"],"web_fix":"none","engines":["python"],"message":"The media is private or not available. Publish the media or remove the link."},{"id":"doc.title.missing","severity":"major","formats":["pdf","docx","pptx","xlsx"],"web_fix":"yes","message":"The document has no title. Add a title."},{"id":"doc.title.hidden","severity":"minor","formats":["pdf"],"web_fix":"yes","message":"The viewer shows the file name, not the title. Set the viewer to show the title."},{"id":"tag.empty","severity":"major","formats":["pdf"],"web_fix":"yes","message":"The text tag holds no text. Change the tag to a Div."},{"id":"doc.lang.missing","severity":"major","formats":["pdf","docx","pptx"],"web_fix":"yes","message":"The document has no language. Set the language."},{"id":"doc.lang.wrong","severity":"major","formats":["docx","pptx"],"web_fix":"yes","message":"The document language does not match the text. Correct the language."},{"id":"heading.none","severity":"major","formats":["html","pdf","docx"],"web_fix":"guided","message":"The document has no headings. Add headings to the sections."},{"id":"heading.start","severity":"major","formats":["pdf","docx"],"web_fix":"guided","web_fix_except":["pdf"],"message":"The first heading is not level 1. Change the heading level."},{"id":"heading.nesting","severity":"major","formats":["html","pdf","docx"],"web_fix":"guided","web_fix_except":["pdf"],"message":"The heading skips a level. Change the heading level."},{"id":"heading.depth","severity":"minor","formats":["html","pdf","docx"],"web_fix":"guided","web_fix_except":["pdf"],"message":"The heading is too deep. Use fewer heading levels."},{"id":"table.header.missing","severity":"major","formats":["html","pdf","docx","pptx","xlsx"],"web_fix":"yes","web_fix_except":["pdf"],"message":"The table has no header row. Mark the first row as the header."},{"id":"table.header.scope","severity":"minor","formats":["html"],"web_fix":"yes","message":"The header cell has no scope. Set the scope."},{"id":"table.caption.missing","severity":"minor","formats":["html","docx"],"web_fix":"yes","message":"The table has no caption. Add a caption."},{"id":"table.empty","severity":"minor","formats":["html"],"web_fix":"yes","message":"The table has no content. Remove the table."},{"id":"contrast.insufficient","severity":"major","formats":["html","pdf","docx","pptx","xlsx"],"web_fix":"suggest","web_fix_except":["pdf"],"engines_by_format":{"pdf":["python"]},"message":"The text contrast is too low. Use a color with more contrast."},{"id":"reading_order","severity":"major","formats":["pdf","pptx"],"web_fix":"yes","web_fix_except":["pdf"],"message":"The reading order is not logical. Correct the order."},{"id":"slide.title.missing","severity":"major","formats":["pptx"],"web_fix":"yes","message":"The slide has no title. Add a title."},{"id":"link.text.generic","severity":"major","formats":["html","docx","pptx","xlsx"],"web_fix":"yes","message":"The link text does not give the destination. Write descriptive text."},{"id":"link.adjacent.duplicate","severity":"minor","formats":["html"],"web_fix":"yes","message":"Adjacent links go to the same destination. Merge the links."},{"id":"link.iframe.title","severity":"minor","formats":["html"],"web_fix":"yes","message":"The iframe has no title. Add a title."},{"id":"font.too_small","severity":"minor","formats":["html","pdf","docx","pptx","xlsx"],"web_fix":"yes","web_fix_except":["pdf"],"message":"The font is smaller than {min_font_pt} pt. Increase the font size."},{"id":"text.justified","severity":"minor","formats":["docx"],"web_fix":"yes","message":"The text is justified. Align the text to the left."},{"id":"list.not_marked","severity":"minor","formats":["html","docx"],"web_fix":"guided","message":"The text looks like a list but has no list markup. Use a real list."},{"id":"img.alt.too_long","severity":"minor","formats":["html"],"web_fix":"yes","message":"The alternative text is longer than {alt_max_chars} characters. Shorten the text."},{"id":"img.alt.filename","severity":"major","formats":["html"],"web_fix":"yes","message":"The alternative text is a file name. Write a description."},{"id":"img.alt.meaningless","severity":"major","formats":["html"],"web_fix":"yes","message":"The alternative text has no meaning. Write a description."},{"id":"img.decorative.interactive","severity":"major","formats":["html"],"web_fix":"yes","message":"The linked image has empty alternative text. Describe the link destination."},{"id":"img.not_inline","severity":"minor","formats":["docx"],"web_fix":"none","message":"The image is not inline with text. Set the image to inline."},{"id":"heading.too_long","severity":"minor","formats":["html"],"web_fix":"yes","message":"The heading is longer than {heading_max_chars} characters. Shorten the heading."},{"id":"content.too_long","severity":"minor","formats":["html"],"web_fix":"none","message":"The page has more than {page_max_words} words. Split the page."},{"id":"target.too_small","severity":"minor","formats":["html"],"web_fix":"none","message":"The target is smaller than {min_target_px} px. Increase the size."},{"id":"xlsx.a1.empty","severity":"minor","formats":["xlsx"],"web_fix":"yes","message":"Cell A1 is empty. Write the sheet title in cell A1."}]}''')
# END SPEC

__version__ = "0.1.0"

CHECKS = {c["id"]: c for c in SPEC.get("checks", [])}
VOCAB = SPEC.get("vocab", {})
MAX_UNZIPPED = 512 * 1024 * 1024
WS = " \t\n\r\f\v  -   　"
WS_RE = re.compile(f"[{WS}]+")
LIST_RE = re.compile(f"^(\\d+[.)]|[-*•])[{WS}]")
ALT_FILE_RE = re.compile(r"^[^ ]+\.(png|jpe?g|gif|svg|webp|bmp|tiff?)$", re.I)
LEGACY = {".doc": "docx", ".dot": "docx", ".rtf": "docx", ".odt": "docx", ".ppt": "pptx",
          ".odp": "pptx", ".xls": "xlsx", ".ods": "xlsx"}


class Params:
    def __init__(self, **kw):
        self.__dict__.update(SPEC["params"])
        for k, v in kw.items():
            if k not in SPEC["params"]:
                raise ValueError(f"Unknown parameter {k}. Use a parameter from the spec.")
            setattr(self, k, v)


@dataclass
class Finding:
    check_id: str
    severity: str
    format: str
    locator: str
    message: str
    fixable: bool


@dataclass
class Report:
    source: str
    format: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def score(self) -> int:
        return score(self.findings)

    def to_dict(self):
        return {"source": self.source, "format": self.format, "estimated_score": self.score,
                "findings": [asdict(f) for f in self.findings]}

    def to_json(self, path=None):
        out = json.dumps(self.to_dict(), indent=2)
        if path:
            with open(path, "w") as f:
                f.write(out)
        return out

    def to_sarif(self, path=None):
        return _write(sarif([self]), path)


def _write(obj, path):
    out = json.dumps(obj, indent=2)
    if path:
        with open(path, "w") as f:
            f.write(out)
    return out


def score(findings: Iterable) -> int:
    """Estimate only. The weights are provisional."""
    w = SPEC["severity_weights"]
    return max(0, 100 - sum(w[f.severity if isinstance(f, Finding) else f["severity"]] for f in findings))


def sarif(reports: list[Report]) -> dict:
    level = {"severe": "error", "major": "warning", "minor": "note"}
    return {"version": "2.1.0", "runs": [{
        "tool": {"driver": {"name": "panocheck", "version": __version__, "rules": [
            {"id": c["id"], "shortDescription": {"text": c["message"]}} for c in SPEC["checks"]]}},
        "results": [{"ruleId": f.check_id, "level": level[f.severity], "message": {"text": f.message},
                     "locations": [{"physicalLocation": {"artifactLocation": {"uri": r.source}},
                                    "logicalLocations": [{"fullyQualifiedName": f.locator}]}]}
                    for r in reports for f in r.findings]}]}


class Ctx:
    def __init__(self, fmt: str, params: Params):
        self.fmt, self.p, self.findings = fmt, params, []

    def add(self, check_id: str, locator: str):
        c = CHECKS[check_id]
        msg = c["message"].format(**self.p.__dict__)
        fixable = c["web_fix"] != "none" and self.fmt not in c.get("web_fix_except", [])
        f = Finding(check_id, c["severity"], self.fmt, locator, msg, fixable)
        if f not in self.findings:
            self.findings.append(f)


# ---- shared helpers ----

def clean(s: str) -> str:
    return WS_RE.sub(" ", s or "").strip(" ")


def words(s: str) -> list[str]:
    return [w for w in WS_RE.split(s or "") if w]


def is_generic(text: str) -> bool:
    t = clean(text).lower().rstrip(".:!")
    return t in VOCAB["generic_link"] or bool(re.match(r"^https?://", t))


def detect_lang(text: str, p: Params):
    toks = re.findall(r"[^\W\d_]+", text.lower())
    if len(toks) < p.lang_min_words:
        return None
    scores = sorted(((sum(t in set(ws) for t in toks), lang)
                     for lang, ws in sorted(VOCAB["stopwords"].items())), key=lambda x: -x[0])
    if scores[0][0] < 3 or scores[0][0] < scores[1][0] * 1.5:
        return None
    return scores[0][1]


def lang_wrong(declared, text: str, p: Params) -> bool:
    if not declared:
        return False
    d = declared.lower().split("-")[0]
    found = detect_lang(text, p)
    return d in VOCAB["stopwords"] and found is not None and found != d


def luminance(hex_: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a: str, b: str) -> float:
    x, y = sorted((luminance(a), luminance(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def low_contrast(fg: str, bg: str, pt, bold: bool, p: Params) -> bool:
    large = pt is not None and (pt >= p.large_text_pt or (bold and pt >= p.large_bold_text_pt))
    return contrast_ratio(fg, bg) < (p.contrast_large if large else p.contrast_normal)


def suggest_color(fg: str, bg: str, target: float = 4.5) -> str:
    """Keep the hue. Move lightness until the ratio passes."""
    r, g, b = (int(fg[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    step = -0.01 if luminance(bg) > 0.18 else 0.01
    while 0 <= l <= 1:
        c = "".join(f"{round(v * 255):02x}" for v in colorsys.hls_to_rgb(h, l, s))
        if contrast_ratio(c, bg) >= target:
            return c
        l += step
    return "000000" if step < 0 else "ffffff"


# ---- format detection ----

def detect(data: bytes, name: str = "") -> str:
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    if b"%PDF-" in data[:1024]:
        return "pdf"
    if data[:2] == b"PK":
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except zipfile.BadZipFile:
            names = []
        for prefix, fmt in (("word/", "docx"), ("ppt/", "pptx"), ("xl/", "xlsx")):
            if any(n.startswith(prefix) for n in names):
                return fmt
    if ext in ("docx", "pptx", "xlsx", "pdf"):
        return ext
    head = data[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if ext in ("html", "htm") or head.startswith((b"<!doctype", b"<html", b"<")):
        return "html"
    raise ValueError(f"The format of {name or 'the input'} is not known. Use HTML, DOCX, PPTX, XLSX or PDF.")


# ---- HTML: own small tree, so both engines walk the same shape ----

VOID = set("area base br col embed hr img input link meta param source track wbr".split())
RAW = {"script", "style"}


class Comment(str):
    pass


class N:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.parent, self.kids = tag, dict(attrs or {}), parent, []

    def els(self):
        for k in self.kids:
            if isinstance(k, N):
                yield k

    def walk(self):
        yield self
        for k in self.els():
            yield from k.walk()

    def find_all(self, *tags):
        return [e for e in self.walk() if e.tag in tags]

    def text(self):
        out = []
        for k in self.kids:
            if isinstance(k, N):
                if k.tag not in RAW:
                    out.append(k.text())
            elif not isinstance(k, Comment):
                out.append(k)
        return "".join(out)

    def own_text(self):
        return "".join(k for k in self.kids if isinstance(k, str) and not isinstance(k, Comment))

    def path(self):
        if self.parent is None or self.tag in ("head", "body"):
            return self.tag if self.parent is None else f"html > {self.tag}"
        same = [e for e in self.parent.els() if e.tag == self.tag]
        return f"{self.parent.path()} > {self.tag}:nth-of-type({same.index(self) + 1})"

    def style(self):
        out = {}
        for part in self.attrs.get("style", "").split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                out[k.strip().lower()] = v.strip().lower()
        return out

    def inherited(self, prop):
        e = self
        while e is not None:
            v = e.style().get(prop)
            if v:
                return v
            e = e.parent
        return None

    def serialize(self):
        if self.tag == "#doc":
            return "".join(_ser(k, self) for k in self.kids)
        return _ser(self, self.parent)


def _ser(k, parent):
    if isinstance(k, Comment):
        return f"<!--{k}-->"
    if isinstance(k, str):
        return k if parent is not None and parent.tag in RAW else html_lib.escape(k, quote=False)
    attrs = "".join(f' {a}="{html_lib.escape(v, quote=True)}"' for a, v in k.attrs.items())
    if k.tag in VOID:
        return f"<{k.tag}{attrs}>"
    return f"<{k.tag}{attrs}>" + "".join(_ser(c, k) for c in k.kids) + f"</{k.tag}>"


def parse_html(data: bytes) -> N:
    import html5lib
    if data[:3] == b"\xef\xbb\xbf":
        data = data[3:]
    src = data.decode("utf-8", "replace")
    root = html5lib.HTMLParser(namespaceHTMLElements=False).parse(src)

    def conv(e, parent):
        tag = re.sub(r"^\{.*\}", "", e.tag)
        n = N(tag, {re.sub(r"^\{.*\}", "", k): v for k, v in e.attrib.items()}, parent)
        if e.text:
            n.kids.append(e.text)
        for c in e:
            if isinstance(c.tag, str):
                if c.tag != "template":
                    n.kids.append(conv(c, n))
            else:
                n.kids.append(Comment(c.text or ""))
            if c.tail:
                n.kids.append(c.tail)
        return n
    tree = conv(root, None)
    m = re.match(r"\s*<!doctype[^>]*>", src, re.I)
    tree.doctype = m.group(0).strip() if m else ""
    return tree


def html_find(tree: N, locator: str) -> N:
    node = tree
    for part in locator.split(" > ")[1:]:
        m = re.match(r"([^:]+)(?::nth-of-type\((\d+)\))?$", part)
        same = [e for e in node.els() if e.tag == m.group(1)]
        node = same[int(m.group(2) or 1) - 1]
    return node


def parse_color(v):
    v = (v or "").strip().lower()
    if v in VOCAB["colors"]:
        return VOCAB["colors"][v]
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", v)
    if m:
        h = m.group(1)
        return h if len(h) == 6 else "".join(c * 2 for c in h)
    m = re.fullmatch(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", v)
    if m:
        return "".join(f"{min(int(x), 255):02x}" for x in m.groups())
    return None


def _pt(v):
    m = re.fullmatch(r"([\d.]+)(pt|px)", v or "")
    if not m:
        return None
    return float(m.group(1)) * (1 if m.group(2) == "pt" else 0.75)


def _heading_seq(ctx, seq, none_loc, text, *, check_start):
    """seq is a list of (level, locator) in document order."""
    p = ctx.p
    if not seq:
        if len(words(text)) >= p.heading_min_words:
            ctx.add("heading.none", none_loc)
        return
    if check_start and seq[0][0] != 1:
        ctx.add("heading.start", seq[0][1])
    prev = None
    for level, loc in seq:
        if prev is not None and level > prev + 1:
            ctx.add("heading.nesting", loc)
        if level > p.heading_max_depth:
            ctx.add("heading.depth", loc)
        prev = level


def check_html(data: bytes, ctx: Ctx, media_probe=None):
    p, tree = ctx.p, parse_html(data)
    body = html_find(tree, "html > body")
    text = body.text()
    seq = []
    for e in tree.walk():
        t, a = e.tag, e.attrs
        if t == "img":
            aria = a.get("aria-label") or a.get("aria-labelledby")
            if "alt" not in a:
                if not aria:
                    ctx.add("img.alt.missing", e.path())
            else:
                alt = clean(a["alt"])
                if len(alt) > p.alt_max_chars:
                    ctx.add("img.alt.too_long", e.path())
                if ALT_FILE_RE.match(alt):
                    ctx.add("img.alt.filename", e.path())
                if alt.lower() in VOCAB["meaningless_alt"]:
                    ctx.add("img.alt.meaningless", e.path())
                if not alt and not aria:
                    a_ = e.parent
                    while a_ is not None and a_.tag not in ("a", "button"):
                        a_ = a_.parent
                    if a_ is not None and not clean(a_.text()) and not a_.attrs.get("aria-label"):
                        ctx.add("img.decorative.interactive", e.path())
        elif t == "video":
            kinds = [x.attrs.get("kind", "").lower() for x in e.find_all("track")]
            if not any(k in ("captions", "subtitles") for k in kinds):
                ctx.add("media.captions.missing", e.path())
        elif t == "iframe":
            if not clean(a.get("title", "")):
                ctx.add("link.iframe.title", e.path())
            src = a.get("src", "")
            if media_probe and re.search(r"youtube\.com|youtu\.be|vimeo\.com", src):
                res = media_probe(src)
                check = {"none": "media.captions.missing", "auto": "media.captions.auto",
                         "private": "media.private"}.get(res)
                if check:
                    ctx.add(check, e.path())
        elif re.fullmatch(r"h[1-6]", t):
            seq.append((int(t[1]), e.path()))
            if len(clean(e.text())) > p.heading_max_chars:
                ctx.add("heading.too_long", e.path())
        elif t == "table":
            rows_text = clean(e.text())
            if not rows_text and not e.find_all("img"):
                ctx.add("table.empty", e.path())
            else:
                ths = e.find_all("th")
                if not ths:
                    ctx.add("table.header.missing", e.path())
                for th in ths:
                    if not th.attrs.get("scope"):
                        ctx.add("table.header.scope", th.path())
                if not any(k.tag == "caption" for k in e.els()):
                    ctx.add("table.caption.missing", e.path())
        elif t == "a":
            if a.get("href") is not None and clean(e.text()) and is_generic(e.text()):
                ctx.add("link.text.generic", e.path())
            sibs = e.parent.kids
            i = next(n for n, k in enumerate(sibs) if k is e)
            j = i + 1
            while j < len(sibs) and isinstance(sibs[j], str) and not clean(sibs[j]):
                j += 1
            if j < len(sibs) and isinstance(sibs[j], N) and sibs[j].tag == "a" \
                    and a.get("href") and sibs[j].attrs.get("href") == a.get("href"):
                ctx.add("link.adjacent.duplicate", sibs[j].path())
        elif t == "p":
            if LIST_RE.match(clean(e.text())):
                sib = [x for x in e.parent.els()]
                i = sib.index(e)
                if i + 1 < len(sib) and sib[i + 1].tag == "p" and LIST_RE.match(clean(sib[i + 1].text())):
                    if i == 0 or not (sib[i - 1].tag == "p" and LIST_RE.match(clean(sib[i - 1].text()))):
                        ctx.add("list.not_marked", e.path())
        st = e.style()
        if t in ("a", "button"):
            for dim in ("width", "height"):
                m = re.fullmatch(r"([\d.]+)px", st.get(dim, ""))
                if m and float(m.group(1)) < p.min_target_px:
                    ctx.add("target.too_small", e.path())
        if clean(e.own_text()):
            size = _pt(st.get("font-size"))
            if size is not None and size < p.min_font_pt:
                ctx.add("font.too_small", e.path())
            if "color" in st or "background-color" in st or "background" in st:
                fg = parse_color(e.inherited("color") or "black")
                bg = None
                n = e
                while n is not None and bg is None:
                    s = n.style()
                    bg = parse_color(s.get("background-color") or s.get("background"))
                    n = n.parent
                if fg:
                    pt = _pt(e.inherited("font-size"))
                    w = e.inherited("font-weight") or ""
                    bold = w == "bold" or (w.isdigit() and int(w) >= 700)
                    if low_contrast(fg, bg or "ffffff", pt, bold, p):
                        ctx.add("contrast.insufficient", e.path())
    _heading_seq(ctx, seq, "html > body", text, check_start=False)
    if len(words(text)) > p.page_max_words:
        ctx.add("content.too_long", "html > body")


# ---- OOXML ----

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "dc": "http://purl.org/dc/elements/1.1/",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}
CORE = "docProps/core.xml"
CORE_TYPE = "application/vnd.openxmlformats-package.core-properties+xml"
CORE_REL = "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"
ADEC_URI = "{C183D7F6-B498-43B3-948B-1728B52AA6E4}"
ADEC_NS = "http://schemas.microsoft.com/office/drawing/2017/decorative"


def q(name: str) -> str:
    pre, local = name.split(":")
    return f"{{{NS[pre]}}}{local}"


class Malformed(Exception):
    pass


class Pkg:
    """OOXML package. Untouched parts keep their exact bytes on save."""

    def __init__(self, data: bytes):
        try:
            self.zip = zipfile.ZipFile(io.BytesIO(data))
            if sum(i.file_size for i in self.zip.infolist()) > MAX_UNZIPPED:
                raise Malformed("zip too large")
            self.names = self.zip.namelist()
        except zipfile.BadZipFile as e:
            raise Malformed(str(e))
        self.cache, self.new = {}, {}

    def has(self, part):
        return part in self.names or part in self.new

    def xml(self, part):
        from lxml import etree
        if part not in self.cache:
            raw = self.new[part] if part in self.new else self.zip.read(part)
            if b"<!DOCTYPE" in raw[:4096] or b"<!ENTITY" in raw[:4096]:
                raise Malformed("DTD in part")
            parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
            try:
                self.cache[part] = etree.fromstring(raw, parser)
            except etree.XMLSyntaxError as e:
                raise Malformed(str(e))
        return self.cache[part]

    def add(self, part, raw: bytes):
        self.new[part] = raw

    def rels(self, part):
        d, b = posixpath.split(part)
        rp = f"{d}/_rels/{b}.rels" if d else f"_rels/{b}.rels"
        if not self.has(rp):
            return {}
        return {r.get("Id"): resolve(part, r.get("Target")) for r in self.xml(rp)}

    def save(self, touched: set) -> bytes:
        from lxml import etree
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for info in self.zip.infolist():
                raw = self.zip.read(info.filename)
                if info.filename in touched:
                    raw = etree.tostring(self.cache[info.filename], xml_declaration=True, encoding="UTF-8", standalone=True)
                z.writestr(info, raw, compress_type=info.compress_type)
            for name in self.new:
                raw = etree.tostring(self.cache[name], xml_declaration=True, encoding="UTF-8", standalone=True) \
                    if name in self.cache else self.new[name]
                z.writestr(name, raw)
        return out.getvalue()


def resolve(base, target):
    if target.startswith("/"):
        return target[1:]
    return posixpath.normpath(posixpath.join(posixpath.dirname(base), target))


def ln(e) -> str:
    return e.tag.split("}")[-1] if isinstance(e.tag, str) else ""


def is_decorative(cnv) -> bool:
    return any(ln(x) == "decorative" and x.get("val") in ("1", "true") for x in cnv.iter())


def core_title(pkg: Pkg) -> str:
    if not pkg.has(CORE):
        return ""
    t = pkg.xml(CORE).find(q("dc:title"))
    return clean(t.text if t is not None else "")


def check_docx(pkg: Pkg, ctx: Ctx):
    part = "word/document.xml"
    if not pkg.has(part):
        raise Malformed("no main part")
    p, doc = ctx.p, pkg.xml(part)
    loc = lambda tag, i: f"{part}#(//{tag})[{i}]"
    if not core_title(pkg):
        ctx.add("doc.title.missing", f"{CORE}#dc:title")
    lang = None
    if pkg.has("word/styles.xml"):
        el = pkg.xml("word/styles.xml").find(f"{q('w:docDefaults')}/{q('w:rPrDefault')}/{q('w:rPr')}/{q('w:lang')}")
        lang = el.get(q("w:val")) if el is not None else None
    lang_loc = "word/styles.xml#w:docDefaults"
    if not lang:
        ctx.add("doc.lang.missing", lang_loc)
    body_text = " ".join("".join(t.text or "" for t in para.iter(q("w:t"))) for para in doc.iter(q("w:p")))
    if lang_wrong(lang, body_text, p):
        ctx.add("doc.lang.wrong", lang_loc)
    for i, d in enumerate(doc.iter(q("wp:docPr")), 1):
        if not clean(d.get("descr")) and not is_decorative(d):
            ctx.add("img.alt.missing", loc("wp:docPr", i))
    for i, _ in enumerate(doc.iter(q("wp:anchor")), 1):
        ctx.add("img.not_inline", loc("wp:anchor", i))
    seq, paras = [], list(doc.iter(q("w:p")))
    texts = [clean("".join(t.text or "" for t in x.iter(q("w:t")))) for x in paras]
    for i, para in enumerate(paras):
        ppr = para.find(q("w:pPr"))
        l = loc("w:p", i + 1)
        st = ppr.find(q("w:pStyle")) if ppr is not None else None
        m = re.fullmatch(r"heading ?(\d)", (st.get(q("w:val")) if st is not None else "") or "", re.I)
        if m:
            seq.append((int(m.group(1)), l))
        jc = ppr.find(q("w:jc")) if ppr is not None else None
        if jc is not None and jc.get(q("w:val")) in ("both", "distribute"):
            ctx.add("text.justified", l)
        marked = ppr is not None and ppr.find(q("w:numPr")) is not None
        if not marked and LIST_RE.match(texts[i]) and i + 1 < len(paras) and LIST_RE.match(texts[i + 1]):
            if i == 0 or not LIST_RE.match(texts[i - 1]):
                ctx.add("list.not_marked", l)
    _heading_seq(ctx, seq, f"{part}#w:body", body_text, check_start=True)
    for i, t in enumerate(doc.iter(q("w:tbl")), 1):
        pr = t.find(q("w:tblPr"))
        if pr is None or pr.find(q("w:tblCaption")) is None or not pr.find(q("w:tblCaption")).get(q("w:val")):
            ctx.add("table.caption.missing", loc("w:tbl", i))
        first = t.find(q("w:tr"))
        trpr = first.find(q("w:trPr")) if first is not None else None
        if trpr is None or trpr.find(q("w:tblHeader")) is None:
            ctx.add("table.header.missing", loc("w:tbl", i))
    for i, h in enumerate(doc.iter(q("w:hyperlink")), 1):
        if is_generic("".join(t.text or "" for t in h.iter(q("w:t")))):
            ctx.add("link.text.generic", loc("w:hyperlink", i))
    for i, r in enumerate(doc.iter(q("w:r")), 1):
        if not clean("".join(t.text or "" for t in r.iter(q("w:t")))):
            continue
        pr = r.find(q("w:rPr"))
        if pr is None:
            continue
        sz = pr.find(q("w:sz"))
        pt = int(sz.get(q("w:val"))) / 2 if sz is not None else None
        if pt is not None and pt < p.min_font_pt:
            ctx.add("font.too_small", loc("w:r", i))
        col = pr.find(q("w:color"))
        val = (col.get(q("w:val")) or "").lower() if col is not None else ""
        if re.fullmatch("[0-9a-f]{6}", val):
            shd = pr.find(q("w:shd"))
            fill = (shd.get(q("w:fill")) or "").lower() if shd is not None else ""
            bg = fill if re.fullmatch("[0-9a-f]{6}", fill) else "ffffff"
            if low_contrast(val, bg, pt, pr.find(q("w:b")) is not None, p):
                ctx.add("contrast.insufficient", loc("w:r", i))


def _slides(pkg: Pkg):
    pres = pkg.xml("ppt/presentation.xml")
    rels = pkg.rels("ppt/presentation.xml")
    lst = pres.find(q("p:sldIdLst"))
    return [rels[s.get(q("r:id"))] for s in (lst if lst is not None else [])]


SHAPES = ("sp", "pic", "graphicFrame")


def _shapes(tree):
    return [e for e in tree.iter() if ln(e) in SHAPES and e.tag.startswith(f"{{{NS['p']}}}")]


def _cnv(shape):
    return next(x for x in shape.iter() if ln(x) == "cNvPr")


def _ph_title(shape):
    return any(ln(x) == "ph" and x.get("type") in ("title", "ctrTitle") for x in shape.iter())


def _def_rpr(pres):
    return pres.find(f"{q('p:defaultTextStyle')}/{q('a:defPPr')}/{q('a:defRPr')}")


def check_pptx(pkg: Pkg, ctx: Ctx):
    if not pkg.has("ppt/presentation.xml"):
        raise Malformed("no main part")
    p, pres = ctx.p, pkg.xml("ppt/presentation.xml")
    if not core_title(pkg):
        ctx.add("doc.title.missing", f"{CORE}#dc:title")
    d = _def_rpr(pres)
    lang = d.get("lang") if d is not None else None
    lang_loc = "ppt/presentation.xml#p:defaultTextStyle"
    if not lang:
        ctx.add("doc.lang.missing", lang_loc)
    all_text = []
    for n, part in enumerate(_slides(pkg), 1):
        if not pkg.has(part):
            raise Malformed("missing slide")
        tree = pkg.xml(part)
        shapes = _shapes(tree)
        title = [s for s in shapes if ln(s) == "sp" and _ph_title(s)]
        if not any(clean("".join(t.text or "" for t in s.iter(q("a:t")))) for s in title):
            ctx.add("slide.title.missing", f"slide:{n}")
        if title and shapes[0] is not title[0]:
            ctx.add("reading_order", f"slide:{n}")
        for s in shapes:
            cnv = _cnv(s)
            sl = f"slide:{n}/shape:{cnv.get('id')}"
            if ln(s) == "pic" and not clean(cnv.get("descr")) and not is_decorative(cnv):
                ctx.add("img.alt.missing", sl)
            tbl = next((x for x in s.iter(q("a:tbl"))), None)
            if tbl is not None:
                pr = tbl.find(q("a:tblPr"))
                if pr is None or pr.get("firstRow") not in ("1", "true"):
                    ctx.add("table.header.missing", sl)
            sppr = s.find(q("p:spPr"))
            fill = sppr.find(f"{q('a:solidFill')}/{q('a:srgbClr')}") if sppr is not None else None
            bg = fill.get("val").lower() if fill is not None else "ffffff"
            for i, r in enumerate(s.iter(q("a:r")), 1):
                txt = "".join(t.text or "" for t in r.iter(q("a:t")))
                all_text.append(txt)
                if not clean(txt):
                    continue
                rl = f"{sl}/run:{i}"
                pr = r.find(q("a:rPr"))
                if pr is None:
                    continue
                if pr.find(q("a:hlinkClick")) is not None and is_generic(txt):
                    ctx.add("link.text.generic", rl)
                pt = int(pr.get("sz")) / 100 if pr.get("sz") else None
                if pt is not None and pt < p.min_font_pt:
                    ctx.add("font.too_small", rl)
                col = pr.find(f"{q('a:solidFill')}/{q('a:srgbClr')}")
                if col is not None and low_contrast(col.get("val").lower(), bg, pt, pr.get("b") in ("1", "true"), p):
                    ctx.add("contrast.insufficient", rl)
    if lang_wrong(lang, " ".join(all_text), p):
        ctx.add("doc.lang.wrong", lang_loc)


def _sheets(pkg: Pkg):
    wb = pkg.xml("xl/workbook.xml")
    rels = pkg.rels("xl/workbook.xml")
    lst = wb.find(q("s:sheets"))
    return [(s.get("name"), rels[s.get(q("r:id"))]) for s in (lst if lst is not None else [])]


def _shared(pkg: Pkg):
    if not pkg.has("xl/sharedStrings.xml"):
        return []
    return ["".join(t.text or "" for t in si.iter(q("s:t"))) for si in pkg.xml("xl/sharedStrings.xml")]


def _cell_text(c, shared):
    t = c.get("t")
    if t == "inlineStr":
        return "".join(x.text or "" for x in c.iter(q("s:t")))
    v = c.find(q("s:v"))
    if v is None or v.text is None:
        return ""
    return shared[int(v.text)] if t == "s" else v.text


def _xlsx_styles(pkg: Pkg):
    if not pkg.has("xl/styles.xml"):
        return None
    st = pkg.xml("xl/styles.xml")
    get = lambda n: list(st.find(q(n))) if st.find(q(n)) is not None else []
    return get("s:cellXfs"), get("s:fonts"), get("s:fills")


def check_xlsx(pkg: Pkg, ctx: Ctx):
    if not pkg.has("xl/workbook.xml"):
        raise Malformed("no main part")
    p = ctx.p
    if not core_title(pkg):
        ctx.add("doc.title.missing", f"{CORE}#dc:title")
    shared, styles = _shared(pkg), _xlsx_styles(pkg)
    for name, part in _sheets(pkg):
        if not pkg.has(part):
            raise Malformed("missing sheet")
        sheet, rels = pkg.xml(part), pkg.rels(part)
        cells = {c.get("r"): c for c in sheet.iter(q("s:c"))}
        if "A1" not in cells or not clean(_cell_text(cells["A1"], shared)):
            ctx.add("xlsx.a1.empty", f"{name}!A1")
        for ref, c in cells.items():
            if not clean(_cell_text(c, shared)) or not styles:
                continue
            xfs, fonts, fills = styles
            xf = xfs[int(c.get("s") or 0)] if xfs else None
            if xf is None:
                continue
            font = fonts[int(xf.get("fontId") or 0)] if fonts else None
            fill = fills[int(xf.get("fillId") or 0)] if fills else None
            pt, fg, bold = None, None, False
            if font is not None:
                sz = font.find(q("s:sz"))
                pt = float(sz.get("val")) if sz is not None else None
                col = font.find(q("s:color"))
                fg = col.get("rgb")[-6:].lower() if col is not None and col.get("rgb") else None
                bold = font.find(q("s:b")) is not None
            if pt is not None and pt < p.min_font_pt:
                ctx.add("font.too_small", f"{name}!{ref}")
            bg = "ffffff"
            if fill is not None:
                pf = fill.find(q("s:patternFill"))
                if pf is not None and pf.get("patternType") == "solid" and pf.find(q("s:fgColor")) is not None \
                        and pf.find(q("s:fgColor")).get("rgb"):
                    bg = pf.find(q("s:fgColor")).get("rgb")[-6:].lower()
            if fg and low_contrast(fg, bg, pt, bold, p):
                ctx.add("contrast.insufficient", f"{name}!{ref}")
        for h in sheet.iter(q("s:hyperlink")):
            c = cells.get(h.get("ref"))
            if c is not None and is_generic(_cell_text(c, shared)):
                ctx.add("link.text.generic", f"{name}!{h.get('ref')}")
        d = sheet.find(q("s:drawing"))
        if d is not None and rels.get(d.get(q("r:id"))):
            for pic in pkg.xml(rels[d.get(q("r:id"))]).iter(q("xdr:pic")):
                cnv = next(x for x in pic.iter() if ln(x) == "cNvPr")
                if not clean(cnv.get("descr")) and not is_decorative(cnv):
                    ctx.add("img.alt.missing", f"{name}!shape:{cnv.get('id')}")
        for tp in sheet.iter(q("s:tablePart")):
            t = pkg.xml(rels[tp.get(q("r:id"))])
            if t.get("headerRowCount") == "0":
                ctx.add("table.header.missing", f"{name}!{t.get('ref').split(':')[0]}")


# ---- PDF ----

def _name(o):
    return str(o).lstrip("/")


TEXT_TAGS = {"P", "H", "H1", "H2", "H3", "H4", "H5", "H6", "LI", "Lbl", "LBody"}


def pdf_struct(pdf) -> tuple[list[dict], list[tuple]]:
    """Preorder struct elements {n, type, alt, ref, mcids, kids} and the (page objgen, mcid) sequence in tree order."""
    import pikepdf
    root = pdf.Root.get("/StructTreeRoot")
    if root is None:
        return [], []
    rolemap = root.get("/RoleMap", {})
    out, order, seen = [], [], set()

    def visit(node, pg, parent):
        if isinstance(node, pikepdf.Array):
            for k in node:
                visit(k, pg, parent)
            return
        if not isinstance(node, pikepdf.Dictionary):
            return
        if node.is_indirect:
            if node.objgen in seen:
                return
            seen.add(node.objgen)
        page = node.get("/Pg", pg)
        pg_id = page.objgen if page is not None else None
        if node.get("/Type") == pikepdf.Name("/MCR"):
            if "/MCID" in node:
                order.append((pg_id, int(node["/MCID"])))
                if parent is not None:
                    parent["mcids"].append((pg_id, int(node["/MCID"])))
            return
        if "/S" not in node:
            return
        s = _name(node["/S"])
        s = _name(rolemap.get("/" + s, "/" + s))
        el = {"n": len(out) + 1, "type": s, "alt": str(node.get("/Alt", "")), "ref": node, "mcids": [], "kids": []}
        out.append(el)
        if parent is not None:
            parent["kids"].append(el)
        k = node.get("/K")
        kids = k if isinstance(k, pikepdf.Array) else [k] if k is not None else []
        for kid in kids:
            if isinstance(kid, (int, pikepdf.Object)) and not isinstance(kid, (pikepdf.Dictionary, pikepdf.Array)):
                order.append((pg_id, int(kid)))
                el["mcids"].append((pg_id, int(kid)))
            else:
                visit(kid, page, el)
    k = root.get("/K")
    if k is not None:
        visit(k, None, None)
    return out, order


def pdf_text_mcids(pdf) -> set:
    """Return the (page objgen, mcid) pairs whose marked content shows text, also through form XObjects."""
    import pikepdf
    found = set()

    def walk(obj, resources, stack, page_id, depth):
        for operands, op in pikepdf.parse_content_stream(obj):
            op = str(op)
            if op in ("BDC", "BMC"):
                mcid = None
                if op == "BDC" and isinstance(operands[1], pikepdf.Dictionary):
                    mcid = operands[1].get("/MCID")
                stack.append(None if mcid is None else int(mcid))
            elif op == "EMC":
                if stack:
                    stack.pop()
            elif op in ("Tj", "TJ", "'", '"'):
                found.update((page_id, m) for m in stack if m is not None)
            elif op == "Do" and depth < 8:
                xobj = resources.get("/XObject", {}).get(str(operands[0])) if resources is not None else None
                if xobj is not None and xobj.get("/Subtype") == pikepdf.Name("/Form"):
                    walk(xobj, xobj.get("/Resources", resources), stack, page_id, depth + 1)
    for page in pdf.pages:
        walk(page, page.obj.get("/Resources"), [], page.objgen, 0)
    return found


def _subtree(el):
    yield el
    for k in el["kids"]:
        yield from _subtree(k)


def tag_is_empty(el, with_text: set) -> bool:
    """A text tag must show text. A tag that holds a figure is not empty."""
    nodes = list(_subtree(el))
    return el["type"] in TEXT_TAGS and not any(n["type"] == "Figure" for n in nodes) \
        and not any(m in with_text for n in nodes for m in n["mcids"])


def order_decreases(mcids: list[int]) -> bool:
    """Compare MCIDs with one reference. Chrome references a page-wide wrapper MCID from several tags, so its position has no meaning."""
    once = [m for m in mcids if mcids.count(m) == 1]
    return any(b < a for a, b in zip(once, once[1:]))


def page_background(pix, bbox, fg: str) -> str:
    """Return the most common color in bbox, without pixels near the text color. A page render holds the real background."""
    r0, g0, b0 = (int(fg[i:i + 2], 16) for i in (0, 2, 4))
    x0, y0 = max(int(bbox[0]), 0), max(int(bbox[1]), 0)
    x1, y1 = min(int(bbox[2]) + 1, pix.width), min(int(bbox[3]) + 1, pix.height)
    counts: dict[tuple, int] = {}
    data, stride, n = pix.samples, pix.stride, pix.n
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = y * stride + x * n
            r, g, b = data[i], data[i + 1], data[i + 2]
            if abs(r - r0) + abs(g - g0) + abs(b - b0) > 48:
                counts[(r, g, b)] = counts.get((r, g, b), 0) + 1
    if not counts:
        return fg
    return "%02x%02x%02x" % max(counts, key=counts.get)


def check_pdf(data: bytes, ctx: Ctx):
    import pikepdf
    import pymupdf
    p = ctx.p
    try:
        pdf = pikepdf.open(io.BytesIO(data))
    except pikepdf.PasswordError:
        ctx.add("doc.encrypted", "document")
        return
    except Exception as e:
        raise Malformed(str(e))
    if pdf.is_encrypted:
        ctx.add("doc.encrypted", "document")
        return
    try:
        pages = list(pdf.pages)
        info = pdf.docinfo if "/Info" in pdf.trailer else {}
        title = str(info.get("/Title", "")) if info else ""
        mark = pdf.Root.get("/MarkInfo")
    except Exception as e:
        raise Malformed(str(e))
    if not clean(title):
        ctx.add("doc.title.missing", "document")
    elif not bool(pdf.Root.get("/ViewerPreferences", {}).get("/DisplayDocTitle", False)):
        ctx.add("doc.title.hidden", "document")
    if not clean(str(pdf.Root.get("/Lang", ""))):
        ctx.add("doc.lang.missing", "document")
    tagged = "/StructTreeRoot" in pdf.Root and mark is not None and bool(mark.get("/Marked", False))
    if not tagged:
        ctx.add("pdf.untagged", "document")
    any_text, text = False, []
    fz = pymupdf.open(stream=data, filetype="pdf")
    for i, page in enumerate(fz, 1):
        t = page.get_text()
        text.append(t)
        any_text = any_text or bool(clean(t))
        small = low = False
        pix = page.get_pixmap(colorspace=pymupdf.csRGB, alpha=False)
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if not clean(span["text"]):
                        continue
                    small = small or span["size"] < p.min_font_pt - 0.01
                    if not low:
                        fg = f"{span['color']:06x}"
                        low = low_contrast(fg, page_background(pix, span["bbox"], fg), span["size"], bool(span["flags"] & 16), p)
        if small:
            ctx.add("font.too_small", f"page:{i}")
        if low:
            ctx.add("contrast.insufficient", f"page:{i}")
    if pages and not any_text:
        ctx.add("pdf.scanned", "document")
    if not tagged:
        return
    els, order = pdf_struct(pdf)
    with_text = pdf_text_mcids(pdf)
    seq, by_page = [], {}
    for pg, mc in order:
        if (pg, mc) in with_text:
            by_page.setdefault(pg, []).append(mc)
    for e in els:
        l = f"struct:{e['n']}:{e['type']}"
        if e["type"] == "Figure" and not clean(e["alt"]):
            ctx.add("img.alt.missing", l)
        if tag_is_empty(e, with_text):
            ctx.add("tag.empty", l)
        m = re.fullmatch(r"H([1-6])", e["type"])
        if m:
            seq.append((int(m.group(1)), l))
        if e["type"] == "Table":
            kids = [x for x in pdf_struct_sub(e["ref"], rolemap_of(pdf))]
            if "TH" not in kids:
                ctx.add("table.header.missing", l)
    _heading_seq(ctx, seq, "document", " ".join(text), check_start=True)
    for i, page in enumerate(pages, 1):
        if order_decreases(by_page.get(page.objgen, [])):
            ctx.add("reading_order", f"page:{i}")


def rolemap_of(pdf):
    return pdf.Root["/StructTreeRoot"].get("/RoleMap", {})


def pdf_struct_sub(node, rolemap):
    """Resolved type names of all descendants of a struct element."""
    import pikepdf
    out = []
    k = node.get("/K")
    kids = k if isinstance(k, pikepdf.Array) else [k] if k is not None else []
    for kid in kids:
        if isinstance(kid, pikepdf.Dictionary) and "/S" in kid:
            s = _name(kid["/S"])
            out.append(_name(rolemap.get("/" + s, "/" + s)))
            out.extend(pdf_struct_sub(kid, rolemap))
    return out


# ---- scan ----

def _read(src, name):
    if isinstance(src, (bytes, bytearray)):
        return bytes(src), name or "<bytes>"
    with open(src, "rb") as f:
        return f.read(), str(src)


def convert_legacy(path: str, target: str, outdir: str) -> str:
    """Convert a legacy or ODF file with LibreOffice. Returns the new path."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError(f"Conversion of {path} failed because LibreOffice is not installed. Install LibreOffice.")
    subprocess.run([soffice, "--headless", "--convert-to", target, "--outdir", outdir, path],
                   check=True, capture_output=True, timeout=300)
    return os.path.join(outdir, os.path.splitext(os.path.basename(path))[0] + "." + target)


def scan(src, params: Params | None = None, *, name: str = "", media_probe: Callable | None = None) -> Report:
    """Scan a path or bytes. Pass name with bytes to help format detection."""
    params = params or Params()
    if not isinstance(src, (bytes, bytearray)):
        ext = os.path.splitext(str(src))[1].lower()
        if ext in LEGACY:
            with tempfile.TemporaryDirectory() as d:
                rep = scan(convert_legacy(str(src), LEGACY[ext], d), params)
                rep.source = str(src)
                return rep
    data, label = _read(src, name)
    fmt = detect(data, name or label)
    ctx = Ctx(fmt, params)
    try:
        if fmt == "html":
            check_html(data, ctx, media_probe)
        elif fmt == "pdf":
            check_pdf(data, ctx)
        else:
            pkg = Pkg(data)
            {"docx": check_docx, "pptx": check_pptx, "xlsx": check_xlsx}[fmt](pkg, ctx)
    except (Malformed, KeyError, IndexError, ValueError, StopIteration):
        ctx.findings = []
        ctx.add("doc.malformed", "document")
    return Report(label, fmt, ctx.findings)


# ---- fixes: pure byte edits keyed by finding ----

class FixError(Exception):
    pass


def fix(src, fixes: list[dict], name: str = "") -> bytes:
    """Apply fixes [{check_id, locator, value?, decorative?}] and return the new bytes."""
    data, label = _read(src, name)
    fmt = detect(data, name or label)
    if fmt == "html":
        return _fix_html(data, fixes)
    if fmt == "pdf":
        return _fix_pdf(data, fixes)
    pkg, touched = Pkg(data), set()
    fn = {"docx": _fix_docx, "pptx": _fix_pptx, "xlsx": _fix_xlsx}[fmt]
    for f in fixes:
        fn(pkg, f, touched)
    return pkg.save(touched)


def _need(f, key="value"):
    if f.get(key) in (None, ""):
        raise FixError(f"The fix for {f['check_id']} at {f['locator']} failed because {key} is empty. Provide {key}.")
    return f[key]


def _no_fix(f):
    raise FixError(f"The check {f['check_id']} has no automatic fix for {f['locator']}. Fix the source file.")


def _fix_html(data, fixes):
    tree = parse_html(data)
    for f in fixes:
        c, e = f["check_id"], html_find(tree, f["locator"])
        if c in ("img.alt.missing", "img.alt.too_long", "img.alt.filename", "img.alt.meaningless", "img.decorative.interactive"):
            e.attrs["alt"] = "" if f.get("decorative") else _need(f)
        elif c == "table.header.missing":
            rows = e.find_all("tr")
            if not rows:
                _no_fix(f)
            for cell in rows[0].els():
                if cell.tag == "td":
                    cell.tag = "th"
                    cell.attrs["scope"] = "col"
        elif c == "table.header.scope":
            e.attrs["scope"] = f.get("value") or "col"
        elif c == "table.caption.missing":
            cap = N("caption", {}, e)
            cap.kids.append(_need(f))
            e.kids.insert(0, cap)
        elif c == "table.empty":
            e.parent.kids.remove(e)
        elif c in ("link.text.generic", "heading.too_long"):
            e.kids = [_need(f)]
        elif c == "link.adjacent.duplicate":
            sibs = e.parent.kids
            i = next(n for n, k in enumerate(sibs) if k is e)
            j = i - 1
            while not isinstance(sibs[j], N):
                j -= 1
            sibs[j].kids.extend([" "] + e.kids)
            for k in e.kids:
                if isinstance(k, N):
                    k.parent = sibs[j]
            del sibs[j + 1:i + 1]
        elif c == "link.iframe.title":
            e.attrs["title"] = _need(f)
        elif c == "font.too_small":
            _set_style(e, "font-size", f"{Params().min_font_pt}pt")
        elif c == "contrast.insufficient":
            _set_style(e, "color", "#" + _need(f).lstrip("#"))
        elif c in ("heading.nesting", "heading.depth"):
            e.tag = f"h{int(_need(f))}"
        else:
            _no_fix(f)
    return ((getattr(tree, "doctype", "") + "\n") if getattr(tree, "doctype", "") else "").encode() + tree.serialize().encode()


def _set_style(e, prop, value):
    st = e.style()
    st[prop] = value
    e.attrs["style"] = "; ".join(f"{k}: {v}" for k, v in st.items())


def _set_decorative(cnv):
    from lxml import etree
    ext_lst = cnv.find(q("a:extLst"))
    if ext_lst is None:
        ext_lst = etree.SubElement(cnv, q("a:extLst"))
    ext = etree.SubElement(ext_lst, q("a:ext"), uri=ADEC_URI)
    etree.SubElement(ext, f"{{{ADEC_NS}}}decorative", {"val": "1"}, nsmap={"adec": ADEC_NS})
    cnv.set("descr", "")


def _set_alt(cnv, f):
    if f.get("decorative"):
        _set_decorative(cnv)
    else:
        cnv.set("descr", _need(f))


def _set_title(pkg: Pkg, value: str, touched: set):
    from lxml import etree
    if not pkg.has(CORE):
        pkg.add(CORE, (f'<cp:coreProperties xmlns:cp="{NS["cp"]}" xmlns:dc="{NS["dc"]}"/>').encode())
        ct = pkg.xml("[Content_Types].xml")
        etree.SubElement(ct, q("ct:Override"), PartName="/" + CORE, ContentType=CORE_TYPE)
        touched.add("[Content_Types].xml")
        rels = pkg.xml("_rels/.rels")
        etree.SubElement(rels, q("rel:Relationship"), Id="rIdCore", Type=CORE_REL, Target=CORE)
        touched.add("_rels/.rels")
    core = pkg.xml(CORE)
    t = core.find(q("dc:title"))
    if t is None:
        t = etree.SubElement(core, q("dc:title"))
    t.text = value
    if CORE in pkg.names:
        touched.add(CORE)


def _nth(root, tag, locator):
    m = re.search(r"\[(\d+)\]$", locator)
    return list(root.iter(q(tag)))[int(m.group(1)) - 1]


def _ensure(parent, tag, first=True):
    from lxml import etree
    e = parent.find(q(tag))
    if e is None:
        e = etree.Element(q(tag))
        parent.insert(0, e) if first else parent.append(e)
    return e


def _fix_docx(pkg, f, touched):
    from lxml import etree
    c, part = f["check_id"], "word/document.xml"
    if c == "doc.title.missing":
        return _set_title(pkg, _need(f), touched)
    if c in ("doc.lang.missing", "doc.lang.wrong"):
        val = _need(f)
        st = pkg.xml("word/styles.xml")
        pr = _ensure(_ensure(_ensure(st, "w:docDefaults"), "w:rPrDefault"), "w:rPr")
        _ensure(pr, "w:lang", first=False).set(q("w:val"), val)
        touched.add("word/styles.xml")
        for el in pkg.xml(part).iter(q("w:lang")):
            el.set(q("w:val"), val)
        touched.add(part)
        return
    doc, touched_ = pkg.xml(part), touched.add(part)
    w = lambda n: q(f"w:{n}")
    if c == "img.alt.missing":
        _set_alt(_nth(doc, "wp:docPr", f["locator"]), f)
    elif c == "table.header.missing":
        tr = _nth(doc, "w:tbl", f["locator"]).find(w("tr"))
        _ensure(_ensure(tr, "w:trPr"), "w:tblHeader")
    elif c == "table.caption.missing":
        t = _nth(doc, "w:tbl", f["locator"])
        _ensure(_ensure(t, "w:tblPr"), "w:tblCaption", first=False).set(w("val"), _need(f))
    elif c in ("heading.start", "heading.nesting", "heading.depth"):
        _ensure(_ensure(_nth(doc, "w:p", f["locator"]), "w:pPr"), "w:pStyle").set(w("val"), f"Heading{int(_need(f))}")
    elif c == "link.text.generic":
        ts = list(_nth(doc, "w:hyperlink", f["locator"]).iter(w("t")))
        if not ts:
            _no_fix(f)
        ts[0].text = _need(f)
        for t in ts[1:]:
            t.text = ""
    elif c == "font.too_small":
        pr = _nth(doc, "w:r", f["locator"]).find(w("rPr"))
        val = str(round(Params().min_font_pt * 2))
        for tag in ("w:sz", "w:szCs"):
            if pr.find(q(tag)) is not None or tag == "w:sz":
                _ensure(pr, tag, first=False).set(w("val"), val)
    elif c == "text.justified":
        _nth(doc, "w:p", f["locator"]).find(w("pPr")).find(w("jc")).set(w("val"), "left")
    elif c == "contrast.insufficient":
        _ensure(_nth(doc, "w:r", f["locator"]).find(w("rPr")), "w:color", first=False).set(w("val"), _need(f).lstrip("#").upper())
    else:
        _no_fix(f)


def _pptx_target(pkg, locator):
    m = re.fullmatch(r"slide:(\d+)(?:/shape:(\d+))?(?:/run:(\d+))?", locator)
    part = _slides(pkg)[int(m.group(1)) - 1]
    tree = pkg.xml(part)
    shape = next((s for s in _shapes(tree) if _cnv(s).get("id") == m.group(2)), None) if m.group(2) else None
    run = list(shape.iter(q("a:r")))[int(m.group(3)) - 1] if m.group(3) else None
    return part, tree, shape, run


def _fix_pptx(pkg, f, touched):
    from lxml import etree
    c = f["check_id"]
    if c == "doc.title.missing":
        return _set_title(pkg, _need(f), touched)
    if c in ("doc.lang.missing", "doc.lang.wrong"):
        val, pres = _need(f), pkg.xml("ppt/presentation.xml")
        d = _ensure(_ensure(pres, "p:defaultTextStyle", first=False), "a:defPPr")
        _ensure(d, "a:defRPr").set("lang", val)
        touched.add("ppt/presentation.xml")
        for part in _slides(pkg):
            for el in pkg.xml(part).iter(q("a:rPr"), q("a:endParaRPr")):
                if el.get("lang"):
                    el.set("lang", val)
            touched.add(part)
        return
    part, tree, shape, run = _pptx_target(pkg, f["locator"])
    touched.add(part)
    if c == "img.alt.missing":
        _set_alt(_cnv(shape), f)
    elif c == "table.header.missing":
        _ensure(next(shape.iter(q("a:tbl"))), "a:tblPr").set("firstRow", "1")
    elif c == "link.text.generic":
        run.find(q("a:t")).text = _need(f)
    elif c == "font.too_small":
        run.find(q("a:rPr")).set("sz", str(round(Params().min_font_pt * 100)))
    elif c == "contrast.insufficient":
        fill = _ensure(run.find(q("a:rPr")), "a:solidFill")
        for k in list(fill):
            fill.remove(k)
        etree.SubElement(fill, q("a:srgbClr"), val=_need(f).lstrip("#").upper())
    elif c == "reading_order":
        shapes = _shapes(tree)
        t = next(s for s in shapes if ln(s) == "sp" and _ph_title(s))
        parent = shapes[0].getparent()
        t.getparent().remove(t)
        parent.insert(parent.index(shapes[0]), t)
    elif c == "slide.title.missing":
        shapes = _shapes(tree)
        title = next((s for s in shapes if ln(s) == "sp" and _ph_title(s)), None)
        if title is not None:
            ts = list(title.iter(q("a:t")))
            if ts:
                ts[0].text = _need(f)
                return
            body = title.find(q("p:txBody"))
            title.remove(body)
        new_id = max([int(_cnv(s).get("id")) for s in shapes] + [1]) + 1
        xml = (f'<p:sp xmlns:p="{NS["p"]}" xmlns:a="{NS["a"]}"><p:nvSpPr><p:cNvPr id="{new_id}" name="Title"/>'
               f'<p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/>'
               f'<a:p><a:r><a:t/></a:r></a:p></p:txBody></p:sp>')
        sp = title if title is not None else etree.fromstring(xml)
        if title is not None:
            sp.append(etree.fromstring(xml).find(q("p:txBody")))
        else:
            root = next(tree.iter(q("p:spTree")))
            pos = max((root.index(x) + 1 for x in root if ln(x) in ("nvGrpSpPr", "grpSpPr")), default=0)
            root.insert(pos, sp)
        next(sp.iter(q("a:t"))).text = _need(f)
    else:
        _no_fix(f)


def _set_cell_text(c, value):
    from lxml import etree
    for k in list(c):
        c.remove(k)
    c.set("t", "inlineStr")
    etree.SubElement(etree.SubElement(c, q("s:is")), q("s:t")).text = value


def _bump_xf(pkg, c, touched, mutate):
    """Clone the cell's font and xf, apply mutate to the new font, and point the cell at it."""
    from copy import deepcopy
    st = pkg.xml("xl/styles.xml")
    fonts, xfs = st.find(q("s:fonts")), st.find(q("s:cellXfs"))
    xf = deepcopy(xfs[int(c.get("s") or 0)])
    font = deepcopy(fonts[int(xf.get("fontId") or 0)])
    mutate(font)
    fonts.append(font)
    fonts.set("count", str(len(fonts)))
    xf.set("fontId", str(len(fonts) - 1))
    xf.set("applyFont", "1")
    xfs.append(xf)
    xfs.set("count", str(len(xfs)))
    c.set("s", str(len(xfs) - 1))
    touched.add("xl/styles.xml")


def _fix_xlsx(pkg, f, touched):
    from lxml import etree
    c = f["check_id"]
    if c == "doc.title.missing":
        return _set_title(pkg, _need(f), touched)
    sheet_name, ref = f["locator"].rsplit("!", 1)
    part = dict(_sheets(pkg))[sheet_name]
    sheet = pkg.xml(part)
    touched.add(part)
    cells = {x.get("r"): x for x in sheet.iter(q("s:c"))}
    if c == "xlsx.a1.empty":
        cell = cells.get("A1")
        if cell is None:
            data = sheet.find(q("s:sheetData"))
            row = next((r for r in data if r.get("r") == "1"), None)
            if row is None:
                row = etree.Element(q("s:row"), r="1")
                data.insert(0, row)
            cell = etree.Element(q("s:c"), r="A1")
            row.insert(0, cell)
        _set_cell_text(cell, f.get("value") or sheet_name)
    elif c == "link.text.generic":
        _set_cell_text(cells[ref], _need(f))
    elif c == "img.alt.missing":
        rels = pkg.rels(part)
        dpart = rels[sheet.find(q("s:drawing")).get(q("r:id"))]
        sid = ref.split(":")[1]
        cnv = next(x for x in pkg.xml(dpart).iter() if ln(x) == "cNvPr" and x.get("id") == sid)
        _set_alt(cnv, f)
        touched.add(dpart)
    elif c == "table.header.missing":
        rels = pkg.rels(part)
        shared = _shared(pkg)
        for tp in sheet.iter(q("s:tablePart")):
            tpart = rels[tp.get(q("r:id"))]
            t = pkg.xml(tpart)
            if t.get("ref").split(":")[0] == ref:
                t.attrib.pop("headerRowCount", None)
                row = re.search(r"\d+", ref).group(0)
                start = re.match(r"[A-Z]+", ref).group(0)
                cols = t.find(q("s:tableColumns"))
                col = _col_index(start)
                for i, tc in enumerate(cols):
                    cell = cells.get(f"{_col_name(col + i)}{row}")
                    if cell is None or not clean(_cell_text(cell, shared)):
                        raise FixError(f"The fix for {f['locator']} failed because the first row has empty cells. Fill the first row.")
                    tc.set("name", _cell_text(cell, shared))
                touched.add(tpart)
    elif c == "font.too_small":
        def m(font):
            _ensure(font, "s:sz").set("val", str(Params().min_font_pt))
        _bump_xf(pkg, cells[ref], touched, m)
    elif c == "contrast.insufficient":
        def m(font):
            _ensure(font, "s:color").attrib.clear()
            font.find(q("s:color")).set("rgb", "FF" + _need(f).lstrip("#").upper())
        _bump_xf(pkg, cells[ref], touched, m)
    else:
        _no_fix(f)


def _col_index(s):
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n


def _col_name(n):
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def pdf_rewrite_risks(pdf) -> list[str]:
    risks = []
    if "/AcroForm" in pdf.Root:
        risks.append("form fields")
        if "/SigFlags" in pdf.Root["/AcroForm"]:
            risks.append("signatures")
    return risks


def _fix_pdf(data, fixes):
    import pikepdf
    pdf = pikepdf.open(io.BytesIO(data))
    els = {f"struct:{e['n']}:{e['type']}": e for e in pdf_struct(pdf)[0]}
    for f in fixes:
        c = f["check_id"]
        if c == "doc.title.missing":
            v = _need(f)
            pdf.docinfo["/Title"] = v
            with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                meta["dc:title"] = v
            vp = pdf.Root.get("/ViewerPreferences")
            if vp is None:
                pdf.Root["/ViewerPreferences"] = pikepdf.Dictionary(DisplayDocTitle=True)
            else:
                vp["/DisplayDocTitle"] = True
        elif c == "doc.title.hidden":
            vp = pdf.Root.get("/ViewerPreferences")
            if vp is None:
                pdf.Root["/ViewerPreferences"] = pikepdf.Dictionary(DisplayDocTitle=True)
            else:
                vp["/DisplayDocTitle"] = True
        elif c == "tag.empty" and f["locator"] in els:
            els[f["locator"]]["ref"]["/S"] = pikepdf.Name("/Div")
        elif c == "doc.lang.missing":
            pdf.Root["/Lang"] = _need(f)
        elif c == "img.alt.missing" and f["locator"] in els:
            node = els[f["locator"]]["ref"]
            if f.get("decorative"):
                node["/S"] = pikepdf.Name("/Artifact")
            else:
                node["/Alt"] = _need(f)
        else:
            _no_fix(f)
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


# ---- optional: media probe and Canvas crawl ----

def probe_media(url: str) -> str:
    """Return manual, auto, none or private. Needs yt-dlp and network access."""
    import yt_dlp
    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "no_warnings": True}) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError:
            return "private"
    if info.get("subtitles"):
        return "manual"
    return "auto" if info.get("automatic_captions") else "none"


def scan_canvas(course_id, token: str, base_url: str, params=None, media_probe=None) -> list[Report]:
    """Scan the pages, assignments, discussions, quizzes and files of one course."""
    from canvasapi import Canvas
    course = Canvas(base_url, token).get_course(course_id)
    out = []

    def html_item(label, body):
        if body:
            out.append(scan((body or "").encode(), params, name=f"{label}.html", media_probe=media_probe))
            out[-1].source = label
    for pg in course.get_pages():
        html_item(f"page/{pg.url}", course.get_page(pg.url).body)
    for a in course.get_assignments():
        html_item(f"assignment/{a.id}", a.description)
    for d in course.get_discussion_topics():
        html_item(f"discussion/{d.id}", d.message)
    for qz in course.get_quizzes():
        html_item(f"quiz/{qz.id}", qz.description)
    for fl in course.get_files():
        name = fl.display_name
        if os.path.splitext(name)[1].lower().lstrip(".") in ("pdf", "docx", "pptx", "xlsx", "html", "htm"):
            with urllib.request.urlopen(fl.url) as r:
                rep = scan(r.read(), params, name=name)
            rep.source = f"file/{name}"
            out.append(rep)
    return out


# ---- CLI ----

SEV_RANK = {"minor": 0, "major": 1, "severe": 2}


def _print(reports, fmt, min_sev):
    keep = lambda f: SEV_RANK[f.severity] >= SEV_RANK[min_sev]
    if fmt == "json":
        print(json.dumps([{**r.to_dict(), "findings": [asdict(f) for f in r.findings if keep(f)]} for r in reports], indent=2))
    elif fmt == "sarif":
        print(json.dumps(sarif(reports), indent=2))
    else:
        for r in reports:
            print(f"{r.source} [{r.format}] estimated score {r.score}")
            for f in sorted(r.findings, key=lambda f: (-SEV_RANK[f.severity], f.check_id, f.locator)):
                if keep(f):
                    print(f"  {f.severity:<6} {f.check_id:<28} {f.locator}\n         {f.message}")


def _exit_code(reports, fail_on):
    if not fail_on:
        return 0
    return int(any(SEV_RANK[f.severity] >= SEV_RANK[fail_on] for r in reports for f in r.findings))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="panocheck", description="Document accessibility checker and fixer")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(s):
        s.add_argument("--format", choices=["text", "json", "sarif"], default="text")
        s.add_argument("--min-severity", choices=list(SEV_RANK), default="minor")
        s.add_argument("--fail-on", choices=list(SEV_RANK))
        s.add_argument("--min-font", type=float)
        s.add_argument("--probe-media", action="store_true", help="probe linked video captions (needs yt-dlp)")
    s = sub.add_parser("scan", help="scan files")
    s.add_argument("files", nargs="+")
    common(s)
    s = sub.add_parser("canvas", help="scan one Canvas course")
    s.add_argument("course_id")
    s.add_argument("--token-env", default="CANVAS_TOKEN")
    s.add_argument("--base-url", default="https://montana.instructure.com")
    common(s)
    s = sub.add_parser("score", help="print the estimated score of a JSON report")
    s.add_argument("report")
    s = sub.add_parser("fix", help="apply a fixes file")
    s.add_argument("file")
    s.add_argument("--apply", required=True, help="JSON list of {check_id, locator, value, decorative}")
    s.add_argument("-o", "--output")
    a = ap.parse_args(argv)

    if a.cmd == "score":
        with open(a.report) as f:
            doc = json.load(f)
        items = doc if isinstance(doc, list) else [doc]
        vals = [score(r["findings"]) for r in items]
        print(round(sum(vals) / len(vals)) if vals else 100)
        return 0
    if a.cmd == "fix":
        with open(a.apply) as f:
            fixes = json.load(f)
        root, ext = os.path.splitext(a.file)
        out = a.output or f"{root}-accessible{ext}"
        with open(a.file, "rb") as f:
            data = f.read()
        if ext.lower() == ".pdf":
            import pikepdf
            risks = pdf_rewrite_risks(pikepdf.open(io.BytesIO(data)))
            if risks:
                print(f"Warning: the rewrite can damage {', '.join(risks)}. Examine the output.", file=sys.stderr)
        new = fix(data, fixes, name=a.file)
        with open(out, "wb") as f:
            f.write(new)
        print(out)
        return 0
    params = Params(**({"min_font_pt": a.min_font} if a.min_font else {}))
    probe = probe_media if a.probe_media else None
    if a.cmd == "scan":
        reports = [scan(f, params, media_probe=probe) for f in a.files]
    else:
        token = os.environ.get(a.token_env)
        if not token:
            print(f"The Canvas scan failed because {a.token_env} is not set. Set {a.token_env}.", file=sys.stderr)
            return 2
        reports = scan_canvas(a.course_id, token, a.base_url, params, probe)
    _print(reports, a.format, a.min_severity)
    return _exit_code(reports, a.fail_on)


if __name__ == "__main__":
    sys.exit(main())
