import { strFromU8, strToU8, unzipSync, zipSync } from '../vendor/fflate.js';
import { DOMParser, XMLSerializer } from '../vendor/xmldom.js';
import { LIST_RE, Malformed, clean, defaults, headingSeq, isGeneric, langWrong, lowContrast, need, noFix, FixError } from './common.js';
const MAX_UNZIPPED = 512 * 1024 * 1024;
const NS = {
    w: 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    wp: 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    a: 'http://schemas.openxmlformats.org/drawingml/2006/main',
    p: 'http://schemas.openxmlformats.org/presentationml/2006/main',
    r: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    s: 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    xdr: 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing',
    dc: 'http://purl.org/dc/elements/1.1/',
    cp: 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
    rel: 'http://schemas.openxmlformats.org/package/2006/relationships',
    ct: 'http://schemas.openxmlformats.org/package/2006/content-types',
};
const CORE = 'docProps/core.xml';
const ADEC_URI = '{C183D7F6-B498-43B3-948B-1728B52AA6E4}';
const ADEC_NS = 'http://schemas.microsoft.com/office/drawing/2017/decorative';
const isEl = (x) => x && x.nodeType === 1;
const kids = (e) => { const o = []; for (let c = e.firstChild; c; c = c.nextSibling)
    if (isEl(c))
        o.push(c); return o; };
const is = (e, name) => { const [p, l] = name.split(':'); return e.localName === l && e.namespaceURI === NS[p]; };
export const child = (e, name) => e ? kids(e).find(k => is(k, name)) ?? null : null;
const path = (e, ...names) => names.reduce((x, n) => x && child(x, n), e);
function* all(e) { yield e; for (const k of kids(e))
    yield* all(k); }
