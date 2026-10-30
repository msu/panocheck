import { parse } from '../vendor/parse5.js';
import { ALT_FILE_RE, LIST_RE, chars, clean, defaults, headingSeq, isGeneric, lowContrast, need, noFix, vocab, words } from './common.js';
const RAW = new Set(['script', 'style']);
class Comment {
    data;
    constructor(data) {
        this.data = data;
    }
}
export class N {
    tag;
    attrs;
    parent;
    kids = [];
    loc;
    constructor(tag, attrs, parent) {
        this.tag = tag;
        this.attrs = attrs;
        this.parent = parent;
    }
    els() { return this.kids.filter((k) => k instanceof N); }
    *walk() { yield this; for (const k of this.els())
        yield* k.walk(); }
    findAll(...tags) { return [...this.walk()].filter(e => tags.includes(e.tag)); }
    text() {
        return this.kids.map(k => k instanceof N ? (RAW.has(k.tag) ? '' : k.text()) : typeof k === 'string' ? k : '').join('');
    }
    ownText() { return this.kids.filter(k => typeof k === 'string').join(''); }
    path() {
        if (!this.parent)
            return this.tag;
        if (this.tag === 'head' || this.tag === 'body')
            return `html > ${this.tag}`;
        const same = this.parent.els().filter(e => e.tag === this.tag);
        return `${this.parent.path()} > ${this.tag}:nth-of-type(${same.indexOf(this) + 1})`;
    }
    style() {
        const out = {};
        for (const part of (this.attrs.style ?? '').split(';')) {
            const i = part.indexOf(':');
            if (i >= 0)
                out[part.slice(0, i).trim().toLowerCase()] = part.slice(i + 1).trim().toLowerCase();
        }
        return out;
    }
    inherited(prop) {
        for (let e = this; e; e = e.parent) {
            const v = e.style()[prop];
            if (v)
                return v;
        }
        return null;
    }
}
export function decode(data) { return new TextDecoder('utf-8', { ignoreBOM: false }).decode(data); }
export function parseHtml(src) {
    const doc = parse(src, { sourceCodeLocationInfo: true, scriptingEnabled: false });
    const conv = (e, parent) => {
        const n = new N(e.tagName, Object.fromEntries(e.attrs.map((a) => [a.name, a.value])), parent);
        n.loc = e.sourceCodeLocation;
        for (const c of e.childNodes) {
            if (c.nodeName === '#text')
                n.kids.push(c.value);
            else if (c.nodeName === '#comment')
                n.kids.push(new Comment(c.data));
            else if (c.tagName && c.tagName !== 'template')
                n.kids.push(conv(c, n));
        }
        return n;
    };
    return conv(doc.childNodes.find((c) => c.tagName === 'html'), null);
}
export function htmlFind(tree, locator) {
    let node = tree;
    for (const part of locator.split(' > ').slice(1)) {
        const m = part.match(/^([^:]+)(?::nth-of-type\((\d+)\))?$/);
        node = node.els().filter(e => e.tag === m[1])[Number(m[2] ?? 1) - 1];
        if (!node)
            throw new Error(`No element at ${locator}.`);
    }
    return node;
}
export function parseColor(v) {
    v = (v ?? '').trim().toLowerCase();
    if (v in vocab.colors)
        return vocab.colors[v];
    let m = v.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/);
    if (m)
        return m[1].length === 6 ? m[1] : [...m[1]].map(c => c + c).join('');
    m = v.match(/^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/);
    if (m)
        return m.slice(1).map(x => Math.min(Number(x), 255).toString(16).padStart(2, '0')).join('');
    return null;
}
function pt(v) {
    const m = (v ?? '').match(/^([\d.]+)(pt|px)$/);
    return m ? parseFloat(m[1]) * (m[2] === 'pt' ? 1 : 0.75) : null;
}
export function checkHtml(src, ctx) {
    const p = ctx.p, tree = parseHtml(src);
    const body = htmlFind(tree, 'html > body'), text = body.text();
    const seq = [];
    for (const e of tree.walk()) {
        const t = e.tag, a = e.attrs;
        if (t === 'img') {
            const aria = a['aria-label'] || a['aria-labelledby'];
            if (!('alt' in a)) {
                if (!aria)
                    ctx.add('img.alt.missing', e.path());
            }
            else {
                const alt = clean(a.alt);
                if (chars(alt) > p.alt_max_chars)
                    ctx.add('img.alt.too_long', e.path());
                if (ALT_FILE_RE.test(alt))
                    ctx.add('img.alt.filename', e.path());
                if (vocab.meaningless_alt.includes(alt.toLowerCase()))
                    ctx.add('img.alt.meaningless', e.path());
                if (!alt && !aria) {
                    let up = e.parent;
                    while (up && up.tag !== 'a' && up.tag !== 'button')
                        up = up.parent;
                    if (up && !clean(up.text()) && !up.attrs['aria-label'])
                        ctx.add('img.decorative.interactive', e.path());
                }
            }
        }
        else if (t === 'video') {
            const kinds = e.findAll('track').map(x => (x.attrs.kind ?? '').toLowerCase());
            if (!kinds.some(k => k === 'captions' || k === 'subtitles'))
                ctx.add('media.captions.missing', e.path());
        }
        else if (t === 'iframe') {
            if (!clean(a.title))
                ctx.add('link.iframe.title', e.path());
        }
        else if (/^h[1-6]$/.test(t)) {
            seq.push([Number(t[1]), e.path()]);
            if (chars(clean(e.text())) > p.heading_max_chars)
                ctx.add('heading.too_long', e.path());
        }
        else if (t === 'table') {
            if (!clean(e.text()) && !e.findAll('img').length)
                ctx.add('table.empty', e.path());
            else {
                const ths = e.findAll('th');
                if (!ths.length)
                    ctx.add('table.header.missing', e.path());
                for (const th of ths)
                    if (!th.attrs.scope)
                        ctx.add('table.header.scope', th.path());
                if (!e.els().some(k => k.tag === 'caption'))
                    ctx.add('table.caption.missing', e.path());
            }
        }
        else if (t === 'a') {
            if (a.href !== undefined && clean(e.text()) && isGeneric(e.text()))
                ctx.add('link.text.generic', e.path());
            const next = nextSibling(e);
            if (next && next.tag === 'a' && a.href && next.attrs.href === a.href)
                ctx.add('link.adjacent.duplicate', next.path());
        }
        else if (t === 'p' && LIST_RE.test(clean(e.text()))) {
            const sib = e.parent.els(), i = sib.indexOf(e);
            const isItem = (x) => !!x && x.tag === 'p' && LIST_RE.test(clean(x.text()));
            if (isItem(sib[i + 1]) && !isItem(sib[i - 1]))
                ctx.add('list.not_marked', e.path());
        }
        const st = e.style();
        if (t === 'a' || t === 'button') {
            for (const dim of ['width', 'height']) {
                const m = (st[dim] ?? '').match(/^([\d.]+)px$/);
                if (m && parseFloat(m[1]) < p.min_target_px)
                    ctx.add('target.too_small', e.path());
            }
        }
        if (clean(e.ownText())) {
            const size = pt(st['font-size']);
            if (size !== null && size < p.min_font_pt)
                ctx.add('font.too_small', e.path());
            if ('color' in st || 'background-color' in st || 'background' in st) {
                const fg = parseColor(e.inherited('color') ?? 'black');
                let bg = null;
                for (let n = e; n && !bg; n = n.parent) {
                    const s = n.style();
                    bg = parseColor(s['background-color'] || s.background);
                }
                if (fg) {
                    const w = e.inherited('font-weight') ?? '';
                    const bold = w === 'bold' || (/^\d+$/.test(w) && Number(w) >= 700);
                    if (lowContrast(fg, bg ?? 'ffffff', pt(e.inherited('font-size')), bold, p)) {
                        ctx.add('contrast.insufficient', e.path(), { fg, bg: bg ?? 'ffffff' });
                    }
                }
            }
        }
    }
    headingSeq(ctx, seq, 'html > body', text, false);
    if (words(text).length > p.page_max_words)
        ctx.add('content.too_long', 'html > body');
}
function nextSibling(e) {
    const sibs = e.parent.kids;
    let j = sibs.indexOf(e) + 1;
    while (j < sibs.length && typeof sibs[j] === 'string' && !clean(sibs[j]))
        j++;
    const n = sibs[j];
    return n instanceof N ? n : null;
}
function prevSibling(e) {
    const sibs = e.parent.kids;
    let j = sibs.indexOf(e) - 1;
    while (!(sibs[j] instanceof N))
        j--;
    return sibs[j];
}
const escAttr = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
const escText = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
function setAttr(e, name, value) {
    const at = e.loc.startTag?.attrs?.[name] ?? e.loc.attrs?.[name];
    const text = `${name}="${escAttr(value)}"`;
    if (at)
        return [at.startOffset, at.endOffset, text];
    const start = (e.loc.startTag ?? e.loc).startOffset + 1 + e.tag.length;
    return [start, start, ' ' + text];
}
function setStyle(e, prop, value) {
    const st = { ...e.style(), [prop]: value };
    return setAttr(e, 'style', Object.entries(st).map(([k, v]) => `${k}: ${v}`).join('; '));
}
function inner(e, text) {
    const { startTag, endTag } = e.loc;
    if (!endTag)
        return noFix({ check_id: 'html', locator: e.path() });
    return [[startTag.endOffset, endTag.startOffset, text]];
}
function retag(e, tag) {
    const s = e.loc.startTag ?? e.loc;
    const out = [[s.startOffset + 1, s.startOffset + 1 + e.tag.length, tag]];
    if (e.loc.endTag)
        out.push([e.loc.endTag.startOffset + 2, e.loc.endTag.startOffset + 2 + e.tag.length, tag]);
    return out;
}
export function fixHtml(src, f) {
    const tree = parseHtml(src), e = htmlFind(tree, f.locator), c = f.check_id;
    let edits;
    if (['img.alt.missing', 'img.alt.too_long', 'img.alt.filename', 'img.alt.meaningless', 'img.decorative.interactive'].includes(c)) {
        edits = [setAttr(e, 'alt', f.decorative ? '' : need(f))];
    }
    else if (c === 'table.header.missing') {
        const row = e.findAll('tr')[0];
        if (!row)
            noFix(f);
        edits = row.els().filter(x => x.tag === 'td').flatMap(x => [...retag(x, 'th'), setAttr(x, 'scope', 'col')]);
    }
    else if (c === 'table.header.scope') {
        edits = [setAttr(e, 'scope', String(f.value || 'col'))];
    }
    else if (c === 'table.caption.missing') {
        const at = e.loc.startTag.endOffset;
        edits = [[at, at, `<caption>${escText(need(f))}</caption>`]];
    }
    else if (c === 'table.empty') {
        edits = [[e.loc.startOffset, e.loc.endOffset, '']];
    }
    else if (c === 'link.text.generic' || c === 'heading.too_long') {
        edits = inner(e, escText(need(f)));
    }
    else if (c === 'link.adjacent.duplicate') {
        const first = prevSibling(e);
        const text = src.slice(e.loc.startTag.endOffset, e.loc.endTag.startOffset);
        const at = first.loc.endTag.startOffset;
        edits = [[at, at, ' ' + text], [first.loc.endOffset, e.loc.endOffset, '']];
    }
    else if (c === 'link.iframe.title') {
        edits = [setAttr(e, 'title', need(f))];
    }
    else if (c === 'font.too_small') {
        edits = [setStyle(e, 'font-size', `${defaults.min_font_pt}pt`)];
    }
    else if (c === 'contrast.insufficient') {
        edits = [setStyle(e, 'color', '#' + need(f).replace(/^#/, ''))];
    }
    else if (c === 'heading.nesting' || c === 'heading.depth') {
        edits = retag(e, `h${Number(need(f))}`);
    }
    else
        return noFix(f);
    for (const [a, b, text] of edits.sort((x, y) => y[0] - x[0]))
        src = src.slice(0, a) + text + src.slice(b);
    return src;
}
