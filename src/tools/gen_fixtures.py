#!/usr/bin/env python3
"""Generate fixtures/ and fixtures/expected.json. Expected findings are written by hand here."""
import io, json, pathlib, shutil, zipfile
import pikepdf, yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT.parent / "fixtures"
SPEC = yaml.safe_load((ROOT / "spec/checks.yaml").read_text())
SEV = {c["id"]: c["severity"] for c in SPEC["checks"]}
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
P = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
XDR = 'xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RELS = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'
CT = 'xmlns="http://schemas.openxmlformats.org/package/2006/content-types"'
fixtures = []


def zipped(parts):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0)), data)
    return b.getvalue()


def core(title):
    return f'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{title}</dc:title></cp:coreProperties>'


def pkg(main, main_type, rest, overrides=(), title="T"):
    ov = "".join(f'<Override PartName="/{p}" ContentType="{t}"/>' for p, t in overrides)
    parts = {
        "[Content_Types].xml": f'<Types {CT}><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/{main}" ContentType="{main_type}"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>{ov}</Types>',
        "_rels/.rels": f'<Relationships {RELS}><Relationship Id="rId1" Type="{REL}/officeDocument" Target="{main}"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>',
        "docProps/core.xml": core(title),
    }
    parts.update(rest)
    return zipped(parts)


# ---- builders ----

def html(body):
    return f'<!doctype html><html lang="en"><head><title>T</title></head><body>{body}</body></html>'.encode()


H1 = '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Title</w:t></w:r></w:p>'


def docx(body=H1, title="T", lang="en-US"):
    l = f'<w:docDefaults><w:rPrDefault><w:rPr><w:lang w:val="{lang}"/></w:rPr></w:rPrDefault></w:docDefaults>' if lang else ""
    return pkg("word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml", {
        "word/document.xml": f"<w:document {W}><w:body>{body}</w:body></w:document>",
        "word/styles.xml": f"<w:styles {W}>{l}</w:styles>",
    }, [("word/styles.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml")], title)


def title_sp(text="Title", id_=2):
    return f'<p:sp><p:nvSpPr><p:cNvPr id="{id_}" name="T"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>'


def box(runs, id_=3, fill=""):
    return f'<p:sp><p:nvSpPr><p:cNvPr id="{id_}" name="B"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>{fill}</p:spPr><p:txBody><a:bodyPr/><a:p>{runs}</a:p></p:txBody></p:sp>'


def pptx(shapes=None, title="T", lang="en-US"):
    shapes = title_sp() if shapes is None else shapes
    d = f'<p:defaultTextStyle><a:defPPr><a:defRPr lang="{lang}"/></a:defPPr></p:defaultTextStyle>' if lang else ""
    return pkg("ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml", {
        "ppt/presentation.xml": f'<p:presentation {P}><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>{d}</p:presentation>',
        "ppt/_rels/presentation.xml.rels": f'<Relationships {RELS}><Relationship Id="rId1" Type="{REL}/slide" Target="slides/slide1.xml"/></Relationships>',
        "ppt/slides/slide1.xml": f'<p:sld {P}><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>{shapes}</p:spTree></p:cSld></p:sld>',
    }, [("ppt/slides/slide1.xml", "application/vnd.openxmlformats-officedocument.presentationml.slide+xml")], title)


STYLES = f'<styleSheet {S}><fonts count="1"><font><sz val="11"/></font></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills><cellXfs count="1"><xf fontId="0" fillId="0"/></cellXfs></styleSheet>'
A1 = '<c r="A1" t="inlineStr"><is><t>Sheet title</t></is></c>'


def xlsx(rows=f'<row r="1">{A1}</row>', tail="", extra=None, sheet_rels="", styles=STYLES, title="T"):
    parts = {
        "xl/workbook.xml": f'<workbook {S}><sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships {RELS}><Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{REL}/styles" Target="styles.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": f'<worksheet {S}><sheetData>{rows}</sheetData>{tail}</worksheet>',
        "xl/styles.xml": styles,
    }
    if sheet_rels:
        parts["xl/worksheets/_rels/sheet1.xml.rels"] = f"<Relationships {RELS}>{sheet_rels}</Relationships>"
    parts.update(extra or {})
    return pkg("xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml", parts, [], title)


