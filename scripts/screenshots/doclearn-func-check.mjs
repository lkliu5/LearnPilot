/**
 * 文档学习页布局改版 · 功能回归检查（临时）：
 * 1) 中栏提问 → 流式回答正常、hero 让位给气泡流
 * 2) 右栏点「定制讲义」→ 进度反馈 → 大预览弹层打开
 * 输出截图到 out/，并打印 console error。
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(HERE, 'out')
const BASE = 'http://localhost:3000'
mkdirSync(OUT, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(20000)
const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 300)) })

await page.goto(BASE)
await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
await sleep(800)
const cta = page.locator('button, a').filter({ hasText: /登录|进入|开始/ }).first()
if (await cta.isVisible().catch(() => false)) { await cta.click(); await sleep(1200) }
if (await page.locator('input[placeholder="请输入用户名"]').isVisible().catch(() => false)) {
  await page.fill('input[placeholder="请输入用户名"]', 'learner_001')
  await page.fill('input[type="password"]', '123456')
  await page.locator('button[type="submit"]').first().click()
}
await page.locator('.sidebar__nav-label').first().waitFor({ timeout: 20000 })
await sleep(1200)
await page.locator('.sidebar__nav-label', { hasText: '文档学习' }).first().click()
const dl = page.locator('.doclearn')
await dl.waitFor({ timeout: 15000 })
await sleep(2500)

// ---- 1) 中栏问答（真实 LLM 偶发首字节超时 → 重试 2 次） ----
const chatBox = dl.locator('.docchat input').first()
const ask = async () => {
  await chatBox.fill('这份资料的核心内容是什么？')
  await dl.locator('.docchat button').filter({ hasText: /提问|发送/ }).first().click()
  const t0 = Date.now()
  while (Date.now() - t0 < 60000) {
    await sleep(3000)
    const texts = await dl.locator('.docchat .socratic__msg--agent .socratic__bubble').allTextContents().catch(() => [])
    const last = texts[texts.length - 1] || ''
    if (/失败|超时|稍后重试/.test(last)) return false
    if (last.replace(/\s/g, '').length > 40) return true
  }
  return false
}
let ok = await ask()
for (let i = 0; !ok && i < 2; i++) { console.log('  ⚠ 问答重试 ' + (i + 1)); await sleep(8000); ok = await ask() }
console.log('chat answer ok:', ok)
const heroGone = !(await dl.locator('.docchat-hero').isVisible().catch(() => false))
console.log('hero replaced by bubbles:', heroGone)
await sleep(1500)
await page.screenshot({ path: resolve(OUT, 'doclearn-func-chat.png') })

// ---- 2) 右栏生成「定制讲义」→ 大预览弹层 ----
await dl.locator('.doclearn-act--lecture').click()
// 进度反馈出现（busy 态）
await sleep(1500)
const busySeen = await dl.locator('.doclearn-act--busy').isVisible().catch(() => false)
console.log('busy progress seen:', busySeen)
await page.locator('.rescard-overlay').waitFor({ timeout: 120000 })
await page.locator('.rescard-detail .markdown-body, .rescard-detail .resource-loading').first().waitFor({ timeout: 30000 }).catch(() => {})
await sleep(2000)
await page.screenshot({ path: resolve(OUT, 'doclearn-func-preview.png') })
console.log('preview modal open: true')
await page.keyboard.press('Escape')
await sleep(800)
await page.screenshot({ path: resolve(OUT, 'doclearn-func-after-gen.png') })

console.log('console errors:', errors.length ? errors : '(none)')
await browser.close()
