import { render } from 'preact'
import { useEffect, useMemo, useRef, useState } from 'preact/hooks'
import pdfWorker from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'
import { checks, suggestColor, type Finding, type Fix } from './engine/common'
import type { OutlineItem } from './engine/ooxml'
import './style.css'

const worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' })
let seq = 0
const pending = new Map<number, [(v: any) => void, (e: Error) => void]>()
worker.onmessage = ({ data }) => {
  // pdf.js also posts messages on this worker. Ignore them.
  const p = data?.rpc && pending.get(data.id)
  if (!p) return
  pending.delete(data.id)
  if (data.error) p[1](new Error(data.error))
  else p[0](data.result)
}
const call = (msg: any) => new Promise<any>((res, rej) => {
  const id = ++seq
  pending.set(id, [res, rej])
  worker.postMessage({ id, ...msg })
})

interface Report { format: string; findings: Finding[]; score: number; outline: OutlineItem[] }
const SEVERITIES = [['severe', 'Severe: blocks access'], ['major', 'Major: needs a workaround'], ['minor', 'Minor: best practice']] as const
const LANGS = [['en-US', 'English'], ['es', 'Spanish'], ['fr', 'French'], ['de', 'German']]
const LABELS: Record<string, string> = {
  'doc.title.missing': 'Document title', 'table.caption.missing': 'Table caption', 'link.iframe.title': 'Iframe title',
  'link.text.generic': 'Link text', 'heading.too_long': 'Heading text', 'slide.title.missing': 'Slide title',
}
const IMG = ['img.alt.missing', 'img.alt.too_long', 'img.alt.filename', 'img.alt.meaningless', 'img.decorative.interactive']
const LEVELS = ['heading.start', 'heading.nesting', 'heading.depth']
const GUIDED = ['heading.none', 'list.not_marked']

function FixPanel({ f, onApply, busy }: { f: Finding; onApply: (x: Partial<Fix>) => void; busy: boolean }) {
  const suggested = f.colors ? suggestColor(f.colors.fg, f.colors.bg) : ''
  const [value, setValue] = useState(f.check_id.startsWith('doc.lang') ? 'en-US' : LEVELS.includes(f.check_id) ? '1' : suggested)
  const apply = (extra: Partial<Fix> = {}) => onApply({ value, ...extra })
  const submit = (e: Event) => { e.preventDefault(); apply() }
  const c = f.check_id
  if (!f.fixable) return <p class="hint">Fix this issue in the source file, then scan again.</p>
  if (GUIDED.includes(c)) return <p class="hint">Fix this issue in the source file, then scan again. The tool cannot pick the structure for you.</p>
  const button = (label = 'Apply fix') => <button type="submit" disabled={busy}>{label}</button>
  if (IMG.includes(c)) {
    return <form onSubmit={submit}>
      <label>Alternative text <input value={value} required onInput={e => setValue(e.currentTarget.value)} /></label>
      {button()} <button type="button" class="secondary" disabled={busy} onClick={() => apply({ decorative: true })}>Mark as decorative</button>
    </form>
  }
  if (LABELS[c]) {
    return <form onSubmit={submit}>
      <label>{LABELS[c]} <input value={value} required onInput={e => setValue(e.currentTarget.value)} /></label>{button()}
    </form>
  }
  if (c.startsWith('doc.lang')) {
    return <form onSubmit={submit}>
      <label>Language <select value={value} onChange={e => setValue(e.currentTarget.value)}>
        {LANGS.map(([v, l]) => <option value={v}>{l}</option>)}
      </select></label>{button()}
    </form>
  }
  if (LEVELS.includes(c)) {
    return <form onSubmit={submit}>
      <label>Heading level <select value={value} onChange={e => setValue(e.currentTarget.value)}>
        {[1, 2, 3, 4, 5, 6].map(n => <option value={String(n)}>{n}</option>)}
      </select></label>{button()}
    </form>
  }
  if (c === 'contrast.insufficient') {
    return <form onSubmit={submit}>
      <label>Text color (hex) <input value={value} pattern="#?[0-9a-fA-F]{6}" required onInput={e => setValue(e.currentTarget.value)} /></label>
      <span class="swatch" style={{ color: `#${value.replace('#', '')}`, background: `#${f.colors?.bg ?? 'ffffff'}` }}>Sample</span>
      {button()}
    </form>
  }
  const labels: Record<string, string> = {
    'table.header.missing': 'Mark first row as header', 'table.header.scope': 'Set scope to column', 'table.empty': 'Remove table',
    'link.adjacent.duplicate': 'Merge links', 'font.too_small': 'Increase font size', 'text.justified': 'Align left',
    reading_order: 'Move title first', 'xlsx.a1.empty': 'Write sheet title in A1',
  }
  return <form onSubmit={submit}>{button(labels[c] ?? 'Apply fix')}</form>
}