def pdf(ops=None, struct=None, title="T", lang="en-US", tagged=True, encrypt=False, show_title=True):
    """ops is a content stream. struct is a function(pdf, page) that returns the root K value."""
    ops = "/H1 <</MCID 0>> BDC BT /F1 24 Tf 72 700 Td (Title) Tj ET EMC /P <</MCID 1>> BDC BT /F1 12 Tf 72 670 Td (Body text) Tj ET EMC" if ops is None else ops
    d = pikepdf.new()
    d.add_blank_page(page_size=(612, 792))
    page = d.pages[0]
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica)))
    page.Contents = d.make_stream(ops.encode())
    if title:
        d.docinfo["/Title"] = title
        if show_title:
            d.Root.ViewerPreferences = pikepdf.Dictionary(DisplayDocTitle=True)
    if lang:
        d.Root.Lang = lang
    if tagged:
        struct = struct or (lambda d, pg: [el(d, "H1", pg, 0), el(d, "P", pg, 1)])
        kids = struct(d, page.obj)
        doc = d.make_indirect(pikepdf.Dictionary(S=pikepdf.Name.Document, K=pikepdf.Array(kids)))
        d.Root.StructTreeRoot = d.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.StructTreeRoot, K=doc))
        d.Root.MarkInfo = pikepdf.Dictionary(Marked=True)
    b = io.BytesIO()
    if encrypt:
        d.save(b, encryption=pikepdf.Encryption(user="", owner="o"))
    else:
        d.save(b, deterministic_id=True)
    return b.getvalue()


def el(d, s, pg, k, **extra):
    node = pikepdf.Dictionary(S=pikepdf.Name("/" + s), Pg=pg, **extra)
    if k is not None:
        node.K = k if isinstance(k, (int, pikepdf.Array)) else pikepdf.Array(k)
    return d.make_indirect(node)


def add(fmt, check, kind, data, expected=(), probe=None):
    ext = fmt
    fixtures.append((f"{fmt}/{check}/{kind}.{ext}", data, list(expected), probe))


def f(check, *locs):
    return [(check, l) for l in locs]


D = "word/document.xml#"
B = "html > body > "

