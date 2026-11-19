import { suggestColor } from './engine/common.js'
import { zipSync } from './vendor/fflate.js'

const worker = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' })
let seq = 0
const pending = new Map()
worker.onmessage = ({ data }) => {
  // pdf.js also posts messages on this worker. Ignore them.
  const p = data?.rpc && pending.get(data.id)
  if (!p) return
  pending.delete(data.id)
  if (data.error) p.reject(new Error(data.error))
  else p.resolve(data.result)
}
const call = msg => new Promise((resolve, reject) => {
  const id = ++seq
  pending.set(id, { resolve, reject })
  worker.postMessage({ id, ...msg })
})

const SEVERITIES = [['severe', 'Severe: blocks access'], ['major', 'Major: needs a workaround'], ['minor', 'Minor: best practice']]
const LANGS = [['en-US', 'English'], ['es', 'Spanish'], ['fr', 'French'], ['de', 'German']]
const LABELS = {
  'doc.title.missing': 'Document title', 'table.caption.missing': 'Table caption', 'link.iframe.title': 'Iframe title',
  'link.text.generic': 'Link text', 'heading.too_long': 'Heading text', 'slide.title.missing': 'Slide title',
}
const BUTTONS = {
  'table.header.missing': 'Mark first row as header', 'table.header.scope': 'Set scope to column', 'table.empty': 'Remove table',
  'link.adjacent.duplicate': 'Merge links', 'font.too_small': 'Increase font size', 'text.justified': 'Align left',
  reading_order: 'Move title first', 'doc.title.hidden': 'Show the title in the viewer', 'tag.empty': 'Change to Div', 'xlsx.a1.empty': 'Write sheet title in A1',
}
const IMG = ['img.alt.missing', 'img.alt.too_long', 'img.alt.filename', 'img.alt.meaningless', 'img.decorative.interactive']
const LEVELS = ['heading.start', 'heading.nesting', 'heading.depth']
const GUIDED = ['heading.none', 'list.not_marked']

const $ = id => document.getElementById(id)

/** Create an element. Keys that start with "on" are event handlers. */
function h(tag, props = {}, ...kids) {
  const e = document.createElement(tag)
  for (const [k, v] of Object.entries(props)) {
    if (k.startsWith('on')) e.addEventListener(k.slice(2), v)
    else if (k === 'class') e.className = v
    else if (v === true) e.setAttribute(k, '')
    else if (v !== false && v != null) e.setAttribute(k, v)
  }
  e.append(...kids.flat().filter(k => k != null))
  return e
}

// docs: one entry for each chosen file. doc: the file in the workspace.
// A doc keeps its bytes only while it is open or has fixes, so that many files do not fill memory.
const state = { docs: [], doc: null, selected: null, busy: false, page: 1 }

function setStatus(text) { $('status').textContent = text }
function setError(text) { $('error').textContent = text; $('error').hidden = !text }

// ---- fix panel ----

