# C2 画像诊断重构：能力靠测 · 偏好归类型 · 主观靠对话

> 本会话重构「画像诊断」：把六维笼统自陈画像，重构为**三类画像 + 三段式诊断**。
> 0 报错完成：后端 `pytest 205 passed, 1 skipped`；前端 `tsc --noEmit` 干净（exit 0）。

## 一、现状说明（重构前）

- **六维纯自陈采集**：`DialogueDiagnosticAgent` → `LLMClient.extract_portrait` 关键词匹配
  用户自陈文本。连「能力分」都是从关键词硬给（`"精通"→85`、`"零基础"→30`）——用户
  说谎/不自知即测不准。
- **混轴雷达**：①学情概览（12.1）把全部 6 异质维铺到 0-100 轴，偏好维取 `confidence×100`
  当轴值（「学习节奏」凭空有了满分）；②4.4 能力雷达用写死基线 `[85,72,68,45,30,20]` 或
  简历自陈——**都不是「测」出来的**。
- **能力、偏好、主观混为一类**：`knowledge_base`(能力) / `cognitive_style`·`learning_pace`·
  `error_preference`(偏好) / `learning_goal`·`prior_experience`(主观) 混在同一套维度、同一轴。
- **题库可复用但无逐题难度**：`QuizQuestion` 仅有知识点级难度（Lesson：ml 入门→finetune
  精通），无逐题 `difficulty` 字段 → 微测「由浅入深」取**知识点难度阶梯**。

## 二、画像新结构（三分类，向后兼容追加字段）

`PortraitDimension` 追加 `kind` / `basis` / `optionKey`，`source` 枚举追加 `diagnostic`：

| 类别 `kind` | 维度 | 测法 | 是否打分 |
|---|---|---|---|
| **ability** 能力 | `knowledge_base`（+ 各知识点细分见 4.4） | 诊断微测**行为反推**，带依据 `basis` | ✅ 0-100 |
| **preference** 偏好 | `cognitive_style`/`learning_pace`/`error_preference` | 偏好选择题**归类型** `optionKey` | ❌ 不打分、不上轴 |
| **subjective** 主观 | `learning_goal`/`prior_experience` | 对话采集、描述性 | ❌ 不打分 |

**三段式诊断**（`POST /profile/dialogue` 追加 `answer` 请求字段、`interaction` 响应字段 +
`event: interaction`）：① 对话开场（主观）→ ② 诊断微测（逐题抛 `quiz`，复用 quiz 题库按知识点
难度阶梯由浅入深，作答反推能力、段末写 Mastery 低置信基线）→ ③ 偏好选择（逐题抛
`preference` 二/三选一，归类型）。三段走完 `diagnosisComplete=true`。

**能力口径统一**：微测基线（`score_source=diagnostic` 低置信）与真实 quiz 评分
（`score_source=quiz` 高置信）写**同一行 Mastery**（追加 `score`/`confidence`/`score_source`
三列）；4.4 能力雷达、12.1 概览能力维由此**单一来源**驱动——不造两个打架的能力来源。

## 三、改动文件清单

**后端（新增 1 / 改 9）**
- `app/services/diagnostic_microtest.py`（新）：微测取题（知识点难度阶梯）/判分/产出能力维+依据/写 Mastery 基线。
- `app/core/llm.py`：维度三分类 `PORTRAIT_DIM_KINDS`、偏好选项库 `PREFERENCE_QUESTIONS`、
  `source` 加 `diagnostic`、`_sanitize_portrait_updates` 附 `kind`/`basis`/`optionKey`、能力维外剥离 `score`。
- `app/agents/dialogue_agent.py`：重写为三段式（开场抽主观→微测交互→偏好归类）纯逻辑。
- `app/services/profile_dialogue.py`：三段式状态机编排 + `event: interaction` + `answer` 作答。
- `app/services/mastery.py`：`set_baseline`/`set_score`/`get_score_map`（能力分单一来源）。
- `app/services/profile.py`：`ability_portrait` 改读 Mastery 能力分（按 `lesson_seq` 6 轴）。
- `app/services/quiz.py`：submit 写 Mastery 高置信能力分（口径统一）。
- `app/services/dashboard.py`：雷达改能力维、`preferences` 类型标签、未测≠盲区。
- `app/services/student_portrait.py`：`replace_portrait` 统一清洗 + 简历/手动自陈分落 Mastery（`source=manual`）。
- `app/models/entities.py`（Mastery +3 列）、`app/core/init_db.py`（迁移）、`app/schemas/profile.py`、`app/api/v1/profile.py`。

**前端（改 7）**
- `services/profileDialogue.ts`：类型（`kind`/`basis`/`optionKey`/`interaction`）、SSE `event:interaction`、
  `getAbilityPortrait`、三段式 mock 状态机。