# ---- HTML ----
add("html", "img.alt.missing", "pass-1", html('<h1>T</h1><img src="a.png" alt="Campus map">'))
add("html", "img.alt.missing", "fail-1", html('<h1>T</h1><img src="a.png">'), f("img.alt.missing", B + "img:nth-of-type(1)"))
add("html", "img.alt.too_long", "pass-1", html(f'<img src="a.png" alt="{"x " * 59}x">'))
add("html", "img.alt.too_long", "fail-1", html(f'<img src="a.png" alt="{"x " * 70}">'), f("img.alt.too_long", B + "img:nth-of-type(1)"))
add("html", "img.alt.filename", "pass-1", html('<img src="a.png" alt="A bobcat">'))
add("html", "img.alt.filename", "fail-1", html('<img src="a.png" alt="IMG_0042.JPG">'), f("img.alt.filename", B + "img:nth-of-type(1)"))
add("html", "img.alt.meaningless", "pass-1", html('<img src="a.png" alt="Lab photo of a circuit">'))
add("html", "img.alt.meaningless", "fail-1", html('<img src="a.png" alt="Image">'), f("img.alt.meaningless", B + "img:nth-of-type(1)"))
add("html", "img.decorative.interactive", "pass-1", html('<a href="x"><img src="a.png" alt="">Home page</a>'))
add("html", "img.decorative.interactive", "fail-1", html('<a href="x"><img src="a.png" alt=""></a>'), f("img.decorative.interactive", B + "a:nth-of-type(1) > img:nth-of-type(1)"))
add("html", "media.captions.missing", "pass-1", html('<video src="a.mp4"><track kind="captions" src="a.vtt"></video>'))
add("html", "media.captions.missing", "fail-1", html('<video src="a.mp4"></video>'), f("media.captions.missing", B + "video:nth-of-type(1)"))
YT = "https://youtube.com/embed/abc"
add("html", "media.captions.auto", "pass-1", html(f'<iframe title="V" src="{YT}"></iframe>'), probe={YT: "manual"})
add("html", "media.captions.auto", "fail-1", html(f'<iframe title="V" src="{YT}"></iframe>'), f("media.captions.auto", B + "iframe:nth-of-type(1)"), probe={YT: "auto"})
add("html", "media.private", "pass-1", html(f'<iframe title="V" src="{YT}"></iframe>'), probe={YT: "manual"})
add("html", "media.private", "fail-1", html(f'<iframe title="V" src="{YT}"></iframe>'), f("media.private", B + "iframe:nth-of-type(1)"), probe={YT: "private"})
add("html", "heading.none", "pass-1", html("<h1>T</h1><p>" + "word " * 40 + "</p>"))
add("html", "heading.none", "fail-1", html("<p>" + "word " * 40 + "</p>"), f("heading.none", "html > body"))
add("html", "heading.nesting", "pass-1", html("<h1>A</h1><h2>B</h2><h3>C</h3><h2>D</h2>"))
add("html", "heading.nesting", "fail-1", html("<h1>A</h1><h3>B</h3>"), f("heading.nesting", B + "h3:nth-of-type(1)"))
add("html", "heading.depth", "pass-1", html("<h1>A</h1><h2>B</h2><h3>C</h3><h4>D</h4>"))
add("html", "heading.depth", "fail-1", html("<h1>A</h1><h2>B</h2><h3>C</h3><h4>D</h4><h5>E</h5>"), f("heading.depth", B + "h5:nth-of-type(1)"))
add("html", "heading.too_long", "pass-1", html("<h1>Short</h1>"))
add("html", "heading.too_long", "fail-1", html(f"<h1>{'long ' * 30}</h1>"), f("heading.too_long", B + "h1:nth-of-type(1)"))
TBL = '<table><caption>C</caption><tr><th scope="col">H</th></tr><tr><td>1</td></tr></table>'
TP = B + "table:nth-of-type(1)"
add("html", "table.header.missing", "pass-1", html(TBL))
add("html", "table.header.missing", "fail-1", html("<table><caption>C</caption><tr><td>1</td></tr></table>"), f("table.header.missing", TP))
add("html", "table.header.scope", "pass-1", html(TBL))
add("html", "table.header.scope", "fail-1", html("<table><caption>C</caption><tr><th>H</th></tr></table>"), f("table.header.scope", TP + " > tbody:nth-of-type(1) > tr:nth-of-type(1) > th:nth-of-type(1)"))
add("html", "table.caption.missing", "pass-1", html(TBL))
add("html", "table.caption.missing", "fail-1", html('<table><tr><th scope="col">H</th></tr></table>'), f("table.caption.missing", TP))
add("html", "table.empty", "pass-1", html(TBL))
add("html", "table.empty", "fail-1", html("<table><tr><td> </td></tr></table>"), f("table.empty", TP))
add("html", "contrast.insufficient", "pass-1", html('<p style="color:#111">Dark</p>'))
add("html", "contrast.insufficient", "pass-2", html('<p style="color:#808080; font-size:24pt">Large gray</p>'))
add("html", "contrast.insufficient", "fail-1", html('<p style="color:#aaaaaa">Light</p>'), f("contrast.insufficient", B + "p:nth-of-type(1)"))
add("html", "contrast.insufficient", "fail-2", html('<div style="background-color:#000"><p style="color:rgb(40,40,40)">Dark on dark</p></div>'), f("contrast.insufficient", B + "div:nth-of-type(1) > p:nth-of-type(1)"))
add("html", "link.text.generic", "pass-1", html('<a href="x">Course syllabus</a>'))
add("html", "link.text.generic", "fail-1", html('<a href="x">Click here</a>'), f("link.text.generic", B + "a:nth-of-type(1)"))
add("html", "link.adjacent.duplicate", "pass-1", html('<a href="x">One link</a> <a href="y">Two link</a>'))
add("html", "link.adjacent.duplicate", "fail-1", html('<a href="x">One link</a> <a href="x">Two link</a>'), f("link.adjacent.duplicate", B + "a:nth-of-type(2)"))
add("html", "link.iframe.title", "pass-1", html('<iframe title="Map" src="m.html"></iframe>'))
add("html", "link.iframe.title", "fail-1", html('<iframe src="m.html"></iframe>'), f("link.iframe.title", B + "iframe:nth-of-type(1)"))
add("html", "font.too_small", "pass-1", html('<p style="font-size:9pt">Ok</p>'))
add("html", "font.too_small", "fail-1", html('<p style="font-size:8px">Tiny</p>'), f("font.too_small", B + "p:nth-of-type(1)"))
add("html", "list.not_marked", "pass-1", html("<ul><li>One</li><li>Two</li></ul>"))
add("html", "list.not_marked", "fail-1", html("<p>1. One</p><p>2. Two</p><p>3. Three</p>"), f("list.not_marked", B + "p:nth-of-type(1)"))
add("html", "content.too_long", "pass-1", html("<h1>T</h1><p>" + "word " * 100 + "</p>"))
add("html", "content.too_long", "fail-1", html("<h1>T</h1><p>" + "word " * 3001 + "</p>"), f("content.too_long", "html > body"))
add("html", "target.too_small", "pass-1", html('<button style="width:44px;height:44px">Go now</button>'))
add("html", "target.too_small", "fail-1", html('<button style="width:10px">Go now</button>'), f("target.too_small", B + "button:nth-of-type(1)"))

