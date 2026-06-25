# 完成总结 · 画像诊断界面重做 + 三种诊断入口（标注来源置信度）

> 对应指令：`docs/progress/CC-diagnosis-ui-three-entries.md`。三入口产出**同一套画像结构（能力 + 偏好 + 主观，6 个 canonical 维度）**，仅 `source`/`confidence` 不同；下游 planner / 学情概览读法不变、无回归。Mock 兜底、tsc 干净、0 console error。

## 一、现状说明（问题定位）

**问题 1「又挤又窄、回答被题目遮挡」根因：** 引导式作答卡 `.pd-itx`（微测/偏好题 + 选项）原是 `ChatPanel` 的**兄弟节点、渲染在整块对话面板之下**，而 `.pd__chat` 为 `overflow:hidden` 且 `.pd .socratic { height:100% }` 让对话面板吃满整列高度——作答卡被挤到可视区之外/被裁切，且位置落在输入框**下方**。叠加容器偏矮（`calc(100vh-300px)`、min 480px），整体显窄。

**三入口缺失：** 原仅「对话式诊断」单一主路径 + 表单次要入口，用户无法按习惯自选；自述/零基础两种产出未接入统一画像结构与来源标注。

## 二、改动文件清单

### 新增（3）
- `frontend/src/components/DiagnosisEntry.tsx` + `.css`：诊断起点三选一卡片（做题式 / 一段话 / 跳过零基础）+ 自述视图样式。
- `frontend/src/components/SelfReportProfile.tsx`：入口②一段话自述（复用 `/profile/parse`，mock 关键词启发式兜底）→ 复用 `StudentPortraitPanel` 出报告。
- `frontend/src/components/ProvenanceBadge.tsx`：画像整体来源/置信度徽章（由 `source`/`confidence` 派生，画像报告 + 学情概览共用）。

### 修改（10）
- `services/profileDialogue.ts`：①`PortraitDimension['source']` 追加 `self_report | default`；②新增 `portraitProvenance()` / `selfReportPortrait()` / `zeroBasePortrait()` / `SelfReportInput`、`ProvenanceTier`、`PortraitProvenance`（三入口统一画像产物 + 来源派生）。
- `components/ChatPanel.tsx` + `.css`：新增可选 `belowChat` 插槽（渲染于对话区↔输入框之间，`.socratic__slot` 不挤压、超高内滚），**对 SocraticTutor 无影响**（默认不传）。
- `components/ProfileDialogue.tsx`：作答卡改由 `belowChat` 插槽承载——回答（上方气泡）与待答题目分区、不重叠。
- `components/ProfileDialogue.css`：`.pd` 加宽加高（`calc(100vh-230px)`、min 620px、gap 调大）；`.pd .socratic` 由 `height:100%` 改 `flex:1 1 auto`（插槽与输入框稳占底部、对话区自适应收缩内滚）；移动端同步；新增 `.sp-srctag--self_report/--default`、`.prov-badge*`、`.sp-panel__prov`。
- `components/StudentPortraitPanel.tsx`：`SOURCE_META` 补 `self_report/default`；头部加 `ProvenanceBadge`。
- `pages/ProfileBuilder.tsx`：`view` → `mode（choose/dialogue/selfreport/form）`，起点渲染三选一；`finish` 抽出 `writePortrait` 并新增 `finishWithPortrait`（入口②③ 用，零基础不带岗位匹配）。
- `pages/ProfileBuilder.css`：`--wide` 1180→1280px。
- `pages/Dashboard.tsx` + `.css`：欢迎卡加 `ProvenanceBadge`（导入 `ProfileDialogue.css` 取徽章样式）。
- `store/mastery.ts`：`initial()` 由 `{ [CURRENT_KP_ID]:'learning' }` 改为 `{}`（**与问题 1 修复 6247a78 一致**：学习状态只由真实学习行为写入；资源页对当前 KP 无状态时回落 `'learning'`，见 `LearningResource ?? 'learning'`，不依赖此种子）——保证零基础新用户「路径全节点未开始」。

### 接口文档增量
- `docs/后端接口文档.md` 17.2：`source` 枚举**追加** `self_report | default`（不改既有取值/语义）；新增「画像三入口与来源/置信度」说明（三入口同结构、仅来源置信度不同；自述复用 4.1 `/profile/parse`、零基础经 17.4 覆盖写；后端落库透传新枚举即可）。**无新增接口、未改任何既有签名。**

## 三、验证结果（Mock 模式，端口实测）

- `npx tsc --noEmit` → **0 错误**；`npm run build`（tsc && vite build）→ **built 成功**。
- Playwright 全程 **0 console error**（早期网络报错为切端口/HMR 整页重载/清缓存的测试过程噪声，非功能错误）。

**三入口各走通一次：**
1. **做题式** → 进入对话，微测作答卡**稳居「对话区↔输入框」之间、完整可见不被遮挡**；右栏画像随答增量刷新（能力维 `source=diagnostic` → 整体徽章「实测·高置信」）。
2. **一段话描述**（输入「我会 Python，机器学习基础还行，神经网络只懂概念，Transformer 没碰过…」）→ 解析出能力维 `score=39（薄弱）`、逐知识点估分（机器学习≈75 / 神经网络≈22 / Transformer≈22，正负语气就近判定）+ 偏好/主观维，**6/6 维齐**；徽章「自述 · 中置信 49%」。
3. **跳过零基础** → 6 维全 `source=default`、能力未测；学习路径 **0 已完成 / 0 进行中 / 0%，全节点「待学习」**；学情概览徽章「未测 · 默认零基础 30% · 已跳过测评…从头学起」。

**结构一致 / 无回归：** 三入口均产出同一套 canonical 维度，学习路径（mock planner 按画像排序 + 偏好推荐资源）与学情概览（synthesizeOverview）正常消费。

**响应式：** 390px 宽下，三选一卡片与对话/画像双栏均堆叠为单列，输入框与作答卡可见、不重叠。

**来源置信度标注：** 画像报告（右栏面板头部）与学情概览（欢迎卡）均显示徽章；实测·高（绿）/ 自述·中（蓝）/ 未测·默认（琥珀）/ 自填·中（兜底）配色区分。

## 四、红线自检

- ✅ 未改任何既有接口路径/字段/枚举语义；新增仅**追加** `source` 枚举值并同步文档。
- ✅ 复用优先：自述复用 `/profile/parse`，零基础/自述复用 `saveStudentPortrait` 覆盖写、复用 `StudentPortraitPanel` 出报告、复用 `source`/`confidence` 字段派生徽章（不另造一套）。
- ✅ 三入口统一画像结构（6 canonical 维度），下游 planner/概览读法不变、无回归。
- ✅ 零基础路径全节点未开始、无「已完成」（且无误报「进行中」）；与问题 1 修复一致。
- ✅ Mock-first：无后端全链路可跑（自述 mock 启发式、零基础默认画像）；深浅主题正常。
- ✅ `ChatPanel` 新增 `belowChat` 为可选插槽，SocraticTutor 等既有消费方零影响。
- ⚠️ 联调（`USE_REAL_API=true`）下后端 `PUT /profile/student-portrait` 需接受追加的 `source` 枚举值（透传存储即可）——已在接口文档注明。
