// Rebuild site/vendor from node_modules. Run: npm run vendor
import { build } from 'esbuild'
import { copyFileSync } from 'node:fs'

// Named re-exports, because esbuild gives CommonJS and UMD packages only a default export.
const bundles = {
  parse5: "export { parse } from 'parse5'",
  fflate: "export { strFromU8, strToU8, unzipSync, zipSync } from 'fflate'",
  xmldom: "export { DOMParser, XMLSerializer } from '@xmldom/xmldom'",
  'pdf-lib': "export { PDFArray, PDFDict, PDFDocument, PDFHexString, PDFName, PDFNumber, PDFRef, PDFString } from 'pdf-lib'",
  'docx-preview': "export { renderAsync } from 'docx-preview'",
}
for (const [out, contents] of Object.entries(bundles)) {
  await build({
    stdin: { contents, resolveDir: process.cwd() }, bundle: true, format: 'esm', minify: true, target: 'es2022',
    platform: 'browser', outfile: `site/vendor/${out}.js`, logLevel: 'error',
  })
}
copyFileSync('node_modules/pdfjs-dist/legacy/build/pdf.min.mjs', 'site/vendor/pdf.js')
copyFileSync('node_modules/pdfjs-dist/legacy/build/pdf.worker.min.mjs', 'site/vendor/pdf.worker.js')