const iter = (e, ...names) => [...all(e)].filter(x => names.some(n => is(x, n)));
const text = (e, tag) => iter(e, tag).map(t => t.textContent ?? '').join('');
const wa = (e, name) => { const [p, l] = name.split(':'); return e?.getAttributeNS(NS[p], l) || null; };
const attr = (e, name) => e?.getAttribute(name) || null;
export function resolve(base, target) {
    if (target.startsWith('/'))
        return target.slice(1);
    const out = base.split('/').slice(0, -1);
    for (const part of target.split('/')) {
        if (part === '..')
            out.pop();
        else if (part !== '.')
            out.push(part);
    }
    return out.join('/');
}
export class Pkg {
    files;
    cache = {};
    touched = new Set();
    constructor(data) {
        let total = 0;
        try {
            this.files = unzipSync(data, { filter: f => { total += f.originalSize; if (total > MAX_UNZIPPED)
                    throw new Malformed('zip too large'); return true; } });
        }
        catch (e) {
            throw new Malformed(String(e));
        }
    }
    has(part) { return part in this.files; }
    doc(part) {
        if (!this.cache[part]) {
            const raw = strFromU8(this.files[part]);
            if (/<!(DOCTYPE|ENTITY)/.test(raw.slice(0, 4096)))
                throw new Malformed('DTD in part');
            try {
                this.cache[part] = new DOMParser().parseFromString(raw, 'text/xml');
            }
            catch (e) {
                throw new Malformed(String(e));
            }
            if (!this.cache[part].documentElement)
                throw new Malformed('no root');
        }
        return this.cache[part];
    }
    xml(part) { return this.doc(part).documentElement; }
    rels(part) {
        const i = part.lastIndexOf('/'), rp = `${part.slice(0, i + 1)}_rels/${part.slice(i + 1)}.rels`;
        if (!this.has(rp))
            return {};
        return Object.fromEntries(kids(this.xml(rp)).map(r => [attr(r, 'Id'), resolve(part, attr(r, 'Target'))]));
    }
    save() {
        for (const part of this.touched) {
            this.files[part] = strToU8('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + new XMLSerializer().serializeToString(this.cache[part]));
        }
        return zipSync(this.files);
    }
}
const decorative = (c) => [...all(c)].some(x => x.localName === 'decorative' && ['1', 'true'].includes(attr(x, 'val') ?? ''));
function coreTitle(pkg) {
    if (!pkg.has(CORE))
        return '';
    return clean(child(pkg.xml(CORE), 'dc:title')?.textContent);
}
export function checkDocx(pkg, ctx) {
    const part = 'word/document.xml';
    if (!pkg.has(part))
        throw new Malformed('no main part');
    const p = ctx.p, doc = pkg.xml(part);
    const loc = (tag, i) => `${part}#(//${tag})[${i}]`;
    if (!coreTitle(pkg))
        ctx.add('doc.title.missing', `${CORE}#dc:title`);
    const lang = pkg.has('word/styles.xml') ? wa(path(pkg.xml('word/styles.xml'), 'w:docDefaults', 'w:rPrDefault', 'w:rPr', 'w:lang'), 'w:val') : null;
    const langLoc = 'word/styles.xml#w:docDefaults';
    if (!lang)
        ctx.add('doc.lang.missing', langLoc);
    const paras = iter(doc, 'w:p');
    const bodyText = paras.map(x => text(x, 'w:t')).join(' ');
    if (langWrong(lang, bodyText, p))
        ctx.add('doc.lang.wrong', langLoc);
    iter(doc, 'wp:docPr').forEach((d, i) => { if (!clean(attr(d, 'descr')) && !decorative(d))
        ctx.add('img.alt.missing', loc('wp:docPr', i + 1)); });
    iter(doc, 'wp:anchor').forEach((_, i) => ctx.add('img.not_inline', loc('wp:anchor', i + 1)));
    const texts = paras.map(x => clean(text(x, 'w:t')));
    const seq = [];
    paras.forEach((para, i) => {
        const ppr = child(para, 'w:pPr'), l = loc('w:p', i + 1);
        const m = (wa(child(ppr, 'w:pStyle'), 'w:val') ?? '').match(/^heading ?(\d)$/i);
        if (m)
            seq.push([Number(m[1]), l]);
        if (['both', 'distribute'].includes(wa(child(ppr, 'w:jc'), 'w:val') ?? ''))
            ctx.add('text.justified', l);
        if (!child(ppr, 'w:numPr') && LIST_RE.test(texts[i]) && i + 1 < paras.length && LIST_RE.test(texts[i + 1])) {
            if (i === 0 || !LIST_RE.test(texts[i - 1]))
                ctx.add('list.not_marked', l);
        }
    });
    headingSeq(ctx, seq, `${part}#w:body`, bodyText, true);
    iter(doc, 'w:tbl').forEach((t, i) => {
        if (!wa(path(t, 'w:tblPr', 'w:tblCaption'), 'w:val'))
            ctx.add('table.caption.missing', loc('w:tbl', i + 1));
        if (!path(t, 'w:tr', 'w:trPr', 'w:tblHeader'))
            ctx.add('table.header.missing', loc('w:tbl', i + 1));
    });
    iter(doc, 'w:hyperlink').forEach((h, i) => { if (isGeneric(text(h, 'w:t')))
        ctx.add('link.text.generic', loc('w:hyperlink', i + 1)); });
    iter(doc, 'w:r').forEach((r, i) => {
        const pr = child(r, 'w:rPr');
        if (!clean(text(r, 'w:t')) || !pr)
            return;
        const sz = wa(child(pr, 'w:sz'), 'w:val'), pt = sz ? Number(sz) / 2 : null;
        if (pt !== null && pt < p.min_font_pt)
            ctx.add('font.too_small', loc('w:r', i + 1));
        const val = (wa(child(pr, 'w:color'), 'w:val') ?? '').toLowerCase();
        if (/^[0-9a-f]{6}$/.test(val)) {
            const fill = (wa(child(pr, 'w:shd'), 'w:fill') ?? '').toLowerCase();
            const bg = /^[0-9a-f]{6}$/.test(fill) ? fill : 'ffffff';
            if (lowContrast(val, bg, pt, !!child(pr, 'w:b'), p))
                ctx.add('contrast.insufficient', loc('w:r', i + 1), { fg: val, bg });
        }
    });
}
function slides(pkg) {
    const rels = pkg.rels('ppt/presentation.xml');
    const lst = child(pkg.xml('ppt/presentation.xml'), 'p:sldIdLst');
    return lst ? kids(lst).map(s => rels[wa(s, 'r:id')]) : [];
}
const shapesOf = (tree) => iter(tree, 'p:sp', 'p:pic', 'p:graphicFrame');
const cnv = (s) => [...all(s)].find(x => x.localName === 'cNvPr');
const phTitle = (s) => [...all(s)].some(x => x.localName === 'ph' && ['title', 'ctrTitle'].includes(attr(x, 'type') ?? ''));
const srgb = (e) => attr(path(e, 'a:solidFill', 'a:srgbClr'), 'val');
export function checkPptx(pkg, ctx) {
    if (!pkg.has('ppt/presentation.xml'))
        throw new Malformed('no main part');
    const p = ctx.p, pres = pkg.xml('ppt/presentation.xml');
    if (!coreTitle(pkg))
        ctx.add('doc.title.missing', `${CORE}#dc:title`);
    const lang = attr(path(pres, 'p:defaultTextStyle', 'a:defPPr', 'a:defRPr'), 'lang');
    const langLoc = 'ppt/presentation.xml#p:defaultTextStyle';
    if (!lang)
        ctx.add('doc.lang.missing', langLoc);
    const allText = [];
    slides(pkg).forEach((part, idx) => {
        if (!part || !pkg.has(part))
            throw new Malformed('missing slide');
        const n = idx + 1, shapes = shapesOf(pkg.xml(part));
        const titles = shapes.filter(s => s.localName === 'sp' && phTitle(s));
        if (!titles.some(s => clean(text(s, 'a:t'))))
            ctx.add('slide.title.missing', `slide:${n}`);
        if (titles.length && shapes[0] !== titles[0])
            ctx.add('reading_order', `slide:${n}`);
        for (const s of shapes) {
            const c = cnv(s), sl = `slide:${n}/shape:${attr(c, 'id')}`;
            if (s.localName === 'pic' && !clean(attr(c, 'descr')) && !decorative(c))
                ctx.add('img.alt.missing', sl);
            const tbl = iter(s, 'a:tbl')[0];
            if (tbl && !['1', 'true'].includes(attr(child(tbl, 'a:tblPr'), 'firstRow') ?? ''))
                ctx.add('table.header.missing', sl);
            const bg = (srgb(child(s, 'p:spPr')) ?? 'ffffff').toLowerCase();
            iter(s, 'a:r').forEach((r, i) => {
                const t = text(r, 'a:t');
                allText.push(t);
                const pr = child(r, 'a:rPr');
                if (!clean(t) || !pr)
                    return;
                const rl = `${sl}/run:${i + 1}`;
                if (child(pr, 'a:hlinkClick') && isGeneric(t))
                    ctx.add('link.text.generic', rl);
                const sz = attr(pr, 'sz'), pt = sz ? Number(sz) / 100 : null;
                if (pt !== null && pt < p.min_font_pt)
                    ctx.add('font.too_small', rl);
                const col = srgb(pr)?.toLowerCase();
                if (col && lowContrast(col, bg, pt, ['1', 'true'].includes(attr(pr, 'b') ?? ''), p))
                    ctx.add('contrast.insufficient', rl, { fg: col, bg });
            });
        }
    });
    if (langWrong(lang, allText.join(' '), p))
        ctx.add('doc.lang.wrong', langLoc);
}
function sheets(pkg) {
    const rels = pkg.rels('xl/workbook.xml');
    const lst = child(pkg.xml('xl/workbook.xml'), 's:sheets');
    return lst ? kids(lst).map(s => [attr(s, 'name'), rels[wa(s, 'r:id')]]) : [];
}
const shared = (pkg) => pkg.has('xl/sharedStrings.xml') ? kids(pkg.xml('xl/sharedStrings.xml')).map(si => text(si, 's:t')) : [];
function cellText(c, strs) {
    const t = attr(c, 't');
    if (t === 'inlineStr')
        return text(c, 's:t');
    const v = child(c, 's:v')?.textContent;
    if (!v)
        return '';
    return t === 's' ? strs[Number(v)] : v;
}
export function checkXlsx(pkg, ctx) {
    if (!pkg.has('xl/workbook.xml'))
        throw new Malformed('no main part');
    const p = ctx.p;
    if (!coreTitle(pkg))
        ctx.add('doc.title.missing', `${CORE}#dc:title`);
    const strs = shared(pkg);
    const st = pkg.has('xl/styles.xml') ? pkg.xml('xl/styles.xml') : null;
    const list = (n) => { const x = st && child(st, n); return x ? kids(x) : []; };
    const xfs = list('s:cellXfs'), fonts = list('s:fonts'), fills = list('s:fills');
    for (const [name, part] of sheets(pkg)) {
        if (!part || !pkg.has(part))
            throw new Malformed('missing sheet');
        const sheet = pkg.xml(part), rels = pkg.rels(part);
        const cells = new Map(iter(sheet, 's:c').map(c => [attr(c, 'r'), c]));
        const a1 = cells.get('A1');
        if (!a1 || !clean(cellText(a1, strs)))
            ctx.add('xlsx.a1.empty', `${name}!A1`);
        for (const [ref, c] of cells) {
            if (!clean(cellText(c, strs)) || !st)
                continue;
            const xf = xfs[Number(attr(c, 's') ?? 0)];
            if (!xf)
                continue;
            const font = fonts[Number(attr(xf, 'fontId') ?? 0)], fill = fills[Number(attr(xf, 'fillId') ?? 0)];
            const sz = attr(child(font, 's:sz'), 'val'), pt = sz ? parseFloat(sz) : null;
            const fg = attr(child(font, 's:color'), 'rgb')?.slice(-6).toLowerCase();
            if (pt !== null && pt < p.min_font_pt)
                ctx.add('font.too_small', `${name}!${ref}`);
            let bg = 'ffffff';
            const pf = child(fill, 's:patternFill');
            if (pf && attr(pf, 'patternType') === 'solid' && attr(child(pf, 's:fgColor'), 'rgb'))
                bg = attr(child(pf, 's:fgColor'), 'rgb').slice(-6).toLowerCase();
            if (fg && lowContrast(fg, bg, pt, !!child(font, 's:b'), p))
                ctx.add('contrast.insufficient', `${name}!${ref}`, { fg, bg });
        }
        for (const h of iter(sheet, 's:hyperlink')) {
            const c = cells.get(attr(h, 'ref'));
            if (c && isGeneric(cellText(c, strs)))
                ctx.add('link.text.generic', `${name}!${attr(h, 'ref')}`);
        }
        const d = child(sheet, 's:drawing');
        if (d && rels[wa(d, 'r:id')]) {
            for (const pic of iter(pkg.xml(rels[wa(d, 'r:id')]), 'xdr:pic')) {
                const c = cnv(pic);
                if (!clean(attr(c, 'descr')) && !decorative(c))
                    ctx.add('img.alt.missing', `${name}!shape:${attr(c, 'id')}`);
            }
        }
        for (const tp of iter(sheet, 's:tablePart')) {
            const t = pkg.xml(rels[wa(tp, 'r:id')]);
            if (attr(t, 'headerRowCount') === '0')
                ctx.add('table.header.missing', `${name}!${attr(t, 'ref').split(':')[0]}`);
        }
    }
}
// ---- fixes ----
function make(owner, name) {
    const [p] = name.split(':');
    return owner.ownerDocument.createElementNS(NS[p], name);
}
function ensure(parent, name, first = true) {
    let e = child(parent, name);
    if (!e) {
        e = make(parent, name);
        if (first && parent.firstChild)
            parent.insertBefore(e, parent.firstChild);
        else
            parent.appendChild(e);
    }
    return e;
}
const setW = (e, v) => e.setAttributeNS(NS.w, 'w:val', v);
function setDecorative(c) {
    const lst = ensure(c, 'a:extLst', false);
    const ext = make(c, 'a:ext');
    ext.setAttribute('uri', ADEC_URI);
    const dec = c.ownerDocument.createElementNS(ADEC_NS, 'adec:decorative');
    dec.setAttribute('val', '1');
    ext.appendChild(dec);
    lst.appendChild(ext);
    c.setAttribute('descr', '');
}
function setAlt(c, f) {
    if (f.decorative)
        setDecorative(c);
    else
        c.setAttribute('descr', need(f));
}
function setTitle(pkg, value) {
    if (!pkg.has(CORE)) {
        pkg.files[CORE] = strToU8(`<cp:coreProperties xmlns:cp="${NS.cp}" xmlns:dc="${NS.dc}"/>`);
        const ct = pkg.xml('[Content_Types].xml');
        const ov = make(ct, 'ct:Override');
        ov.setAttribute('PartName', '/' + CORE);
        ov.setAttribute('ContentType', 'application/vnd.openxmlformats-package.core-properties+xml');
        ct.appendChild(ov);
        pkg.touched.add('[Content_Types].xml');
        const rels = pkg.xml('_rels/.rels');
        const r = make(rels, 'rel:Relationship');
        r.setAttribute('Id', 'rIdCore');
        r.setAttribute('Type', 'http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties');
        r.setAttribute('Target', CORE);
        rels.appendChild(r);
        pkg.touched.add('_rels/.rels');
    }
    const core = pkg.xml(CORE);
    ensure(core, 'dc:title', false).textContent = value;
    pkg.touched.add(CORE);
}
const nth = (root, tag, locator) => iter(root, tag)[Number(locator.match(/\[(\d+)\]$/)[1]) - 1];
export function fixDocx(pkg, f) {
    const c = f.check_id, part = 'word/document.xml';
    if (c === 'doc.title.missing')
        return setTitle(pkg, need(f));
    const doc = pkg.xml(part);
    pkg.touched.add(part);
    if (c === 'doc.lang.missing' || c === 'doc.lang.wrong') {
        const val = need(f);
        const pr = ensure(ensure(ensure(pkg.xml('word/styles.xml'), 'w:docDefaults'), 'w:rPrDefault'), 'w:rPr');
        setW(ensure(pr, 'w:lang', false), val);
        pkg.touched.add('word/styles.xml');
        iter(doc, 'w:lang').forEach(el => setW(el, val));
    }
    else if (c === 'img.alt.missing')
        setAlt(nth(doc, 'wp:docPr', f.locator), f);
    else if (c === 'table.header.missing')
        ensure(ensure(child(nth(doc, 'w:tbl', f.locator), 'w:tr'), 'w:trPr'), 'w:tblHeader');
    else if (c === 'table.caption.missing')
        setW(ensure(ensure(nth(doc, 'w:tbl', f.locator), 'w:tblPr'), 'w:tblCaption', false), need(f));
    else if (['heading.start', 'heading.nesting', 'heading.depth'].includes(c))
        setW(ensure(ensure(nth(doc, 'w:p', f.locator), 'w:pPr'), 'w:pStyle'), `Heading${Number(need(f))}`);
    else if (c === 'link.text.generic') {
        const ts = iter(nth(doc, 'w:hyperlink', f.locator), 'w:t');
        if (!ts.length)
            noFix(f);
        ts.forEach((t, i) => { t.textContent = i ? '' : need(f); });
    }
    else if (c === 'font.too_small') {
        const pr = child(nth(doc, 'w:r', f.locator), 'w:rPr'), val = String(Math.round(defaults.min_font_pt * 2));
        setW(ensure(pr, 'w:sz', false), val);
        if (child(pr, 'w:szCs'))
            setW(child(pr, 'w:szCs'), val);
    }
    else if (c === 'text.justified')
        setW(path(nth(doc, 'w:p', f.locator), 'w:pPr', 'w:jc'), 'left');
    else if (c === 'contrast.insufficient')
        setW(ensure(child(nth(doc, 'w:r', f.locator), 'w:rPr'), 'w:color', false), need(f).replace(/^#/, '').toUpperCase());
    else
        noFix(f);
}
export function fixPptx(pkg, f) {
    const c = f.check_id;
    if (c === 'doc.title.missing')
        return setTitle(pkg, need(f));
    if (c === 'doc.lang.missing' || c === 'doc.lang.wrong') {
        const val = need(f), pres = pkg.xml('ppt/presentation.xml');
        ensure(ensure(ensure(pres, 'p:defaultTextStyle', false), 'a:defPPr'), 'a:defRPr').setAttribute('lang', val);
        pkg.touched.add('ppt/presentation.xml');
        for (const part of slides(pkg)) {
            iter(pkg.xml(part), 'a:rPr', 'a:endParaRPr').forEach(el => { if (attr(el, 'lang'))
                el.setAttribute('lang', val); });
            pkg.touched.add(part);
        }
        return;
    }
    const m = f.locator.match(/^slide:(\d+)(?:\/shape:(\d+))?(?:\/run:(\d+))?$/);
    if (!m)
        return noFix(f);
    const part = slides(pkg)[Number(m[1]) - 1], tree = pkg.xml(part);
    const shape = m[2] ? shapesOf(tree).find(s => attr(cnv(s), 'id') === m[2]) : null;
    const run = m[3] ? iter(shape, 'a:r')[Number(m[3]) - 1] : null;
    pkg.touched.add(part);
    if (c === 'img.alt.missing')
        setAlt(cnv(shape), f);
    else if (c === 'table.header.missing')
        ensure(iter(shape, 'a:tbl')[0], 'a:tblPr').setAttribute('firstRow', '1');
    else if (c === 'link.text.generic')
        child(run, 'a:t').textContent = need(f);
    else if (c === 'font.too_small')
        child(run, 'a:rPr').setAttribute('sz', String(Math.round(defaults.min_font_pt * 100)));
    else if (c === 'contrast.insufficient') {
        const fill = ensure(child(run, 'a:rPr'), 'a:solidFill');
        kids(fill).forEach(k => fill.removeChild(k));
        const clr = make(fill, 'a:srgbClr');
        clr.setAttribute('val', need(f).replace(/^#/, '').toUpperCase());
        fill.appendChild(clr);
    }
    else if (c === 'reading_order') {
        const shapes = shapesOf(tree), t = shapes.find(s => s.localName === 'sp' && phTitle(s));
        t.parentNode.removeChild(t);
        shapes[0].parentNode.insertBefore(t, shapes[0]);
    }
    else if (c === 'slide.title.missing') {
        const shapes = shapesOf(tree), title = shapes.find(s => s.localName === 'sp' && phTitle(s));
        const value = need(f);
        const ts = title ? iter(title, 'a:t') : [];
        if (ts.length) {
            ts[0].textContent = value;
            return;
        }
        const id = Math.max(1, ...shapes.map(s => Number(attr(cnv(s), 'id')))) + 1;
        const xml = `<p:sp xmlns:p="${NS.p}" xmlns:a="${NS.a}"><p:nvSpPr><p:cNvPr id="${id}" name="Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:p><a:r><a:t/></a:r></a:p></p:txBody></p:sp>`;
        const fresh = new DOMParser().parseFromString(xml, 'text/xml').documentElement;
        if (title) {
            const old = child(title, 'p:txBody');
            if (old)
                title.removeChild(old);
            const body = tree.ownerDocument.importNode(child(fresh, 'p:txBody'), true);
            title.appendChild(body);
            iter(body, 'a:t')[0].textContent = value;
            return;
        }
        const sp = tree.ownerDocument.importNode(fresh, true);
        iter(sp, 'a:t')[0].textContent = value;
        const root = iter(tree, 'p:spTree')[0], after = kids(root).find(x => !['nvGrpSpPr', 'grpSpPr'].includes(x.localName));
        if (after)
            root.insertBefore(sp, after);
        else
            root.appendChild(sp);
    }
    else
        noFix(f);
}
function setCellText(c, value) {
    kids(c).forEach(k => c.removeChild(k));
    c.setAttribute('t', 'inlineStr');
    const is_ = make(c, 's:is'), t = make(c, 's:t');
    t.textContent = value;
    is_.appendChild(t);
    c.appendChild(is_);
}
function bumpXf(pkg, c, mutate) {
    const st = pkg.xml('xl/styles.xml'), fonts = child(st, 's:fonts'), xfs = child(st, 's:cellXfs');
    const xf = kids(xfs)[Number(attr(c, 's') ?? 0)].cloneNode(true);
    const font = kids(fonts)[Number(attr(xf, 'fontId') ?? 0)].cloneNode(true);
    mutate(font);
    fonts.appendChild(font);
    fonts.setAttribute('count', String(kids(fonts).length));
    xf.setAttribute('fontId', String(kids(fonts).length - 1));
    xf.setAttribute('applyFont', '1');
    xfs.appendChild(xf);
    xfs.setAttribute('count', String(kids(xfs).length));
    c.setAttribute('s', String(kids(xfs).length - 1));
    pkg.touched.add('xl/styles.xml');
}
const colIndex = (s) => [...s].reduce((n, ch) => n * 26 + ch.charCodeAt(0) - 64, 0);
function colName(n) {
    let out = '';
    while (n) {
        const r = (n - 1) % 26;
        out = String.fromCharCode(65 + r) + out;
        n = (n - 1 - r) / 26;
    }
    return out;
}
export function fixXlsx(pkg, f) {
    const c = f.check_id;
    if (c === 'doc.title.missing')
        return setTitle(pkg, need(f));
    const i = f.locator.lastIndexOf('!'), name = f.locator.slice(0, i), ref = f.locator.slice(i + 1);
    const part = sheets(pkg).find(s => s[0] === name)?.[1];
    if (!part)
        return noFix(f);
    const sheet = pkg.xml(part);
    pkg.touched.add(part);
    const cells = new Map(iter(sheet, 's:c').map(x => [attr(x, 'r'), x]));
    if (c === 'xlsx.a1.empty') {
        let cell = cells.get('A1');
        if (!cell) {
            const data = child(sheet, 's:sheetData');
            let row = kids(data).find(r => attr(r, 'r') === '1');
            if (!row) {
                row = make(data, 's:row');
                row.setAttribute('r', '1');
                data.insertBefore(row, data.firstChild);
            }
            cell = make(data, 's:c');
            cell.setAttribute('r', 'A1');
            row.insertBefore(cell, row.firstChild);
        }
        setCellText(cell, String(f.value || name));
    }
    else if (c === 'link.text.generic')
        setCellText(cells.get(ref), need(f));
    else if (c === 'img.alt.missing') {
        const dpart = pkg.rels(part)[wa(child(sheet, 's:drawing'), 'r:id')], sid = ref.split(':')[1];
        setAlt([...all(pkg.xml(dpart))].find(x => x.localName === 'cNvPr' && attr(x, 'id') === sid), f);
        pkg.touched.add(dpart);
    }
    else if (c === 'table.header.missing') {
        const rels = pkg.rels(part), strs = shared(pkg);
        for (const tp of iter(sheet, 's:tablePart')) {
            const tpart = rels[wa(tp, 'r:id')], t = pkg.xml(tpart);
            if (attr(t, 'ref').split(':')[0] !== ref)
                continue;
            const row = ref.match(/\d+/)[0], start = colIndex(ref.match(/[A-Z]+/)[0]);
            kids(child(t, 's:tableColumns')).forEach((tc, n) => {
                const cell = cells.get(`${colName(start + n)}${row}`);
                if (!cell || !clean(cellText(cell, strs)))
                    throw new FixError(`The fix for ${f.locator} failed because the first row has empty cells. Fill the first row.`);
                tc.setAttribute('name', cellText(cell, strs));
            });
            t.removeAttribute('headerRowCount');
            pkg.touched.add(tpart);
        }
    }
    else if (c === 'font.too_small') {
        bumpXf(pkg, cells.get(ref), font => ensure(font, 's:sz').setAttribute('val', String(defaults.min_font_pt)));
    }
    else if (c === 'contrast.insufficient') {
        bumpXf(pkg, cells.get(ref), font => {
            const col = ensure(font, 's:color');
            for (const a of [...col.attributes])
                col.removeAttribute(a.name);
            col.setAttribute('rgb', 'FF' + need(f).replace(/^#/, '').toUpperCase());
        });
    }
    else
        noFix(f);
}
/** Text outline for the PPTX and XLSX preview. */
export function outline(pkg, fmt) {
    const out = [];
    if (fmt === 'pptx') {
        slides(pkg).forEach((part, i) => {
            out.push({ locator: `slide:${i + 1}`, label: `Slide ${i + 1}` });
            for (const s of shapesOf(pkg.xml(part))) {
                const c = cnv(s), kind = s.localName === 'pic' ? 'Picture' : s.localName === 'graphicFrame' ? 'Table' : phTitle(s) ? 'Title' : 'Text';
                out.push({ locator: `slide:${i + 1}/shape:${attr(c, 'id')}`, label: `  ${kind}: ${clean(text(s, 'a:t')) || attr(c, 'descr') || '(empty)'}` });
            }
        });
    }
    else {
        const strs = shared(pkg);
        for (const [name, part] of sheets(pkg)) {
            out.push({ locator: `${name}!`, label: `Sheet ${name}` });
            for (const c of iter(pkg.xml(part), 's:c')) {
                const t = cellText(c, strs);
                if (t)
                    out.push({ locator: `${name}!${attr(c, 'r')}`, label: `  ${attr(c, 'r')}: ${t}` });
            }
        }
    }
    return out;
}