# ---- DOCX ----
def para(text, style=None, extra=""):
    st = f'<w:pStyle w:val="{style}"/>' if style else ""
    return f"<w:p><w:pPr>{st}{extra}</w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>"


def pic(descr=None, anchor=False):
    d = f' descr="{descr}"' if descr is not None else ""
    tag = "anchor" if anchor else "inline"
    return f'<w:p><w:r><w:drawing><wp:{tag}><wp:docPr id="1" name="P"{d}/></wp:{tag}></w:drawing></w:r></w:p>'


def tbl(header=True, caption=True):
    c = '<w:tblCaption w:val="C"/>' if caption else ""
    h = "<w:trPr><w:tblHeader/></w:trPr>" if header else ""
    return f"<w:tbl><w:tblPr>{c}</w:tblPr><w:tr>{h}<w:tc><w:p><w:r><w:t>H</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"


EN = "the cat and the dog of this town are in the park with you for a walk on the path that is near the river as the sun sets and the people go to the shop in the old part of the town"
ES = "el perro y la casa de los amigos que viven en la ciudad con una familia para el trabajo por la tarde en el centro de la ciudad y los hijos de la familia son del pueblo en una calle"
add("docx", "doc.malformed", "pass-1", docx())
add("docx", "doc.malformed", "fail-1", zipped({"[Content_Types].xml": "<Types/>", "word/document.xml": "<w:document><broken"}), f("doc.malformed", "document"))
add("docx", "doc.title.missing", "pass-1", docx())
add("docx", "doc.title.missing", "fail-1", docx(title=""), f("doc.title.missing", "docProps/core.xml#dc:title"))
add("docx", "doc.lang.missing", "pass-1", docx())
add("docx", "doc.lang.missing", "fail-1", docx(lang=None), f("doc.lang.missing", "word/styles.xml#w:docDefaults"))
add("docx", "doc.lang.wrong", "pass-1", docx(H1 + para(EN)))
add("docx", "doc.lang.wrong", "fail-1", docx(H1 + para(ES)), f("doc.lang.wrong", "word/styles.xml#w:docDefaults"))
add("docx", "img.alt.missing", "pass-1", docx(H1 + pic("Campus map")))
add("docx", "img.alt.missing", "fail-1", docx(H1 + pic()), f("img.alt.missing", D + "(//wp:docPr)[1]"))
add("docx", "img.not_inline", "pass-1", docx(H1 + pic("Map")))
add("docx", "img.not_inline", "fail-1", docx(H1 + pic("Map", anchor=True)), f("img.not_inline", D + "(//wp:anchor)[1]"))
add("docx", "heading.none", "pass-1", docx(H1 + para("word " * 40)))
add("docx", "heading.none", "fail-1", docx(para("word " * 40)), f("heading.none", D + "w:body"))
add("docx", "heading.start", "pass-1", docx())
add("docx", "heading.start", "fail-1", docx(para("A", "Heading2")), f("heading.start", D + "(//w:p)[1]"))
add("docx", "heading.nesting", "pass-1", docx(H1 + para("B", "Heading2")))
add("docx", "heading.nesting", "fail-1", docx(H1 + para("B", "Heading3")), f("heading.nesting", D + "(//w:p)[2]"))
add("docx", "heading.depth", "pass-1", docx(H1 + para("B", "Heading2") + para("C", "Heading3") + para("D", "Heading4")))
add("docx", "heading.depth", "fail-1", docx(H1 + para("B", "Heading2") + para("C", "Heading3") + para("D", "Heading4") + para("E", "Heading5")), f("heading.depth", D + "(//w:p)[5]"))
add("docx", "table.header.missing", "pass-1", docx(H1 + tbl()))
add("docx", "table.header.missing", "fail-1", docx(H1 + tbl(header=False)), f("table.header.missing", D + "(//w:tbl)[1]"))
add("docx", "table.caption.missing", "pass-1", docx(H1 + tbl()))
add("docx", "table.caption.missing", "fail-1", docx(H1 + tbl(caption=False)), f("table.caption.missing", D + "(//w:tbl)[1]"))
RUN = lambda pr, t="Text": f"<w:p><w:r><w:rPr>{pr}</w:rPr><w:t>{t}</w:t></w:r></w:p>"
add("docx", "contrast.insufficient", "pass-1", docx(H1 + RUN('<w:color w:val="111111"/>')))
add("docx", "contrast.insufficient", "fail-1", docx(H1 + RUN('<w:color w:val="AAAAAA"/>')), f("contrast.insufficient", D + "(//w:r)[2]"))
add("docx", "link.text.generic", "pass-1", docx(H1 + '<w:p><w:hyperlink r:id="rId9"><w:r><w:t>Course syllabus</w:t></w:r></w:hyperlink></w:p>'))
add("docx", "link.text.generic", "fail-1", docx(H1 + '<w:p><w:hyperlink r:id="rId9"><w:r><w:t>click here</w:t></w:r></w:hyperlink></w:p>'), f("link.text.generic", D + "(//w:hyperlink)[1]"))
add("docx", "font.too_small", "pass-1", docx(H1 + RUN('<w:sz w:val="18"/>')))
add("docx", "font.too_small", "fail-1", docx(H1 + RUN('<w:sz w:val="14"/>')), f("font.too_small", D + "(//w:r)[2]"))
add("docx", "text.justified", "pass-1", docx(H1 + para("A", extra='<w:jc w:val="left"/>')))
add("docx", "text.justified", "fail-1", docx(H1 + para("A", extra='<w:jc w:val="both"/>')), f("text.justified", D + "(//w:p)[2]"))
add("docx", "list.not_marked", "pass-1", docx(H1 + para("1. One", extra="<w:numPr/>") + para("2. Two", extra="<w:numPr/>")))
add("docx", "list.not_marked", "fail-1", docx(H1 + para("1. One") + para("2. Two")), f("list.not_marked", D + "(//w:p)[2]"))

