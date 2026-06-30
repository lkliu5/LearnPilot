/* 智学中枢 · 软件杯参赛汇报 PPT v4 — 贴合官方赛题点与考核点：核心功能(是什么·如何完成)/防幻觉·内容安全/加分项/创新点/合规 */
const pptxgen = require('pptxgenjs');
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const SHOTS = path.join(__dirname, '..', 'ppt-assets', 'shots');
const ASSETS = path.join(__dirname, 'assets');
if (!fs.existsSync(ASSETS)) fs.mkdirSync(ASSETS, { recursive: true });

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
}

function footer(slide, n) {
  slide.addShape('line', { x: 0.55, y: 7.06, w: 12.23, h: 0, line: { color: LINE, width: 1 } });
  slide.addText('智学中枢 · 领域知识个性化资源生成和多智能体系统开发', { x: 0.55, y: 7.08, w: 8, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 9, color: INK_SOFT, valign: 'middle' });
  slide.addText('中国软件杯 2026 · A 赛题', { x: 8.8, y: 7.08, w: 2.8, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 9, color: INK_SOFT, align: 'right', valign: 'middle' });
  slide.addText(String(n).padStart(2, '0'), { x: 11.75, y: 7.08, w: 1.03, h: 0.32, fontFace: 'Arial', fontSize: 10, bold: true, color: GREEN_D, align: 'right', valign: 'middle' });
}

function header(slide, { kicker, title, idx }) {
  slide.background = { color: PAPER };
  slide.addShape('rect', { x: 0, y: 0, w: W, h: 1.18, fill: { color: NAVY } });
  slide.addShape('rect', { x: 0, y: 1.18, w: W, h: 0.06, fill: { color: GREEN } });
  slide.addShape('rect', { x: 0.55, y: 0.30, w: 0.12, h: 0.6, fill: { color: GREEN } });
  slide.addText((kicker || '').toUpperCase(), { x: 0.82, y: 0.26, w: 9.5, h: 0.26, fontFace: 'Arial', fontSize: 10.5, bold: true, color: '9FB7AC', charSpacing: 2 });
  slide.addText(title, { x: 0.8, y: 0.5, w: 10.4, h: 0.6, fontFace: 'Microsoft YaHei', fontSize: 23, bold: true, color: WHITE, valign: 'middle' });
  if (idx) slide.addText(idx, { x: 11.2, y: 0.18, w: 1.58, h: 0.82, fontFace: 'Arial', fontSize: 36, bold: true, color: '32507A', align: 'right', valign: 'middle' });
}

