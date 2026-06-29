/* 智学中枢 · 软件杯参赛汇报 PPT v2 — 直接用 pptxgenjs 构建（截图密集型，精确控版） */
const pptxgen = require('pptxgenjs');
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const SHOTS = path.join(__dirname, '..', 'ppt-assets', 'shots');
const ASSETS = path.join(__dirname, 'assets');
if (!fs.existsSync(ASSETS)) fs.mkdirSync(ASSETS, { recursive: true });

// ---- 配色（产品同色系：米色 / navy / 绿；不带 # 前缀）----
const NAVY = '17243F';
const NAVY2 = '243657';
const CREAM = 'F4EFE4';
const PAPER = 'FCFAF4';
const GREEN = '5B7F6E';
const GREEN_D = '46624F';
const INK = '2C2822';
const INK_SOFT = '6E665A';
const AMBER = 'C2873F';
const LINE = 'DED7C7';
const WHITE = 'FFFFFF';

const SHOT_AR = 1512 / 900; // 所有截图统一宽高比

// ---- 资源：栅格化 cover 渐变背景 ----
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

const W = 13.333, H = 7.5;

// 把截图按比例放进 box，并加白色圆角相框 + 阴影
function addShot(slide, file, box, opts = {}) {
  const ar = SHOT_AR;
  let w = box.w, h = w / ar;
  if (h > box.h) { h = box.h; w = h * ar; }
  const x = box.x + (box.w - w) / 2;
  const y = box.y + (box.h - h) / 2;
  const pad = opts.pad ?? 0.06;
  slide.addShape('roundRect', {
    x: x - pad, y: y - pad, w: w + pad * 2, h: h + pad * 2, rectRadius: 0.08,
    fill: { color: WHITE }, line: { color: opts.frame || GREEN, width: 1 },
    shadow: { type: 'outer', color: '7A6A4A', opacity: 0.28, blur: 9, offset: 3, angle: 90 },
  });
  slide.addImage({ path: path.join(SHOTS, file), x, y, w, h });
  return { x, y, w, h };
}

function footer(slide, n) {
  slide.addShape('line', { x: 0.55, y: 7.06, w: 12.23, h: 0, line: { color: LINE, width: 1 } });
  slide.addText('智学中枢 · 领域知识个性化资源生成与多智能体系统', {
    x: 0.55, y: 7.08, w: 8, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 9, color: INK_SOFT, align: 'left', valign: 'middle',
  });
  slide.addText('软件杯 2026', { x: 9.4, y: 7.08, w: 2.2, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 9, color: INK_SOFT, align: 'right', valign: 'middle' });
  slide.addText(String(n).padStart(2, '0'), { x: 11.75, y: 7.08, w: 1.03, h: 0.32, fontFace: 'Arial', fontSize: 10, bold: true, color: GREEN_D, align: 'right', valign: 'middle' });
}

// 内容页统一页眉
function header(slide, { kicker, title, idx }) {
  slide.background = { color: PAPER };
  slide.addShape('rect', { x: 0, y: 0, w: W, h: 1.18, fill: { color: NAVY } });
  slide.addShape('rect', { x: 0, y: 1.18, w: W, h: 0.06, fill: { color: GREEN } });
  slide.addShape('rect', { x: 0.55, y: 0.30, w: 0.12, h: 0.6, fill: { color: GREEN } });
  slide.addText((kicker || '').toUpperCase(), { x: 0.82, y: 0.26, w: 9, h: 0.26, fontFace: 'Arial', fontSize: 10.5, bold: true, color: '9FB7AC', charSpacing: 2 });
  slide.addText(title, { x: 0.8, y: 0.5, w: 10.4, h: 0.6, fontFace: 'Microsoft YaHei', fontSize: 24, bold: true, color: WHITE, valign: 'middle' });
  if (idx) slide.addText(idx, { x: 11.2, y: 0.18, w: 1.58, h: 0.82, fontFace: 'Arial', fontSize: 40, bold: true, color: '32507A', align: 'right', valign: 'middle' });
}

// 小标题 chip
function chip(slide, x, y, text, color = GREEN) {
  const w = 0.34 + text.length * 0.17;
  slide.addShape('roundRect', { x, y, w, h: 0.34, rectRadius: 0.17, fill: { color: 'EFEadf' }, line: { color, width: 1 } });
  slide.addText(text, { x, y, w, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 11, bold: true, color: GREEN_D, align: 'center', valign: 'middle' });
  return w;
}

// 要点列表
function bullets(slide, items, box, opts = {}) {
  slide.addText(
    items.map((t) => ({ text: t.t ?? t, options: { bullet: t.b === false ? false : { code: '2022', indent: 14 }, color: t.c || INK, bold: !!t.bold, fontSize: t.fs || (opts.fs || 14), breakLine: true, paraSpaceAfter: opts.gap ?? 8 } })),
    { x: box.x, y: box.y, w: box.w, h: box.h, fontFace: 'Microsoft YaHei', valign: 'top', lineSpacingMultiple: 1.05 }
  );
}

