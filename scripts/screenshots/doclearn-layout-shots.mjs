/**
 * 文档学习页布局改版 · 前后对比截图脚本（临时验证用）。
 *
 * 用法：node doclearn-layout-shots.mjs <suffix> [baseUrl]
 *   suffix  截图文件名后缀（before / after）
 *   baseUrl 前端地址，默认 http://localhost:3000
 *
 * 输出（到 scripts/screenshots/out/）：
 *   doclearn-1440-sage-<suffix>.png / doclearn-1280-sage-<suffix>.png / doclearn-1440-ink-<suffix>.png
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(HERE, 'out')
const SUFFIX = process.argv[2] || 'shot'
const BASE = process.argv[3] || 'http://localhost:3000'
const USER = 'learner_001'
const PASS = '123456'

mkdirSync(OUT, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function settle(page, extra = 1200) {
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
  await sleep(extra)
}

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(20000)

// ---------- 登录 ----------
console.log('登录…')
await page.goto(BASE)
await settle(page)
const cta = page.locator('button, a').filter({ hasText: /登录|进入|开始/ }).first()
if (await cta.isVisible().catch(() => false)) { await cta.click(); await settle(page, 600) }
if (await page.locator('input[placeholder="请输入用户名"]').isVisible().catch(() => false)) {
  await page.fill('input[placeholder="请输入用户名"]', USER)
  await page.fill('input[type="password"]', PASS)
  await page.locator('button[type="submit"]').first().click()
}
await page.locator('.sidebar__nav-label').first().waitFor({ timeout: 20000 })
await settle(page, 1200)

// ---------- 进入文档学习 ----------
await page.locator('.sidebar__nav-label', { hasText: '文档学习' }).first().click()
await page.locator('.doclearn').waitFor({ timeout: 15000 })
await settle(page, 2500)

const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)) })

async function shot(width, height, theme, name) {
  await page.setViewportSize({ width, height })
  await page.evaluate((t) => {
    localStorage.setItem('zx-theme', t)
    document.documentElement.setAttribute('data-theme', t === 'ink' ? 'ink' : '')
    if (t !== 'ink') document.documentElement.removeAttribute('data-theme')
  }, theme)
  await sleep(1200)
  await page.screenshot({ path: resolve(OUT, `${name}.png`) })
  console.log(`  ✓ ${name}.png`)
}

await shot(1440, 900, 'sage', `doclearn-1440-sage-${SUFFIX}`)
await shot(1280, 800, 'sage', `doclearn-1280-sage-${SUFFIX}`)
await shot(1440, 900, 'ink', `doclearn-1440-ink-${SUFFIX}`)
await shot(800, 900, 'sage', `doclearn-800-sage-${SUFFIX}`)
// 复原默认主题，避免影响后续手动查看
await page.evaluate(() => { localStorage.setItem('zx-theme', 'sage'); document.documentElement.removeAttribute('data-theme') })

console.log('console errors:', errors.length ? errors : '(none)')
await browser.close()
