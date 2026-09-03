/**
 * 答辩 PPT 补截脚本（Playwright headless，1440×900）。
 *
 * 用法（scripts/screenshots/ 下）：node ppt-shots.mjs [--headed] [--only=hero,feynman,...]
 * 前置：后端 :8000、前端 :3000 已启动；种子账号 learner_001/123456。
 *
 * 输出到 docs/screenshots/：
 *   00-欢迎页-KnowledgeCore.png     P1/P15 封面 Hero（初始化动画完成态）
 *   04-4b-费曼讲解-CNN.png          P8（CNN 知识点，展示精准缺口反馈）
 *   04-5b-代码实操-CNN运行.png       P6（右侧 iframe 真渲染出结果）
 *   13-2-苏格拉底导学-CNN.png        P8（CNN 知识点导学对话）
 *
 * 顺序：hero →（登录）→ flow（费曼 → 代码实操）→ browse（导学对话）。
 * 费曼评估 / 导学 SSE 都是同步阻塞后端的 LLM 调用，全程串行。
 */
import { chromium } from 'playwright'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const OUT = resolve(ROOT, 'docs', 'screenshots')
const BASE = 'http://localhost:3000'
const USER = 'learner_001'
const PASS = '123456'
const HEADED = process.argv.includes('--headed')
const onlyArg = process.argv.find((a) => a.startsWith('--only='))
const ONLY = onlyArg ? onlyArg.slice(7).split(',') : null
const want = (k) => !ONLY || ONLY.includes(k)

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function settle(page, extra = 1200) {
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
  await sleep(extra)
}

async function shot(page, name) {
  const file = resolve(OUT, `${name}.png`)
  await page.screenshot({ path: file })
  console.log(`  ✓ ${name}.png`)
}

async function nav(page, label) {
  await page.locator('.sidebar__nav-label', { hasText: label }).first().click()
  await settle(page)
}

/** 关闭 flow 模式自动弹出的推荐资源浮层（拦截一切点击） */
async function closeOverlay(page) {
  const overlay = page.locator('.rescard-overlay')
  for (let i = 0; i < 3; i++) {
    if (!(await overlay.isVisible().catch(() => false))) return
    await page.keyboard.press('Escape').catch(() => {})
    await sleep(600)
    if (await overlay.isVisible().catch(() => false)) {
      await overlay.locator('button').first().click().catch(() => {})
      await sleep(600)
    }
  }
}

/** 学习路径页 → 点击 CNN架构 节点 → 弹窗按钮（开始学习/查看资源） */
async function enterCnn(page, btnText) {
  await nav(page, '学习路径')
  await settle(page, 2000)
  // 路径 GET 可能被后端压住数十秒——先等节点列表真正出现再匹配
  await page.locator('.timeline-item__title, .cards-grid h3').first().waitFor({ timeout: 60000 }).catch(() => {})
  const node = page.locator('.timeline-item__title, .cards-grid h3, .cards-grid [class*="title"]', { hasText: /CNN/ }).first()
  if (!(await node.isVisible().catch(() => false))) {
    console.log('    ⚠ 路径里未见 CNN 节点，尝试 Transformer')
    const alt = page.locator('.timeline-item__title', { hasText: /Transformer/ }).first()
    await alt.click()
  } else {
    await node.click()
  }
  const modal = page.locator('.topic-modal')
  await modal.waitFor({ timeout: 10000 })
  await modal.locator('button', { hasText: btnText }).first().click()
  await settle(page, 1500)
}

/** flow 页 bootstrap 完成 + 切到指定阶段并确认稳定（bootstrap 迟到会改写 phase） */
async function gotoFlowPhase(page, phaseText) {
  await page.locator('.flow__stepper').waitFor({ timeout: 20000 })
  await closeOverlay(page)
  await page
    .locator('.flow__progress-text')
    .filter({ hasText: /[1-6]\/6/ })
    .first()
    .waitFor({ timeout: 150000 })
    .catch(() => console.log('    ⚠ 等待进度回填超时，继续'))
  await sleep(1500)
  const step = page.locator('.flow__step', { hasText: phaseText }).first()
  let stable = 0
  for (let i = 0; i < 15 && stable < 2; i++) {
    await closeOverlay(page)
    const cls = (await step.getAttribute('class').catch(() => '')) || ''
    if (cls.includes('flow__step--active')) {
      stable++
    } else {
      stable = 0
      await step.click({ timeout: 5000 }).catch(() => {})
    }
    await sleep(2000)
  }
}

const browser = await chromium.launch({ headless: !HEADED })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(20000)