function fixPanel(f) {
  const hint = text => h('p', { class: 'hint' }, text)
  const c = f.check_id
  if (!f.fixable) return hint('Fix this issue in the source file, then scan again.')
  if (GUIDED.includes(c)) return hint('Fix this issue in the source file, then scan again. The tool cannot pick the structure for you.')

  const form = (control, ...more) => {
    const e = h('form', {}, control, ...more)
    e.addEventListener('submit', ev => {
      ev.preventDefault()
      const input = e.querySelector('input, select')
      applyFix(f, input ? { value: input.value } : {})
    })
    return e
  }
  const submit = (label = 'Apply fix') => h('button', { type: 'submit', disabled: state.busy }, label)
  const text = (label, value = '', extra = {}) => h('label', {}, `${label} `, h('input', { value, required: true, ...extra }))
  const select = (label, options, value) => {
    const s = h('select', {}, options.map(([v, l]) => h('option', { value: v }, l)))
    s.value = value
    return h('label', {}, `${label} `, s)
  }

  if (IMG.includes(c)) {
    return form(text('Alternative text'), submit(), ' ', h('button', {
      type: 'button', class: 'secondary', disabled: state.busy, onclick: () => applyFix(f, { decorative: true }),
    }, 'Mark as decorative'))
  }
  if (LABELS[c]) return form(text(LABELS[c]), submit())
  if (c.startsWith('doc.lang')) return form(select('Language', LANGS, 'en-US'), submit())
  if (LEVELS.includes(c)) return form(select('Heading level', [1, 2, 3, 4, 5, 6].map(n => [String(n), String(n)]), '1'), submit())
  if (c === 'contrast.insufficient') {
    const bg = f.colors?.bg ?? 'ffffff'
    const swatch = h('span', { class: 'swatch' }, 'Sample')
    const paint = v => { swatch.style.color = `#${v.replace('#', '')}`; swatch.style.background = `#${bg}` }
    const suggested = f.colors ? suggestColor(f.colors.fg, f.colors.bg) : ''
    paint(suggested)
    return form(text('Text color (hex)', suggested, { pattern: '#?[0-9a-fA-F]{6}', oninput: e => paint(e.target.value) }), swatch, submit())
  }
  return form(submit(BUTTONS[c] ?? 'Apply fix'))
}

// ---- findings ----

const keyOf = f => `${f.check_id}|${f.locator}`

function renderFindings(focusKey) {
  const { selected } = state
  const { report } = state.doc
  const host = $('findings')
  host.replaceChildren()
  if (!report.findings.length) {
    host.append(h('p', {}, 'The tool found no issues. Automatic checks do not find all accessibility problems.'))
    return
  }
  for (const [sev, label] of SEVERITIES) {
    const items = report.findings.filter(f => f.severity === sev)
    if (!items.length) continue
    host.append(h('h3', { class: `sev ${sev}` }, `${label} (${items.length})`), h('ul', { class: 'findings' }, items.map(f => {
      const open = selected === f
      const button = h('button', {
        class: 'finding', 'aria-expanded': String(open), 'data-key': keyOf(f),
        onclick: () => select(open ? null : f, keyOf(f)),
      }, f.message, h('code', {}, `${f.check_id} at ${f.locator}`))
      return h('li', { class: open ? 'open' : '' }, button, open ? fixPanel(f) : null)
    })))
  }
  if (focusKey) [...host.querySelectorAll('.finding')].find(b => b.dataset.key === focusKey)?.focus()
}

function select(f, focusKey) {
  state.selected = f
  renderFindings(focusKey)
  const m = f?.locator.match(/^page:(\d+)$/)
  if (m && state.doc.report.format === 'pdf') state.page = Number(m[1])
  renderPreview(false)
}

// ---- preview ----

let cancelPdf = null

async function drawPdf(host) {
  cancelPdf?.()
  let live = true, task, render
  const job = (async () => {
    const { pdfjs } = await import('./engine/pdf.js')
    task = pdfjs.getDocument({ data: state.doc.bytes.slice(), isEvalSupported: false, verbosity: 0 })
    const pdf = await task.promise
    if (!live) return
    state.page = Math.min(state.page, pdf.numPages)
    const page = state.page
    const canvas = h('canvas', { class: 'pdf', role: 'img', 'aria-label': `Image of page ${page}` })
    const go = n => { state.page = n; renderPreview(true) }
    host.replaceChildren(h('div', { class: 'pager' },
      h('button', { class: 'secondary', disabled: page <= 1, onclick: () => go(page - 1) }, 'Previous page'),
      h('span', {}, `Page ${page} of ${pdf.numPages}`),
      h('button', { class: 'secondary', disabled: page >= pdf.numPages, onclick: () => go(page + 1) }, 'Next page'),
    ), canvas)
    const pg = await pdf.getPage(page)
    if (!live) return
    const viewport = pg.getViewport({ scale: 1.2 })
    canvas.width = viewport.width
    canvas.height = viewport.height
    render = pg.render({ canvas, canvasContext: canvas.getContext('2d'), viewport })
    await render.promise
  })().catch(e => {
    if (live) { console.error(e); host.replaceChildren(h('p', { class: 'hint' }, 'The preview is not available for this file.')) }
  })
  cancelPdf = () => {
    live = false
    render?.cancel()
    job.finally(() => task?.destroy())
  }
}