# ---- PPTX ----
def ppic(descr=None, id_=4):
    d = f' descr="{descr}"' if descr is not None else ""
    return f'<p:pic><p:nvPicPr><p:cNvPr id="{id_}" name="P"{d}/><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill/><p:spPr/></p:pic>'


def ptbl(first):
    a = ' firstRow="1"' if first else ""
    return f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="5" name="G"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr><p:xfrm/><a:graphic><a:graphicData><a:tbl><a:tblPr{a}/></a:tbl></a:graphicData></a:graphic></p:graphicFrame>'


def run(text="Text", attrs="", inner=""):
    return f"<a:r><a:rPr{attrs}>{inner}</a:rPr><a:t>{text}</a:t></a:r>"


add("pptx", "doc.malformed", "pass-1", pptx())
add("pptx", "doc.malformed", "fail-1", zipped({"[Content_Types].xml": "<Types/>", "ppt/presentation.xml": "<broken"}), f("doc.malformed", "document"))
add("pptx", "doc.title.missing", "pass-1", pptx())
add("pptx", "doc.title.missing", "fail-1", pptx(title=""), f("doc.title.missing", "docProps/core.xml#dc:title"))
add("pptx", "doc.lang.missing", "pass-1", pptx())
add("pptx", "doc.lang.missing", "fail-1", pptx(lang=None), f("doc.lang.missing", "ppt/presentation.xml#p:defaultTextStyle"))
add("pptx", "doc.lang.wrong", "pass-1", pptx(title_sp() + box(run(EN))))
add("pptx", "doc.lang.wrong", "fail-1", pptx(title_sp() + box(run(ES))), f("doc.lang.wrong", "ppt/presentation.xml#p:defaultTextStyle"))
add("pptx", "img.alt.missing", "pass-1", pptx(title_sp() + ppic("Map")))
add("pptx", "img.alt.missing", "fail-1", pptx(title_sp() + ppic()), f("img.alt.missing", "slide:1/shape:4"))
add("pptx", "slide.title.missing", "pass-1", pptx())
add("pptx", "slide.title.missing", "fail-1", pptx(box(run("Body"))), f("slide.title.missing", "slide:1"))
add("pptx", "table.header.missing", "pass-1", pptx(title_sp() + ptbl(True)))
add("pptx", "table.header.missing", "fail-1", pptx(title_sp() + ptbl(False)), f("table.header.missing", "slide:1/shape:5"))
add("pptx", "reading_order", "pass-1", pptx(title_sp() + box(run("Body"))))
add("pptx", "reading_order", "fail-1", pptx(box(run("Body")) + title_sp()), f("reading_order", "slide:1"))
add("pptx", "link.text.generic", "pass-1", pptx(title_sp() + box(run("Course syllabus", inner='<a:hlinkClick r:id="rId9"/>'))))
add("pptx", "link.text.generic", "fail-1", pptx(title_sp() + box(run("click here", inner='<a:hlinkClick r:id="rId9"/>'))), f("link.text.generic", "slide:1/shape:3/run:1"))
add("pptx", "font.too_small", "pass-1", pptx(title_sp() + box(run(attrs=' sz="900"'))))
add("pptx", "font.too_small", "fail-1", pptx(title_sp() + box(run(attrs=' sz="700"'))), f("font.too_small", "slide:1/shape:3/run:1"))
CLR = '<a:solidFill><a:srgbClr val="{}"/></a:solidFill>'
add("pptx", "contrast.insufficient", "pass-1", pptx(title_sp() + box(run(inner=CLR.format("111111")))))
add("pptx", "contrast.insufficient", "fail-1", pptx(title_sp() + box(run(inner=CLR.format("AAAAAA")))), f("contrast.insufficient", "slide:1/shape:3/run:1"))
add("pptx", "contrast.insufficient", "fail-2", pptx(title_sp() + box(run(inner=CLR.format("222222")), fill=CLR.format("000000"))), f("contrast.insufficient", "slide:1/shape:3/run:1"))