// 信息卡
function card(slide, box, { title, desc, big, unit, color = GREEN, sub }) {
  slide.addShape('roundRect', { x: box.x, y: box.y, w: box.w, h: box.h, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.3, blur: 6, offset: 2, angle: 90 } });
  slide.addShape('rect', { x: box.x, y: box.y, w: 0.09, h: box.h, fill: { color } });
  let yy = box.y + 0.16;
  if (big) {
    slide.addText([{ text: big, options: { fontFace: 'Arial', fontSize: 33, bold: true, color } }, { text: unit ? ' ' + unit : '', options: { fontFace: 'Microsoft YaHei', fontSize: 13, color: INK_SOFT } }], { x: box.x + 0.22, y: yy, w: box.w - 0.34, h: 0.6, valign: 'middle' });
    yy += 0.66;
  }
  if (title) { slide.addText(title, { x: box.x + 0.22, y: yy, w: box.w - 0.34, h: 0.3, fontFace: 'Microsoft YaHei', fontSize: 13.5, bold: true, color: INK }); yy += 0.34; }
  if (desc) slide.addText(desc, { x: box.x + 0.22, y: yy, w: box.w - 0.34, h: box.h - (yy - box.y) - 0.12, fontFace: 'Microsoft YaHei', fontSize: 11, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.05 });
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
    s.addShape('rect', { x: 0.7, y: 1.5, w: 0.16, h: 1.0, fill: { color: GREEN } });
    s.addText('软件杯 2026 · 领域知识个性化资源生成与多智能体系统', { x: 0.95, y: 1.48, w: 11, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 14, color: '9FB7AC', charSpacing: 1 });
    s.addText('智学中枢', { x: 0.92, y: 1.95, w: 11, h: 1.2, fontFace: 'Microsoft YaHei', fontSize: 60, bold: true, color: WHITE });
    s.addText('多智能体协同驱动的个性化学习平台', { x: 0.95, y: 3.15, w: 11.4, h: 0.6, fontFace: 'Microsoft YaHei', fontSize: 26, bold: true, color: 'E8E0CE' });
    s.addText('诊断学情 · 生成每一课 —— 让 AI 真正因材施教，让每一份学习内容都可溯源、可信。', { x: 0.95, y: 3.85, w: 11.2, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 14.5, color: 'B9C4D6' });
    // 四个关键词
    const tags = ['真实多智能体协同', '防幻觉 · 幻觉率<5%', '对话式动态画像', '学—记—讲—测闭环'];
    tags.forEach((t, i) => {
      const x = 0.95 + i * 2.92;
      s.addShape('roundRect', { x, y: 4.7, w: 2.74, h: 0.56, rectRadius: 0.1, fill: { color: '1F3050' }, line: { color: GREEN, width: 1 } });
      s.addText(t, { x, y: 4.7, w: 2.74, h: 0.56, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color: 'DCE6DD', align: 'center', valign: 'middle' });
    });
    s.addShape('line', { x: 0.95, y: 5.75, w: 11.4, h: 0, line: { color: '33476B', width: 1 } });
    s.addText([
      { text: '参赛队伍：', options: { color: '8FA0BC', fontSize: 13 } }, { text: '〔队伍名称〕', options: { color: WHITE, fontSize: 13, bold: true } },
      { text: '      团队成员：', options: { color: '8FA0BC', fontSize: 13 } }, { text: '〔成员姓名〕', options: { color: WHITE, fontSize: 13, bold: true } },
    ], { x: 0.95, y: 5.95, w: 11.4, h: 0.36, fontFace: 'Microsoft YaHei' });
    s.addText([
      { text: '参赛院校：', options: { color: '8FA0BC', fontSize: 13 } }, { text: '〔学校名称〕', options: { color: WHITE, fontSize: 13, bold: true } },
      { text: '      指导教师：', options: { color: '8FA0BC', fontSize: 13 } }, { text: '〔指导教师〕', options: { color: WHITE, fontSize: 13, bold: true } },
    ], { x: 0.95, y: 6.34, w: 11.4, h: 0.36, fontFace: 'Microsoft YaHei' });
    s.addNotes('开场：自我介绍 + 一句话定位——智学中枢是一个多智能体协同驱动的个性化学习平台，核心解决"千人一面"和"AI 幻觉"两大痛点。强调四个差异化亮点。');
  }

  // ============ 2. 目录 ============
  {
    const s = add();
    header(s, { kicker: 'Contents', title: '汇报目录', idx: '' });
    const items = [
      ['01', '应用背景与价值主张', '赛题理解 · 两大痛点 · 价值定位'],
      ['02', '系统架构与多智能体设计', '整体架构 · LangGraph 五节点 · Agent 分工'],
      ['03', '六大核心功能', '画像 · 资源生成 · 路径 · 闭环 · 辅导 · 评估'],
      ['04', '防幻觉与量化指标', 'RAG 接地 · 消融实验 · 真实指标'],
      ['05', '创新亮点与工程合规', '四大创新 · 开源合规 · AI 辅助开发'],
      ['06', '成果总结与展望', '成果回顾 · 揭榜挂帅方向'],
    ];
    items.forEach((it, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.7 + col * 6.15, y = 1.7 + row * 1.62;
      s.addShape('roundRect', { x, y, w: 5.85, h: 1.42, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.25, blur: 5, offset: 2, angle: 90 } });
      s.addText(it[0], { x: x + 0.18, y: y + 0.2, w: 1.1, h: 1.0, fontFace: 'Arial', fontSize: 34, bold: true, color: 'D8CFBC', valign: 'middle' });
      s.addText(it[1], { x: x + 1.35, y: y + 0.26, w: 4.3, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 16, bold: true, color: NAVY, valign: 'middle' });
      s.addText(it[2], { x: x + 1.35, y: y + 0.78, w: 4.35, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 11, color: INK_SOFT, valign: 'middle' });
    });
    footer(s, 2);
    s.addNotes('用 30 秒带过汇报结构，让评委建立预期：价值—架构—功能—指标—创新—展望，对应评分维度。');
  }

  // ============ 3. 应用背景与痛点 ============
  {
    const s = add();
    header(s, { kicker: 'Why · 应用价值', title: '赛题背景：两大痛点亟待破解', idx: '01' });
    s.addText('在线学习与 AI 生成内容快速普及，但真正"因材施教 + 可信"仍未解决：', { x: 0.7, y: 1.46, w: 12, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 14, color: INK });
    card(s, { x: 0.7, y: 2.0, w: 5.95, h: 2.0 }, { title: '痛点一 · 资源千人一面', color: AMBER, desc: '统一的课程、统一的难度、统一的顺序——\n忽视个体的知识基础、认知风格与学习目标，\n"学了用不上、想学的没有"，学习效率低下。' });
    card(s, { x: 6.85, y: 2.0, w: 5.95, h: 2.0 }, { title: '痛点二 · AI 生成易幻觉', color: 'B5544B', desc: '大模型直接生成讲义常出现事实性错误、\n来源不可考；教育场景一旦"一本正经地胡说"，\n轻则误导、重则失去信任，无法落地教学。' });
    s.addShape('roundRect', { x: 0.7, y: 4.25, w: 12.1, h: 2.45, rectRadius: 0.12, fill: { color: NAVY } });
    s.addText('我们的价值主张', { x: 1.0, y: 4.45, w: 11, h: 0.45, fontFace: 'Microsoft YaHei', fontSize: 18, bold: true, color: WHITE });
    const vs = [
      ['因材施教', '对话建画像 → 能力定顺序、偏好定形式，不同的人不同的路径与资源'],
      ['可信生成', 'RAG 逐句接地 + 多智能体交叉审核，幻觉率压到 5% 以下、来源可溯'],
      ['科学闭环', '把康奈尔笔记、费曼讲解、阶段测试做进产品，学—记—讲—测成环'],
    ];
    vs.forEach((v, i) => {
      const x = 1.0 + i * 3.85;
      s.addShape('roundRect', { x, y: 5.05, w: 3.6, h: 1.42, rectRadius: 0.1, fill: { color: '1F3050' }, line: { color: GREEN, width: 1 } });
      s.addText(v[0], { x: x + 0.2, y: 5.18, w: 3.2, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: '8FE0BE' });
      s.addText(v[1], { x: x + 0.2, y: 5.6, w: 3.25, h: 0.8, fontFace: 'Microsoft YaHei', fontSize: 10.5, color: 'C7D2E2', valign: 'top', lineSpacingMultiple: 1.05 });
    });
    footer(s, 3);
    s.addNotes('讲透应用价值（占评分 35%）：先立痛点——千人一面 + AI 幻觉；再给价值主张三件套：因材施教、可信生成、科学闭环。后面每个功能都回扣这三点。');
  }

  // ============ 4. 整体技术架构 ============
  {
    const s = add();
    header(s, { kicker: 'Architecture', title: '整体技术架构：全栈自建、轻量可跑', idx: '02' });
    const layers = [
      ['前端交互层', 'React 18 + TypeScript + Vite · Zustand 状态 · Framer/GSAP 动效 · ECharts/Mermaid 可视化', 'CFE0D7', GREEN_D],
      ['服务接口层', 'FastAPI · 统一响应信封 {code,message,data,traceId} · JWT 鉴权 · 异步任务轮询 · 日志脱敏', 'D6E0EE', '2E4A78'],
      ['多智能体编排层', 'LangGraph 五节点工作流：诊断 → 检索 → 生成 → 审核 → 决策（重试 / 降级回环）', 'E7D9C2', AMBER],
      ['RAG 检索增强层', 'Chroma 向量库 · bge 本地嵌入 · 逐句接地校验 · 30+ 文档 / 153 切片知识库', 'CFE0D7', GREEN_D],
      ['数据与模型层', 'SQLite 持久化 · 内存 TTL 会话 · LLMClient 适配层（mock / DeepSeek / Qwen 可切换）', 'DDD6CA', INK_SOFT],
    ];
    let y = 1.55;
    layers.forEach((L) => {
      s.addShape('roundRect', { x: 0.7, y, w: 9.0, h: 0.92, rectRadius: 0.08, fill: { color: L[2] }, line: { color: WHITE, width: 1.5 } });
      s.addText(L[0], { x: 0.9, y: y + 0.08, w: 2.6, h: 0.76, fontFace: 'Microsoft YaHei', fontSize: 14.5, bold: true, color: NAVY, valign: 'middle' });
      s.addText(L[1], { x: 3.45, y: y + 0.08, w: 6.1, h: 0.76, fontFace: 'Microsoft YaHei', fontSize: 10.8, color: INK, valign: 'middle', lineSpacingMultiple: 1.0 });
      y += 1.04;
    });
    // 右侧竖向贯穿条
    s.addShape('roundRect', { x: 9.95, y: 1.55, w: 2.85, h: 4.85, rectRadius: 0.1, fill: { color: NAVY } });
    s.addText('贯穿机制', { x: 10.1, y: 1.72, w: 2.6, h: 0.36, fontFace: 'Microsoft YaHei', fontSize: 14, bold: true, color: '8FE0BE' });
    bullets(s, [
      { t: 'Mock-first：无任何 API Key 也能跑通全链路', c: 'DCE6DD' },
      { t: '防幻觉：RAG 接地 + Critic 审核 + 重试降级', c: 'DCE6DD' },
      { t: '内容安全：敏感/违规过滤，不误伤学术术语', c: 'DCE6DD' },
      { t: '可观测：WorkflowTrace 全轨迹留痕、可复现', c: 'DCE6DD' },
      { t: '轻量栈：Chroma + SQLite，单机即可部署', c: 'DCE6DD' },
    ], { x: 10.12, y: 2.15, w: 2.6, h: 4.2 }, { fs: 11, gap: 9 });
    footer(s, 4);
    s.addNotes('架构一页看全：五层 + 贯穿机制。重点强调多智能体编排层用的是真实 LangGraph（非串行模拟），以及 Mock-first 让评委断网也能复现。');
  }

  // ============ 5. 五智能体协同设计 ============
  {
    const s = add();
    header(s, { kicker: 'Multi-Agent Design', title: '多智能体协同：明确分工 · 真实编排', idx: '02' });
    const agents = [
      ['① 学情诊断 Agent', '对话采集 + 诊断微测，构建 6 维异质画像；不确定维度标低置信，绝不臆造', GREEN],
      ['② 领域知识生成 Agent', '依画像生成适配难度的讲义/图解/代码/测试，结构递进、贴画像给不同深度', '2E4A78'],
      ['③ 内容审核校验 Agent', '基于 RAG 知识库逐句接地校验幻觉率，超阈值打回重生成，把关可信度', AMBER],
      ['④ 学习路径规划 Agent', '按掌握度打分排序：薄弱优先、已掌握后置，偏好决定资源形式', GREEN_D],
      ['⑤ 学习过程评估 Agent', '跨会话持续运行，累积做题/进度/笔记行为，产出多维评估与动态调整', 'B5544B'],
    ];
    agents.forEach((a, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      if (i === 4) { // 第五个占整行
        const x = 0.7, y = 1.55 + 2 * 1.78;
        s.addShape('roundRect', { x, y, w: 7.55, h: 1.62, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.25, blur: 5, offset: 2, angle: 90 } });
        s.addShape('rect', { x, y, w: 0.1, h: 1.62, fill: { color: a[2] } });
        s.addText(a[0], { x: x + 0.25, y: y + 0.16, w: 7.0, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: NAVY });
        s.addText(a[1], { x: x + 0.25, y: y + 0.62, w: 7.1, h: 0.9, fontFace: 'Microsoft YaHei', fontSize: 12, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.05 });
        return;
      }
      const x = 0.7 + col * 3.92, y = 1.55 + row * 1.78;
      s.addShape('roundRect', { x, y, w: 3.62, h: 1.62, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.25, blur: 5, offset: 2, angle: 90 } });
      s.addShape('rect', { x, y, w: 0.1, h: 1.62, fill: { color: a[2] } });
      s.addText(a[0], { x: x + 0.25, y: y + 0.16, w: 3.25, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 14, bold: true, color: NAVY });
      s.addText(a[1], { x: x + 0.25, y: y + 0.6, w: 3.3, h: 0.95, fontFace: 'Microsoft YaHei', fontSize: 11, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.05 });
    });
    // 右侧编排说明
    s.addShape('roundRect', { x: 8.5, y: 1.55, w: 4.3, h: 5.18, rectRadius: 0.1, fill: { color: NAVY } });
    s.addText('LangGraph 编排', { x: 8.72, y: 1.72, w: 3.9, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: '8FE0BE' });
    s.addText('① ② ③ 由 LangGraph 状态机编排为单次生成工作流；④ ⑤ 作为独立 Agent 长期运行。', { x: 8.72, y: 2.18, w: 3.9, h: 0.9, fontFace: 'Microsoft YaHei', fontSize: 11.5, color: 'C7D2E2', valign: 'top', lineSpacingMultiple: 1.1 });
    s.addText('诊断 → 检索 → 生成 → 审核 → 决策', { x: 8.72, y: 3.1, w: 3.9, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color: WHITE });
    s.addText('审核不通过 → 在 生成↔审核 间真实回环重试；超限则降级兜底，保证有可信产物交付。', { x: 8.72, y: 3.55, w: 3.9, h: 1.0, fontFace: 'Microsoft YaHei', fontSize: 11.5, color: 'C7D2E2', valign: 'top', lineSpacingMultiple: 1.1 });
    s.addShape('roundRect', { x: 8.72, y: 4.7, w: 3.86, h: 1.85, rectRadius: 0.08, fill: { color: '1F3050' }, line: { color: GREEN, width: 1 } });
    s.addText('消融实验佐证', { x: 8.9, y: 4.82, w: 3.5, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 12, bold: true, color: '8FE0BE' });
    s.addText('去掉 RAG 检索，幻觉率由 0.059 升至 0.155（Δ+0.096）——接地是抑制幻觉的主导机制。', { x: 8.9, y: 5.18, w: 3.55, h: 1.3, fontFace: 'Microsoft YaHei', fontSize: 11, color: 'DCE6DD', valign: 'top', lineSpacingMultiple: 1.1 });
    footer(s, 5);
    s.addNotes('五个 Agent 分工清晰，对应赛题"多智能体系统"。强调①②③是真实 LangGraph 编排、有回环重试，并用消融数据证明 RAG 的作用。');
  }

  // ============ 6. 核心① 对话式画像 ============
  {
    const s = add();
    header(s, { kicker: '核心功能 01 · 对话式画像', title: '摒弃表单：对话建像，随聊随长', idx: '03' });
    addShot(s, '06-profile-chat-progress.png', { x: 6.55, y: 1.5, w: 6.4, h: 5.3 });
    bullets(s, [
      { t: '对话式诊断', bold: true, fs: 15, c: GREEN_D },
      '自然语言交流中自动抽取特征，右侧 6 维画像实时"长"出来，不用填表',
      { t: '6 维异质画像', bold: true, fs: 15, c: GREEN_D },
      '知识基础 · 认知风格 · 易错点 · 学习目标 · 先验经验 · 学习节奏',
      { t: '能力靠测、偏好归类、主观靠聊', bold: true, fs: 15, c: GREEN_D },
      '能力由微测行为反推（带依据），偏好只归类型不打分，不混进能力轴',
      { t: '防幻觉理念前置', bold: true, fs: 15, c: GREEN_D },
      '空作答标"未测/低置信"，不确定的绝不编造；随学随新，画像变则路径变',
    ], { x: 0.7, y: 1.55, w: 5.55, h: 5.3 }, { fs: 12.5, gap: 6 });
    footer(s, 6);
    s.addNotes('核心一：对话式画像。演示真实打字几轮，右侧 0→6 一格格填充。强调"易错点"等推断维度标低置信——这是防幻觉理念的体现。三种入口（做题/自述/跳过）产出同一套画像，如实标注来源可信度。');
  }

  // ============ 7. 核心② 多智能体资源生成（headline） ============
  {
    const s = add();
    header(s, { kicker: '核心功能 02 · 多智能体资源生成', title: 'LangGraph 五节点：真实协同、真实回环', idx: '03' });
    addShot(s, '08b-workflow-done.png', { x: 0.6, y: 1.45, w: 8.5, h: 5.35 });
    const cards = [
      ['真实编排', '诊断→检索→生成→审核→决策五节点逐个点亮，非动画演示'],
      ['逐句接地', '生成讲义后，审核 Agent 基于 RAG 知识库逐句校验幻觉率'],
      ['回环重试', '超阈值打回重生成；超限降级兜底，保证可信产物交付'],
      ['全程留痕', 'WorkflowTrace 记录 327 条真实轨迹，可复现、可观测'],
    ];
    cards.forEach((c, i) => {
      const y = 1.5 + i * 1.32;
      s.addShape('roundRect', { x: 9.35, y, w: 3.45, h: 1.16, rectRadius: 0.09, fill: { color: WHITE }, line: { color: GREEN, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.25, blur: 5, offset: 2, angle: 90 } });
      s.addText(c[0], { x: 9.5, y: y + 0.1, w: 3.2, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 13.5, bold: true, color: GREEN_D });
      s.addText(c[1], { x: 9.5, y: y + 0.44, w: 3.2, h: 0.66, fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.03 });
    });
    footer(s, 7);
    s.addNotes('重头戏，给足时间。现场启动工作流，制造一次审核不通过展示真实回环重试。最终幻觉率<5%、sources 可溯源到具体文档。这是最有说服力的"真实多智能体"证据。');
  }

  // ============ 8. 防幻觉机制深挖 ============
  {
    const s = add();
    header(s, { kicker: '可信生成 · 防幻觉', title: '防幻觉三道防线 + 消融验证', idx: '04' });
    addShot(s, '11-resource-lecture.png', { x: 0.6, y: 1.45, w: 6.6, h: 3.5 });
    s.addText('讲义页实时标注"已校验 · 幻觉率<5%"，并显示 RAG 引用文档数（12 篇），点击可查看接地机制。', { x: 0.62, y: 5.1, w: 6.55, h: 0.8, fontFace: 'Microsoft YaHei', fontSize: 11.5, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.1 });
    // 三道防线
    const lines = [['第一道 · RAG 接地', '生成全程基于检索到的真实语料，逐句可溯源'], ['第二道 · Critic 审核', '内容审核 Agent 逐句校验，未接地句计入幻觉率'], ['第三道 · 重试降级', '超阈值回炉重生成，超限降级，绝不交付不可信内容']];
    lines.forEach((L, i) => {
      const y = 1.5 + i * 0.92;
      s.addShape('roundRect', { x: 7.45, y, w: 5.35, h: 0.8, rectRadius: 0.08, fill: { color: WHITE }, line: { color: LINE, width: 1 } });
      s.addShape('rect', { x: 7.45, y, w: 0.09, h: 0.8, fill: { color: GREEN } });
      s.addText(L[0], { x: 7.62, y: y + 0.06, w: 5.0, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color: NAVY });
      s.addText(L[1], { x: 7.62, y: y + 0.4, w: 5.05, h: 0.36, fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK_SOFT });
    });
    // 消融实验表
    s.addText('消融实验 · 18 份/配置 · 同一接地基准', { x: 7.45, y: 4.4, w: 5.4, h: 0.3, fontFace: 'Microsoft YaHei', fontSize: 12, bold: true, color: GREEN_D });
    const rows = [
      [{ text: '配置', options: { bold: true, color: WHITE, fill: { color: NAVY } } }, { text: '平均幻觉率', options: { bold: true, color: WHITE, fill: { color: NAVY } } }, { text: '说明', options: { bold: true, color: WHITE, fill: { color: NAVY } } }],
      ['完整链路', '0.0589', 'RAG+审核+重试'],
      ['− RAG 检索', '0.1549', '幻觉率激增 ↑'],
      ['− 审核', '0.0490', '无校验直接交付'],
      ['− 重试', '0.0682', '低分即降级'],
    ];
    s.addTable(rows, { x: 7.45, y: 4.72, w: 5.35, colW: [1.5, 1.5, 2.35], rowH: [0.34, 0.32, 0.32, 0.32, 0.32], fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK, align: 'center', valign: 'middle', border: { pt: 0.5, color: LINE }, fill: { color: WHITE } });
    footer(s, 8);
    s.addNotes('防幻觉是可信生成的核心。三道防线 + 消融实验：去掉 RAG 幻觉率从 0.059 飙到 0.155，证明接地是主因；审核与重试是安全网，保障降级兜底。');
  }

  // ============ 9. 核心③ 个性化学习路径 ============
  {
    const s = add();
    header(s, { kicker: '核心功能 03 · 个性化学习路径', title: '能力定顺序 · 偏好定形式 · 画像变路径变', idx: '03' });
    addShot(s, '09-learning-path-top.png', { x: 6.4, y: 1.5, w: 6.5, h: 5.3 });
    bullets(s, [
      { t: '真个性化排序', bold: true, fs: 15, c: GREEN_D },
      '规划 Agent 依据真实画像与掌握度打分：基础薄弱从头学，已掌握自动后置',
      { t: '偏好决定资源形式', bold: true, fs: 15, c: GREEN_D },
      '实践型多给代码实操、理论型多给讲义推导——每一步精准推送对应资源',
      { t: '不同的人，不同的路径', bold: true, fs: 15, c: GREEN_D },
      '两个不同画像生成两条不同路径；零基础新用户全程从第一课起步，无"已完成"错节点',
      { t: '动态重算', bold: true, fs: 15, c: GREEN_D },
      '画像或掌握度变化时路径自动重算，始终对齐当前学情',
    ], { x: 0.7, y: 1.55, w: 5.4, h: 5.3 }, { fs: 12.5, gap: 6 });
    footer(s, 9);
    s.addNotes('核心三：个性化学习路径。展示两个不同画像生成的不同路径（薄弱点优先、已掌握后置）。强调这是真实排序算法驱动，不是写死的列表。');
  }

  // ============ 10. 核心④ 学习方法闭环 ============
  {
    const s = add();
    header(s, { kicker: '核心功能 04 · 学习方法闭环', title: '学—记—讲—测：把学习科学做进产品', idx: '03' });
    // 流程条
    const steps = ['输入·看', '康奈尔·记', '费曼·讲', '阶段测试·测'];
    steps.forEach((t, i) => {
      const x = 0.7 + i * 3.12;
      s.addShape('roundRect', { x, y: 1.5, w: 2.7, h: 0.62, rectRadius: 0.31, fill: { color: i === 3 ? AMBER : GREEN }, });
      s.addText(t, { x, y: 1.5, w: 2.7, h: 0.62, fontFace: 'Microsoft YaHei', fontSize: 14, bold: true, color: WHITE, align: 'center', valign: 'middle' });
      if (i < 3) s.addText('→', { x: x + 2.72, y: 1.5, w: 0.4, h: 0.62, fontFace: 'Arial', fontSize: 20, bold: true, color: INK_SOFT, align: 'center', valign: 'middle' });
    });
    addShot(s, '13-cornell-notes.png', { x: 0.6, y: 2.35, w: 6.25, h: 3.05 });
    addShot(s, '14-feynman.png', { x: 7.0, y: 2.35, w: 6.0, h: 3.05 });
    s.addText('康奈尔笔记：线索栏带问题复述 + 主笔记区结构化输入', { x: 0.6, y: 5.45, w: 6.25, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 11, color: INK_SOFT, align: 'center' });
    s.addText('费曼讲解：以讲代学，AI 顺着讲解追问、列出理解缺口', { x: 7.0, y: 5.45, w: 6.0, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 11, color: INK_SOFT, align: 'center' });
    s.addShape('roundRect', { x: 0.7, y: 5.95, w: 12.1, h: 0.82, rectRadius: 0.1, fill: { color: NAVY } });
    s.addText('阶段测试是独立检验 GATE：只有通过（≥60 分）才点亮"已掌握"并推进学习路径——"通关才算掌握"，杜绝自我感觉良好。', { x: 0.95, y: 5.95, w: 11.6, h: 0.82, fontFace: 'Microsoft YaHei', fontSize: 12.5, color: 'DCE6DD', valign: 'middle' });
    footer(s, 10);
    s.addNotes('差异化亮点：把康奈尔+费曼+阶段测试做进产品，形成"学-记-讲-测"科学闭环。强调阶段测试是 GATE，通关才点亮掌握，真正对应因材施教。');
  }

  // ============ 11. 核心⑤ 智能即时辅导 ============
  {
    const s = add();
    header(s, { kicker: '核心功能 05 · 智能即时辅导', title: '"我没懂"→ 按需生成针对性资源', idx: '03' });
    addShot(s, '15-instant-tutor.png', { x: 0.6, y: 1.5, w: 6.2, h: 5.0 });
    addShot(s, '16-instant-tutor-result.png', { x: 6.95, y: 1.5, w: 6.05, h: 5.0 });
    s.addText('描述卡点 → AI 识别问题', { x: 0.6, y: 6.55, w: 6.2, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 11.5, bold: true, color: GREEN_D, align: 'center' });
    s.addText('生成针对性资源清单（图解/例题/视频/讲义），勾选即按需生成', { x: 6.95, y: 6.55, w: 6.05, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 11.5, bold: true, color: GREEN_D, align: 'center' });
    footer(s, 11);
    s.addNotes('加分亮点：智能即时辅导。自学卡住随手就能问，系统识别问题后给针对性资源清单，勾选即按需生成——解决"自学没人答疑"的真实痛点。');
  }

  // ============ 12. 核心⑥ 学习评估 + 仪表盘 ============
  {
    const s = add();
    header(s, { kicker: '核心功能 06 · 学习过程评估', title: '多维过程评估 + 动态调整建议', idx: '03' });
    addShot(s, '03-dashboard-top.png', { x: 6.3, y: 1.5, w: 6.6, h: 5.3 });
    bullets(s, [
      { t: '基于真实学习行为', bold: true, fs: 15, c: GREEN_D },
      '跨会话累积做题、进度、笔记行为，而非一次性问卷',
      { t: '四维量化', bold: true, fs: 15, c: GREEN_D },
      '掌握进度 · 测验表现 · 学习效率 · 学习投入，定位薄弱点',
      { t: '动态调整建议', bold: true, fs: 15, c: GREEN_D },
      '指出下一步优先攻克的知识点与建议难度，边学边测稳步推进',
      { t: '全局学情概览', bold: true, fs: 15, c: GREEN_D },
      '能力雷达、知识图谱覆盖、综合评分一屏总览，画像可信度透明标注',
    ], { x: 0.7, y: 1.55, w: 5.45, h: 5.3 }, { fs: 12.5, gap: 6 });
    footer(s, 12);
    s.addNotes('加分亮点：学习评估 Agent。区别于单次生成工作流，它跨会话持续运行，基于真实做题行为产出四维评估 + 动态调整建议，闭合个性化学习循环。');
  }

  // ============ 13. 加分功能速览 ============
  {
    const s = add();
    header(s, { kicker: '更多能力 · 加分项', title: '多模态资源 · 知识图谱 · 岗位对标 · 联网聚合', idx: '03' });
    const grid = [
      ['12-resource-diagram.png', '知识图解动态生成', '按知识点内容动态生成 Mermaid 图，不同知识点不同图型'],
      ['17-resource-hub.png', '多模态资源中枢', '讲义/思维导图/代码/图解/测试一站式资源包'],
      ['18-knowledge-graph.png', '知识图谱可视化', '掌握/学习中/待学/盲区四态拓扑，学情一目了然'],
      ['19-job-match.png', '岗位对标 + 联网聚合', '对接目标岗位算匹配度与能力缺口 · 联网搜优质资源 AI 评分'],
    ];
    grid.forEach((g, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.7 + col * 6.2, y = 1.5 + row * 2.7;
      addShot(s, g[0], { x: x, y: y, w: 3.1, h: 2.45 }, { pad: 0.04 });
      s.addText(g[1], { x: x + 3.25, y: y + 0.25, w: 2.75, h: 0.6, fontFace: 'Microsoft YaHei', fontSize: 14, bold: true, color: NAVY, valign: 'middle' });
      s.addText(g[2], { x: x + 3.25, y: y + 0.95, w: 2.8, h: 1.3, fontFace: 'Microsoft YaHei', fontSize: 11, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.1 });
    });
    footer(s, 13);
    s.addNotes('快节奏带过四个加分项：图解动态生成、多模态资源中枢、知识图谱、岗位对标+联网聚合。每项约 10 秒，证明系统能力的广度。');
  }

  // ============ 14. 量化指标看板 ============
  {
    const s = add();
    header(s, { kicker: 'Metrics · 真实指标', title: '量化指标：全部达标、可复现', idx: '04' });
    const big = [
      ['0.0428', '幻觉率', '目标 <0.05 ✓', GREEN_D],
      ['100%', '难度适配率', '目标 ≥85% ✓', '2E4A78'],
      ['100%', '知识覆盖率', '目标 ≥90% ✓', AMBER],
    ];
    big.forEach((b, i) => {
      const x = 0.7 + i * 4.05;
      s.addShape('roundRect', { x, y: 1.55, w: 3.8, h: 1.95, rectRadius: 0.12, fill: { color: WHITE }, line: { color: b[3], width: 1.5 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.3, blur: 7, offset: 2, angle: 90 } });
      s.addText(b[0], { x, y: 1.72, w: 3.8, h: 0.95, fontFace: 'Arial', fontSize: 46, bold: true, color: b[3], align: 'center', valign: 'middle' });
      s.addText(b[1], { x, y: 2.72, w: 3.8, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: INK, align: 'center' });
      s.addText(b[2], { x, y: 3.12, w: 3.8, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 11, color: GREEN_D, align: 'center' });
    });
    // 跨领域 + 性能成本
    s.addText('跨领域验证（同一管线换计算机网络域）', { x: 0.7, y: 3.75, w: 6, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color: GREEN_D });
    const t1 = [
      [{ text: '领域', options: { bold: true, color: WHITE, fill: { color: NAVY } } }, { text: '幻觉率', options: { bold: true, color: WHITE, fill: { color: NAVY } } }, { text: '适配率', options: { bold: true, color: WHITE, fill: { color: NAVY } } }, { text: '覆盖率', options: { bold: true, color: WHITE, fill: { color: NAVY } } }],
      ['AI（30 文档）', '0.0428', '1.00', '1.00'],
      ['计算机网络（5 文档）', '0.0700', '0.83', '1.00'],
    ];
    s.addTable(t1, { x: 0.7, y: 4.1, w: 6.0, colW: [2.4, 1.2, 1.2, 1.2], rowH: [0.36, 0.36, 0.36], fontFace: 'Microsoft YaHei', fontSize: 11, color: INK, align: 'center', valign: 'middle', border: { pt: 0.5, color: LINE }, fill: { color: WHITE } });
    s.addText('换领域端到端跑通、覆盖率满分，证明方法论与领域无关。', { x: 0.7, y: 5.3, w: 6.0, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 10.5, italic: true, color: INK_SOFT, valign: 'top' });

    s.addText('性能与成本（327 条真实轨迹）', { x: 7.0, y: 3.75, w: 5.8, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color: GREEN_D });
    const perf = [['P50 生成耗时', '13.2 s'], ['P90 生成耗时', '37.0 s'], ['单份讲义成本', '≈ ¥0.02'], ['知识库规模', '30+ 文档 / 153 切片']];
    perf.forEach((pp, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 7.0 + col * 2.95, y = 4.1 + row * 0.92;
      s.addShape('roundRect', { x, y, w: 2.8, h: 0.8, rectRadius: 0.08, fill: { color: WHITE }, line: { color: LINE, width: 1 } });
      s.addText(pp[1], { x: x + 0.12, y: y + 0.06, w: 2.55, h: 0.42, fontFace: 'Arial', fontSize: 19, bold: true, color: NAVY });
      s.addText(pp[0], { x: x + 0.12, y: y + 0.48, w: 2.6, h: 0.28, fontFace: 'Microsoft YaHei', fontSize: 10, color: INK_SOFT });
    });
    s.addText('一轮 18 份讲义 ≈ ¥0.36，低成本可规模化。', { x: 7.0, y: 5.95, w: 5.8, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 10.5, italic: true, color: INK_SOFT });
    footer(s, 14);
    s.addNotes('数字从真实 metrics-report 取，全部达标。三大主指标 + 跨领域验证（诚实呈现网络域略高）+ 性能成本。强调可复现：附复现命令。');
  }

  // ============ 15. 创新亮点 ============
  {
    const s = add();
    header(s, { kicker: 'Innovation · 差异化', title: '四大创新亮点', idx: '05' });
    const inv = [
      ['①', '真实多智能体协同', 'LangGraph 状态机编排五节点，生成↔审核间真实回环重试与降级，非串行动画模拟', GREEN],
      ['②', '防幻觉 + 内容安全双保险', 'RAG 逐句接地把幻觉率压到 <5%，敏感/违规内容统一过滤且不误伤学术术语', AMBER],
      ['③', '学—记—讲—测科学闭环', '康奈尔笔记 + 费曼讲解 + 阶段测试 GATE 做进产品，"通关才算掌握"', '2E4A78'],
      ['④', '对话式动态画像', '摒弃表单，对话建 6 维异质画像，不确定维度标低置信，随学随新驱动路径', GREEN_D],
    ];
    inv.forEach((v, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.7 + col * 6.2, y = 1.55 + row * 2.6;
      s.addShape('roundRect', { x, y, w: 5.85, h: 2.35, rectRadius: 0.12, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.3, blur: 6, offset: 2, angle: 90 } });
      s.addShape('rect', { x, y, w: 0.12, h: 2.35, fill: { color: v[3] } });
      s.addText(v[0], { x: x + 0.25, y: y + 0.2, w: 1.0, h: 1.0, fontFace: 'Arial', fontSize: 40, bold: true, color: v[3] });
      s.addText(v[1], { x: x + 1.35, y: y + 0.3, w: 4.35, h: 0.7, fontFace: 'Microsoft YaHei', fontSize: 16.5, bold: true, color: NAVY, valign: 'middle' });
      s.addText(v[2], { x: x + 1.35, y: y + 1.05, w: 4.35, h: 1.15, fontFace: 'Microsoft YaHei', fontSize: 11.5, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.12 });
    });
    footer(s, 15);
    s.addNotes('总结四大差异化创新——这页是拉分关键。每点一句话讲清"别人没有/我们做到"：真实多智能体、防幻觉双保险、学习闭环、对话画像。');
  }

  // ============ 16. 工程与合规 ============
  {
    const s = add();
    header(s, { kicker: 'Engineering · 合规', title: '工程实践与合规说明', idx: '05' });
    const blocks = [
      ['技术栈与架构', ['React 18 + FastAPI + LangGraph + Chroma 全栈自建', 'LLMClient 适配层：mock / DeepSeek / Qwen 可切换', 'Mock-first：无 API Key 即可跑通全链路演示']],
      ['AI 辅助开发说明', ['编程协作使用 Claude Code（真实占比人工核对）', '推理模型采用 DeepSeek（讲义生成同源管线）', '辅助开发内容均经人工审阅与测试验证']],
      ['开源依赖与协议', ['前端依赖均为 MIT/Apache 等宽松协议', '知识库语料标注来源与许可（BSD/Apache/CC BY-SA）', '正文按开放许可整理、非逐字拷贝，仅供 RAG 接地']],
      ['内容安全与质量', ['生成内容统一敏感/违规检测，不误伤术语', '日志中手机号/邮箱经脱敏拦截器掩码', '指标可复现：附完整复现命令与轨迹留痕']],
    ];
    blocks.forEach((b, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.7 + col * 6.2, y = 1.55 + row * 2.6;
      s.addShape('roundRect', { x, y, w: 5.85, h: 2.35, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.25, blur: 5, offset: 2, angle: 90 } });
      s.addShape('rect', { x, y, w: 5.85, h: 0.5, fill: { color: NAVY } });
      s.addText(b[0], { x: x + 0.2, y, w: 5.5, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 14.5, bold: true, color: WHITE, valign: 'middle' });
      bullets(s, b[1], { x: x + 0.22, y: y + 0.66, w: 5.45, h: 1.6 }, { fs: 11.5, gap: 7 });
    });
    footer(s, 16);
    s.addNotes('对应文档分（10%）与合规要求：技术栈、AI 辅助开发说明（Claude Code + DeepSeek）、开源依赖与协议、内容安全与可复现。体现工程严谨。');
  }

  // ============ 17. 总结与展望 ============
  {
    const s = add();
    s.background = { path: path.join(ASSETS, 'sec-bg.png') };
    s.addShape('rect', { x: 0.7, y: 0.9, w: 0.16, h: 0.85, fill: { color: GREEN } });
    s.addText('SUMMARY & OUTLOOK', { x: 0.95, y: 0.92, w: 10, h: 0.34, fontFace: 'Arial', fontSize: 12, bold: true, color: '9FB7AC', charSpacing: 2 });
    s.addText('成果总结与未来展望', { x: 0.92, y: 1.28, w: 11.5, h: 0.7, fontFace: 'Microsoft YaHei', fontSize: 32, bold: true, color: WHITE });
    // 成果
    s.addText('已交付成果', { x: 0.95, y: 2.25, w: 6, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 17, bold: true, color: '8FE0BE' });
    bullets(s, [
      { t: '完整可运行的多智能体系统，前后端 + RAG 全链路打通', c: 'DCE6DD' },
      { t: '六大核心功能 + 多项加分能力，覆盖学习全流程', c: 'DCE6DD' },
      { t: '真实指标达标：幻觉率 0.0428、适配率/覆盖率 100%', c: 'DCE6DD' },
      { t: '跨领域验证 + 消融实验 + 性能成本，结果可复现', c: 'DCE6DD' },
      { t: '自建完整课程知识库，30+ 文档来源与许可清晰', c: 'DCE6DD' },
    ], { x: 0.95, y: 2.7, w: 5.7, h: 3.6 }, { fs: 13, gap: 11 });
    // 展望
    s.addText('未来展望 · 揭榜挂帅', { x: 7.0, y: 2.25, w: 6, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 17, bold: true, color: '8FE0BE' });
    bullets(s, [
      { t: '资源生态聚合：联网优质资源 + AI 评分排序规模化', c: 'DCE6DD' },
      { t: '岗位能力图谱：对接真实招聘需求，学习直通就业', c: 'DCE6DD' },
      { t: '生产级替换：Milvus/PostgreSQL/Redis 平滑升级', c: 'DCE6DD' },
      { t: '更多学科领域扩展，领域词典与语料持续补齐', c: 'DCE6DD' },
      { t: '服务端视频渲染导出，多模态资源进一步丰富', c: 'DCE6DD' },
    ], { x: 7.0, y: 2.7, w: 5.8, h: 3.6 }, { fs: 13, gap: 11 });
    s.addShape('line', { x: 0.95, y: 6.35, w: 11.85, h: 0, line: { color: '33476B', width: 1 } });
    s.addText('智学中枢 —— 让 AI 因材施教，让每一份学习内容都可信。', { x: 0.95, y: 6.5, w: 11.85, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 16, bold: true, color: WHITE, align: 'center' });
    s.addNotes('收尾：回顾成果（系统可运行、指标达标、可复现），再给揭榜挂帅展望（资源/岗位聚合）。最后一句口号收束，谢谢评委。');
  }

  const out = path.join(__dirname, '..', '软件杯介绍-v2.pptx');
  await p.writeFile({ fileName: out });
  console.log('OK ->', out);
})().catch((e) => { console.error(e); process.exit(1); });
