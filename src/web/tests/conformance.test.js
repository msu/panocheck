import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { applyFix, checks, runsOnWeb, scan } from '../site/engine/index.js';
const FX = resolve(import.meta.dirname, '../../../fixtures');
const expected = JSON.parse(readFileSync(`${FX}/expected.json`, 'utf8'));
const read = (p) => new Uint8Array(readFileSync(`${FX}/${p}`));
const norm = (fs) => fs.map(f => ({ check_id: f.check_id, severity: f.severity, locator: f.locator }))
    .sort((a, b) => (a.check_id + '\0' + a.locator < b.check_id + '\0' + b.locator ? -1 : 1));
describe('conformance', () => {
    for (const path of Object.keys(expected).sort()) {
        const fmt = path.split('/')[0];
        it(path, async () => {
            const want = expected[path].findings.filter((f) => runsOnWeb(f.check_id, fmt));
            expect(norm((await scan(read(path), path)).findings)).toEqual(norm(want));
        });
    }
});
const NO_FIX = new Set(Object.values(checks).filter((c) => c.web_fix === 'none').map((c) => c.id));
const value = (c, path) => {
    if (c === 'doc.lang.wrong')
        return 'es';
    if (c.startsWith('doc.lang'))
        return 'en-US';
    if (c === 'contrast.insufficient')
        return path.includes('fail-2') ? 'ffffff' : '111111';
    if (c === 'heading.nesting')
        return 2;
    if (c === 'heading.depth')
        return 4;
    if (c === 'heading.start')
        return 1;
    if (c === 'heading.too_long')
        return 'Short';
    if (c.startsWith('img.') || c.startsWith('doc.title') || c === 'table.caption.missing' || c === 'link.iframe.title' || c === 'slide.title.missing')
        return 'A value';
    if (c === 'link.text.generic')
        return 'Course syllabus';
};
const guided = new Set(['heading.none', 'list.not_marked']);
describe('fix round trip', () => {
    for (const path of Object.keys(expected).sort()) {
        const fmt = path.split('/')[0], check = path.split('/')[1];
        const c = checks[check];
        if (!path.includes('/fail') || NO_FIX.has(check) || guided.has(check) || (c.web_fix_except ?? []).includes(fmt))
            continue;
        it(path, async () => {
            let data = read(path);
            for (const f of (await scan(data, path)).findings) {
                data = await applyFix(data, path, { check_id: f.check_id, locator: f.locator, value: value(f.check_id, path) });
            }
            expect((await scan(data, path)).findings).toEqual([]);
        });
    }
    it('keeps other HTML bytes', async () => {
        const src = '<!-- keep   me --><P CLASS=x>a</P><IMG src=a.png>';
        const data = new TextEncoder().encode(src);
        const f = (await scan(data, 'a.html')).findings[0];
        const out = new TextDecoder().decode(await applyFix(data, 'a.html', { ...f, value: 'Alt' }));
        expect(out).toBe('<!-- keep   me --><P CLASS=x>a</P><IMG alt="Alt" src=a.png>');
    });
    it('marks an image as decorative', async () => {
        const path = 'docx/img.alt.missing/fail-1.docx', data = read(path);
        const f = (await scan(data, path)).findings[0];
        const out = await applyFix(data, path, { ...f, decorative: true });
        expect((await scan(out, path)).findings).toEqual([]);
    });
});
