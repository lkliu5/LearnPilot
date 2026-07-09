/**
 * 技术文档界面截图脚本（Playwright）。
 *
 * 用法（在 scripts/screenshots/ 目录下）：
 *   node shot.mjs              # 默认主题（鼠尾草）截一套 12 张
 *   node shot.mjs --theme=ink  # 墨纸主题再截一套（文件名加 -ink 后缀）
 *   node shot.mjs --headed     # 有头模式观察执行过程
 *
 * 前置：后端 :8000、前端 :3001 已启动；登录账号 learner_001/123456（种子）。
 * 输出：docs/screenshots/NN-名称[-ink].png（1440×900 视口，可重复运行覆盖）。
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const OUT = resolve(ROOT, 'docs', 'screenshots')
const BASE = 'http://localhost:3001'
const USER = 'learner_001'
const PASS = '123456'
const THEME = process.argv.find(a => a.startsWith('--theme='))?.split('=')[1] ?? 'sage'
const HEADED = process.argv.includes('--headed')
const SUFFIX = THEME === 'ink' ? '-ink' : ''

mkdirSync(OUT, { recursive: true })

const sleep = ms => new Promise(r => setTimeout(r, ms))

/** 等待页面安静：networkidle（容忍超时）+ 固定延时兜底动效 */
async function settle(page, extra = 1200) {
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
  await sleep(extra)
}

/** 等待「生成中/加载中」类指示消失（真实模式讲义生成可达 ~40s） */
async function waitGenerated(page, timeout = 90000) {
  const busy = page.locator('text=/正在生成|生成中|加载中|渲染中|请稍候/').first()
  const t0 = Date.now()
  while (Date.now() - t0 < timeout) {
    if (!(await busy.isVisible().catch(() => false))) return
    await sleep(1500)
  }
  console.log('    ⚠ 等待生成超时（继续截图，画面可能仍在生成态）')
}

async function shot(page, name) {
  const file = resolve(OUT, `${name}${SUFFIX}.png`)
  await page.screenshot({ path: file })
  console.log(`  ✓ ${name}${SUFFIX}.png`)
}

/** 点侧边栏导航（App 为 currentPage 状态机，无路由 URL） */
async function nav(page, label) {
  await page.locator('.sidebar__nav-label', { hasText: label }).first().click()
  await settle(page)
}

const browser = await chromium.launch({ headless: !HEADED })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(20000)

// ---------- 登录 ----------
console.log('登录…')
await page.goto(BASE)
await settle(page)
// Landing → 登录入口（按钮文案兜底匹配）
const cta = page.locator('button, a').filter({ hasText: /登录|进入|开始/ }).first()
if (await cta.isVisible().catch(() => false)) { await cta.click(); await settle(page, 600) }
if (await page.locator('input[placeholder="请输入用户名"]').isVisible().catch(() => false)) {
  await page.fill('input[placeholder="请输入用户名"]', USER)
  await page.fill('input[type="password"]', PASS)
  await page.locator('button[type="submit"]').first().click()   // 文案为「进入系统」
}
await page.locator('.sidebar__nav-label').first().waitFor({ timeout: 20000 })
await settle(page, 1500)
console.log('登录完成，当前主题：' + THEME)

// ---------- 主题 ----------
if (THEME === 'ink') {
  await page.evaluate(() => {
    document.documentElement.setAttribute('data-theme', 'ink')
    localStorage.setItem('zx-theme', 'ink')
  })
  await sleep(600)
}

// ---------- 01 学情管家首页 ----------
console.log('[01] 学情管家中枢首页（闭环四部分）')
await nav(page, '学情管家')
await settle(page, 2500)
await shot(page, '01-学情管家首页')

// ---------- 02 画像诊断 ----------
console.log('[02] 画像诊断页（三入口/微测/雷达）')
await nav(page, '画像诊断')
await settle(page, 2000)
await shot(page, '02-画像诊断')

// ---------- 03 学习路径 ----------
console.log('[03] 学习路径页（路径+时间线+双驱动）')
await nav(page, '学习路径')
await settle(page, 2500)
await shot(page, '03-学习路径')