let drawnPage = null

function renderPreview(changed) {
  const { selected } = state
  const { report, bytes } = state.doc
  const host = $('preview')
  if (report.format === 'html') {
    const mark = selected ? `<style>${selected.locator}{outline:3px solid #c00;outline-offset:2px}</style>` : ''
    host.replaceChildren(h('iframe', { class: 'preview-frame', title: 'Document preview', sandbox: '', srcdoc: new TextDecoder().decode(bytes) + mark }))
  } else if (report.format === 'pdf') {
    if (changed || drawnPage !== state.page) { drawnPage = state.page; drawPdf(host) }
  } else if (report.format === 'docx') {
    if (!changed) return
    const div = h('div', { class: 'docx' })
    host.replaceChildren(div)
    import('./vendor/docx-preview.js')
      .then(m => m.renderAsync(new Blob([bytes]), div, undefined, { inWrapper: false }))
      .catch(() => host.replaceChildren(h('p', { class: 'hint' }, 'The preview is not available for this file.')))
  } else {
    const hit = i => selected && selected.locator.startsWith(i.locator) && !i.locator.endsWith('!')
    host.replaceChildren(h('ul', { class: 'outline' }, report.outline.map(i => h('li', { class: hit(i) ? 'hit' : '' }, i.label))))
  }
}


// ---- document state ----

function renderReport() {
  const { report, undo } = state.doc
  $('score').textContent = `Estimated score: ${report.score} of 100.`
  $('count').textContent = `${report.findings.length} issues.`
  $('undo').disabled = !undo.length || state.busy
  renderFindings()
  renderPreview(true)
  if (state.docs.length > 1) renderSummary()
}

function renderSummary() {
  const num = v => h('td', { class: 'num' }, v)
  $('rows').replaceChildren(...state.docs.map(d => h('tr', { 'aria-current': d === state.doc ? 'true' : false },
    h('th', { scope: 'row' }, d.report ? h('button', { class: 'link', onclick: () => show(d) }, d.name) : d.name),
    d.report
      ? [num(String(d.report.score)), num(String(d.report.findings.length)), num(d.undo.length ? String(d.undo.length) : '')]
      : h('td', { colspan: 3, class: 'error' }, d.error))))
  $('save-all').disabled = !state.docs.some(d => d.undo.length)
}

/** Scan each file in turn. One file opens at once; more files give a summary table. */
async function load(files) {
  files = [...files]
  if (!files.length || state.busy) return
  setError('')
  cancelPdf?.()
  Object.assign(state, { docs: files.map(file => ({ file, name: file.name, bytes: null, report: null, undo: [], risks: null, error: '' })), doc: null, busy: true })
  $('workspace').hidden = true
  $('batch').hidden = true
  for (const [i, d] of state.docs.entries()) {
    setStatus(files.length > 1 ? `Checking file ${i + 1} of ${files.length}: ${d.name}.` : `Checking ${d.name}.`)
    try {
      d.report = await call({ op: 'scan', bytes: new Uint8Array(await d.file.arrayBuffer()), name: d.name })
    } catch (e) {
      d.error = `The check failed: ${e.message}`
    }
  }
  state.busy = false
  if (files.length === 1) {
    const [d] = state.docs
    if (d.error) { setError(d.error); setStatus(''); return }
    if (await show(d)) setStatus(`${d.report.findings.length} issues found in ${d.name}.`)
    return
  }
  renderSummary()
  $('batch-h').textContent = `${files.length} files`
  $('batch').hidden = false
  const failed = state.docs.filter(d => d.error).length
  const issues = state.docs.reduce((n, d) => n + (d.report?.findings.length ?? 0), 0)
  setStatus(`${files.length} files checked. ${issues} issues found.${failed ? ` ${failed} files failed.` : ''}`)
  $('batch-h').focus()
}

