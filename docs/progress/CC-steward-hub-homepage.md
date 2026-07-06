# CC 会话总结 · 学情管家中枢首页（闭环叙事 + 功能全景 + 全局返回）

> 指令：`docs/CC-steward-hub-homepage.md`。把学情管家升级为登录后默认落地的**中枢首页**：
> 「需求推测 → 规划 → 监测 → 建议」四段闭环 + 全功能入口 + 各功能页一键返回。纯展示层 + 导航，复用现有数据，不新造能力。

## 一、现状（改造前）

- 侧栏「学情管家」已存在（指向 `dashboard` 页，第二组），登录后默认落地页已是 `dashboard`；
- Dashboard 已有 StewardHero / AgentActivityBoard / 学习评估面板，但中段仍有**静态占位**的「推荐学习路径 / 推荐动态」（写死 3 张卡）与假天气卡；
- 各功能页无返回中枢入口；路由为 App.tsx 状态机（无 react-router），全部 learner 页已接收 `onNavigate`。

## 二、中枢首页设计（各部分数据来源）

签名元素：左侧「管家链路」竖轨串起 01→04 步骤章，末段渐隐 + ↺ 回环注脚，视觉化「闭环」。

| 段落 | 内容 | 数据来源（全部复用既有能力） |
|---|---|---|
| Hero | 管家身份 + 监测中 + 4 指标 | 既有 StewardHero（文案更新为 5 位专家） |
| 引导 | GuideCard 唯一下一步 | 既有 journey 状态机 |
| ① 我对你的理解 | 「我推测你想 X、目标岗位 Y、在 Z 较薄弱」叙事 + 置信徽章 + 雷达 + 能力分析 | `usePortrait` dims（learning_goal 维）、`/dashboard/overview`（联调）或 `synthesizeOverview`（mock）、ProvenanceBadge、betterThanPct |
| ② 为你规划的路径 | 时间线（预计 N 周 / 知识点数 / 总时长 / 已学 / 进度% / 节奏）+ 真实 3 步路径预览 + 下一步卡 +「继续学习」 | `getLearningPath()`（6.1，联调/mock 同口径），summary.timeline + lessons；继续学习走 `setResourceNav(kpId,'flow')` 与路径页同协议 |
| ③ 学习监测 | 掌握度 stats ×4 + 学习过程评估 + 各 Agent 活动看板（诊断/规划/生成/评估/**文档学习**） | `useMastery`、`/dashboard/overview`、`getLearningEvaluation`/`synthesizeEvaluation`、`synthesizeSteward`（新增可选 docCount ← `listDocuments()` 20.2） |
| ④ 管家建议 | 主动建议（薄弱补强/下一步/阶段测试/方法建议）+ 回环注脚 | 既有 `synthesizeSteward().suggestions` |
| 功能全景 | 三组入口：核心学习主线①②③ / 自主学习（文档学习·即时辅导）/ 资产与全景（资源库·知识图谱·工作流），每项一句话 + 真实状态徽章 | journey / timeline.completionPct / docCount / resourceCount / coveragePct；即时辅导 = `setResourceNav('', 'browse', 'tutor')` 落资源页导学对话 |

未诊断空态保留原引导（不展示任何臆造数据），下方仍渲染功能全景。
删除的静态假数据：三栏 header（假天气/贴士、与 hero 重复的欢迎语和仪表盘）、写死的「推荐学习路径/推荐动态」双栏。

## 三、改动文件清单

- `frontend/src/components/Sidebar.tsx`：学情管家组置顶第一组，描述改「中枢首页 · 统筹全局」
- `frontend/src/pages/Dashboard.tsx`：重组为闭环四段 + 功能全景（HubSection/HubEntryGroup 局部组件；新增 path/docCount 两个数据源 effect）
- `frontend/src/pages/Dashboard.css`：追加 `.hub-*` 样式（链路轨/步骤章/时间线/入口卡/回环注脚/响应式），补 1100px 中等宽度断点
- `frontend/src/services/stewardActivity.ts`：**仅追加** `docCount?` 入参 + 第 5 个「文档学习 Agent」条目（既有调用不受影响）
- `frontend/src/components/LearningSteward.tsx`：拆出 `AgentActivityPanel` / `StewardSuggestPanel`（`AgentActivityBoard` 签名不变、内部组合）；hero 文案 5 位专家
- `frontend/src/components/PageHeader.tsx` + `.css`：**仅追加**可选 `onBack` / `crumb` props →「← 学情管家 / 当前功能」层级条
- 7 个功能页接返回条：`ProfileBuilder` / `LearningPath` / `LearningResource` / `DocumentLearning`（顺带把 `_onNavigate` 改回 `onNavigate`）/ `MyResourceLibrary` / `KnowledgeGraph` / `AgentWorkflow`

## 四、接口文档增量

无。纯前端展示层 + 导航，复用既有接口（6.1 / 12.1 / 12.2 / 19.1 / 20.2 / 29），未新增、未改任何接口签名。

## 五、验证结果（联调模式 · learner_001 实测）

- `npx tsc --noEmit` → 0 错误；Playwright 全程 console **0 error / 0 warning**；
- 侧栏学情管家为第一组、登录默认落地中枢；进入即见 Hero → 引导 → 01 理解你（真实画像叙事：转岗或求职 / 数据分析师 / 高级 80 分 + 实测·高置信 82%）→ 02 规划（后端真实 12 点路径：预计 2 周 / 20.5h / 28% / 下一步「深度学习原理」）→ 03 监测（掌握度 33% + deepseek 生成的学习评估 + 5 Agent 看板：6 维画像/1 条路径/42 份资源/2 知识点/5 篇文档，全真实）→ 04 建议（4 条真实派生建议）→ 功能全景（状态徽章：已完成/进度 28%/5 篇文档/42 份/覆盖 33%）；
- 7 个功能页均有「← 学情管家 / 当前功能」，点击实测回中枢；即时辅导入口实测落资源页并弹出苏格拉底导学对话（当前知识点上下文正确）；
- 鼠尾草/墨纸双主题实测正常（全部套 CSS 令牌）；853px 中等宽度实测单列不挤压（修了一处新增断点）；
- 截图存 `.playwright-mcp/hub-01..10.png`（gitignored）。

## 六、红线自检

- ✅ 不改既有接口签名：stewardActivity 入参、PageHeader props 均为可选追加；AgentActivityBoard 签名不变；
- ✅ 不改内置画像/诊断/路径/掌握度逻辑与 Zustand store 结构；只做展示收拢 + 叙事 + 导航；
- ✅ 数据真实：删除了旧静态占位（假天气/写死路径卡/写死推荐动态），四段数据全部来自既有 store/service；无对应信号不展示（未诊断空态、未规划提示、加载中不误报）；
- ✅ Mock 兜底：新增数据源均走既有 mock-first service（`getLearningPath`→mockLearningPath、`listDocuments`→内存表、synthesize* 本地合成），无 Key 可跑通；
- ✅ 深浅主题 / 响应式 / prefers-reduced-motion（回环图标动画已豁免）。