// ---------- 04/05/12 学习资源 · 讲义 · 溯源 ----------
console.log('[04] 学习资源页（多智能体生成/多类资源）')
await nav(page, '学习资源')
await settle(page, 2000)
await waitGenerated(page)
await shot(page, '04-学习资源')

console.log('[05] 讲义查看（进入资源库 → 定制讲义卡片 → 查看器，等生成后截公式/图解）')
await page.locator('button, a').filter({ hasText: /进入资源库/ }).first().click()
await settle(page, 1500)
await page.locator('.rescard').filter({ hasText: '定制讲义' }).first().click()
await settle(page, 1500)
await waitGenerated(page, 120000)
await page.locator('.markdown-body').first().waitFor({ timeout: 60000 }).catch(() => {})
await settle(page, 1500)
// 滚到含公式/图解的中部
await page.evaluate(() => {
  const el = document.querySelector('.katex-display, .katex, .paper-figure, .markdown-body svg')
  if (el) el.scrollIntoView({ block: 'center' })
  else document.querySelector('main')?.scrollBy(0, 900)
})
await sleep(1200)
await shot(page, '05-讲义-公式与图解')

console.log('[12] 防幻觉溯源（滚到讲义查看器底部的参考来源/引用列表）')
await page.evaluate(() => {
  // 讲义查看器是弹窗，滚它自己的滚动容器（而非 main）
  const scrollables = [...document.querySelectorAll('*')].filter(e =>
    e.scrollHeight > e.clientHeight + 100 && /auto|scroll/.test(getComputedStyle(e).overflowY))
  const inModal = scrollables.filter(e => e.closest('[class*=modal], [role="dialog"], [class*=viewer], [class*=rescard]'))
  const target = (inModal.length ? inModal : scrollables).pop()
  if (target) target.scrollTop = target.scrollHeight
})
await sleep(1500)
await shot(page, '12-防幻觉溯源-讲义来源')

// ---------- 07 即时辅导（选中即问） ----------
console.log('[07] 即时辅导（选中即问浮泡+对话）——自动划选正文触发')
try {
  // 讲义弹窗此刻在底部——先挑一段视口可见的长段落滚到中央再拖选
  const idx = await page.evaluate(() => {
    const ps = [...document.querySelectorAll('.markdown-body p')]
    const i = ps.findIndex(p => (p.textContent || '').trim().length > 40)
    if (i >= 0) ps[i].scrollIntoView({ block: 'center' })
    return i
  })
  if (idx < 0) throw new Error('未找到可划选正文段落')
  await sleep(800)
  const para = page.locator('.markdown-body p').nth(idx)
  const box = await para.boundingBox()
  if (!box || box.y < 60) throw new Error('目标段落不在视口内')
  await page.mouse.move(box.x + 4, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + Math.min(box.width - 8, 360), box.y + box.height / 2, { steps: 12 })
  await page.mouse.up()
  await page.locator('.sel-ask-bubble').waitFor({ timeout: 5000 })
  await sleep(600)
  await shot(page, '07a-选中即问浮泡')
  await page.locator('.sel-ask-bubble').click()
  await page.locator('.ask-tutor-drawer').waitFor({ timeout: 8000 })
  await sleep(800)
  const q = page.locator('.ask-tutor-drawer__input')
  if (!(await q.inputValue().catch(() => ''))) await q.fill('这一段是什么意思？请用直观例子解释。')
  await page.locator('.ask-tutor-drawer__primary').click()
  console.log('    已提问，等待流式回答…')
  await sleep(14000)   // SSE 打字机推进
  await shot(page, '07b-即时辅导对话')
} catch (e) {
  console.log('    ⚠ 选中划词自动化失败（' + e.message.split('\n')[0] + '），回退：点右侧「即时辅导」侧签打开对话')
  try {
    await page.locator('.ask-tutor-dock').click({ timeout: 5000 })
    await page.locator('.ask-tutor-drawer').waitFor({ timeout: 8000 })
    await sleep(800)
    await page.locator('.ask-tutor-drawer__input').fill('什么是反向传播？请用直观例子解释。')
    await page.locator('.ask-tutor-drawer__primary').click()
    console.log('    已提问（侧签入口），等待流式回答…')
    await sleep(14000)
    await shot(page, '07b-即时辅导对话')
  } catch (e2) {
    console.log('    ⚠ 侧签回退也失败——请手动：讲义正文划选文字→点浮泡→提问后截图')
    await shot(page, '07-即时辅导-需手动补截')
  }
}