// ---------- 0 欢迎页 Hero（未登录，等初始化动画到 READY） ----------
if (want('hero')) {
  console.log('[hero] 欢迎页 Knowledge Core')
  await page.goto(BASE)
  await settle(page, 1500)
  await page.getByText('READY', { exact: true }).first().waitFor({ timeout: 45000 })
    .catch(() => console.log('    ⚠ 未等到 READY，按当前状态截图'))
  await sleep(2500)
  await shot(page, '00-欢迎页-KnowledgeCore')
  // 变体：滚到 AI Knowledge Core 演示窗口整框（P1/P15 备选素材）
  await page.evaluate(() => {
    const el = document.querySelector('.wk [class*="shell"], .wk [class*="core"], .wk svg')
    el?.scrollIntoView({ block: 'center' })
  }).catch(() => {})
  await sleep(2500)
  await shot(page, '00b-欢迎页-KnowledgeCore-窗口')
}

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
await settle(page, 1500)
console.log('登录完成')

// ---------- 1 费曼讲解（CNN，有序学习流第 5 步） ----------
if (want('feynman')) {
  console.log('[feynman] CNN 费曼讲解')
  await enterCnn(page, '开始学习')
  await gotoFlowPhase(page, '费曼讲解')
  const fey = page.locator('.feynman')
  await fey.waitFor({ timeout: 15000 })
  const box = fey.locator('.socratic__input input')
  const EXPLAIN =
    'CNN 就是用卷积核在图像上滑动做卷积，每个卷积核提取一种局部特征，比如边缘或纹理；卷积核参数在整张图上共享，所以参数量比全连接网络少得多。多层卷积堆起来，浅层学边缘、深层学更复杂的形状，最后把特征展平送进全连接层做分类。'
  const submit = async () => {
    await box.fill(EXPLAIN)
    await fey.locator('.socratic__input button').first().click()
    console.log('    已提交讲解，等待 AI 评估…')
    const t0 = Date.now()
    while (Date.now() - t0 < 120000) {
      await sleep(3000)
      if ((await fey.locator('.feynman__gap').count()) > 0) return true
      const texts = await fey.locator('.socratic__msg--agent .socratic__bubble').allTextContents().catch(() => [])
      if (/不可用|稍后再试/.test(texts[texts.length - 1] || '')) return false
    }
    return false
  }
  let ok = await submit()
  if (!ok) { console.log('    ⚠ 评估失败/超时，重试一次'); await sleep(8000); ok = await submit() }
  if (!ok) console.log('    ⚠ 费曼评估未出缺口清单——截图可能不完整')
  await sleep(2000)
  await shot(page, '04-4b-费曼讲解-CNN')
}

// ---------- 2 代码实操（CNN，第 6 步，等右侧 iframe 真渲染） ----------
if (want('codelab')) {
  console.log('[codelab] CNN 代码实操')
  if (!(await page.locator('.flow__stepper').isVisible().catch(() => false))) {
    await enterCnn(page, '开始学习')
  }
  await gotoFlowPhase(page, '代码实操')
  const frame = page.frameLocator('.csx__preview')
  const t0 = Date.now()
  let rendered = false
  while (Date.now() - t0 < 60000) {
    const txt = await frame.locator('#app').textContent().catch(() => '')
    if (txt && txt.replace(/\s/g, '').length > 10) { rendered = true; break }
    await sleep(2000)
  }
  console.log(rendered ? '    预览已渲染' : '    ⚠ 预览未见内容，仍截图')
  await sleep(1500)
  await shot(page, '04-5b-代码实操-CNN运行')
}

// ---------- 3 苏格拉底导学（CNN，browse 模式 → 导学对话横幅） ----------
if (want('socratic')) {
  console.log('[socratic] CNN 导学对话')
  await enterCnn(page, '查看资源')
  await closeOverlay(page)
  const banner = page.locator('.tutor-banner').first()
  if (!(await banner.isVisible().catch(() => false))) {
    // 落点在资源中枢深处时先回资源总览
    await page.locator('button, .res-tab', { hasText: /总览|概览/ }).first().click().catch(() => {})
    await sleep(1200)
  }
  await banner.click()
  const wrap = page.locator('.socratic-wrap')
  await wrap.waitFor({ timeout: 15000 })
  await sleep(1500)
  const box = wrap.locator('.socratic__input input')
  const say = async (text) => {
    await box.fill(text)
    await wrap.locator('.socratic__input button').first().click()
    // 等最后一条 agent 气泡出现且长度稳定（SSE 流式）
    let last = ''
    const t0 = Date.now()
    while (Date.now() - t0 < 90000) {
      await sleep(3000)
      const texts = await wrap.locator('.socratic__msg--agent .socratic__bubble').allTextContents().catch(() => [])
      const cur = texts[texts.length - 1] || ''
      if (cur.length > 20 && cur === last) return
      last = cur
    }
  }
  await say('老师，CNN 里的卷积核到底在学什么？为什么要参数共享？')
  await say('我理解了：卷积核像特征探测器，同一个特征在图像任何位置都该用同一组参数去找，所以共享参数')
  await sleep(1500)
  await shot(page, '13-2-苏格拉底导学-CNN')
}

await browser.close()
console.log(`\n完成。输出目录：${OUT}`)
