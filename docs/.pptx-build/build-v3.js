/* 智学中枢 · 软件杯参赛汇报 PPT v3 — 按官方《PPT流程》结构重构（封面/痛点/架构核心技术/功能演示/创新对比/测试安全/商业价值/致谢） */
const pptxgen = require('pptxgenjs');
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const SHOTS = path.join(__dirname, '..', 'ppt-assets', 'shots');
const ASSETS = path.join(__dirname, 'assets');
if (!fs.existsSync(ASSETS)) fs.mkdirSync(ASSETS, { recursive: true });

// ---- 配色（产品同色系：米色 / navy(科技蓝) / 绿）----
const NAVY = '17243F', NAVY2 = '243657', CREAM = 'F4EFE4', PAPER = 'FCFAF4';
const GREEN = '5B7F6E', GREEN_D = '46624F', INK = '2C2822', INK_SOFT = '6E665A';
const AMBER = 'C2873F', LINE = 'DED7C7', WHITE = 'FFFFFF';
const SHOT_AR = 1512 / 900;
const W = 13.333, H = 7.5;

async function makeGradient(file, c1, c2, w = 1920, h = 1080) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">
    <defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#${c1}"/><stop offset="100%" stop-color="#${c2}"/>
    </linearGradient></defs>
    <rect width="100%" height="100%" fill="url(#g)"/>
    <circle cx="${w*0.82}" cy="${h*0.2}" r="${h*0.42}" fill="#${GREEN}" opacity="0.16"/>
    <circle cx="${w*0.12}" cy="${h*0.86}" r="${h*0.34}" fill="#${AMBER}" opacity="0.10"/>
  </svg>`;
  await sharp(Buffer.from(svg)).png().toFile(path.join(ASSETS, file));
}

function addShot(slide, file, box, opts = {}) {
  const ar = SHOT_AR; let w = box.w, h = w / ar;
  if (h > box.h) { h = box.h; w = h * ar; }
  const x = box.x + (box.w - w) / 2, y = box.y + (box.h - h) / 2, pad = opts.pad ?? 0.06;
  slide.addShape('roundRect', { x: x - pad, y: y - pad, w: w + pad * 2, h: h + pad * 2, rectRadius: 0.08,
    fill: { color: WHITE }, line: { color: opts.frame || GREEN, width: 1 },
    shadow: { type: 'outer', color: '7A6A4A', opacity: 0.28, blur: 9, offset: 3, angle: 90 } });
  slide.addImage({ path: path.join(SHOTS, file), x, y, w, h });
  return { x, y, w, h };
}

function footer(slide, n) {
  slide.addShape('line', { x: 0.55, y: 7.06, w: 12.23, h: 0, line: { color: LINE, width: 1 } });
  slide.addText('智学中枢 · 领域知识个性化资源生成与多智能体系统', { x: 0.55, y: 7.08, w: 8, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 9, color: INK_SOFT, valign: 'middle' });
  slide.addText('软件杯 2026', { x: 9.4, y: 7.08, w: 2.2, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 9, color: INK_SOFT, align: 'right', valign: 'middle' });
  slide.addText(String(n).padStart(2, '0'), { x: 11.75, y: 7.08, w: 1.03, h: 0.32, fontFace: 'Arial', fontSize: 10, bold: true, color: GREEN_D, align: 'right', valign: 'middle' });
}

function header(slide, { kicker, title, idx }) {
  slide.background = { color: PAPER };
  slide.addShape('rect', { x: 0, y: 0, w: W, h: 1.18, fill: { color: NAVY } });
  slide.addShape('rect', { x: 0, y: 1.18, w: W, h: 0.06, fill: { color: GREEN } });
  slide.addShape('rect', { x: 0.55, y: 0.30, w: 0.12, h: 0.6, fill: { color: GREEN } });
  slide.addText((kicker || '').toUpperCase(), { x: 0.82, y: 0.26, w: 9, h: 0.26, fontFace: 'Arial', fontSize: 10.5, bold: true, color: '9FB7AC', charSpacing: 2 });
  slide.addText(title, { x: 0.8, y: 0.5, w: 10.4, h: 0.6, fontFace: 'Microsoft YaHei', fontSize: 23, bold: true, color: WHITE, valign: 'middle' });
  if (idx) slide.addText(idx, { x: 11.2, y: 0.18, w: 1.58, h: 0.82, fontFace: 'Arial', fontSize: 38, bold: true, color: '32507A', align: 'right', valign: 'middle' });
}

function bullets(slide, items, box, opts = {}) {
  slide.addText(items.map((t) => ({ text: t.t ?? t, options: { bullet: t.b === false ? false : { code: '2022', indent: 14 }, color: t.c || INK, bold: !!t.bold, fontSize: t.fs || (opts.fs || 14), breakLine: true, paraSpaceAfter: opts.gap ?? 8 } })),
    { x: box.x, y: box.y, w: box.w, h: box.h, fontFace: 'Microsoft YaHei', valign: 'top', lineSpacingMultiple: 1.05 });
}

function card(slide, box, { title, desc, color = GREEN }) {
  slide.addShape('roundRect', { x: box.x, y: box.y, w: box.w, h: box.h, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.3, blur: 6, offset: 2, angle: 90 } });
  slide.addShape('rect', { x: box.x, y: box.y, w: 0.09, h: box.h, fill: { color } });
  slide.addText(title, { x: box.x + 0.22, y: box.y + 0.14, w: box.w - 0.34, h: 0.36, fontFace: 'Microsoft YaHei', fontSize: 13.5, bold: true, color: INK });
  slide.addText(desc, { x: box.x + 0.22, y: box.y + 0.52, w: box.w - 0.34, h: box.h - 0.62, fontFace: 'Microsoft YaHei', fontSize: 11, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.05 });
}

// 公式块（等宽字体呈现）
function formula(slide, x, y, w, title, lines, color = GREEN_D) {
  slide.addShape('roundRect', { x, y, w, h: 0.42 + lines.length * 0.34 + 0.2, rectRadius: 0.08, fill: { color: 'F1ECE0' }, line: { color, width: 1 } });
  slide.addText(title, { x: x + 0.18, y: y + 0.1, w: w - 0.36, h: 0.3, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color });
  slide.addText(lines.map((l) => ({ text: l, options: { breakLine: true, fontSize: 11.5, color: INK, paraSpaceAfter: 4 } })), { x: x + 0.18, y: y + 0.44, w: w - 0.36, h: lines.length * 0.34, fontFace: 'Consolas', valign: 'top' });
}

(async () => {
  await makeGradient('cover-bg.png', NAVY, '0E1830');
  await makeGradient('sec-bg.png', '1B2A47', '111B30');

  const p = new pptxgen();
  p.defineLayout({ name: 'W', width: W, height: H });
  p.layout = 'W';
  p.author = '智学中枢团队';
  p.title = '智学中枢 · 软件杯参赛汇报';
  const add = () => p.addSlide();

  // ============ 1. 封面 ============
  {
    const s = add();
    s.background = { path: path.join(ASSETS, 'cover-bg.png') };
    s.addShape('rect', { x: 0.7, y: 1.35, w: 0.16, h: 1.0, fill: { color: GREEN } });
    s.addText('软件杯 2026 · 领域知识个性化资源生成与多智能体系统', { x: 0.95, y: 1.33, w: 11, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 14, color: '9FB7AC', charSpacing: 1 });
    s.addText('智学中枢', { x: 0.92, y: 1.8, w: 11, h: 1.2, fontFace: 'Microsoft YaHei', fontSize: 58, bold: true, color: WHITE });
    s.addText('多智能体协同驱动的个性化学习平台', { x: 0.95, y: 2.98, w: 11.4, h: 0.6, fontFace: 'Microsoft YaHei', fontSize: 25, bold: true, color: 'E8E0CE' });
    s.addText('诊断学情 · 生成每一课 —— 让 AI 真正因材施教，让每一份学习内容都可溯源、可信。', { x: 0.95, y: 3.66, w: 11.2, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 14, color: 'B9C4D6' });
    const tags = ['真实多智能体协同', '防幻觉 · 幻觉率<5%', '对话式动态画像', '学—记—讲—测闭环'];
    tags.forEach((t, i) => {
      const x = 0.95 + i * 2.92;
      s.addShape('roundRect', { x, y: 4.42, w: 2.74, h: 0.54, rectRadius: 0.1, fill: { color: '1F3050' }, line: { color: GREEN, width: 1 } });
      s.addText(t, { x, y: 4.42, w: 2.74, h: 0.54, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color: 'DCE6DD', align: 'center', valign: 'middle' });
    });
    s.addShape('line', { x: 0.95, y: 5.42, w: 11.4, h: 0, line: { color: '33476B', width: 1 } });
    const rows = [
      ['参赛组别：', '〔本科组 · 企业命题 / 自主命题〕', '答辩人：', '〔答辩人姓名〕'],
      ['参赛队伍：', '〔队伍名称〕', '团队成员：', '〔成员姓名〕'],
      ['参赛院校：', '〔学校名称〕', '指导教师：', '〔指导教师〕'],
    ];
    rows.forEach((r, i) => {
      const y = 5.62 + i * 0.4;
      s.addText([
        { text: r[0], options: { color: '8FA0BC', fontSize: 12.5 } }, { text: r[1] + '      ', options: { color: WHITE, fontSize: 12.5, bold: true } },
        { text: r[2], options: { color: '8FA0BC', fontSize: 12.5 } }, { text: r[3], options: { color: WHITE, fontSize: 12.5, bold: true } },
      ], { x: 0.95, y, w: 11.4, h: 0.36, fontFace: 'Microsoft YaHei' });
    });
    s.addNotes('开场 30 秒：报项目名 + 组别 + 答辩人，一句话定位——多智能体协同驱动的个性化学习平台，解决"千人一面"与"AI 幻觉"两大痛点，四个差异化亮点见标签。');
  }

  // ============ 2. 项目背景与痛点 ============
  {
    const s = add();
    header(s, { kicker: 'Background · 痛点', title: '项目背景：从痛点到解决方案', idx: '01' });
    // 核心公式三段式
    const steps = [['痛点', '资源千人一面\nAI 生成易幻觉', AMBER], ['现有方案不足', '统一难度顺序\n生成不可溯源', 'B5544B'], ['我们的解决方案', '多智能体 + RAG\n因材施教·可信生成', GREEN]];
    steps.forEach((st, i) => {
      const x = 0.7 + i * 4.3;
      s.addShape('roundRect', { x, y: 1.5, w: 3.85, h: 1.55, rectRadius: 0.12, fill: { color: i === 2 ? NAVY : WHITE }, line: { color: st[2], width: 1.5 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.3, blur: 6, offset: 2, angle: 90 } });
      s.addText(st[0], { x: x + 0.2, y: 1.62, w: 3.5, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: i === 2 ? '8FE0BE' : st[2] });
      s.addText(st[1], { x: x + 0.2, y: 2.04, w: 3.5, h: 0.9, fontFace: 'Microsoft YaHei', fontSize: 12.5, color: i === 2 ? 'DCE6DD' : INK, valign: 'top', lineSpacingMultiple: 1.05 });
      if (i < 2) s.addText('→', { x: x + 3.88, y: 1.5, w: 0.42, h: 1.55, fontFace: 'Arial', fontSize: 26, bold: true, color: INK_SOFT, align: 'center', valign: 'middle' });
    });
    // 两大痛点详述
    card(s, { x: 0.7, y: 3.35, w: 5.95, h: 1.65 }, { title: '痛点一 · 资源千人一面', color: AMBER, desc: '统一课程、统一难度、统一顺序，忽视个体的知识基础、认知风格与学习目标——"学了用不上、想学的没有"，效率低下。' });
    card(s, { x: 6.85, y: 3.35, w: 5.95, h: 1.65 }, { title: '痛点二 · AI 生成易幻觉', color: 'B5544B', desc: '大模型直接生成讲义常含事实错误、来源不可考；教育场景一旦"一本正经地胡说"，轻则误导、重则失信，无法落地教学。' });
    // 解决方案三件套
    s.addShape('roundRect', { x: 0.7, y: 5.2, w: 12.1, h: 1.5, rectRadius: 0.12, fill: { color: NAVY } });
    const vs = [['因材施教', '对话建画像 → 能力定顺序、偏好定形式，不同的人不同路径'], ['可信生成', 'RAG 逐句接地 + 多智能体审核，幻觉率<5%、来源可溯'], ['科学闭环', '康奈尔+费曼+阶段测试做进产品，学—记—讲—测成环']];
    vs.forEach((v, i) => {
      const x = 1.0 + i * 3.85;
      s.addText(v[0], { x: x, y: 5.34, w: 3.6, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: '8FE0BE' });
      s.addText(v[1], { x: x, y: 5.74, w: 3.65, h: 0.85, fontFace: 'Microsoft YaHei', fontSize: 11, color: 'C7D2E2', valign: 'top', lineSpacingMultiple: 1.05 });
    });
    footer(s, 2);
    s.addNotes('核心公式：痛点 → 现有方案不足 → 我们的解决方案。先立两大痛点，再给价值主张三件套（因材施教/可信生成/科学闭环），后续每个功能都回扣这三点。');
  }

  // ============ 3. 总体架构 + 技术选型 ============
  {
    const s = add();
    header(s, { kicker: 'Architecture · 技术选型', title: '总体架构：全栈自建、轻量可跑', idx: '02' });
    const layers = [
      ['前端交互层', 'React 18 + TypeScript + Vite · Zustand · Framer/GSAP · ECharts/Mermaid', 'CFE0D7'],
      ['服务接口层', 'FastAPI · 统一信封 {code,message,data,traceId} · JWT · 异步任务 · 日志脱敏', 'D6E0EE'],
      ['多智能体编排层', 'LangGraph 五节点：诊断 → 检索 → 生成 → 审核 → 决策（重试/降级回环）', 'E7D9C2'],
      ['RAG 检索增强层', 'Chroma 向量库 · bge 本地嵌入 · 逐句接地校验 · 30+ 文档 / 153 切片', 'CFE0D7'],
      ['数据与模型层', 'SQLite · 内存 TTL 会话 · LLMClient 适配（mock/DeepSeek/Qwen 可切换）', 'DDD6CA'],
    ];
    let y = 1.5;
    layers.forEach((L) => {
      s.addShape('roundRect', { x: 0.7, y, w: 9.0, h: 0.9, rectRadius: 0.08, fill: { color: L[2] }, line: { color: WHITE, width: 1.5 } });
      s.addText(L[0], { x: 0.9, y: y + 0.06, w: 2.6, h: 0.78, fontFace: 'Microsoft YaHei', fontSize: 14, bold: true, color: NAVY, valign: 'middle' });
      s.addText(L[1], { x: 3.45, y: y + 0.06, w: 6.1, h: 0.78, fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK, valign: 'middle' });
      y += 1.02;
    });
    s.addShape('roundRect', { x: 9.95, y: 1.5, w: 2.85, h: 4.6, rectRadius: 0.1, fill: { color: NAVY } });
    s.addText('技术选型亮点', { x: 10.1, y: 1.66, w: 2.6, h: 0.36, fontFace: 'Microsoft YaHei', fontSize: 13.5, bold: true, color: '8FE0BE' });
    bullets(s, [
      { t: '真实 LangGraph 多智能体编排', c: 'DCE6DD' },
      { t: 'RAG 接地抑制幻觉', c: 'DCE6DD' },
      { t: 'Mock-first：无 Key 跑全链路', c: 'DCE6DD' },
      { t: '轻量栈：Chroma+SQLite 单机', c: 'DCE6DD' },
      { t: 'LLM 适配层·模型可切换', c: 'DCE6DD' },
      { t: 'WorkflowTrace 全轨迹可观测', c: 'DCE6DD' },
    ], { x: 10.12, y: 2.1, w: 2.6, h: 3.9 }, { fs: 11, gap: 9 });
    s.addText('生产替换路径（README 说明）：Chroma→Milvus · SQLite→PostgreSQL · 内存会话→Redis，业务代码零改动平滑升级。', { x: 0.7, y: 6.25, w: 12.1, h: 0.6, fontFace: 'Microsoft YaHei', fontSize: 11.5, italic: true, color: INK_SOFT, valign: 'top' });
    footer(s, 3);
    s.addNotes('架构一页看全：五层 + 技术选型亮点。强调多智能体编排是真实 LangGraph（非串行模拟）、Mock-first 可断网复现、轻量栈单机可部署、生产平滑替换路径。');
  }

  // ============ 4. 多智能体协同设计 ============
  {
    const s = add();
    header(s, { kicker: 'Multi-Agent Design', title: '多智能体协同：明确分工 · 真实编排', idx: '02' });
    const agents = [
      ['① 学情诊断 Agent', '对话采集+诊断微测，构建 6 维异质画像；不确定维度标低置信', GREEN],
      ['② 领域知识生成 Agent', '依画像生成适配难度的讲义/图解/代码/测试，贴画像给不同深度', '2E4A78'],
      ['③ 内容审核校验 Agent', '基于 RAG 逐句接地校验幻觉率，超阈值打回重生成', AMBER],
      ['④ 学习路径规划 Agent', '按掌握度打分排序：薄弱优先、已掌握后置，偏好定形式', GREEN_D],
    ];
    agents.forEach((a, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.7 + col * 3.92, y = 1.5 + row * 1.42;
      s.addShape('roundRect', { x, y, w: 3.62, h: 1.26, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.25, blur: 5, offset: 2, angle: 90 } });
      s.addShape('rect', { x, y, w: 0.1, h: 1.26, fill: { color: a[2] } });
      s.addText(a[0], { x: x + 0.24, y: y + 0.12, w: 3.25, h: 0.36, fontFace: 'Microsoft YaHei', fontSize: 13.5, bold: true, color: NAVY });
      s.addText(a[1], { x: x + 0.24, y: y + 0.5, w: 3.3, h: 0.7, fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.03 });
    });
    s.addShape('roundRect', { x: 0.7, y: 4.4, w: 7.54, h: 1.2, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.25, blur: 5, offset: 2, angle: 90 } });
    s.addShape('rect', { x: 0.7, y: 4.4, w: 0.1, h: 1.2, fill: { color: 'B5544B' } });
    s.addText('⑤ 学习过程评估 Agent', { x: 0.94, y: 4.52, w: 7.1, h: 0.36, fontFace: 'Microsoft YaHei', fontSize: 13.5, bold: true, color: NAVY });
    s.addText('跨会话持续运行，累积做题/进度/笔记行为，产出多维学情评估与动态调整建议（独立 Agent，非编排节点）。', { x: 0.94, y: 4.9, w: 7.15, h: 0.65, fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.05 });
    // 右侧编排
    s.addShape('roundRect', { x: 8.5, y: 1.5, w: 4.3, h: 4.95, rectRadius: 0.1, fill: { color: NAVY } });
    s.addText('LangGraph 状态机编排', { x: 8.72, y: 1.66, w: 3.9, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 14, bold: true, color: '8FE0BE' });
    s.addText('① ② ③ 由 LangGraph 编排为单次生成工作流；④ ⑤ 作为独立 Agent 长期运行。', { x: 8.72, y: 2.1, w: 3.9, h: 0.8, fontFace: 'Microsoft YaHei', fontSize: 11.5, color: 'C7D2E2', valign: 'top', lineSpacingMultiple: 1.1 });
    s.addText('诊断 → 检索 → 生成 → 审核 → 决策', { x: 8.72, y: 2.95, w: 3.9, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 12, bold: true, color: WHITE });
    s.addText('审核不通过 → 生成↔审核 间真实回环重试；超限降级兜底，保证可信产物交付。', { x: 8.72, y: 3.38, w: 3.9, h: 0.85, fontFace: 'Microsoft YaHei', fontSize: 11.5, color: 'C7D2E2', valign: 'top', lineSpacingMultiple: 1.1 });
    s.addShape('roundRect', { x: 8.72, y: 4.35, w: 3.86, h: 1.9, rectRadius: 0.08, fill: { color: '1F3050' }, line: { color: GREEN, width: 1 } });
    s.addText('消融实验佐证', { x: 8.9, y: 4.46, w: 3.5, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 12, bold: true, color: '8FE0BE' });
    s.addText('去掉 RAG 检索，幻觉率由 0.059 升至 0.155（Δ+0.096）——接地是抑制幻觉的主导机制。', { x: 8.9, y: 4.82, w: 3.55, h: 1.35, fontFace: 'Microsoft YaHei', fontSize: 11, color: 'DCE6DD', valign: 'top', lineSpacingMultiple: 1.1 });
    footer(s, 4);
    s.addNotes('五个 Agent 分工清晰，对应赛题"多智能体系统"。①②③真实 LangGraph 编排、有回环重试；④⑤独立运行。消融数据证明 RAG 作用。');
  }

  // ============ 5. 核心技术与算法亮点（技术硬核·公式） ============
  {
    const s = add();
    header(s, { kicker: 'Core Algorithms · 技术硬核', title: '核心算法与关键公式', idx: '02' });
    formula(s, 0.7, 1.45, 6.0, '① RAG 逐句接地 / 幻觉率', [
      'sim(s) = max  cos( emb(s), emb(d) )',
      's 接地  ⟺  sim(s) ≥ 0.6',
      '幻觉率 = |未接地句| / |总句|   → 0.0428',
    ]);
    formula(s, 0.7, 3.4, 6.0, '② 难度适配率 / 知识覆盖率', [
      '适配率 = 三档难度分「有序对」正确率',
      '       = 正确序对 / 总序对   → 1.00',
      '覆盖率 = 命中核心概念 / 概念清单 → 1.00',
    ]);
    formula(s, 6.95, 1.45, 5.85, '③ 学习路径优先级打分（升序，分越小越先学）', [
      'score(kp) = lesson_seq            # 先修骨架',
      '  + 100            若 已达标/已掌握  # 大幅后置',
      '  + 0.8·(能力分/100) 若 薄弱        # 越低越前',
      '  ± 0.4            基础课×画像基础联动',
      '  − 0.8·(岗位需求/100)  目标岗位高需求前置',
    ], '2E4A78');
    // 防幻觉三道防线条
    s.addText('防幻觉三道防线', { x: 6.95, y: 3.95, w: 5.85, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color: GREEN_D });
    const lines = [['第一道 · RAG 接地', '生成全程基于检索真实语料，逐句可溯源'], ['第二道 · Critic 审核', '审核 Agent 逐句校验，未接地句计入幻觉率'], ['第三道 · 重试降级', '超阈值回炉重生成，超限降级，绝不交付不可信']];
    lines.forEach((L, i) => {
      const y = 4.3 + i * 0.74;
      s.addShape('roundRect', { x: 6.95, y, w: 5.85, h: 0.64, rectRadius: 0.07, fill: { color: WHITE }, line: { color: LINE, width: 1 } });
      s.addShape('rect', { x: 6.95, y, w: 0.08, h: 0.64, fill: { color: GREEN } });
      s.addText(L[0], { x: 7.1, y: y + 0.04, w: 2.4, h: 0.56, fontFace: 'Microsoft YaHei', fontSize: 12, bold: true, color: NAVY, valign: 'middle' });
      s.addText(L[1], { x: 9.5, y: y + 0.04, w: 3.25, h: 0.56, fontFace: 'Microsoft YaHei', fontSize: 10, color: INK_SOFT, valign: 'middle' });
    });
    s.addText('① 接地阈值 0.6（与评测同源口径） · ② 三档难度由难度评分确定性区分 · ③ 路径打分由 planner_agent 按画像+掌握度确定性计算（无随机）。', { x: 0.7, y: 6.35, w: 6.0, h: 0.55, fontFace: 'Microsoft YaHei', fontSize: 9.5, italic: true, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.05 });
    footer(s, 5);
    s.addNotes('技术硬核页：用真实公式展示技术深度。幻觉率/适配率/覆盖率口径、RAG 接地相似度阈值 0.6、路径优先级打分（来自 planner_agent 真实代码）。强调全部确定性计算、可复现。');
  }

  // ============ 6. 功能模块总览 + 业务主线 ============
  {
    const s = add();
    header(s, { kicker: 'Modules · 功能演示', title: '功能模块总览与业务主线', idx: '03' });
    // 业务主线流程
    const flow = ['① 画像诊断', '② 学习路径', '③ 资源生成', '④ 学习闭环', '⑤ 过程评估'];
    flow.forEach((t, i) => {
      const x = 0.7 + i * 2.46;
      s.addShape('roundRect', { x, y: 1.55, w: 2.18, h: 0.74, rectRadius: 0.1, fill: { color: i === 2 ? AMBER : GREEN } });
      s.addText(t, { x, y: 1.55, w: 2.18, h: 0.74, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color: WHITE, align: 'center', valign: 'middle' });
      if (i < 4) s.addText('→', { x: x + 2.18, y: 1.55, w: 0.3, h: 0.74, fontFace: 'Arial', fontSize: 18, bold: true, color: INK_SOFT, align: 'center', valign: 'middle' });
    });
    s.addText('⟲ 画像/掌握度变化 → 路径与资源自动重算（学情驱动的闭环回流）', { x: 0.7, y: 2.42, w: 12, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 11.5, italic: true, color: GREEN_D });
    // 模块卡片
    const mods = [
      ['对话式画像诊断', '三入口（做题/自述/跳过）· 6 维异质画像 · 随学随新', GREEN],
      ['个性化学习路径', '能力定顺序 · 偏好定形式 · 画像变路径变', '2E4A78'],
      ['多模态资源生成', '讲义/思维导图/代码/图解/视频/测试一站式', AMBER],
      ['学—记—讲—测闭环', '康奈尔笔记 + 费曼讲解 + 阶段测试 GATE', GREEN_D],
      ['智能即时辅导', '"我没懂"→ 识别问题 → 按需生成针对性资源', GREEN],
      ['学习过程评估', '四维量化 + 薄弱点定位 + 动态调整建议', '2E4A78'],
      ['知识图谱可视化', '掌握/学习中/待学/盲区四态拓扑', AMBER],
      ['岗位对标 + 联网聚合', '匹配度+能力缺口 · 联网搜优质资源 AI 评分', GREEN_D],
    ];
    mods.forEach((m, i) => {
      const col = i % 4, row = Math.floor(i / 4);
      const x = 0.7 + col * 3.06, y = 3.0 + row * 1.78;
      s.addShape('roundRect', { x, y, w: 2.86, h: 1.6, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.22, blur: 4, offset: 2, angle: 90 } });
      s.addShape('rect', { x, y, w: 2.86, h: 0.08, fill: { color: m[2] } });
      s.addText(m[0], { x: x + 0.16, y: y + 0.18, w: 2.55, h: 0.6, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color: NAVY, valign: 'top' });
      s.addText(m[1], { x: x + 0.16, y: y + 0.74, w: 2.58, h: 0.78, fontFace: 'Microsoft YaHei', fontSize: 10, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.05 });
    });
    footer(s, 6);
    s.addNotes('功能模块总览：先给业务主线（画像→路径→资源→闭环→评估，闭环回流），再展示 8 大模块。后三页用真实界面截图逐一演示核心模块。');
  }

  // ============ 7. 功能演示 ①② 画像 + 多智能体生成 ============
  {
    const s = add();
    header(s, { kicker: '功能演示 01 · 画像 + 资源生成', title: '对话建像 + LangGraph 真实协同生成', idx: '03' });
    addShot(s, '06-profile-chat-progress.png', { x: 0.55, y: 1.45, w: 6.05, h: 3.45 });
    addShot(s, '08b-workflow-done.png', { x: 6.85, y: 1.45, w: 6.0, h: 3.45 });
    s.addText('① 对话式画像：自然语言抽取特征，右侧 6 维画像随聊随长；不确定维度标低置信', { x: 0.55, y: 4.95, w: 6.05, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK_SOFT, align: 'center', valign: 'top' });
    s.addText('② 多智能体生成：诊断→检索→生成→审核→决策五节点真实点亮，审核不通过真实回环', { x: 6.85, y: 4.95, w: 6.0, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK_SOFT, align: 'center', valign: 'top' });
    s.addShape('roundRect', { x: 0.7, y: 5.6, w: 12.1, h: 1.1, rectRadius: 0.1, fill: { color: NAVY } });
    s.addText([
      { text: '图文并茂 · 实际运行效果：', options: { bold: true, color: '8FE0BE', fontSize: 12.5 } },
      { text: '最终讲义页实时标注"已校验 · 幻觉率<5%"并显示 RAG 引用文档数，sources 可溯源到具体文档；WorkflowTrace 留存 327 条真实轨迹，可复现、可观测。', options: { color: 'DCE6DD', fontSize: 12 } },
    ], { x: 0.95, y: 5.6, w: 11.6, h: 1.1, fontFace: 'Microsoft YaHei', valign: 'middle', lineSpacingMultiple: 1.1 });
    footer(s, 7);
    s.addNotes('重头戏：现场演示对话建像 + 启动工作流，制造一次审核不通过展示真实回环重试。这是最有说服力的"真实多智能体"证据。');
  }

  // ============ 8. 功能演示 ③④ 路径 + 闭环 ============
  {
    const s = add();
    header(s, { kicker: '功能演示 02 · 路径 + 学习闭环', title: '个性化路径 + 学—记—讲—测闭环', idx: '03' });
    addShot(s, '09-learning-path-top.png', { x: 0.55, y: 1.45, w: 4.3, h: 3.0 });
    addShot(s, '13-cornell-notes.png', { x: 5.0, y: 1.45, w: 4.0, h: 3.0 });
    addShot(s, '14-feynman.png', { x: 9.1, y: 1.45, w: 3.85, h: 3.0 });
    s.addText('③ 路径：薄弱优先、已掌握后置', { x: 0.55, y: 4.5, w: 4.3, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 10, color: INK_SOFT, align: 'center' });
    s.addText('④ 康奈尔笔记：结构化记录', { x: 5.0, y: 4.5, w: 4.0, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 10, color: INK_SOFT, align: 'center' });
    s.addText('④ 费曼讲解：以讲代学暴露缺口', { x: 9.1, y: 4.5, w: 3.85, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 10, color: INK_SOFT, align: 'center' });
    // 流程条
    const steps = ['输入·看', '康奈尔·记', '费曼·讲', '阶段测试·测'];
    steps.forEach((t, i) => {
      const x = 0.7 + i * 2.62;
      s.addShape('roundRect', { x, y: 5.05, w: 2.3, h: 0.56, rectRadius: 0.28, fill: { color: i === 3 ? AMBER : GREEN } });
      s.addText(t, { x, y: 5.05, w: 2.3, h: 0.56, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color: WHITE, align: 'center', valign: 'middle' });
      if (i < 3) s.addText('→', { x: x + 2.3, y: 5.05, w: 0.32, h: 0.56, fontFace: 'Arial', fontSize: 17, bold: true, color: INK_SOFT, align: 'center', valign: 'middle' });
    });
    s.addShape('roundRect', { x: 0.7, y: 5.78, w: 12.1, h: 0.92, rectRadius: 0.1, fill: { color: NAVY } });
    s.addText('阶段测试是独立检验 GATE：只有通过（≥60 分）才点亮"已掌握"并推进学习路径——"通关才算掌握"，杜绝自我感觉良好。', { x: 0.95, y: 5.78, w: 11.6, h: 0.92, fontFace: 'Microsoft YaHei', fontSize: 12.5, color: 'DCE6DD', valign: 'middle' });
    footer(s, 8);
    s.addNotes('核心模块③④：个性化路径（真实排序算法）+ 学-记-讲-测闭环。强调阶段测试 GATE，通关才点亮掌握，真正对应因材施教。');
  }

  // ============ 9. 功能演示 ⑤⑥ + 加分 ============
  {
    const s = add();
    header(s, { kicker: '功能演示 03 · 辅导/评估/扩展', title: '即时辅导 · 过程评估 · 多模态扩展', idx: '03' });
    const grid = [
      ['16-instant-tutor-result.png', '⑤ 智能即时辅导', '描述卡点 → 识别问题 → 按需生成针对性资源'],
      ['03-dashboard-top.png', '⑥ 学习过程评估', '四维量化 + 薄弱点定位 + 动态调整建议'],
      ['18-knowledge-graph.png', '知识图谱可视化', '掌握/学习中/待学/盲区四态拓扑一目了然'],
      ['19-job-match.png', '岗位对标 + 联网聚合', '匹配度 + 能力缺口 · 联网优质资源 AI 评分'],
    ];
    grid.forEach((g, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.7 + col * 6.2, y = 1.5 + row * 2.66;
      addShot(s, g[0], { x, y, w: 3.05, h: 2.42 }, { pad: 0.04 });
      s.addText(g[1], { x: x + 3.2, y: y + 0.2, w: 2.8, h: 0.55, fontFace: 'Microsoft YaHei', fontSize: 14, bold: true, color: NAVY, valign: 'middle' });
      s.addText(g[2], { x: x + 3.2, y: y + 0.85, w: 2.85, h: 1.3, fontFace: 'Microsoft YaHei', fontSize: 11, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.1 });
    });
    footer(s, 9);
    s.addNotes('核心模块⑤⑥ + 加分项：即时辅导（按需生成）、过程评估（跨会话）、知识图谱、岗位对标+联网聚合。证明系统能力广度。');
  }

  // ============ 10. 项目创新性与优势（对比表格） ============
  {
    const s = add();
    header(s, { kicker: 'Innovation · 创新性与优势', title: '横向对比：四维领先传统与通用方案', idx: '04' });
    const head = (t) => ({ text: t, options: { bold: true, color: WHITE, fill: { color: NAVY }, fontSize: 12.5, align: 'center', valign: 'middle' } });
    const cell = (t, b) => ({ text: t, options: { fontSize: 11, color: b ? GREEN_D : INK, bold: !!b, align: 'left', valign: 'middle', fill: { color: b ? 'EAF1EC' : WHITE } } });
    const rows = [
      [head('对比维度'), head('传统在线学习'), head('通用 AI 问答/生成'), head('智学中枢（本作品）')],
      [cell('个性化', 1), cell('千人一面、固定课程'), cell('仅会话级、无画像'), cell('6 维画像·能力定序·偏好定形', 1)],
      [cell('内容可信', 1), cell('人工制作、静态更新'), cell('易幻觉、来源不可溯'), cell('RAG 接地·幻觉<5%·可溯源', 1)],
      [cell('学习方法', 1), cell('看视频/读文档为主'), cell('一问一答、无方法'), cell('学—记—讲—测闭环 + 测试 GATE', 1)],
      [cell('过程评估', 1), cell('无 / 仅完成度'), cell('无'), cell('四维评估 + 动态调整建议', 1)],
      [cell('成本 / 效率', 1), cell('优质内容制作昂贵'), cell('—'), cell('≈¥0.02/份·分钟级生成', 1)],
    ];
    s.addTable(rows, { x: 0.7, y: 1.55, w: 12.1, colW: [1.9, 3.2, 3.0, 4.0], rowH: [0.5, 0.62, 0.62, 0.62, 0.62, 0.62], fontFace: 'Microsoft YaHei', border: { pt: 0.5, color: LINE }, valign: 'middle' });
    // 四大创新精简
    const inv = ['① 真实多智能体协同（非串行模拟）', '② 防幻觉 + 内容安全双保险', '③ 学—记—讲—测科学闭环', '④ 对话式动态画像（低置信透明）'];
    inv.forEach((t, i) => {
      const x = 0.7 + i * 3.06;
      s.addShape('roundRect', { x, y: 5.7, w: 2.86, h: 1.0, rectRadius: 0.1, fill: { color: NAVY } });
      s.addText(t, { x: x + 0.16, y: 5.7, w: 2.55, h: 1.0, fontFace: 'Microsoft YaHei', fontSize: 11.5, bold: true, color: 'DCE6DD', valign: 'middle', lineSpacingMultiple: 1.05 });
    });
    footer(s, 10);
    s.addNotes('创新性与优势：用对比表格直观展示四维领先（个性化/可信/方法/评估/成本）。这页是拉分关键——别人没有、我们做到。');
  }

  // ============ 11. 量化指标看板 ============
  {
    const s = add();
    header(s, { kicker: 'Metrics · 真实指标', title: '量化指标：全部达标、可复现', idx: '04' });
    const big = [['0.0428', '幻觉率', '目标 <0.05 ✓', GREEN_D], ['100%', '难度适配率', '目标 ≥85% ✓', '2E4A78'], ['100%', '知识覆盖率', '目标 ≥90% ✓', AMBER]];
    big.forEach((b, i) => {
      const x = 0.7 + i * 4.05;
      s.addShape('roundRect', { x, y: 1.55, w: 3.8, h: 1.9, rectRadius: 0.12, fill: { color: WHITE }, line: { color: b[3], width: 1.5 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.3, blur: 7, offset: 2, angle: 90 } });
      s.addText(b[0], { x, y: 1.7, w: 3.8, h: 0.95, fontFace: 'Arial', fontSize: 44, bold: true, color: b[3], align: 'center', valign: 'middle' });
      s.addText(b[1], { x, y: 2.68, w: 3.8, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: INK, align: 'center' });
      s.addText(b[2], { x, y: 3.08, w: 3.8, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 11, color: GREEN_D, align: 'center' });
    });
    s.addText('跨领域验证（同一管线换计算机网络域）', { x: 0.7, y: 3.7, w: 6, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color: GREEN_D });
    const t1 = [
      [{ text: '领域', options: { bold: true, color: WHITE, fill: { color: NAVY } } }, { text: '幻觉率', options: { bold: true, color: WHITE, fill: { color: NAVY } } }, { text: '适配率', options: { bold: true, color: WHITE, fill: { color: NAVY } } }, { text: '覆盖率', options: { bold: true, color: WHITE, fill: { color: NAVY } } }],
      ['AI（30 文档）', '0.0428', '1.00', '1.00'],
      ['计算机网络（5 文档）', '0.0700', '0.83', '1.00'],
    ];
    s.addTable(t1, { x: 0.7, y: 4.05, w: 6.0, colW: [2.4, 1.2, 1.2, 1.2], rowH: [0.36, 0.36, 0.36], fontFace: 'Microsoft YaHei', fontSize: 11, color: INK, align: 'center', valign: 'middle', border: { pt: 0.5, color: LINE }, fill: { color: WHITE } });
    s.addText('换领域端到端跑通、覆盖率满分，证明方法论与领域无关。', { x: 0.7, y: 5.25, w: 6.0, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 10.5, italic: true, color: INK_SOFT, valign: 'top' });
    s.addText('性能与成本（327 条真实轨迹）', { x: 7.0, y: 3.7, w: 5.8, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color: GREEN_D });
    const perf = [['P50 生成耗时', '13.2 s'], ['P90 生成耗时', '37.0 s'], ['单份讲义成本', '≈ ¥0.02'], ['知识库规模', '30+ 文档/153 切片']];
    perf.forEach((pp, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 7.0 + col * 2.95, y = 4.05 + row * 0.9;
      s.addShape('roundRect', { x, y, w: 2.8, h: 0.78, rectRadius: 0.08, fill: { color: WHITE }, line: { color: LINE, width: 1 } });
      s.addText(pp[1], { x: x + 0.12, y: y + 0.05, w: 2.55, h: 0.42, fontFace: 'Arial', fontSize: 18, bold: true, color: NAVY });
      s.addText(pp[0], { x: x + 0.12, y: y + 0.47, w: 2.6, h: 0.28, fontFace: 'Microsoft YaHei', fontSize: 10, color: INK_SOFT });
    });
    s.addText('一轮 18 份讲义 ≈ ¥0.36，低成本可规模化。', { x: 7.0, y: 5.9, w: 5.8, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 10.5, italic: true, color: INK_SOFT });
    footer(s, 11);
    s.addNotes('数字从真实 metrics-report 取，全部达标。三大主指标 + 跨领域验证（诚实呈现网络域略高）+ 性能成本。强调可复现：附复现命令。');
  }

  // ============ 12. 测试与安全性 ============
  {
    const s = add();
    header(s, { kicker: 'Test & Security · 规范开发', title: '测试与安全性保障', idx: '05' });
    const blocks = [
      ['软件测试', [
        { t: '后端 pytest：18 个测试文件 / 195 条用例，全量通过', bold: true },
        '前端 TypeScript 编译 tsc 0 报错，0 回归',
        '关键链路（工作流/评估/防幻觉）覆盖单元 + 集成测试',
      ], GREEN],
      ['性能与压测', [
        { t: '端到端生成 P50 13.2s / P90 37.0s（327 条真实轨迹）', bold: true },
        '单份讲义成本 ≈ ¥0.02，低成本可规模化',
        '异步任务 + 状态机轮询，耗时操作不阻塞',
      ], '2E4A78'],
      ['鲁棒性验证', [
        { t: '消融实验：去 RAG 幻觉率 0.059→0.155，验证组件有效', bold: true },
        '跨领域验证：换计算机网络域端到端跑通',
        'Mock-first 隔离：断网/无 Key 全链路可复现',
      ], AMBER],
      ['数据与内容安全', [
        { t: 'JWT 鉴权 + admin/learner 角色守卫（越权 403）', bold: true },
        '日志手机号/邮箱经脱敏拦截器掩码',
        '生成内容统一敏感/违规过滤，不误伤学术术语',
      ], GREEN_D],
    ];
    blocks.forEach((b, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.7 + col * 6.2, y = 1.5 + row * 2.66;
      s.addShape('roundRect', { x, y, w: 5.85, h: 2.42, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.25, blur: 5, offset: 2, angle: 90 } });
      s.addShape('rect', { x, y, w: 5.85, h: 0.5, fill: { color: b[2] } });
      s.addText(b[0], { x: x + 0.2, y, w: 5.5, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 14.5, bold: true, color: WHITE, valign: 'middle' });
      bullets(s, b[1], { x: x + 0.22, y: y + 0.66, w: 5.45, h: 1.65 }, { fs: 11.5, gap: 8 });
    });
    footer(s, 12);
    s.addNotes('对应"测试与安全性"：规范开发流程——195 条 pytest 用例 + tsc 0 报错；性能压测 P50/P90；消融/跨领域鲁棒性；JWT 权限 + 日志脱敏 + 内容安全。体现工程严谨。');
  }

  // ============ 13. 商业价值与应用前景 ============
  {
    const s = add();
    header(s, { kicker: 'Value · 商业价值与前景', title: '应用落地与未来规划', idx: '06' });
    // 应用场景
    s.addText('落地场景', { x: 0.7, y: 1.5, w: 6, h: 0.36, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: GREEN_D });
    const scenes = [['高校课程辅学', '按学情个性化补差培优'], ['职业技能/转岗培训', '岗位对标 + 缺口补齐'], ['考证备考', '分阶讲义 + 阶段测试通关'], ['企业内训', '领域知识库低成本定制']];
    scenes.forEach((sc, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.7 + col * 3.05, y = 1.95 + row * 1.0;
      s.addShape('roundRect', { x, y, w: 2.9, h: 0.86, rectRadius: 0.09, fill: { color: WHITE }, line: { color: LINE, width: 1 } });
      s.addShape('rect', { x, y, w: 0.08, h: 0.86, fill: { color: GREEN } });
      s.addText(sc[0], { x: x + 0.18, y: y + 0.1, w: 2.6, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color: NAVY });
      s.addText(sc[1], { x: x + 0.18, y: y + 0.44, w: 2.62, h: 0.36, fontFace: 'Microsoft YaHei', fontSize: 10, color: INK_SOFT });
    });
    // 受众 + 价值
    s.addShape('roundRect', { x: 6.95, y: 1.9, w: 5.85, h: 2.06, rectRadius: 0.1, fill: { color: NAVY } });
    s.addText('目标受众与核心价值', { x: 7.15, y: 2.04, w: 5.5, h: 0.36, fontFace: 'Microsoft YaHei', fontSize: 14, bold: true, color: '8FE0BE' });
    bullets(s, [
      { t: '受众：在校学生 / 转岗求职者 / 终身学习者 / 培训机构', c: 'DCE6DD' },
      { t: '价值：把优质个性化教学的边际成本降到 ≈¥0.02/份', c: 'DCE6DD' },
      { t: '规模化"因材施教"，破解优质师资稀缺与千人一面', c: 'DCE6DD' },
    ], { x: 7.15, y: 2.46, w: 5.5, h: 1.4 }, { fs: 11.5, gap: 9 });
    // 迭代路线
    s.addText('未来迭代规划 · 揭榜挂帅方向', { x: 0.7, y: 4.2, w: 12, h: 0.36, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: GREEN_D });
    const road = [['近期', '资源生态聚合：联网优质资源 + AI 评分排序规模化'], ['中期', '岗位能力图谱：对接真实招聘需求，学习直通就业'], ['远期', '多学科领域扩展 + 生产级架构（Milvus/PG/Redis）平滑升级']];
    road.forEach((r, i) => {
      const x = 0.7 + i * 4.05, y = 4.65;
      s.addShape('roundRect', { x, y, w: 3.8, h: 1.7, rectRadius: 0.1, fill: { color: WHITE }, line: { color: GREEN, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.25, blur: 5, offset: 2, angle: 90 } });
      s.addText(r[0], { x: x + 0.2, y: y + 0.16, w: 3.4, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: AMBER });
      s.addText(r[1], { x: x + 0.2, y: y + 0.62, w: 3.45, h: 0.95, fontFace: 'Microsoft YaHei', fontSize: 11.5, color: INK, valign: 'top', lineSpacingMultiple: 1.1 });
    });
    footer(s, 13);
    s.addNotes('商业价值与应用前景：落地场景（高校/职培/考证/企业内训）+ 受众 + 核心价值（边际成本¥0.02、规模化因材施教）+ 近中远期迭代路线。');
  }

  // ============ 14. 致谢与问答 ============
  {
    const s = add();
    s.background = { path: path.join(ASSETS, 'sec-bg.png') };
    s.addShape('rect', { x: 0.7, y: 2.4, w: 0.16, h: 1.0, fill: { color: GREEN } });
    s.addText('THANKS & Q / A', { x: 0.95, y: 2.42, w: 10, h: 0.34, fontFace: 'Arial', fontSize: 13, bold: true, color: '9FB7AC', charSpacing: 2 });
    s.addText('感谢聆听 · 敬请指正', { x: 0.92, y: 2.82, w: 11.5, h: 0.9, fontFace: 'Microsoft YaHei', fontSize: 42, bold: true, color: WHITE });
    s.addText('感谢各位评委老师的耐心评审，感谢团队的协作付出。', { x: 0.95, y: 3.95, w: 11.4, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 16, color: 'C7D2E2' });
    s.addShape('roundRect', { x: 0.95, y: 4.7, w: 11.4, h: 0.92, rectRadius: 0.1, fill: { color: '1F3050' }, line: { color: GREEN, width: 1 } });
    s.addText('智学中枢 —— 让 AI 因材施教，让每一份学习内容都可信。', { x: 0.95, y: 4.7, w: 11.4, h: 0.92, fontFace: 'Microsoft YaHei', fontSize: 17, bold: true, color: WHITE, align: 'center', valign: 'middle' });
    s.addText('欢迎就技术架构、多智能体协同、防幻觉机制等提问交流 ✦', { x: 0.95, y: 5.85, w: 11.4, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 14, color: '9FB7AC', align: 'center' });
    s.addNotes('收尾：感谢评委与团队，重申口号，主动引导提问方向（架构/多智能体/防幻觉），从容进入答辩问答环节。');
  }

  const out = path.join(__dirname, '..', '软件杯介绍-v3.pptx');
  await p.writeFile({ fileName: out });
  console.log('OK ->', out);
})().catch((e) => { console.error(e); process.exit(1); });
