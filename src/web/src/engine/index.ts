import { Ctx, Malformed, defaults, score, type Finding, type Fix, type Format, type Params } from './common'
import { checkHtml, decode, fixHtml } from './html'
import { Pkg, checkDocx, checkPptx, checkXlsx, fixDocx, fixPptx, fixXlsx, outline, type OutlineItem } from './ooxml'
import { checkPdf, fixPdf, pdfRisks } from './pdf'

export * from './common'
export { pdfRisks, type OutlineItem }

export function detect(data: Uint8Array, name = ''): Format {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  const latin = String.fromCharCode(...data.subarray(0, 2048))
  if (latin.slice(0, 1024).includes('%PDF-')) return 'pdf'
  if (latin.slice(0, 2) === 'PK') {
    try {
      const names = Object.keys(new Pkg(data).files)
      for (const [prefix, fmt] of [['word/', 'docx'], ['ppt/', 'pptx'], ['xl/', 'xlsx']] as const) {
        if (names.some(x => x.startsWith(prefix))) return fmt
      }
    } catch { /* falls through to the extension */ }
  }
  if (['docx', 'pptx', 'xlsx', 'pdf'].includes(ext)) return ext as Format
  const head = latin.replace(/^(\xef\xbb\xbf)?[ \t\r\n]*/, '').toLowerCase()
  if (ext === 'html' || ext === 'htm' || head.startsWith('<')) return 'html'
  throw new Error(`The format of ${name || 'the file'} is not known. Use HTML, DOCX, PPTX, XLSX or PDF.`)
}

const OOXML: Record<string, (p: Pkg, c: Ctx) => void> = { docx: checkDocx, pptx: checkPptx, xlsx: checkXlsx }
const OOXML_FIX: Record<string, (p: Pkg, f: Fix) => void> = { docx: fixDocx, pptx: fixPptx, xlsx: fixXlsx }

export async function scan(data: Uint8Array, name = '', params: Params = defaults) {
  const format = detect(data, name), ctx = new Ctx(format, params)
  let items: OutlineItem[] = []
  try {
    if (format === 'html') checkHtml(decode(data), ctx)
    else if (format === 'pdf') await checkPdf(data, ctx)
    else {
      const pkg = new Pkg(data)
      OOXML[format](pkg, ctx)
      if (format !== 'docx') items = outline(pkg, format)
    }
  } catch (e) {
    if (!(e instanceof Malformed) && !(e instanceof TypeError)) throw e
    ctx.findings = []
    ctx.add('doc.malformed', 'document')
  }
  return { format, findings: ctx.findings as Finding[], score: score(ctx.findings), outline: items }
}

export async function applyFix(data: Uint8Array, name: string, fix: Fix): Promise<Uint8Array> {
  const format = detect(data, name)
  if (format === 'html') return new TextEncoder().encode(fixHtml(decode(data), fix))
  if (format === 'pdf') return fixPdf(data, fix)
  const pkg = new Pkg(data)
  OOXML_FIX[format](pkg, fix)
  return pkg.save()
}