/** Open one scanned file in the workspace. */
async function show(d) {
  if (state.busy) return false
  const prev = state.doc
  if (prev && prev !== d && !prev.undo.length) prev.bytes = null
  cancelPdf?.()
  drawnPage = null
  Object.assign(state, { doc: d, selected: null, page: 1 })
  setError('')
  try {
    d.bytes ??= new Uint8Array(await d.file.arrayBuffer())
    if (d.risks === null) {
      const broken = d.report.findings.some(f => f.check_id === 'doc.malformed' || f.check_id === 'doc.encrypted')
      d.risks = d.report.format === 'pdf' && !broken ? await call({ op: 'risks', bytes: d.bytes.slice() }) : []
    }
  } catch (e) {
    setError(`The file ${d.name} did not open: ${e.message}`)
    return false
  }
  $('risks').textContent = `Warning: this PDF has ${d.risks.join(' and ')}. A fix rewrites the file and can damage them. Examine the output.`
  $('risks').hidden = !d.risks.length
  $('results').textContent = d.name
  $('workspace').hidden = false
  renderReport()
  if (state.docs.length > 1) setStatus(`${d.report.findings.length} issues in ${d.name}.`)
  $('results').focus()
  return true
}

async function applyFix(f, extra) {
  const d = state.doc
  state.busy = true
  setError('')
  renderFindings()
  try {
    const r = await call({ op: 'fix', bytes: d.bytes.slice(), name: d.name, fix: { check_id: f.check_id, locator: f.locator, ...extra } })
    d.undo.push({ bytes: d.bytes, report: d.report })
    Object.assign(d, { bytes: r.bytes, report: r.report })
    Object.assign(state, { selected: null, busy: false })
    renderReport()
    setStatus(`Fix applied. ${r.report.findings.length} issues remain.`)
    $('results').focus()
  } catch (e) {
    state.busy = false
    setError(e.message)
    renderFindings()
  }
}

function undo() {
  const d = state.doc
  Object.assign(d, d.undo.pop())
  state.selected = null
  renderReport()
  setStatus(`Last fix removed. ${d.report.findings.length} issues remain.`)
  $('results').focus()
}

function save(blob, filename) {
  const a = h('a', { href: URL.createObjectURL(blob), download: filename })
  a.click()
  URL.revokeObjectURL(a.href)
}

const stem = name => name.replace(/\.[^.]+$/, '')
const fixedName = name => `${stem(name)}-accessible.${name.split('.').pop()}`
const json = v => new Blob([JSON.stringify(v, null, 2)], { type: 'application/json' })
const reportOf = d => ({ source: d.name, format: d.report.format, score: d.report.score, findings: d.report.findings })

/** Zip the files that have fixes. Two files with the same name get a number prefix. */
function saveAll() {
  const out = {}
  for (const d of state.docs.filter(d => d.undo.length)) {
    let name = fixedName(d.name)
    for (let i = 2; out[name]; i++) name = `${i}-${fixedName(d.name)}`
    out[name] = d.bytes
  }
  save(new Blob([zipSync(out, { level: 0 })], { type: 'application/zip' }), 'panocheck-fixed.zip')
}

$('file').addEventListener('change', e => {
  load(e.target.files ?? [])
  e.target.value = ''
})
const drop = $('drop')
drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over') })
drop.addEventListener('dragleave', () => drop.classList.remove('over'))
drop.addEventListener('drop', e => {
  e.preventDefault()
  drop.classList.remove('over')
  load(e.dataTransfer?.files ?? [])
})
$('undo').addEventListener('click', undo)
$('save').addEventListener('click', () => save(new Blob([state.doc.bytes]), fixedName(state.doc.name)))
$('report').addEventListener('click', () => save(json(reportOf(state.doc)), `${stem(state.doc.name)}-report.json`))
$('save-all').addEventListener('click', saveAll)
$('report-all').addEventListener('click', () => save(json(state.docs.filter(d => d.report).map(reportOf)), 'panocheck-report.json'))