# ---- XLSX ----
def cell(ref, text, s=None):
    st = f' s="{s}"' if s is not None else ""
    return f'<c r="{ref}"{st} t="inlineStr"><is><t>{text}</t></is></c>'


def styled(font, fill="", ):
    fills = f'<fills count="2"><fill><patternFill patternType="none"/></fill>{fill}</fills>' if fill else '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
    fid = 1 if fill else 0
    return f'<styleSheet {S}><fonts count="2"><font><sz val="11"/></font>{font}</fonts>{fills}<cellXfs count="2"><xf fontId="0" fillId="0"/><xf fontId="1" fillId="{fid}"/></cellXfs></styleSheet>'


def xdraw(descr=None):
    d = f' descr="{descr}"' if descr is not None else ""
    return dict(tail='<drawing r:id="rId1"/>',
                sheet_rels=f'<Relationship Id="rId1" Type="{REL}/drawing" Target="../drawings/drawing1.xml"/>',
                extra={"xl/drawings/drawing1.xml": f'<xdr:wsDr {XDR}><xdr:oneCellAnchor><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="7" name="P"{d}/><xdr:cNvPicPr/></xdr:nvPicPr><xdr:blipFill/><xdr:spPr/></xdr:pic></xdr:oneCellAnchor></xdr:wsDr>'})


def xtable(attrs):
    return dict(rows=f'<row r="1">{A1}</row><row r="3">{cell("A3", "Name")}{cell("B3", "Age")}</row><row r="4">{cell("A4", "Ann")}{cell("B4", "30")}</row>',
                tail='<tableParts count="1"><tablePart r:id="rId1"/></tableParts>',
                sheet_rels=f'<Relationship Id="rId1" Type="{REL}/table" Target="../tables/table1.xml"/>',
                extra={"xl/tables/table1.xml": f'<table {S} id="1" name="T1" displayName="T1" ref="A3:B4"{attrs}><tableColumns count="2"><tableColumn id="1" name="Column1"/><tableColumn id="2" name="Column2"/></tableColumns></table>'})