// 赛题要求标签条（贴合考核点）
function reqTag(slide, x, y, w, text) {
  slide.addShape('roundRect', { x, y, w, h: 0.5, rectRadius: 0.08, fill: { color: '2A1E12' }, line: { color: AMBER, width: 1 } });
  slide.addText([{ text: '赛题要求  ', options: { bold: true, color: 'E2B66B', fontSize: 11 } }, { text, options: { color: 'F0E6D4', fontSize: 11 } }],
    { x: x + 0.18, y, w: w - 0.36, h: 0.5, fontFace: 'Microsoft YaHei', valign: 'middle' });
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

// "如何完成" 小节块
function howBox(slide, box, title, items, color = GREEN_D) {
  slide.addShape('roundRect', { x: box.x, y: box.y, w: box.w, h: box.h, rectRadius: 0.1, fill: { color: 'F1ECE0' }, line: { color, width: 1 } });
  slide.addText('如何完成 · ' + title, { x: box.x + 0.18, y: box.y + 0.12, w: box.w - 0.36, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color });
  bullets(slide, items, { x: box.x + 0.2, y: box.y + 0.5, w: box.w - 0.4, h: box.h - 0.62 }, { fs: 11.5, gap: 6 });
}

(async () => {
  await makeGradient('cover-bg.png', NAVY, '0E1830');
  await makeGradient('sec-bg.png', '1B2A47', '111B30');

  const p = new pptxgen();
  p.defineLayout({ name: 'W', width: W, height: H });
  p.layout = 'W';
  p.author = '智学中枢团队';
  p.title = '智学中枢 · 软件杯参赛汇报（考核点对齐版）';
  const add = () => p.addSlide();
  const TH = (t) => ({ text: t, options: { bold: true, color: WHITE, fill: { color: NAVY }, fontSize: 11.5, align: 'center', valign: 'middle' } });

  // ============ 1. 封面 ============
  {
    const s = add();
    s.background = { path: path.join(ASSETS, 'cover-bg.png') };
    s.addShape('rect', { x: 0.7, y: 1.35, w: 0.16, h: 1.0, fill: { color: GREEN } });
    s.addText('中国软件杯 2026 · A 赛题：领域知识个性化资源生成和多智能体系统开发', { x: 0.95, y: 1.33, w: 11.5, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 13.5, color: '9FB7AC', charSpacing: 1 });
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
    s.addNotes('开场：报项目名 + 赛题 + 组别 + 答辩人。一句话定位——面向 A 赛题"领域知识个性化资源生成和多智能体系统"，核心解决千人一面与 AI 幻觉两大痛点。');
  }

  // ============ 2. 赛题理解与考核点映射（关键页） ============
  {
    const s = add();
    header(s, { kicker: 'Rubric Mapping · 考核点对齐', title: '赛题考核点 → 我们的实现（逐条对齐）', idx: '00' });
    const rows = [
      [TH('赛题考核点'), TH('官方要求'), TH('我们的实现'), TH('状态')],
      ['① 对话式学习画像', '摒弃表单·自然语言·≥6 异质维度·随学随新', '三入口对话诊断 · 6 异质维度 · 低置信标注 · 随学更新', '✅'],
      ['② 多智能体资源生成', '多 Agent 协作 · 至少 5 种资源', 'LangGraph 诊断/生成/审核 · 8 类多模态资源', '✅'],
      ['③ 个性化路径规划', '动态规划步骤 · 基于画像精准推送', 'planner 打分排序 · 偏好定形 · 画像变路径变', '✅'],
      ['④ 防幻觉机制（核心）', 'RAG + 多 Agent 校验 · 可溯源', '逐句接地 + Critic + 重试降级 · 白盒徽章 · 4.28%', '✅'],
      ['⑤ 内容安全过滤', '无敏感/违规信息', '统一输出过滤层 · 命中拦截脱敏 · 不误伤术语', '✅'],
      ['⑥ 三大量化指标', '幻觉<5% / 适配≥85% / 覆盖≥90%', '4.28% / 100% / 100%（30+ 文档实测）', '✅'],
      ['⑦ 智能辅导 + 评估（加分）', '即时答疑 · 多维评估动态调整', '即时辅导按需生成 · 四维评估 + 动态建议', '✅'],
      ['⑧ 多智能体框架 + 合规', '明确框架 · 开源协议 · AI 工具说明', 'LangGraph 状态机 · 协议标注 · Claude Code+DeepSeek', '✅'],
    ];
    s.addTable(rows, { x: 0.6, y: 1.42, w: 12.2, colW: [2.55, 3.5, 5.0, 1.15], rowH: 0.6, fontFace: 'Microsoft YaHei', fontSize: 10.3, color: INK, valign: 'middle', align: 'left', border: { pt: 0.5, color: LINE }, fill: { color: WHITE } });
    s.addText('评分维度参照：应用价值 35% · 功能实现与技术 45% · 文档 10% · 视频/PPT 10% —— 本汇报逐条覆盖。', { x: 0.6, y: 6.78, w: 12.2, h: 0.28, fontFace: 'Microsoft YaHei', fontSize: 10, italic: true, color: INK_SOFT, align: 'center' });
    footer(s, 2);
    s.addNotes('关键页：先让评委看到我们对赛题考核点的逐条覆盖。八大考核点 + 三大指标全部达成。后续每页深入"是什么·如何完成"。这页直接对应"贴合官方赛题点与考核点"。');
  }

  // ============ 3. 应用价值与痛点 ============
  {
    const s = add();
    header(s, { kicker: 'Value · 应用价值（35%）', title: '应用背景：从痛点到解决方案', idx: '01' });
    const steps = [['痛点', '资源千人一面\nAI 生成易幻觉', AMBER], ['现有方案不足', '统一难度顺序\n生成不可溯源', 'B5544B'], ['我们的解决方案', '多智能体 + RAG\n因材施教·可信生成', GREEN]];
    steps.forEach((st, i) => {
      const x = 0.7 + i * 4.3;
      s.addShape('roundRect', { x, y: 1.5, w: 3.85, h: 1.5, rectRadius: 0.12, fill: { color: i === 2 ? NAVY : WHITE }, line: { color: st[2], width: 1.5 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.3, blur: 6, offset: 2, angle: 90 } });
      s.addText(st[0], { x: x + 0.2, y: 1.62, w: 3.5, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: i === 2 ? '8FE0BE' : st[2] });
      s.addText(st[1], { x: x + 0.2, y: 2.04, w: 3.5, h: 0.85, fontFace: 'Microsoft YaHei', fontSize: 12.5, color: i === 2 ? 'DCE6DD' : INK, valign: 'top', lineSpacingMultiple: 1.05 });
      if (i < 2) s.addText('→', { x: x + 3.88, y: 1.5, w: 0.42, h: 1.5, fontFace: 'Arial', fontSize: 26, bold: true, color: INK_SOFT, align: 'center', valign: 'middle' });
    });
    card(s, { x: 0.7, y: 3.3, w: 5.95, h: 1.65 }, { title: '痛点一 · 资源千人一面', color: AMBER, desc: '统一课程、统一难度、统一顺序，忽视个体的知识基础、认知风格与学习目标——"学了用不上、想学的没有"，效率低下。' });
    card(s, { x: 6.85, y: 3.3, w: 5.95, h: 1.65 }, { title: '痛点二 · AI 生成易幻觉', color: 'B5544B', desc: '大模型直接生成讲义常含事实错误、来源不可考；教育场景一旦"一本正经地胡说"，轻则误导、重则失信，无法落地教学。' });
    s.addShape('roundRect', { x: 0.7, y: 5.15, w: 12.1, h: 1.55, rectRadius: 0.12, fill: { color: NAVY } });
    const vs = [['因材施教', '对话建画像 → 能力定顺序、偏好定形式，不同的人不同路径'], ['可信生成', 'RAG 逐句接地 + 多智能体审核，幻觉率<5%、来源可溯'], ['科学闭环', '康奈尔+费曼+阶段测试做进产品，学—记—讲—测成环']];
    vs.forEach((v, i) => {
      const x = 1.0 + i * 3.85;
      s.addText(v[0], { x, y: 5.3, w: 3.6, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: '8FE0BE' });
      s.addText(v[1], { x, y: 5.72, w: 3.65, h: 0.9, fontFace: 'Microsoft YaHei', fontSize: 11, color: 'C7D2E2', valign: 'top', lineSpacingMultiple: 1.05 });
    });
    footer(s, 3);
    s.addNotes('应用价值 35%：核心公式 痛点→现有方案不足→解决方案。两大痛点 + 价值主张三件套（因材施教/可信生成/科学闭环）。');
  }

  // ============ 4. 总体架构 + 多智能体框架 ============
  {
    const s = add();
    header(s, { kicker: 'Architecture · 多智能体框架', title: '总体架构：明确的多智能体协同框架', idx: '02' });
    reqTag(s, 0.7, 1.42, 12.1, '须明确采用的"多智能体协同框架" —— 本作品采用 LangGraph 状态机编排，诊断/生成/审核三 Agent 协同。');
    const layers = [
      ['前端交互层', 'React 18 + TS + Vite · Zustand · Framer/GSAP · ECharts/Mermaid', 'CFE0D7'],
      ['服务接口层', 'FastAPI · 统一信封 {code,message,data,traceId} · JWT · 异步任务 · 脱敏', 'D6E0EE'],
      ['多智能体编排层', 'LangGraph 五节点：诊断 → 检索 → 生成 → 审核 → 决策（重试/降级回环）', 'E7D9C2'],
      ['RAG 检索增强层', 'Chroma 向量库 · bge 本地嵌入 · Top-3 接地 · 30+ 文档/153 切片', 'CFE0D7'],
      ['数据与模型层', 'SQLite · 内存 TTL 会话 · LLMClient 适配（mock/DeepSeek/Qwen 可切）', 'DDD6CA'],
    ];
    let y = 2.1;
    layers.forEach((L) => {
      s.addShape('roundRect', { x: 0.7, y, w: 9.0, h: 0.82, rectRadius: 0.08, fill: { color: L[2] }, line: { color: WHITE, width: 1.5 } });
      s.addText(L[0], { x: 0.9, y: y + 0.04, w: 2.6, h: 0.74, fontFace: 'Microsoft YaHei', fontSize: 13.5, bold: true, color: NAVY, valign: 'middle' });
      s.addText(L[1], { x: 3.45, y: y + 0.04, w: 6.1, h: 0.74, fontFace: 'Microsoft YaHei', fontSize: 10, color: INK, valign: 'middle' });
      y += 0.94;
    });
    s.addShape('roundRect', { x: 9.95, y: 2.1, w: 2.85, h: 4.16, rectRadius: 0.1, fill: { color: NAVY } });
    s.addText('技术选型亮点', { x: 10.1, y: 2.24, w: 2.6, h: 0.36, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color: '8FE0BE' });
    bullets(s, [
      { t: '真实 LangGraph 编排（非串行模拟）', c: 'DCE6DD' },
      { t: 'RAG 接地抑制幻觉', c: 'DCE6DD' },
      { t: 'Mock-first：无 Key 跑全链路', c: 'DCE6DD' },
      { t: '轻量栈 Chroma+SQLite 单机部署', c: 'DCE6DD' },
      { t: '模型可切换·适配层解耦', c: 'DCE6DD' },
      { t: 'WorkflowTrace 全轨迹可观测', c: 'DCE6DD' },
    ], { x: 10.12, y: 2.66, w: 2.6, h: 3.5 }, { fs: 10.5, gap: 8 });
    s.addText('生产替换路径（README）：Chroma→Milvus · SQLite→PostgreSQL · 内存会话→Redis，业务代码零改动。', { x: 0.7, y: 6.4, w: 12.1, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 11, italic: true, color: INK_SOFT, valign: 'top' });
    footer(s, 4);
    s.addNotes('技术架构与多智能体框架（赛题硬要求"须明确框架"）：五层 + LangGraph 编排。强调真实编排、Mock-first 可复现、轻量可跑。');
  }

  // ============ 5. 核心功能① 对话式学习画像 ============
  {
    const s = add();
    header(s, { kicker: '核心功能 01 · 对话式画像', title: '对话式学习画像：摒弃表单、随聊随长', idx: '03' });
    reqTag(s, 0.7, 1.42, 12.1, '摒弃传统繁琐表单，通过自然语言对话自动抽取特征，构建不少于 6 个异质维度的画像，随学随新。');
    addShot(s, '06-profile-chat-progress.png', { x: 6.85, y: 2.1, w: 5.95, h: 3.4 });
    s.addText('是什么', { x: 0.7, y: 2.05, w: 5.9, h: 0.3, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color: GREEN_D });
    bullets(s, [
      '对话式诊断：自然语言交流自动抽取特征，右侧 6 维画像随聊实时生长',
      '6 维异质画像：知识基础 · 认知风格 · 易错点 · 学习目标 · 先验经验 · 学习节奏',
      '三种入口：做题式(实测高置信) / 一段话自述(中置信) / 跳过(零基础)，产出同一套画像',
    ], { x: 0.72, y: 2.4, w: 5.95, h: 1.7 }, { fs: 11.5, gap: 6 });
    howBox(s, { x: 0.7, y: 4.2, w: 5.95, h: 2.35 }, '技术实现', [
      '能力靠测：诊断微测按答题行为反推，带依据、不靠自陈',
      '偏好归类：认知风格/节奏只归类型、不打分，不混进能力轴',
      '防幻觉前置：空作答标"未测/低置信"，不确定绝不编造',
      '随学随新：错题/进度回流自动更新画像，驱动路径重算',
    ]);
    s.addText('▲ 右图：对话进行中，右侧 6 维画像逐格点亮、可信度透明标注', { x: 6.85, y: 5.6, w: 5.95, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 10.5, italic: true, color: INK_SOFT, align: 'center', valign: 'top' });
    footer(s, 5);
    s.addNotes('核心功能①——直接回应赛题"对话式自主构建·摒弃表单·6 异质维度"。强调三入口、能力靠测偏好归类、低置信不编造。这是从早期表单方案重构后的成果。');
  }

  // ============ 6. 核心功能② 多智能体资源生成 ============
  {
    const s = add();
    header(s, { kicker: '核心功能 02 · 多智能体生成', title: '多智能体协同资源生成（重头戏）', idx: '03' });
    reqTag(s, 0.7, 1.42, 12.1, '体现多智能体架构，由不同角色智能体协作完成、生成至少 5 种学习资源类型。');
    addShot(s, '08b-workflow-done.png', { x: 0.6, y: 2.05, w: 7.7, h: 4.5 });
    s.addText('是什么 + 如何完成', { x: 8.5, y: 2.0, w: 4.3, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color: GREEN_D });
    const cards = [
      ['真实编排', '诊断→检索→生成→审核→决策五节点逐个点亮，LangGraph 状态机驱动'],
      ['角色协作', '诊断 Agent 定学情 · 生成 Agent 产资源 · 审核 Agent 校幻觉'],
      ['回环重试', '审核不通过 → 生成↔审核 真实回环；超限降级兜底'],
      ['8 类资源', '讲义/思维导图/图解/代码/视频/测试/外链/导学，远超"≥5 种"'],
    ];
    cards.forEach((c, i) => {
      const y = 2.36 + i * 1.06;
      s.addShape('roundRect', { x: 8.5, y, w: 4.3, h: 0.94, rectRadius: 0.09, fill: { color: WHITE }, line: { color: GREEN, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.25, blur: 5, offset: 2, angle: 90 } });
      s.addText(c[0], { x: 8.66, y: y + 0.08, w: 4.0, h: 0.3, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color: GREEN_D });
      s.addText(c[1], { x: 8.66, y: y + 0.38, w: 4.0, h: 0.52, fontFace: 'Microsoft YaHei', fontSize: 10.3, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.03 });
    });
    s.addText('▲ 工作流大屏：五节点全部点亮 + 智能体状态 + 真实消息日志（327 条轨迹留痕，可复现）', { x: 0.6, y: 6.62, w: 7.7, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 10, italic: true, color: INK_SOFT, align: 'center' });
    footer(s, 6);
    s.addNotes('核心功能②重头戏：真实多智能体协同。现场启动工作流、制造审核不通过展示回环重试。8 类资源远超"≥5种"要求。');
  }

  // ============ 7. 核心功能③ 个性化路径规划 ============
  {
    const s = add();
    header(s, { kicker: '核心功能 03 · 路径规划', title: '个性化学习路径：能力定序、偏好定形', idx: '03' });
    reqTag(s, 0.7, 1.42, 12.1, '动态规划学习路径、明确步骤顺序，并基于画像向学习者精准推送资源。');
    addShot(s, '09-learning-path-top.png', { x: 6.95, y: 2.1, w: 5.85, h: 3.35 });
    s.addText('是什么', { x: 0.7, y: 2.05, w: 6, h: 0.3, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color: GREEN_D });
    bullets(s, [
      '动态规划：依画像与掌握度排序——薄弱优先、已掌握后置',
      '精准推送：偏好决定资源形式（实践型给代码、理论型给推导）',
      '不同的人不同的路径；画像或掌握度变化时自动重算',
    ], { x: 0.72, y: 2.4, w: 6.0, h: 1.5 }, { fs: 11.5, gap: 6 });
    s.addShape('roundRect', { x: 0.7, y: 4.0, w: 6.05, h: 2.5, rectRadius: 0.1, fill: { color: 'F1ECE0' }, line: { color: '2E4A78', width: 1 } });
    s.addText('如何完成 · 路径优先级打分（planner_agent 真实代码）', { x: 0.88, y: 4.12, w: 5.7, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 12, bold: true, color: '2E4A78' });
    s.addText([
      'score(kp) = lesson_seq            # 先修骨架',
      '  + 100            若 已达标/已掌握  # 大幅后置',
      '  + 0.8·(能力分/100) 若 薄弱        # 越低越前',
      '  ± 0.4            基础课×画像基础联动',
      '  − 0.8·(岗位需求/100)  目标岗位高需求前置',
    ].map((l) => ({ text: l, options: { breakLine: true, fontSize: 11, color: INK, paraSpaceAfter: 5 } })), { x: 0.9, y: 4.5, w: 5.7, h: 1.95, fontFace: 'Consolas', valign: 'top' });
    s.addText('▲ 升序排列、分越小越先学；确定性计算、无随机、可复现', { x: 6.95, y: 5.55, w: 5.85, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 10.5, italic: true, color: INK_SOFT, align: 'center', valign: 'top' });
    footer(s, 7);
    s.addNotes('核心功能③：个性化路径。用真实打分公式展示"动态规划+精准推送"如何实现——确定性计算、画像驱动、可复现。');
  }

  // ============ 8. 核心功能④⑤ 即时辅导 + 学习评估 ============
  {
    const s = add();
    header(s, { kicker: '核心功能 04 · 05 · 辅导与评估', title: '智能即时辅导 + 学习过程评估', idx: '03' });
    reqTag(s, 0.7, 1.42, 12.1, '智能辅导：即时（多模态）答疑；学习评估：多维度精准评估、跟踪学习行为并动态调整。');
    addShot(s, '16-instant-tutor-result.png', { x: 0.6, y: 2.1, w: 6.0, h: 3.15 });
    addShot(s, '03-dashboard-top.png', { x: 6.9, y: 2.1, w: 6.0, h: 3.15 });
    howBox(s, { x: 0.6, y: 5.35, w: 6.0, h: 1.35 }, '④ 即时辅导', [
      '"我没懂"→ 识别问题 → 按需生成针对性资源',
      '资源含图解/例题/视频/讲义，勾选即生成（多模态答疑）',
    ]);
    howBox(s, { x: 6.9, y: 5.35, w: 6.0, h: 1.35 }, '⑤ 学习评估', [
      '跨会话累积做题/进度/笔记行为，四维量化评估',
      '定位薄弱点 + 给出下一步与难度的动态调整建议',
    ], '2E4A78');
    footer(s, 8);
    s.addNotes('核心功能④⑤（赛题列为可选加分）：即时辅导按需生成多模态资源；学习评估跨会话跟踪行为、四维量化、动态调整。');
  }

  // ============ 9. 核心考察点：防幻觉 + 内容安全 ============
  {
    const s = add();
    header(s, { kicker: '核心考察点 · 可信与安全', title: '防幻觉机制 + 内容安全（双保险）', idx: '04' });
    reqTag(s, 0.7, 1.42, 12.1, '会议反复强调的核心考察点：RAG + 多 Agent 交叉校验抑制幻觉；并须有内容安全过滤、无敏感违规。');
    // 防幻觉三道防线
    s.addText('防幻觉三道防线', { x: 0.7, y: 2.1, w: 6, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 13.5, bold: true, color: GREEN_D });
    const lines = [['① RAG 接地', 'Top-3 检索真实语料，逐句可溯源（白盒徽章标来源+置信）'], ['② Critic 审核', '审核 Agent 逐句 embedding 接地校验，未接地句计入幻觉率'], ['③ 重试降级', '幻觉率>阈值回炉重生成，超限降级，绝不交付不可信内容']];
    lines.forEach((L, i) => {
      const y = 2.46 + i * 0.78;
      s.addShape('roundRect', { x: 0.7, y, w: 6.05, h: 0.68, rectRadius: 0.07, fill: { color: WHITE }, line: { color: LINE, width: 1 } });
      s.addShape('rect', { x: 0.7, y, w: 0.08, h: 0.68, fill: { color: GREEN } });
      s.addText(L[0], { x: 0.86, y: y + 0.05, w: 1.5, h: 0.58, fontFace: 'Microsoft YaHei', fontSize: 12, bold: true, color: NAVY, valign: 'middle' });
      s.addText(L[1], { x: 2.35, y: y + 0.05, w: 4.3, h: 0.58, fontFace: 'Microsoft YaHei', fontSize: 10, color: INK_SOFT, valign: 'middle' });
    });
    s.addShape('roundRect', { x: 0.7, y: 4.94, w: 6.05, h: 1.6, rectRadius: 0.1, fill: { color: NAVY } });
    s.addText('内容安全过滤（与防幻觉并列硬要求）', { x: 0.88, y: 5.06, w: 5.7, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 12.5, bold: true, color: '8FE0BE' });
    bullets(s, [
      { t: '所有 LLM 生成内容返回前过统一安全检测层', c: 'DCE6DD' },
      { t: '检测政治敏感/暴力/违法/不良信息，命中即拦截脱敏', c: 'DCE6DD' },
      { t: '可配敏感词表，且不误伤"梯度/激活"等学术术语', c: 'DCE6DD' },
    ], { x: 0.9, y: 5.42, w: 5.7, h: 1.05 }, { fs: 10.5, gap: 6 });
    // 右：消融实验 + 截图
    addShot(s, '11-resource-lecture.png', { x: 6.95, y: 2.1, w: 5.85, h: 2.5 });
    s.addText('消融实验验证 RAG 是抑制幻觉的主导机制', { x: 6.95, y: 4.7, w: 5.85, h: 0.3, fontFace: 'Microsoft YaHei', fontSize: 12, bold: true, color: GREEN_D });
    const rows = [
      [TH('配置'), TH('平均幻觉率'), TH('说明')],
      ['完整链路', '0.0589', 'RAG+审核+重试'],
      ['− RAG 检索', '0.1549', '幻觉率激增 ↑'],
      ['− 审核 / − 重试', '0.049 / 0.068', '安全网兜底'],
    ];
    s.addTable(rows, { x: 6.95, y: 5.02, w: 5.85, colW: [1.9, 1.85, 2.1], rowH: [0.34, 0.32, 0.32, 0.32], fontFace: 'Microsoft YaHei', fontSize: 10, color: INK, align: 'center', valign: 'middle', border: { pt: 0.5, color: LINE }, fill: { color: WHITE } });
    footer(s, 9);
    s.addNotes('核心考察点：防幻觉（三道防线 + 白盒溯源 + 消融数据）+ 内容安全过滤（赛题与防幻觉并列的硬要求）。讲义页实时标注幻觉率<5%、RAG 引用数。');
  }

  // ============ 10. 多模态学习资源 ============
  {
    const s = add();
    header(s, { kicker: '差异化优势 · 多模态资源', title: '8 类多模态学习资源中枢', idx: '03' });
    reqTag(s, 0.7, 1.42, 12.1, '至少 5 种资源类型 —— 本作品提供 8 类多模态资源，并支持入门/初级/高级难度自适应再生成。');
    const mods = [
      ['📖 定制讲义', '按画像/难度自适应'], ['🧠 思维导图', 'markmap 结构脑图'], ['📊 知识图解', 'Mermaid 动态生成'], ['💻 代码沙箱', 'Sandpack 可运行'],
      ['🎬 讲解视频', 'Remotion + TTS 旁白'], ['📝 分阶测试', '阶段测试 GATE'], ['🔗 外部资源聚合', '联网搜索 + AI 评分'], ['🎓 苏格拉底导学', '费曼式启发追问'],
    ];
    mods.forEach((m, i) => {
      const col = i % 4, row = Math.floor(i / 4);
      const x = 0.7 + col * 3.06, y = 2.1 + row * 1.0;
      s.addShape('roundRect', { x, y, w: 2.86, h: 0.86, rectRadius: 0.09, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.2, blur: 4, offset: 1, angle: 90 } });
      s.addShape('rect', { x, y, w: 2.86, h: 0.07, fill: { color: [GREEN, '2E4A78', AMBER, GREEN_D][i % 4] } });
      s.addText(m[0], { x: x + 0.16, y: y + 0.12, w: 2.6, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color: NAVY });
      s.addText(m[1], { x: x + 0.16, y: y + 0.46, w: 2.62, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 10, color: INK_SOFT });
    });
    addShot(s, '17-resource-hub.png', { x: 0.6, y: 4.3, w: 6.3, h: 2.4 });
    addShot(s, '12-resource-diagram.png', { x: 7.0, y: 4.3, w: 5.9, h: 2.4 });
    s.addText('▲ 资源中枢一站式聚合', { x: 0.6, y: 6.55, w: 6.3, h: 0.3, fontFace: 'Microsoft YaHei', fontSize: 10, italic: true, color: INK_SOFT, align: 'center' });
    s.addText('▲ 知识图解按知识点动态生成（非写死）', { x: 7.0, y: 6.55, w: 5.9, h: 0.3, fontFace: 'Microsoft YaHei', fontSize: 10, italic: true, color: INK_SOFT, align: 'center' });
    footer(s, 10);
    s.addNotes('多模态资源是差异化优势：8 类资源远超"≥5种"，且难度自适应、图解动态生成。强调由智能体协作生成、非静态。');
  }

  // ============ 11. 量化指标 + 实验验证 ============
  {
    const s = add();
    header(s, { kicker: 'Metrics · 技术实现（45%）', title: '三大量化指标全部达标、可复现', idx: '04' });
    const big = [['0.0428', '幻觉率', '目标 <0.05 ✓', GREEN_D], ['100%', '难度适配率', '目标 ≥85% ✓', '2E4A78'], ['100%', '知识覆盖率', '目标 ≥90% ✓', AMBER]];
    big.forEach((b, i) => {
      const x = 0.7 + i * 4.05;
      s.addShape('roundRect', { x, y: 1.5, w: 3.8, h: 1.85, rectRadius: 0.12, fill: { color: WHITE }, line: { color: b[3], width: 1.5 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.3, blur: 7, offset: 2, angle: 90 } });
      s.addText(b[0], { x, y: 1.64, w: 3.8, h: 0.92, fontFace: 'Arial', fontSize: 44, bold: true, color: b[3], align: 'center', valign: 'middle' });
      s.addText(b[1], { x, y: 2.6, w: 3.8, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: INK, align: 'center' });
      s.addText(b[2], { x, y: 3.0, w: 3.8, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 11, color: GREEN_D, align: 'center' });
    });
    s.addText('多维实验验证（不止跑通，更证明可靠）', { x: 0.7, y: 3.6, w: 12, h: 0.32, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color: GREEN_D });
    const exp = [
      ['规模化对比', '4 份 vs 30+ 份语料，扩库后指标稳定'],
      ['跨领域验证', '换计算机网络域端到端跑通，覆盖率满分'],
      ['消融实验', '去 RAG 幻觉率 0.059→0.155，证组件有效'],
      ['性能与成本', 'P50 13.2s / P90 37s · 单份 ≈¥0.02'],
      ['人工盲评', '5 维主观打分交叉验证自动指标'],
      ['知识库规模', '30+ 文档 / 153 切片，一门完整课程'],
    ];
    exp.forEach((e, i) => {
      const col = i % 3, row = Math.floor(i / 3);
      const x = 0.7 + col * 4.05, y = 3.98 + row * 1.32;
      s.addShape('roundRect', { x, y, w: 3.8, h: 1.16, rectRadius: 0.09, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.22, blur: 4, offset: 1, angle: 90 } });
      s.addShape('rect', { x, y, w: 0.08, h: 1.16, fill: { color: GREEN } });
      s.addText(e[0], { x: x + 0.2, y: y + 0.12, w: 3.45, h: 0.34, fontFace: 'Microsoft YaHei', fontSize: 13, bold: true, color: NAVY });
      s.addText(e[1], { x: x + 0.2, y: y + 0.48, w: 3.48, h: 0.62, fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.05 });
    });
    footer(s, 11);
    s.addNotes('技术实现 45%：三大主指标全部达标，且用规模化/跨领域/消融/性能成本/人工盲评五类实验佐证可靠性与可复现性。数字均取自真实 metrics-report。');
  }

  // ============ 12. 创新点 + 对比 ============
  {
    const s = add();
    header(s, { kicker: 'Innovation · 创新点（35%）', title: '四大创新点 + 横向对比领先', idx: '05' });
    const inv = [
      ['①', '真实多智能体协同', 'LangGraph 编排、生成↔审核真实回环重试，非串行动画模拟', GREEN],
      ['②', '防幻觉 + 内容安全双保险', 'RAG 接地压幻觉<5% + 敏感违规过滤不误伤术语', AMBER],
      ['③', '学—记—讲—测科学闭环', '康奈尔+费曼+阶段测试 GATE，"通关才算掌握"', '2E4A78'],
      ['④', '对话式动态画像', '摒弃表单、6 异质维度、低置信透明、随学随新', GREEN_D],
    ];
    inv.forEach((v, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.7 + col * 6.2, y = 1.5 + row * 1.5;
      s.addShape('roundRect', { x, y, w: 5.85, h: 1.34, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.28, blur: 5, offset: 2, angle: 90 } });
      s.addShape('rect', { x, y, w: 0.12, h: 1.34, fill: { color: v[3] } });
      s.addText(v[0], { x: x + 0.22, y: y + 0.12, w: 0.9, h: 1.1, fontFace: 'Arial', fontSize: 32, bold: true, color: v[3] });
      s.addText(v[1], { x: x + 1.2, y: y + 0.16, w: 4.5, h: 0.46, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: NAVY });
      s.addText(v[2], { x: x + 1.2, y: y + 0.64, w: 4.5, h: 0.62, fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK_SOFT, valign: 'top', lineSpacingMultiple: 1.05 });
    });
    // 对比表
    const rows = [
      [TH('维度'), TH('传统在线学习'), TH('通用 AI 生成'), TH('智学中枢')],
      ['个性化', '千人一面', '仅会话级', '6 维画像·能力定序'],
      ['内容可信', '人工·静态', '易幻觉·不可溯', 'RAG 接地·<5%·可溯源'],
      ['学习方法', '看视频为主', '一问一答', '学—记—讲—测 + GATE'],
      ['成本效率', '制作昂贵', '—', '≈¥0.02/份·分钟级'],
    ];
    s.addTable(rows, { x: 0.7, y: 4.65, w: 12.1, colW: [1.7, 3.1, 3.0, 4.3], rowH: [0.44, 0.4, 0.4, 0.4, 0.4], fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK, align: 'left', valign: 'middle', border: { pt: 0.5, color: LINE }, fill: { color: WHITE } });
    footer(s, 12);
    s.addNotes('创新点（应用价值/创新占 35%）：四大创新 + 对比表格直观展示四维领先。这页是拉分关键——别人没有、我们做到。');
  }

  // ============ 13. 加分项汇总（积分项） ============
  {
    const s = add();
    header(s, { kicker: 'Bonus · 加分项', title: '加分项一览：有哪些 · 如何完成', idx: '05' });
    const rows = [
      [TH('加分项'), TH('如何完成（实现方式）'), TH('价值 / 亮点')],
      ['多模态学习资源', '8 类资源由智能体协作生成 · 难度自适应 · 图解动态生成', '远超"≥5 种"要求'],
      ['智能即时辅导', '"我没懂"→ 识别问题 → 按需生成图解/例题/视频/讲义', '解决自学无人答疑'],
      ['学习过程评估', '跨会话累积行为 · 四维量化 · 薄弱定位 + 动态调整', '闭合个性化学习循环'],
      ['苏格拉底 / 费曼导学', '以讲代学、启发式追问，自动列出理解缺口', '学习方法创新'],
      ['知识图谱可视化', '掌握/学习中/待学/盲区四态拓扑动态渲染', '学情一目了然'],
      ['岗位对标（轻量入口）', '匹配度 + 能力缺口分析（A 赛题轻量、不喧宾夺主）', '学习直通就业'],
      ['联网资源聚合', '真实搜索 + AI 评分排序 + URL 白名单防幻觉', '优质资源扩展'],
      ['内容安全 + 工程合规', '敏感违规过滤 · 开源协议标注 · 195 条测试 · 日志脱敏', '守住合规分'],
    ];
    s.addTable(rows, { x: 0.6, y: 1.45, w: 12.2, colW: [2.9, 6.2, 3.1], rowH: [0.48, 0.62, 0.62, 0.62, 0.62, 0.62, 0.62, 0.62], fontFace: 'Microsoft YaHei', fontSize: 10.5, color: INK, align: 'left', valign: 'middle', border: { pt: 0.5, color: LINE }, fill: { color: WHITE } });
    footer(s, 13);
    s.addNotes('加分项（积分项）汇总：逐条说明"有哪些 + 如何完成"。多模态、即时辅导、评估、导学、图谱、岗位、联网聚合、内容安全合规。直接回应用户"加分项有哪些、如何完成"。');
  }

  // ============ 14. 工程合规与 AI 辅助开发 ============
  {
    const s = add();
    header(s, { kicker: 'Compliance · 文档与合规（10%）', title: '工程合规与 AI 辅助开发说明', idx: '06' });
    const blocks = [
      ['多智能体框架声明', ['明确采用 LangGraph 状态机编排多智能体', '诊断/生成/审核三 Agent + 路径/评估独立 Agent', 'WorkflowTrace 全轨迹留痕、可复现可观测']],
      ['AI 辅助开发说明', ['AI 编程协作：Claude Code（占比经人工核对）', '底层推理模型：DeepSeek（讲义同源管线）', 'AI 生成内容均经人工审阅与测试验证']],
      ['开源依赖与协议', ['LangGraph/Remotion/Sandpack/markmap/Chroma/bge 等', '文档显著位置标注名称·来源·License', '知识库语料标注来源与开放许可、非逐字拷贝']],
      ['测试与安全', ['后端 pytest 18 文件/195 用例全通过 · 前端 tsc 0 报错', 'JWT 鉴权 + 角色权限守卫 + 日志脱敏拦截', '内容安全过滤 + Mock-first 断网可复现']],
    ];
    blocks.forEach((b, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.7 + col * 6.2, y = 1.5 + row * 2.66;
      s.addShape('roundRect', { x, y, w: 5.85, h: 2.42, rectRadius: 0.1, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: { type: 'outer', color: 'C9BEA6', opacity: 0.25, blur: 5, offset: 2, angle: 90 } });
      s.addShape('rect', { x, y, w: 5.85, h: 0.5, fill: { color: NAVY } });
      s.addText(b[0], { x: x + 0.2, y, w: 5.5, h: 0.5, fontFace: 'Microsoft YaHei', fontSize: 14.5, bold: true, color: WHITE, valign: 'middle' });
      bullets(s, b[1], { x: x + 0.22, y: y + 0.66, w: 5.45, h: 1.65 }, { fs: 11, gap: 8 });
    });
    footer(s, 14);
    s.addNotes('文档与合规（10%）+ 提交必交项：多智能体框架声明、AI 辅助开发说明（Claude Code+DeepSeek）、开源协议标注、测试与安全。逐项守住合规分。');
  }

  // ============ 15. 总结与展望 + 致谢 ============
  {
    const s = add();
    s.background = { path: path.join(ASSETS, 'sec-bg.png') };
    s.addShape('rect', { x: 0.7, y: 0.85, w: 0.16, h: 0.85, fill: { color: GREEN } });
    s.addText('SUMMARY · OUTLOOK · THANKS', { x: 0.95, y: 0.87, w: 10, h: 0.34, fontFace: 'Arial', fontSize: 12, bold: true, color: '9FB7AC', charSpacing: 2 });
    s.addText('成果总结与未来展望', { x: 0.92, y: 1.22, w: 11.5, h: 0.7, fontFace: 'Microsoft YaHei', fontSize: 30, bold: true, color: WHITE });
    s.addText('已交付成果', { x: 0.95, y: 2.15, w: 6, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 16, bold: true, color: '8FE0BE' });
    bullets(s, [
      { t: '赛题八大考核点 + 三大指标全部达成', c: 'DCE6DD' },
      { t: '完整可运行的多智能体系统，前后端+RAG 全链路', c: 'DCE6DD' },
      { t: '幻觉率 4.28% · 适配/覆盖 100%，结果可复现', c: 'DCE6DD' },
      { t: '8 类多模态资源 + 多项加分项，覆盖学习全流程', c: 'DCE6DD' },
    ], { x: 0.95, y: 2.6, w: 5.6, h: 3.0 }, { fs: 12.5, gap: 10 });
    s.addText('未来展望', { x: 7.0, y: 2.15, w: 6, h: 0.4, fontFace: 'Microsoft YaHei', fontSize: 16, bold: true, color: '8FE0BE' });
    bullets(s, [
      { t: '资源生态聚合：联网优质资源 + AI 评分规模化', c: 'DCE6DD' },
      { t: '岗位能力图谱：对接真实招聘，学习直通就业', c: 'DCE6DD' },
      { t: '多学科扩展 + 生产级架构平滑升级', c: 'DCE6DD' },
      { t: '防幻觉接更强模型、扩权威语料进一步压低', c: 'DCE6DD' },
    ], { x: 7.0, y: 2.6, w: 5.7, h: 3.0 }, { fs: 12.5, gap: 10 });
    s.addShape('roundRect', { x: 0.95, y: 5.65, w: 11.4, h: 0.92, rectRadius: 0.1, fill: { color: '1F3050' }, line: { color: GREEN, width: 1 } });
    s.addText('感谢各位评委聆听 · 敬请指正 ——  智学中枢：让 AI 因材施教，让每一份学习内容都可信。', { x: 0.95, y: 5.65, w: 11.4, h: 0.92, fontFace: 'Microsoft YaHei', fontSize: 15, bold: true, color: WHITE, align: 'center', valign: 'middle' });
    s.addNotes('收尾：回扣"考核点全部达成"，给展望，致谢评委，主动引导提问方向（多智能体协同/防幻觉）。');
  }

  const out = path.join(__dirname, '..', '软件杯介绍-v4.pptx');
  await p.writeFile({ fileName: out });
  console.log('OK ->', out);
})().catch((e) => { console.error(e); process.exit(1); });