// 关闭辅导抽屉与讲义查看器（遮罩会拦截后续导航点击）
await page.locator('.ask-tutor-drawer__close').click({ timeout: 2000 }).catch(() => {})
await page.keyboard.press('Escape').catch(() => {})
await sleep(500)
await page.keyboard.press('Escape').catch(() => {})
await sleep(600)
const scrim = page.locator('.ask-tutor-scrim')
if (await scrim.isVisible().catch(() => false)) {
  await page.locator('[aria-label="关闭"], .ask-tutor-scrim button').filter({ hasText: /关闭|×|✕/ }).first()
    .click({ timeout: 3000 }).catch(async () => { await scrim.click({ position: { x: 10, y: 10 } }).catch(() => {}) })
  await sleep(600)
}

// ---------- 06 知识图谱 ----------
console.log('[06] 知识图谱（78 点分层）')
await nav(page, '知识图谱')
await settle(page, 3500)   // ECharts 力导向图布局稳定
await shot(page, '06-知识图谱')

// ---------- 08 文档学习 ----------
console.log('[08] 文档学习（三栏：来源/问答/生成）')
await nav(page, '文档学习')
await settle(page, 2000)
try {
  // 无文档则上传仓库内样例（Playwright 上传须用仓库根下文件）
  const hasDoc = await page.locator('text=/已入库|indexed|\\.md|\\.pdf/').first().isVisible().catch(() => false)
  if (!hasDoc) {
    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles(resolve(ROOT, 'docs', '讲义-机器学习基础-初级.md'))
    console.log('    已上传样例文档，等待入库…')
    await page.locator('text=/已入库|完成/').first().waitFor({ timeout: 60000 }).catch(() => {})
    await settle(page, 1500)
  }
  // 选中首篇文档并提问（展示三栏工作台）
  await page.locator('text=/机器学习|讲义/').first().click({ timeout: 5000 }).catch(() => {})
  await sleep(1000)
  const chatBox = page.locator('textarea, input[placeholder*="问"]').first()
  if (await chatBox.isVisible().catch(() => false)) {
    await chatBox.fill('这份资料的核心内容是什么？')
    await chatBox.press('Enter')
    console.log('    已提问，等待流式回答…')
    await sleep(15000)
  }
} catch (e) {
  console.log('    ⚠ 文档问答自动化部分失败（' + e.message + '）——可手动上传/提问后补截')
}
await shot(page, '08-文档学习三栏')

// ---------- 09 我的资源库 ----------
console.log('[09] 我的资源库（CRUD/筛选）')
await nav(page, '我的资源库')
await settle(page, 2000)
await shot(page, '09-我的资源库')

// ---------- 10 模型管理 ----------
console.log('[10] 模型管理页（多模型/魔搭配置）')
await nav(page, '模型管理')
await settle(page, 2000)
await shot(page, '10-模型管理')

// ---------- 11 Agent 工作流 ----------
console.log('[11] Agent 工作流可视化（等待演示/实时推进后截图）')
await nav(page, 'Agent工作流')
await settle(page, 1500)
const startBtn = page.locator('button').filter({ hasText: /启动|开始|执行|运行/ }).first()
if (await startBtn.isVisible().catch(() => false)) { await startBtn.click().catch(() => {}) }
await sleep(9000)   // 让 Agent 状态卡/消息流推进出内容
await shot(page, '11-Agent工作流')

await browser.close()
console.log(`\n完成。截图目录：${OUT}`)
console.log('提示：07/08 若标记“需手动”，请按控制台提示手动操作后用系统截图补拍。')
