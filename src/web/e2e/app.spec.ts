import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const FX = resolve(import.meta.dirname, '../../../fixtures')

test('has a CSP that blocks network requests', async ({ page }) => {
  await page.goto('/')
  const csp = await page.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute('content')
  expect(csp).toContain("connect-src 'none'")
  const blocked = await page.evaluate(() => fetch('https://example.com').then(() => false, () => true))
  expect(blocked).toBe(true)
})

test('landing page passes axe', async ({ page }) => {
  await page.goto('/')
  const r = await new AxeBuilder({ page }).analyze()
  expect(r.violations).toEqual([])
})

for (const [path, id] of [
  ['html/img.alt.missing/fail-1.html', 'img.alt.missing'],
  ['docx/img.alt.missing/fail-1.docx', 'img.alt.missing'],
  ['pptx/img.alt.missing/fail-1.pptx', 'img.alt.missing'],
  ['xlsx/img.alt.missing/fail-1.xlsx', 'img.alt.missing'],
  ['pdf/img.alt.missing/fail-1.pdf', 'img.alt.missing'],
]) {
  test(`scan, fix, undo and download: ${path}`, async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', e => errors.push(e.stack ?? e.message))
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
    await page.goto('/')
    await page.setInputFiles('input[type=file]', `${FX}/${path}`)
    await expect(page.getByRole('status')).toContainText('1 issues found')
    await expect(page.getByText(`${id} at`)).toBeVisible()
    const axe = await new AxeBuilder({ page }).exclude('.preview-frame').exclude('.docx').analyze()
    expect(axe.violations).toEqual([])

    await page.getByRole('button', { name: /no alternative text/ }).click()
    await page.getByLabel('Alternative text').fill('A campus map')
    await page.getByRole('button', { name: 'Apply fix' }).click()
    await expect(page.getByRole('status')).toContainText('0 issues remain')

    await page.getByRole('button', { name: 'Undo last fix' }).click()
    await expect(page.getByRole('status')).toContainText('1 issues remain')

    await page.getByRole('button', { name: /no alternative text/ }).click()
    await page.getByLabel('Alternative text').fill('A campus map')
    await page.getByRole('button', { name: 'Apply fix' }).click()
    await expect(page.getByRole('status')).toContainText('0 issues remain')
    const [dl] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Download fixed copy' }).click()])
    expect(dl.suggestedFilename()).toContain('-accessible.')
    expect(readFileSync(await dl.path()).length).toBeGreaterThan(0)
    await page.screenshot({ path: `test-results/${id}-${path.split('.').pop()}.png`, fullPage: true })
    expect(errors).toEqual([])
  })
}

test('keyboard only flow', async ({ page }) => {
  await page.goto('/')
  await page.setInputFiles('input[type=file]', `${FX}/docx/doc.title.missing/fail-1.docx`)
  await expect(page.locator('#results')).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Download fixed copy' })).toBeFocused()
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: /no title/ })).toBeFocused()
  await page.keyboard.press('Enter')
  await page.keyboard.press('Tab')
  await page.keyboard.type('Syllabus')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('status')).toContainText('0 issues remain')
})

test('sets the contrast suggestion', async ({ page }) => {
  await page.goto('/')
  await page.setInputFiles('input[type=file]', `${FX}/html/contrast.insufficient/fail-1.html`)
  await page.getByRole('button', { name: /contrast/ }).click()
  await expect(page.getByLabel('Text color (hex)')).not.toHaveValue('')
  await page.getByRole('button', { name: 'Apply fix' }).click()
  await expect(page.getByRole('status')).toContainText('0 issues remain')
})

test('PDF preview draws the page before and after a fix', async ({ page }) => {
  await page.goto('/')
  await page.setInputFiles('input[type=file]', `${FX}/pdf/doc.title.missing/fail-1.pdf`)
  await expect(page.getByText('Page 1 of 1')).toBeVisible()
  const dark = () => page.locator('canvas.pdf').evaluate((c: HTMLCanvasElement) => {
    const d = c.getContext('2d')!.getImageData(0, 0, c.width, c.height).data
    let dark = 0
    for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 0 && d[i] < 128) dark++
    return dark
  })
  await expect.poll(dark).toBeGreaterThan(0)
  await page.getByRole('button', { name: /no title/ }).click()
  await page.getByLabel('Document title').fill('Syllabus')
  await page.getByRole('button', { name: 'Apply fix' }).click()
  await expect(page.getByRole('status')).toContainText('0 issues remain')
  await expect.poll(dark).toBeGreaterThan(0)
})
