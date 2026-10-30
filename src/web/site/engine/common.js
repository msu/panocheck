import spec from './spec.js';
export { spec };
export const defaults = spec.params;
export const vocab = spec.vocab;
export const checks = Object.fromEntries(spec.checks.map((c) => [c.id, c]));
export function runsOnWeb(id, fmt) {
    const c = checks[id];
    if (c.engines && !c.engines.includes('web'))
        return false;
    const by = c.engines_by_format?.[fmt];
    return !by || by.includes('web');
}
export class Ctx {
    fmt;
    p;
    findings = [];
    constructor(fmt, p) {
        this.fmt = fmt;
        this.p = p;
    }
    add(id, locator, colors) {
        if (!runsOnWeb(id, this.fmt))
            return;
        if (this.findings.some(f => f.check_id === id && f.locator === locator))
            return;
        const c = checks[id];
        const message = c.message.replace(/\{(\w+)\}/g, (_, k) => String(this.p[k]));
        const fixable = c.web_fix !== 'none' && !(c.web_fix_except ?? []).includes(this.fmt);
        this.findings.push({ check_id: id, severity: c.severity, format: this.fmt, locator, message, fixable, ...(colors ? { colors } : {}) });
    }
}
export class Malformed extends Error {
}
export class FixError extends Error {
}
const WS = ' \\t\\n\\r\\f\\v\\u00a0\\u2000-\\u200a\\u2028\\u2029\\u3000';
const WS_RE = new RegExp(`[${WS}]+`, 'g');
export const LIST_RE = new RegExp(`^(\\d+[.)]|[-*\\u2022])[${WS}]`);
export const ALT_FILE_RE = /^[^ ]+\.(png|jpe?g|gif|svg|webp|bmp|tiff?)$/i;
export const clean = (s) => (s ?? '').replace(WS_RE, ' ').replace(/^ +| +$/g, '');
export const words = (s) => (s ?? '').split(WS_RE).filter(Boolean);
export const chars = (s) => [...s].length;
export function isGeneric(text) {
    const t = clean(text).toLowerCase().replace(/[.:!]+$/, '');
    return vocab.generic_link.includes(t) || /^https?:\/\//.test(t);
}
export function detectLang(text, p) {
    const toks = text.toLowerCase().match(/\p{L}+/gu) ?? [];
    if (toks.length < p.lang_min_words)
        return null;
    const scores = Object.keys(vocab.stopwords).sort().map(lang => {
        const set = new Set(vocab.stopwords[lang]);
        return [toks.filter(t => set.has(t)).length, lang];
    }).sort((a, b) => b[0] - a[0]);
    if (scores[0][0] < 3 || scores[0][0] < scores[1][0] * 1.5)
        return null;
    return scores[0][1];
}
export function langWrong(declared, text, p) {
    if (!declared)
        return false;
    const d = declared.toLowerCase().split('-')[0];
    const found = detectLang(text, p);
    return d in vocab.stopwords && found !== null && found !== d;
}
export function luminance(hex) {
    const ch = (i) => {
        const v = parseInt(hex.slice(i, i + 2), 16) / 255;
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * ch(0) + 0.7152 * ch(2) + 0.0722 * ch(4);
}
export function contrastRatio(a, b) {
    const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m);
    return (x + 0.05) / (y + 0.05);
}
export function lowContrast(fg, bg, pt, bold, p) {
    const large = pt !== null && (pt >= p.large_text_pt || (bold && pt >= p.large_bold_text_pt));
    return contrastRatio(fg, bg) < (large ? p.contrast_large : p.contrast_normal);
}
function hls(hex) {
    const [r, g, b] = [0, 2, 4].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
    const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
    if (max === min)
        return [0, l, 0];
    const d = max - min, s = l <= 0.5 ? d / (max + min) : d / (2 - max - min);
    const h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return [h / 6, l, s];
}
function toHex(h, l, s) {
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
    const f = (t) => {
        t = (t + 1) % 1;
        if (t < 1 / 6)
            return p + (q - p) * 6 * t;
        if (t < 1 / 2)
            return q;
        if (t < 2 / 3)
            return p + (q - p) * (2 / 3 - t) * 6;
        return p;
    };
    const c = s === 0 ? [l, l, l] : [f(h + 1 / 3), f(h), f(h - 1 / 3)];
    return c.map(v => Math.round(v * 255).toString(16).padStart(2, '0')).join('');
}
/** Keep the hue. Move lightness until the ratio passes. */
export function suggestColor(fg, bg, target = 4.5) {
    const [h, start, s] = hls(fg);
    const step = luminance(bg) > 0.18 ? -0.01 : 0.01;
    for (let l = start; l >= 0 && l <= 1; l += step) {
        const c = toHex(h, l, s);
        if (contrastRatio(c, bg) >= target)
            return c;
    }
    return step < 0 ? '000000' : 'ffffff';
}
export function headingSeq(ctx, seq, noneLoc, text, checkStart) {
    if (!seq.length) {
        if (words(text).length >= ctx.p.heading_min_words)
            ctx.add('heading.none', noneLoc);
        return;
    }
    if (checkStart && seq[0][0] !== 1)
        ctx.add('heading.start', seq[0][1]);
    let prev = null;
    for (const [level, loc] of seq) {
        if (prev !== null && level > prev + 1)
            ctx.add('heading.nesting', loc);
        if (level > ctx.p.heading_max_depth)
            ctx.add('heading.depth', loc);
        prev = level;
    }
}
export function score(findings) {
    return Math.max(0, 100 - findings.reduce((n, f) => n + spec.severity_weights[f.severity], 0));
}
export function need(f) {
    if (f.value === undefined || f.value === null || f.value === '') {
        throw new FixError(`The fix for ${f.check_id} failed because the value is empty. Enter a value.`);
    }
    return String(f.value);
}
export function noFix(f) {
    throw new FixError(`The check ${f.check_id} has no automatic fix for ${f.locator}. Fix the source file.`);
}
