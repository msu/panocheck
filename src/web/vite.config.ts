/// <reference types="vitest" />
import { defineConfig, type Plugin } from 'vite'
import preact from '@preact/preset-vite'
import { parse } from 'yaml'

const yaml = (): Plugin => ({
  name: 'yaml',
  enforce: 'pre',
  transform(code, id) {
    if (id.endsWith('.yaml')) return { code: `export default ${JSON.stringify(parse(code))}`, map: null }
  },
})

// connect-src 'none' stops the page from sending document bytes anywhere.
const CSP = [
  "default-src 'none'", "script-src 'self'", "style-src 'self' 'unsafe-inline'", "img-src 'self' data: blob:",
  "font-src 'self' data:", "worker-src 'self'", "frame-src 'self' about:", "connect-src 'none'", "base-uri 'none'", "form-action 'none'",
].join('; ')

const csp = (): Plugin => ({
  name: 'csp',
  apply: 'build',
  transformIndexHtml: () => [{ tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: CSP }, injectTo: 'head-prepend' }],
})

export default defineConfig({
  base: './',
  plugins: [yaml(), csp(), preact()],
  worker: { format: 'es', plugins: () => [yaml()] },
  build: { target: 'es2022' },
  server: { fs: { allow: ['..', '../..'] } },
  test: { include: ['tests/**/*.test.ts'] },
})
