import { PDFArray, PDFDict, PDFDocument, PDFHexString, PDFName, PDFNumber, PDFRef, PDFString } from '../vendor/pdf-lib.js';
import * as pdfjs from '../vendor/pdf.js';
import { Malformed, clean, headingSeq, need, noFix } from './common.js';
pdfjs.GlobalWorkerOptions.workerSrc = new URL('../vendor/pdf.worker.js', import.meta.url).href;
export { pdfjs };
const n = (s) => PDFName.of(s);
const nameOf = (o) => o instanceof PDFName ? o.decodeText() : String(o ?? '').replace(/^\//, '');
const strOf = (o) => o instanceof PDFString || o instanceof PDFHexString ? o.decodeText() : '';
function structOf(doc) {
    const ctx = doc.context, els = [], order = [];
    const root = doc.catalog.lookup(n('StructTreeRoot'));
    if (!(root instanceof PDFDict))
        return { els, order };
    const rolemap = root.lookup(n('RoleMap'));
    const seen = new Set();
    const refKey = (r) => r instanceof PDFRef ? r.toString() : null;
    const visit = (raw, pg, parent) => {
        if (raw instanceof PDFRef) {
            if (seen.has(raw.toString()))
                return;
            seen.add(raw.toString());
        }
        const node = ctx.lookup(raw);
        if (node instanceof PDFArray) {
            node.asArray().forEach(k => visit(k, pg, parent));
            return;
        }
        if (!(node instanceof PDFDict))
            return;
        const page = refKey(node.get(n('Pg'))) ?? pg;
        if (node.lookup(n('Type')) === n('MCR')) {
            const m = node.lookup(n('MCID'));
            if (m instanceof PDFNumber) {
                order.push([page, m.asNumber()]);
                parent?.mcids.push(`${page}:${m.asNumber()}`);
            }
            return;
        }
        const S = node.lookup(n('S'));
        if (!S)
            return;
        let s = nameOf(S);
        if (rolemap instanceof PDFDict && rolemap.lookup(n(s)))
            s = nameOf(rolemap.lookup(n(s)));
        const el = { n: els.length + 1, type: s, alt: strOf(node.lookup(n('Alt'))), node, mcids: [], kids: [] };
        els.push(el);
        parent?.kids.push(el);
        const k = node.get(n('K')), kv = k ? ctx.lookup(k) : undefined;
        for (const kid of kv instanceof PDFArray ? kv.asArray() : k ? [k] : []) {
            const v = ctx.lookup(kid);
            if (v instanceof PDFNumber) {
                order.push([page, v.asNumber()]);
                el.mcids.push(`${page}:${v.asNumber()}`);
            }
            else
                visit(kid, page, el);
        }
    };
    const k = root.get(n('K'));
    if (k)
        visit(k, null, null);
    return { els, order };
}
const TEXT_TAGS = new Set(['P', 'H', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'LI', 'Lbl', 'LBody']);
const subtree = (el) => [el, ...el.kids.flatMap(subtree)];
/** A text tag must show text. A tag that holds a figure is not empty. */
function tagIsEmpty(el, withText) {
    const nodes = subtree(el);
    return TEXT_TAGS.has(el.type) && !nodes.some(x => x.type === 'Figure') && !nodes.some(x => x.mcids.some(m => withText.has(m)));
}
/** Compare MCIDs with one reference. Chrome references a page-wide wrapper MCID from several tags, so its position has no meaning. */
function orderDecreases(mcids) {
    const once = mcids.filter(m => mcids.indexOf(m) === mcids.lastIndexOf(m));
    return once.some((v, j) => j > 0 && v < once[j - 1]);
}
function descendants(doc, node, rolemap) {
    const out = [];
    const k = node.get(n('K')), kv = k ? doc.context.lookup(k) : undefined;
    for (const kid of kv instanceof PDFArray ? kv.asArray() : k ? [k] : []) {
        const v = doc.context.lookup(kid);
        if (v instanceof PDFDict && v.lookup(n('S'))) {
            let s = nameOf(v.lookup(n('S')));
            if (rolemap instanceof PDFDict && rolemap.lookup(n(s)))
                s = nameOf(rolemap.lookup(n(s)));
            out.push(s, ...descendants(doc, v, rolemap));
        }
    }
    return out;
}
export async function loadPdf(data) {
    return PDFDocument.load(data, { ignoreEncryption: true, updateMetadata: false, throwOnInvalidObject: true });
}
export async function checkPdf(data, ctx) {
    const p = ctx.p;
    let doc;
    try {
        doc = await loadPdf(data);
        doc.getPages();
    }
    catch (e) {
        throw new Malformed(String(e));
    }
    if (doc.isEncrypted) {
        ctx.add('doc.encrypted', 'document');
        return;
    }
    if (!clean(doc.getTitle()))
        ctx.add('doc.title.missing', 'document');
    else if (!doc.catalog.getViewerPreferences()?.getDisplayDocTitle())
        ctx.add('doc.title.hidden', 'document');
    if (!clean(strOf(doc.catalog.lookup(n('Lang')))))
        ctx.add('doc.lang.missing', 'document');
    const mark = doc.catalog.lookup(n('MarkInfo'));
    const marked = mark instanceof PDFDict && String(mark.lookup(n('Marked'))) === 'true';
    const tagged = !!doc.catalog.lookup(n('StructTreeRoot')) && marked;
    if (!tagged)
        ctx.add('pdf.untagged', 'document');
    const task = pdfjs.getDocument({ data: data.slice(), isEvalSupported: false, verbosity: 0 });
    const pdf = await task.promise;
    let anyText = false;
    const allText = [];
    const withText = new Set();
    const pageRefs = doc.getPages().map(pg => pg.ref.toString());
    for (let i = 1; i <= pdf.numPages; i++) {
        const tc = await (await pdf.getPage(i)).getTextContent({ includeMarkedContent: true });
        let small = false;
        const stack = [];
        for (const item of tc.items) {
            if (item.type === 'beginMarkedContent' || item.type === 'beginMarkedContentProps') {
                stack.push(item.id?.match(/_mc(\d+)$/)?.[1] ?? null);
                continue;
            }
            if (item.type === 'endMarkedContent') {
                stack.pop();
                continue;
            }
            for (const m of stack)
                if (m !== null)
                    withText.add(`${pageRefs[i - 1]}:${m}`);
            if (!clean(item.str))
                continue;
            anyText = true;
            allText.push(item.str);
            const size = Math.hypot(item.transform[2], item.transform[3]);
            if (size < p.min_font_pt - 0.01)
                small = true;
        }
        if (small)
            ctx.add('font.too_small', `page:${i}`);
    }
    await task.destroy();
    const pages = doc.getPages();
    if (pages.length && !anyText)
        ctx.add('pdf.scanned', 'document');
    if (!tagged)
        return;
    const { els, order } = structOf(doc);
    const rolemap = doc.catalog.lookup(n('StructTreeRoot')).lookup(n('RoleMap'));
    const seq = [];
    for (const e of els) {
        const l = `struct:${e.n}:${e.type}`;
        if (e.type === 'Figure' && !clean(e.alt))
            ctx.add('img.alt.missing', l);
        if (tagIsEmpty(e, withText))
            ctx.add('tag.empty', l);
        const m = e.type.match(/^H([1-6])$/);
        if (m)
            seq.push([Number(m[1]), l]);
        if (e.type === 'Table' && !descendants(doc, e.node, rolemap).includes('TH'))
            ctx.add('table.header.missing', l);
    }
    headingSeq(ctx, seq, 'document', allText.join(' '), true);
    pages.forEach((page, i) => {
        if (orderDecreases(order.filter(o => o[0] === page.ref.toString() && withText.has(`${o[0]}:${o[1]}`)).map(o => o[1])))
            ctx.add('reading_order', `page:${i + 1}`);
    });
}
/** Features that the pdf-lib rewrite can damage. */
export async function pdfRisks(data) {
    const doc = await loadPdf(data), risks = [];
    const form = doc.catalog.lookup(n('AcroForm'));
    if (form instanceof PDFDict) {
        risks.push('form fields');
        if (form.lookup(n('SigFlags')))
            risks.push('signatures');
    }
    return risks;
}
export async function fixPdf(data, f) {
    const doc = await loadPdf(data), c = f.check_id;
    if (c === 'doc.title.missing')
        doc.setTitle(need(f), { showInWindowTitleBar: true });
    else if (c === 'doc.title.hidden')
        doc.catalog.getOrCreateViewerPreferences().setDisplayDocTitle(true);
    else if (c === 'tag.empty') {
        const el = structOf(doc).els.find(e => `struct:${e.n}:${e.type}` === f.locator);
        if (!el)
            return noFix(f);
        el.node.set(n('S'), n('Div'));
    }
    else if (c === 'doc.lang.missing')
        doc.catalog.set(n('Lang'), PDFHexString.fromText(need(f)));
    else if (c === 'img.alt.missing') {
        const el = structOf(doc).els.find(e => `struct:${e.n}:${e.type}` === f.locator);
        if (!el)
            return noFix(f);
        if (f.decorative)
            el.node.set(n('S'), n('Artifact'));
        else
            el.node.set(n('Alt'), PDFHexString.fromText(need(f)));
    }
    else
        return noFix(f);
    return doc.save({ useObjectStreams: false, updateFieldAppearances: false });
}
