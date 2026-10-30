import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: 'e2e',
  use: { baseURL: 'http://localhost:4173' },
  webServer: { command: 'python3 -m http.server 4173 -d site', port: 4173, reuseExistingServer: true },
})