add("xlsx", "doc.malformed", "pass-1", xlsx())
add("xlsx", "doc.malformed", "fail-1", zipped({"[Content_Types].xml": "<Types/>", "xl/workbook.xml": "<broken"}), f("doc.malformed", "document"))
add("xlsx", "doc.title.missing", "pass-1", xlsx())
add("xlsx", "doc.title.missing", "fail-1", xlsx(title=""), f("doc.title.missing", "docProps/core.xml#dc:title"))
add("xlsx", "xlsx.a1.empty", "pass-1", xlsx())
add("xlsx", "xlsx.a1.empty", "fail-1", xlsx(rows=f'<row r="2">{cell("B2", "x")}</row>'), f("xlsx.a1.empty", "Data!A1"))
add("xlsx", "img.alt.missing", "pass-1", xlsx(**xdraw("Chart of grades")))
add("xlsx", "img.alt.missing", "fail-1", xlsx(**xdraw()), f("img.alt.missing", "Data!shape:7"))
add("xlsx", "table.header.missing", "pass-1", xlsx(**xtable("")))
add("xlsx", "table.header.missing", "fail-1", xlsx(**xtable(' headerRowCount="0"')), f("table.header.missing", "Data!A3"))
add("xlsx", "font.too_small", "pass-1", xlsx(rows=f'<row r="1">{cell("A1", "T", 1)}</row>', styles=styled('<font><sz val="9"/></font>')))
add("xlsx", "font.too_small", "fail-1", xlsx(rows=f'<row r="1">{cell("A1", "T", 1)}</row>', styles=styled('<font><sz val="7"/></font>')), f("font.too_small", "Data!A1"))
add("xlsx", "contrast.insufficient", "pass-1", xlsx(rows=f'<row r="1">{cell("A1", "T", 1)}</row>', styles=styled('<font><sz val="11"/><color rgb="FF111111"/></font>')))
add("xlsx", "contrast.insufficient", "fail-1", xlsx(rows=f'<row r="1">{cell("A1", "T", 1)}</row>', styles=styled('<font><sz val="11"/><color rgb="FFAAAAAA"/></font>')), f("contrast.insufficient", "Data!A1"))
add("xlsx", "contrast.insufficient", "fail-2", xlsx(rows=f'<row r="1">{cell("A1", "T", 1)}</row>', styles=styled('<font><sz val="11"/><color rgb="FF222222"/></font>', '<fill><patternFill patternType="solid"><fgColor rgb="FF000000"/></patternFill></fill>')), f("contrast.insufficient", "Data!A1"))
HL = '<hyperlinks><hyperlink ref="A2" r:id="rId9"/></hyperlinks>'
add("xlsx", "link.text.generic", "pass-1", xlsx(rows=f'<row r="1">{A1}</row><row r="2">{cell("A2", "Syllabus")}</row>', tail=HL))
add("xlsx", "link.text.generic", "fail-1", xlsx(rows=f'<row r="1">{A1}</row><row r="2">{cell("A2", "here")}</row>', tail=HL), f("link.text.generic", "Data!A2"))

# ---- PDF ----
def tx(mc, tag, size=12, y=700, text="Text", color=""):
    return f"/{tag} <</MCID {mc}>> BDC BT {color} /F1 {size} Tf 72 {y} Td ({text}) Tj ET EMC "


def figure(alt):
    def s(d, pg):
        extra = {"Alt": alt} if alt else {}
        return [el(d, "H1", pg, 0), el(d, "Figure", pg, 1, **extra)]
    return s


def heads(*ls):
    ops = "".join(tx(i, f"H{l}", y=700 - i * 20) for i, l in enumerate(ls))
    return ops, lambda d, pg: [el(d, f"H{l}", pg, i) for i, l in enumerate(ls)]


add("pdf", "doc.malformed", "pass-1", pdf())
add("pdf", "doc.malformed", "fail-1", b"%PDF-1.7\nnot a real pdf at all\n", f("doc.malformed", "document"))
add("pdf", "doc.encrypted", "pass-1", pdf())
add("pdf", "doc.encrypted", "fail-1", pdf(encrypt=True), f("doc.encrypted", "document"))
add("pdf", "pdf.scanned", "pass-1", pdf())
add("pdf", "pdf.scanned", "fail-1", pdf(ops="q 100 0 0 100 0 0 cm Q", tagged=False), f("pdf.untagged", "document") + f("pdf.scanned", "document"))
add("pdf", "pdf.untagged", "pass-1", pdf())
add("pdf", "pdf.untagged", "fail-1", pdf(tagged=False), f("pdf.untagged", "document"))
add("pdf", "doc.title.missing", "pass-1", pdf())
add("pdf", "doc.title.missing", "fail-1", pdf(title=None), f("doc.title.missing", "document"))
add("pdf", "doc.title.hidden", "pass-1", pdf())
add("pdf", "doc.title.hidden", "fail-1", pdf(show_title=False), f("doc.title.hidden", "document"))
add("pdf", "doc.lang.missing", "pass-1", pdf())
add("pdf", "doc.lang.missing", "fail-1", pdf(lang=None), f("doc.lang.missing", "document"))
FIG = tx(0, "H1") + tx(1, "Figure", y=670)
add("pdf", "img.alt.missing", "pass-1", pdf(FIG, figure("Campus map")))
add("pdf", "img.alt.missing", "fail-1", pdf(FIG, figure(None)), f("img.alt.missing", "struct:3:Figure"))
add("pdf", "heading.none", "pass-1", pdf())
add("pdf", "heading.none", "fail-1", pdf(tx(0, "P", size=9, text="word " * 22), lambda d, pg: [el(d, "P", pg, 0)]), f("heading.none", "document"))
add("pdf", "heading.start", "pass-1", pdf(*heads(1, 2)))
add("pdf", "heading.start", "fail-1", pdf(*heads(2)), f("heading.start", "struct:2:H2"))
add("pdf", "heading.nesting", "pass-1", pdf(*heads(1, 2, 3)))
add("pdf", "heading.nesting", "fail-1", pdf(*heads(1, 3)), f("heading.nesting", "struct:3:H3"))
add("pdf", "heading.depth", "pass-1", pdf(*heads(1, 2, 3, 4)))
add("pdf", "heading.depth", "fail-1", pdf(*heads(1, 2, 3, 4, 5)), f("heading.depth", "struct:6:H5"))


