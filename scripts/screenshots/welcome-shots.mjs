/**
 * 欢迎页三处「界面截图占位」的实拍脚本（Playwright）。
 *
 * 用法（在 scripts/screenshots/ 目录下）：
 *   node welcome-shots.mjs             # 截 3 张到 frontend/public/welcome-shots/
 *   node welcome-shots.mjs --headed    # 有头模式观察执行过程
 *
 * 前置：后端 :8000、前端 :3001 已启动；登录账号 learner_001/123456（种子）。
 * 输出（1440×900 视口，可重复运行覆盖）：
 *   doc-learning.png   文档学习页（来源/问答/生成 三栏，含对话）
 *   path-timeline.png  学习路径页（路径节点 + 时间线 + 双驱动）
 *   learning-flow.png  学习资源 · 有序学习流（阶段步进器 + 讲义正文）
 *
 * 顺序说明：文档问答必须排在最前——前端 SSE 有 12s 首字节看门狗
 * （services/documentChat.ts IDLE_MS），后端一旦还压着其它 LLM 调用
 * （进入有序学习会触发康奈尔线索等生成），DeepSeek 首字节超时即被判失败。
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const OUT = resolve(ROOT, 'frontend', 'public', 'welcome-shots')
const BASE = 'http://localhost:3001'
const USER = 'learner_001'
const PASS = '123456'
const HEADED = process.argv.includes('--headed')

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
  const file = resolve(OUT, `${name}.png`)
  await page.screenshot({ path: file })
  console.log(`  ✓ ${name}.png`)
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

// ---------- 1/3 文档学习（三栏：来源/问答/生成）——趁后端空闲先问答 ----------
console.log('[1/3] 文档学习三栏 → doc-learning.png')
await nav(page, '文档学习')
await settle(page, 2000)
try {
  // 一切选择器限定在 .doclearn 容器内——裸 text 选择器会先命中侧边栏
  // 「学习资源 · AI讲义·测试题」（含「讲义」），把页面点走
  const dl = page.locator('.doclearn')
  await dl.waitFor({ timeout: 15000 })
  // 历次脚本运行会重复上传同名样例——清到只剩 1 份，来源栏才不显得杂乱
  page.on('dialog', (d) => d.accept().catch(() => {}))
  let docCount = await dl.locator('.doclearn-docitem').count()
  for (let guard = 0; docCount > 1 && guard < 20; guard++) {
    await dl.locator('.doclearn-docitem__del').last().click()
    // 删除走后端 + 列表重拉，等到条数真正减少为止（上限 8s）
    const t0 = Date.now()
    let now = docCount
    while (Date.now() - t0 < 8000) {
      await sleep(1000)
      now = await dl.locator('.doclearn-docitem').count()
      if (now < docCount) break
    }
    if (now >= docCount) { console.log('    ⚠ 删除重复文档未生效，停止清理'); break }
    docCount = now
  }
  console.log(`    来源文档数：${docCount}`)
  // 无文档则上传仓库内样例（Playwright 上传须用仓库根下文件）
  if (!(await dl.locator('.doclearn-docitem__title').first().isVisible().catch(() => false))) {
    const fileInput = dl.locator('input[type="file"]').first()
    await fileInput.setInputFiles(resolve(ROOT, 'docs', '讲义-机器学习基础-初级.md'))
    console.log('    已上传样例文档，等待入库…')
    await dl.locator('.doclearn-docitem__title').first().waitFor({ timeout: 60000 }).catch(() => {})
    await settle(page, 1500)
  }
  // 未勾选文档时（对话框锁定提示「请先在左侧勾选文档」）→ 勾选首篇
  const chatBox = dl.locator('.docchat textarea, .docchat input').first()
  const locked = ((await chatBox.getAttribute('placeholder').catch(() => '')) || '').includes('勾选')
  if (locked || (await chatBox.isDisabled().catch(() => false))) {
    await dl.locator('.doclearn-docitem__main, .doclearn-docitem__check').first().click({ timeout: 5000 }).catch(() => {})
    await sleep(1200)
  }
  // 诊断：捕获 /document/chat 的响应状态与前端 doc-chat 报错
  page.on('response', (r) => {
    if (r.url().includes('/document/chat')) console.log(`    [net] ${r.status()} ${r.headers()['content-type'] || ''}`)
  })
  page.on('console', (m) => {
    if (m.text().includes('doc-chat')) console.log('    [console] ' + m.text().slice(0, 300))
  })
  // 就文档提问（展示三栏工作台：来源/问答/生成）；真实 LLM 偶发超时 → 最多重问 2 次
  const ask = async () => {
    await chatBox.fill('这份资料的核心内容是什么？')
    const send = dl.locator('.docchat button').filter({ hasText: /提问|发送/ }).first()
    if (await send.isVisible().catch(() => false)) await send.click()
    else await chatBox.press('Enter')
    console.log('    已提问，等待流式回答…')
    // 轮询：出现「非失败提示」的实质回答（>40 字）即成功
    const t0 = Date.now()
    while (Date.now() - t0 < 60000) {
      await sleep(3000)
      const texts = await dl.locator('.docchat .socratic__msg--agent .socratic__bubble').allTextContents().catch(() => [])
      const last = texts[texts.length - 1] || ''
      if (/失败|超时|稍后重试/.test(last)) return false
      if (last.replace(/\s/g, '').length > 40 && !/左侧勾选/.test(last)) return true
    }
    return false
  }
  let ok = await ask()
  for (let i = 0; !ok && i < 2; i++) {
    console.log('    ⚠ 回答失败/超时，重试第 ' + (i + 1) + ' 次…')
    await sleep(8000) // 给后端喘息，避开 12s 首字节看门狗连环触发
    ok = await ask()
  }
  if (!ok) console.log('    ⚠ 文档问答多次失败——截图可能含失败气泡，建议手动补截')
  await sleep(2500) // 让流式排版/溯源折叠稳定
  // 把「最后一个提问气泡」滚到对话区顶部：问题+回答同框，重试留下的失败气泡滚出视野
  await page.evaluate(() => {
    const msgs = [...document.querySelectorAll('.docchat .socratic__msg')]
    const users = msgs.filter((m) => !m.className.includes('agent'))
    users[users.length - 1]?.scrollIntoView({ block: 'start' })
  }).catch(() => {})
  await sleep(600)
} catch (e) {
  console.log('    ⚠ 文档问答自动化部分失败（' + e.message.split('\n')[0] + '）——可手动上传/提问后补截')
}
await shot(page, 'doc-learning')

// ---------- 2/3 学习路径（路径节点 + 时间线 + 双驱动） ----------
console.log('[2/3] 学习路径页 → path-timeline.png')
await nav(page, '学习路径')
await settle(page, 2500)
await waitGenerated(page)
await shot(page, 'path-timeline')

// ---------- 3/3 有序学习流（学习资源 → 有序学习） ----------
console.log('[3/3] 学习资源 · 有序学习流 → learning-flow.png')
await nav(page, '学习资源')
await settle(page, 2000)
await waitGenerated(page)
// 资源总览两大卡 → 进入「有序学习」流
await page.locator('.res-hero--flow').click({ timeout: 10000 })
await settle(page, 1500)
// flow 模式会自动弹出推荐资源浮层（.rescard-overlay），拦截一切点击——先关掉
const overlay = page.locator('.rescard-overlay')
if (await overlay.isVisible().catch(() => false)) {
  await page.keyboard.press('Escape').catch(() => {})
  await sleep(600)
  if (await overlay.isVisible().catch(() => false)) {
    await overlay.locator('button').first().click().catch(() => {})
    await sleep(600)
  }
}
await page.locator('.flow__stepper').waitFor({ timeout: 15000 })
await waitGenerated(page, 120000)
// 关键同步点：等 bootstrap 真正完成（进度文本从 0/6 回填为实际步数）再动手。
// 进入 flow 会触发康奈尔线索 LLM 生成，同步阻塞的后端会把 18.3 进度 GET 一起
// 压住数十秒——bootstrap 在那之后才把 phaseIdx 改写到末段；早点/盲点必被覆盖
await page
  .locator('.flow__progress-text')
  .filter({ hasText: /[1-6]\/6/ })
  .first()
  .waitFor({ timeout: 150000 })
  .catch(() => console.log('    ⚠ 等待进度回填超时，继续（阶段可能仍会被改写）'))
// 组件 bootstrap 落位到「当前未完成/末段」阶段（全步完成的账号=代码实操，画面偏空），
// 现在切回第 1 阶段「输入」。点击仍可能被迟到浮层/动画拦截——点击后校验、不稳则重试
await sleep(1500)
// bootstrap 落位可能晚于首次点击并把阶段改写回末段——持续「不在输入则点回」，
// 直到「输入」连续两次检查都保持 active（说明 bootstrap 已结束且不再改写）
let stable = 0
for (let i = 0; i < 15 && stable < 2; i++) {
  if (await overlay.isVisible().catch(() => false)) { await page.keyboard.press('Escape'); await sleep(500) }
  const cls = await page.locator('.flow__step').first().getAttribute('class').catch(() => '')
  if (cls && cls.includes('flow__step--active')) {
    stable++
  } else {
    stable = 0
    console.log('    「输入」阶段未落位，点回…')
    await page.locator('.flow__step').first().click({ timeout: 5000 }).catch(() => {})
  }
  await sleep(2000)
}
// 输入阶段切「定制讲义」Tab（讲义正文最饱满），同样校验后重试
for (let i = 0; i < 3; i++) {
  await page.locator('.flow__input-tab', { hasText: '定制讲义' }).first().click({ timeout: 5000 }).catch(() => {})
  await sleep(800)
  const cls = await page.locator('.flow__input-tab', { hasText: '定制讲义' }).first().getAttribute('class').catch(() => '')
  if (cls && cls.includes('--active')) break
}
await settle(page, 1500)
await waitGenerated(page, 120000)
await page.locator('.flow__lecture .markdown-body').first().waitFor({ timeout: 30000 }).catch(() => {})
await sleep(1200)
await shot(page, 'learning-flow')

await browser.close()
console.log(`\n完成。截图目录：${OUT}`)
