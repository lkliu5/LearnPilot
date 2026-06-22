const pptxgen = require('pptxgenjs');
const html2pptx = require('./html2pptx');

const NOTES = {
1:`开场定位。智学中枢是一个多智能体驱动的个性化学习平台。一句话讲清楚我们解决两件事：让 AI 真正因材施教，并且生成的每一句都可溯源、可信。四个关键词就是全片的主线——对话式画像、真实多智能体协同、防幻觉<5%、学习方法闭环。封面底部留了队伍信息位，录制前替换。`,
2:`讲价值（应用价值占 35%）。传统在线学习两大痛点：资源千人一面，无法适配个人；AI 直接生成又常幻觉、不可信。我们的价值主张正好对症——因材施教解决"千人一面"，可信生成解决"AI 幻觉"。这一页是整个作品的价值锚点。`,
3:`讲架构。强调全栈自建，五层结构。重点指向中间高亮的多智能体编排层：我们用的多智能体框架是 LangGraph，五节点带真实回环。RAG 引擎用 Chroma + bge 本地嵌入，30 文档 153 切片做接地证据。底层 LLMClient 适配层支持 mock/deepseek，无 Key 也能跑通全链路。`,
4:`核心功能一：对话式画像。我们摒弃填表，改用几轮自然对话构建六个异质维度。特别指出"易错点"这类推断维度标了"低置信"——这是我们防幻觉理念的体现：不确定的，绝不编造。画像随学随新。演示时这里走真实对话。`,
5:`重头戏：真实多智能体协同。这是真的 LangGraph 五节点，不是动画。生成 Agent 产讲义，审核 Agent 基于 RAG 逐句接地校验幻觉率，超阈值就打回重生成——你看到的回环就是真实重试（实测 18 份里触发 2 次、降级 1 次）。最终幻觉率压到 4.28%，每句可溯源到 sources。演示时故意制造一次审核不通过展示回环。`,
6:`核心功能三：个性化学习路径。同一批知识点，画像 A 基础薄弱就从头夯实，画像 B 有基础则已掌握的自动后置、薄弱优先。规划依据真实画像加掌握度打分排序，每步精准推送资源。一句话收尾：不同的人，不同的路径。`,
7:`两个加分功能合并讲。智能辅导：学习者说"我没懂"，系统自动定位卡点、给资源清单、勾选即按需生成。学习评估：基于真实做题行为做多维过程评估，输出学情概览和动态调整建议。两个面板演示时各露一眼真实界面。`,
8:`创新亮点，四点说清差异化。一是真实多智能体协同（非串行模拟的伪多智能体）；二是防幻觉+内容安全双保险，两道关正交互补；三是费曼+康奈尔学习方法闭环；四是对话式画像。这页是评委记忆点，讲得干脆。`,
9:`学习方法闭环。我们把科学学习法做进产品：学（精读）—记（康奈尔三栏）—讲（费曼向 AI 讲、暴露缺口）—测（阶段测试通关才点亮已掌握）。未通关就回到薄弱点循环巩固。这是真正落地"因材施教"的闭环设计。`,
10:`技术与指标（功能实现占 45%）。三个大字数字是真实测得：幻觉率 4.28%、难度适配率 100%、知识覆盖率 100%，全部达标。右侧消融实验是最有说服力的证据——去掉 RAG 后幻觉率从 5.89% 飙到 15.49%，证明 RAG 接地是抑制幻觉的主导机制。性能 P50 13.2 秒、单份成本约两分钱，都来自 327 条真实轨迹。`,
11:`工程与合规（文档占 10%）。四个象限：开源依赖与协议逐项标注，许可均合规；AI 辅助开发用 Claude Code 编程、DeepSeek 推理；内容安全是集中式单点覆盖全部 13 个生成器、四类违规拦截且学术不误伤；测试 179 passed、0 回归，Mock-first 无 Key 可跑。守得住底线。`,
12:`收尾。成果回顾对应前面讲过的能力，幻觉率 4.28% 是硬指标。展望承接赛题揭榜挂帅方向：资源聚合（联网搜索+AI评分）和岗位聚合（匹配度+能力缺口），以及知识库扩容让跨域指标看齐。最后一句口号收束全场：让 AI 因材施教，让每一份学习内容都可信。`
};

(async () => {
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = '智学中枢团队';
  pptx.title = '智学中枢 · 多智能体个性化学习平台';

  for (let i = 1; i <= 12; i++) {
    const { slide, placeholders } = await html2pptx(`slides/slide${i}.html`, pptx);
    if (i === 10 && placeholders.length) {
      const ab = placeholders.find(p => p.id === 'ablation') || placeholders[0];
      slide.addChart(pptx.charts.BAR, [{
        name: '幻觉率',
        labels: ['完整链路', '−RAG', '−审核', '−重试'],
        values: [5.89, 15.49, 4.90, 6.82]
      }], {
        ...ab,
        barDir: 'col',
        showTitle: true, title: '消融实验：去掉 RAG，幻觉率飙升 (%)',
        titleFontSize: 11, titleColor: '46624F',
        showLegend: false,
        showValue: true, dataLabelPosition: 'outEnd', dataLabelColor: '262A23',
        dataLabelFontSize: 10, dataLabelFontBold: true,
        showCatAxisTitle: false, showValAxisTitle: false,
        catAxisLabelColor: '4C5247', catAxisLabelFontSize: 10,
        valAxisHidden: true, valGridLine: { style: 'none' },
        valAxisMaxVal: 18, valAxisMinVal: 0,
        chartColors: ['5B7F6E', 'C0612F', '5B7F6E', '5B7F6E'],
        barGapWidthPct: 60
      });
    }
    slide.addNotes(NOTES[i]);
    console.log('ok slide' + i);
  }

  await pptx.writeFile({ fileName: '../软件杯介绍.pptx' });
  console.log('WROTE docs/软件杯介绍.pptx');
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