def table(th):
    def s(d, pg):
        cell_ = el(d, "TH" if th else "TD", pg, 1)
        tr = el(d, "TR", pg, None, K=pikepdf.Array([cell_]))
        return [el(d, "H1", pg, 0), el(d, "Table", pg, None, K=pikepdf.Array([tr]))]
    return s


TOPS = tx(0, "H1") + tx(1, "TD", y=670)
add("pdf", "table.header.missing", "pass-1", pdf(TOPS, table(True)))
add("pdf", "table.header.missing", "fail-1", pdf(TOPS, table(False)), f("table.header.missing", "struct:3:Table"))
EMPTY = "/H1 <</MCID 0>> BDC BT /F1 24 Tf 72 700 Td (Title) Tj ET EMC /P <</MCID 1>> BDC 0 0 m EMC "
add("pdf", "tag.empty", "pass-1", pdf())
add("pdf", "tag.empty", "pass-2", pdf(tx(0, "H1") + tx(1, "P", y=670), lambda d, pg: [el(d, "H1", pg, 0), el(d, "P", pg, None, K=pikepdf.Array([el(d, "Figure", pg, 1, Alt="A map")]))]))
add("pdf", "tag.empty", "fail-1", pdf(EMPTY), f("tag.empty", "struct:3:P"))
add("pdf", "reading_order", "pass-1", pdf())
add("pdf", "reading_order", "pass-2", pdf(struct=lambda d, pg: [el(d, "H1", pg, 0), el(d, "P", pg, 1), el(d, "Span", pg, 0)]))
add("pdf", "reading_order", "fail-1", pdf(struct=lambda d, pg: [el(d, "P", pg, 1), el(d, "H1", pg, 0)]), f("reading_order", "page:1"))
add("pdf", "font.too_small", "pass-1", pdf(tx(0, "H1", size=9), lambda d, pg: [el(d, "H1", pg, 0)]))
add("pdf", "font.too_small", "fail-1", pdf(tx(0, "H1", size=7), lambda d, pg: [el(d, "H1", pg, 0)]), f("font.too_small", "page:1"))
add("pdf", "contrast.insufficient", "pass-1", pdf(tx(0, "H1", color="0.1 0.1 0.1 rg"), lambda d, pg: [el(d, "H1", pg, 0)]))
DARK = "0 0 0 rg 0 600 612 192 re f "
add("pdf", "contrast.insufficient", "pass-2", pdf(DARK + tx(0, "H1", color="1 1 1 rg"), lambda d, pg: [el(d, "H1", pg, 0)]))
add("pdf", "contrast.insufficient", "fail-2", pdf(DARK + tx(0, "H1", color="0.2 0.2 0.2 rg"), lambda d, pg: [el(d, "H1", pg, 0)]), f("contrast.insufficient", "page:1"))
add("pdf", "contrast.insufficient", "fail-1", pdf(tx(0, "H1", color="0.8 0.8 0.8 rg"), lambda d, pg: [el(d, "H1", pg, 0)]), f("contrast.insufficient", "page:1"))


shutil.rmtree(OUT, ignore_errors=True)
expected = {}
for path, data, exp, probe in fixtures:
    p = OUT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    entry = {"findings": sorted([{"check_id": c, "severity": SEV[c], "locator": l} for c, l in exp], key=lambda x: (x["check_id"], x["locator"]))}
    if probe:
        entry["probe"] = probe
    expected[path] = entry
(OUT / "expected.json").write_text(json.dumps(expected, indent=1, sort_keys=True) + "\n")
print(len(fixtures), "fixtures")
