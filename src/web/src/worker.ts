import pdfWorker from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'
import { applyFix, pdfRisks, scan } from './engine'
import { pdfjs } from './engine/pdf'

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker

self.addEventListener('message', async ({ data: { id, op, bytes, name, fix } }: MessageEvent) => {
  if (!op) return
  try {
    let result: any
    if (op === 'fix') {
      const next = await applyFix(bytes, name, fix)
      result = { bytes: next, report: await scan(next, name) }
    } else if (op === 'risks') result = await pdfRisks(bytes)
    else result = await scan(bytes, name)
    self.postMessage({ rpc: true, id, result })
  } catch (e) {
    self.postMessage({ rpc: true, id, error: e instanceof Error ? e.message : String(e) })
  }
})