- `components/ProfileDialogue.tsx`：渲染微测/偏好选项卡片、点选经 `answer` 提交。
- `components/StudentPortraitPanel.tsx`：三分区呈现（能力进度条+依据 / 偏好类型标签 / 主观描述）。
- `services/dashboard.ts`：`synthesizeOverview` 能力雷达 + `preferences`；`DashboardOverview.preferences`。
- `components/ProfileConfirmModal.tsx`：取 4.4 能力雷达 + 偏好类型标签。
- `pages/Dashboard.tsx`：能力雷达标题 + 偏好类型标签区。
- CSS：`ProfileDialogue.css` / `ProfileConfirmModal.css` / `Dashboard.css`。

**测试**：重写 `test_dialogue_profile.py`（16 例，三段式）、更新 `test_b6.py`/`test_cfix_logic.py`/
`test_contract_snapshot.py` 至 C2 能力雷达契约。

## 四、接口文档增量（`docs/后端接口文档.md`）

- **17.2 PortraitDimension**：追加 `kind`/`basis`/`optionKey`，`score` 限 `ability`，`source` 加 `diagnostic`，建议维度集改三分类。
- **17.5（新）**：三段式编排 + `answer` 请求字段 + `interaction`/`event: interaction` + 能力口径统一 + 12.1 增量。
- **4.4**：能力雷达真实化说明（由 Mastery 能力分驱动）。
- **12.1**：`radar` 改能力维、新增 `preferences`、强弱项仅在已测知识点判定。

## 五、验证结果（两用户对比 + 行为驱动）

后端 `pytest -q`：**205 passed, 1 skipped**；前端 `tsc --noEmit`：**exit 0**。
两用户 + 空作答三组对比（行为驱动实测）：

| | 用户A（答对 6/6 + 图像型） | 用户B（答错 6/6 + 案例型） | 用户C（跳过全部微测） |
|---|---|---|---|
| 能力 `knowledge_base` | **score=100「扎实」** `source=diagnostic` | **score=0「薄弱」** `source=diagnostic` | **未测、无 score、`inferred` conf=0.2** |
| 依据 `basis` | 「答对 6/6…」逐知识点 | 「答错…」逐知识点 | 「全部跳过，不臆造分数」 |
| 4.4 能力雷达 | `[78,78,78,78,78,78]` | `[32,32,32,32,32,32]` | `[0,0,0,0,0,0]` |
| 概览综合分/水平 | 78.0 / 中级 | 32.0 / 初学 | 0.0 / 初学 |
| 偏好（归类型、无 score） | 图像型·快速概览型·概念混淆 | 案例型·稳步细钻型·代码卡壳 | （示例 visual/overview/concept） |
| 偏好混入 0-100 雷达轴 | 否 | 否 | 否 |

1. **能力靠测不靠说**：A 答得好→100、B 答得差→0，分数显著不同且带依据；空作答→未测/低置信、不臆造。✅
2. **偏好归类型不打分**：偏好选择不同→类型码不同（`visual`≠`example`…）；偏好维 `hasScore=False`、不出现在雷达轴。✅
3. **两用户对比**：能力画像（100 vs 0）、偏好画像（图像/快概 vs 案例/细钻）、综合分（78 vs 32）均明显不同。✅
4. **雷达不混轴**：能力维打分雷达（6 知识点轴）+ 偏好类型标签分区；`偏好是否混入雷达轴 = False`。✅
5. **重做覆盖 + 下游无回归**：PUT 覆盖刷新概览；概览/4.4/工作流诊断读新画像；全量 205 测试通过、tsc 干净。✅

## 六、红线自检

- ✅ **不改既有接口签名**：`kind`/`basis`/`optionKey`/`answer`/`interaction`/`preferences` 均为**追加**字段/事件；
  Mastery 加 3 个可空列 + 幂等迁移；旧客户端不带新字段仍可用（按 `key` 自动归类）。
- ✅ **复用现有 quiz 题库作微测来源、复用对话能力**；Mock 兜底：无 Key 全链路跑通（微测判分/偏好归类确定性合成）。
- ✅ **下游同步适配新结构、不回归**：4.4 / 12.1 / 确认弹窗 / 学情概览 / 工作流诊断读新画像；205 测试通过。
- ✅ **前端仅按本任务授权改呈现层 + services**：未改 Zustand store 结构 / 路由 / 业务逻辑（仅画像呈现与数据获取层）。
- ⚠️ **微测题量 6 题（每核心知识点 1 题）**：略多于建议的「3-5 题」——换取**能力雷达每轴都有实测依据、零臆造空轴**；
  「未测/低置信」由「空作答」路径（用户C）覆盖，符合验证1。