function HtmlPreview({ bytes, selected }: { bytes: Uint8Array; selected: Finding | null }) {
  const doc = useMemo(() => {
    const src = new TextDecoder().decode(bytes)
    const mark = selected ? `<style>${selected.locator}{outline:3px solid #c00;outline-offset:2px}</style>` : ''
    return src + mark
  }, [bytes, selected])
  return <iframe class="preview-frame" title="Document preview" sandbox="" srcDoc={doc} />
}

function PdfPreview({ bytes, selected }: { bytes: Uint8Array; selected: Finding | null }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [page, setPage] = useState(1)
  const [count, setCount] = useState(0)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    const m = selected?.locator.match(/^page:(\d+)$/)
    if (m) setPage(Number(m[1]))
  }, [selected])
  useEffect(() => {
    let live = true
    let task: any, render: any
    const job = (async () => {
      const { pdfjs } = await import('./engine/pdf')
      pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker
      task = pdfjs.getDocument({ data: bytes.slice(), isEvalSupported: false, verbosity: 0 })
      const pdf = await task.promise
      if (!live) return
      setCount(pdf.numPages)
      const pg = await pdf.getPage(Math.min(page, pdf.numPages))
      if (!live) return
      const viewport = pg.getViewport({ scale: 1.2 })
      const c = canvas.current!
      c.width = viewport.width
      c.height = viewport.height
      render = pg.render({ canvas: c, canvasContext: c.getContext('2d')!, viewport })
      await render.promise
    })().catch(e => { if (live) { console.error(e); setFailed(true) } })
    return () => {
      live = false
      render?.cancel()
      job.finally(() => task?.destroy())
    }
  }, [bytes, page])
  if (failed) return <p class="hint">The preview is not available for this file.</p>
  return <div>
    <div class="pager">
      <button class="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous page</button>
      <span>Page {page} of {count}</span>
      <button class="secondary" disabled={page >= count} onClick={() => setPage(page + 1)}>Next page</button>
    </div>
    <canvas ref={canvas} class="pdf" role="img" aria-label={`Image of page ${page}`} />
  </div>
}

function DocxPreview({ bytes }: { bytes: Uint8Array }) {
  const host = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    import('docx-preview').then(m => m.renderAsync(new Blob([bytes as BlobPart]), host.current!, undefined, { inWrapper: false })).catch(() => setFailed(true))
  }, [bytes])
  return failed ? <p class="hint">The preview is not available for this file.</p> : <div ref={host} class="docx" />
}

function Outline({ items, selected }: { items: OutlineItem[]; selected: Finding | null }) {
  return <ul class="outline">
    {items.map(i => <li class={selected && selected.locator.startsWith(i.locator) && !i.locator.endsWith('!') ? 'hit' : ''}>{i.label}</li>)}
  </ul>
}

function App() {
  const [name, setName] = useState('')
  const [bytes, setBytes] = useState<Uint8Array | null>(null)
  const [undo, setUndo] = useState<{ bytes: Uint8Array; report: Report }[]>([])
  const [report, setReport] = useState<Report | null>(null)
  const [selected, setSelected] = useState<Finding | null>(null)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [risks, setRisks] = useState<string[]>([])
  const [drag, setDrag] = useState(false)
  const results = useRef<HTMLHeadingElement>(null)

  async function open(file: File) {
    setError(''); setBusy(true); setSelected(null); setUndo([]); setReport(null); setBytes(null); setRisks([])
    setStatus(`Checking ${file.name}.`)
    try {
      const data = new Uint8Array(await file.arrayBuffer())
      const r: Report = await call({ op: 'scan', bytes: data.slice(), name: file.name })
      setName(file.name); setBytes(data); setReport(r)
      if (r.format === 'pdf' && !r.findings.some(f => f.check_id === 'doc.malformed' || f.check_id === 'doc.encrypted')) {
        setRisks(await call({ op: 'risks', bytes: data.slice() }))
      }
      setStatus(`${r.findings.length} issues found in ${file.name}.`)
      setTimeout(() => results.current?.focus())
    } catch (e: any) {
      setError(e.message); setStatus('')
    }
    setBusy(false)
  }

  async function applyFix(f: Finding, extra: Partial<Fix>) {
    setBusy(true); setError('')
    try {
      const r = await call({ op: 'fix', bytes: bytes!.slice(), name, fix: { check_id: f.check_id, locator: f.locator, ...extra } })
      setUndo([...undo, { bytes: bytes!, report: report! }])
      setBytes(r.bytes); setReport(r.report); setSelected(null)
      setStatus(`Fix applied. ${r.report.findings.length} issues remain.`)
    } catch (e: any) { setError(e.message) }
    setBusy(false)
  }

  function revert() {
    const last = undo[undo.length - 1]
    setBytes(last.bytes); setReport(last.report); setUndo(undo.slice(0, -1)); setSelected(null)
    setStatus(`Last fix removed. ${last.report.findings.length} issues remain.`)
  }

  function save(blob: Blob, filename: string) {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    a.click()
    URL.revokeObjectURL(a.href)
  }
  const stem = name.replace(/\.[^.]+$/, ''), ext = name.split('.').pop()

  return <>
    <a class="skip" href="#main">Skip to content</a>
    <header class="bar">
      <div class="wrap">
        <a class="dept" href="https://www.cs.montana.edu/">Montana State University <span>Gianforte School of Computing</span></a>
      </div>
    </header>
    <main id="main" class="wrap">
      <h1>panocheck</h1>
      <p class="lead">Check a document for accessibility issues, fix them, and download a corrected copy.</p>
      <p class="privacy"><strong>Your file stays on your computer.</strong> This page has no server, and its security policy blocks all network requests.</p>

      <label class={`drop ${drag ? 'over' : ''}`}
        onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); const f = e.dataTransfer?.files[0]; if (f) open(f) }}>
        <span>Drop a file here, or choose a file</span>
        <small>HTML, DOCX, PPTX, XLSX or PDF</small>
        <input type="file" accept=".html,.htm,.docx,.pptx,.xlsx,.pdf" onChange={e => { const f = e.currentTarget.files?.[0]; if (f) open(f); e.currentTarget.value = '' }} />
      </label>

      <p role="status" class="status">{status}</p>
      {error && <p role="alert" class="error">{error}</p>}

      {report && bytes && <div class="grid">
        <section aria-labelledby="results">
          <h2 id="results" tabIndex={-1} ref={results}>{name}</h2>
          <p><strong>Estimated score: {report.score} of 100.</strong> {report.findings.length} issues.</p>
          <p class="hint">The score is an estimate. Use it only to compare versions of a file.</p>
          <div class="actions">
            <button onClick={() => save(new Blob([bytes as BlobPart]), `${stem}-accessible.${ext}`)}>Download fixed copy</button>
            <button class="secondary" onClick={() => save(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }), `${stem}-report.json`)}>Download report</button>
            <button class="secondary" disabled={!undo.length || busy} onClick={revert}>Undo last fix</button>
          </div>
          {risks.length > 0 && <p class="warn">Warning: this PDF has {risks.join(' and ')}. A fix rewrites the file and can damage them. Examine the output.</p>}
          {!report.findings.length && <p>The tool found no issues. Automatic checks do not find all accessibility problems.</p>}
          {SEVERITIES.map(([sev, label]) => {
            const items = report.findings.filter(f => f.severity === sev)
            return items.length > 0 && <div key={sev}>
              <h3 class={`sev ${sev}`}>{label} ({items.length})</h3>
              <ul class="findings">
                {items.map(f => {
                  const open = selected === f
                  return <li key={f.check_id + f.locator} class={open ? 'open' : ''}>
                    <button class="finding" aria-expanded={open} onClick={() => setSelected(open ? null : f)}>
                      {f.message}
                      <code>{f.check_id} at {f.locator}</code>
                    </button>
                    {open && <FixPanel f={f} busy={busy} onApply={x => applyFix(f, x)} />}
                  </li>
                })}
              </ul>
            </div>
          })}
        </section>
        <section aria-labelledby="preview-h" class="preview">
          <h2 id="preview-h">Preview</h2>
          {report.format === 'html' && <HtmlPreview bytes={bytes} selected={selected} />}
          {report.format === 'pdf' && <PdfPreview bytes={bytes} selected={selected} />}
          {report.format === 'docx' && <DocxPreview key={bytes.length + undo.length} bytes={bytes} />}
          {(report.format === 'pptx' || report.format === 'xlsx') && <Outline items={report.outline} selected={selected} />}
        </section>
      </div>}
    </main>
    <footer class="foot">
      <div class="wrap">
        <p>panocheck is open source. <a href="https://github.com/msu/panocheck">Read the code</a>. Checks: {Object.keys(checks).length}. Automatic checks do not replace a manual review.</p>
      </div>
    </footer>
  </>
}

render(<App />, document.getElementById('app')!)
