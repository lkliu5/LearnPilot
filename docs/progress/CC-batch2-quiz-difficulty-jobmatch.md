# CC 指令 · 批2 — 考核质量 + 难度诚实化 + 岗位匹配进诊断（问题 5 / 6 / 3）

> 第二轮测试的问题 5、6、3。三项相对独立，逐项修、逐项验。
> 全局纪律：已联调接口签名禁改、统一信封、Mock/真实双模式、复用优先、完成即停、0 报错。
> 口径：岗位匹配用**现有静态岗位数据**，本轮**不做岗位联网采集**。

═══════════════════════════════════════════════════════════════

# 角色
资深全栈工程师。项目已联调，禁止改既有接口签名。本会话修 3 项。

## 任务 1（问题 5）：阶段测试加量加类型 + 简答 AI 评分
**现状（先查并报告）**：当前测试题怎么生成的？几道、什么题型、及格线多少？
**修复目标**：
- **题量提到 10 道**；题型至少含 **单选 / 多选 / 判断**；**最后 1 道为简答题**。
- **简答题由 AI 评分**（经 `LLMClient` 对照参考要点给 0–100 分 + 简短点评；Mock 给确定性评分兜底）。
- **及格线 60 分**（综合客观题 + 简答得分）；通过仍走既有 quiz→Mastery（mark_pass）驱动已掌握。
- 前端渲染简答输入框 + 展示 AI 评分/点评；其余题型复用现有 QuizRenderer。
- 若需新增"简答评分"接口/字段，仅追加并同步接口文档（追加不重排）。

## 任务 2（问题 6）：难度收成"讲义专属"，UI 诚实化
**现状**：顶部"适配难度"像是全局设置，但实际只有讲义按难度生成（视频等各难度同一份），误导用户以为全资源分级。
**修复目标**：
- **难度控件归到「定制讲义」视图内**（与 S12 卡片化方向一致），不再以全局"适配难度"形式暗示所有资源分级。
- 顶部如保留难度信息，**明确标注为"讲义难度"**而非泛指全部资源。
- 不改其它资源的生成逻辑（本轮不扩展视频/图解按难度生成）。

## 任务 3（问题 3）：岗位匹配进诊断（用现有静态岗位数据，不联网）
**目标**：让"学情概览里的目标岗位信息"有真实出处，并补上岗位匹配度诊断。
- 对话诊断采集到**学习目标 / 目标岗位**后，用**现有 `/job-market` 静态岗位数据**计算**岗位匹配度 + 能力缺口**（画像维度/掌握度 与 该岗位所需技能的重合度；轻量匹配函数或新增 `/job-market/match`，套信封）。
- 在**诊断确认弹窗 / 学情概览**展示岗位匹配结果（目标岗位 + 匹配度 + 能力缺口），与概览里的目标岗位信息打通、口径一致。
- **不做联网采集**，只用现有静态岗位数据；保持轻量、不喧宾夺主。

# 约束
复用现有 quiz / QuizRenderer / job-market / portrait / 设计令牌，不重建；不改既有接口签名（新增仅追加并同步文档）；保留 Mock 兜底。

# 验证（逐项实测并贴结果）
1. 测试：生成 10 道、含单选/多选/判断 + 末尾 1 道简答；简答 AI 给分；综合 ≥60 及格 → 驱动已掌握。
2. 难度：难度控件在讲义视图内、顶部不再暗示全资源分级（标注为讲义难度）。
3. 岗位匹配：对话说出目标岗位后 → 诊断/概览出现匹配度 + 能力缺口，数据来自现有静态岗位库，与概览目标岗位一致。
4. 全量测试通过、既有接口回归未变、tsc 干净、mock 可跑。

# 输出
现状说明（任务1）+ 改动文件清单 + 接口文档增量（如有）+ 4 项验证结果 + 红线自检。完成即停。

═══════════════════════════════════════════════════════════════

## 提示
- 任务 1 的简答 AI 评分是新点——让它走 LLMClient、mock 有确定性兜底，别让无 Key 时崩。
- 任务 3 严格用现有静态岗位数据，**不要触发任何联网/爬取**（那是 C 赛题大工程，本轮不做）。
- 三项各自单独 commit。

═══════════════════════════════════════════════════════════════

# ✅ 完成总结（C-fix 批2）

## 任务 1 现状说明（修复前）
- 测验题来自 `backend/app/core/init_db.py` 的 `_QUIZ_QUESTIONS` 种子库，**每个知识点仅 3 道**
  （1 单选 + 1 多选 + 1 判断），无简答题。
- 及格线 60：`services/quiz.py` `submit` 按 `答对数/总题数×100`，`score≥60 → passed` 并联动
  Mastery（`mark_pass`，7.3）。前端 `QuizRenderer.tsx` 本地判分，仅支持 single/multiple/boolean。

## 改动文件清单
**任务 1（考核质量 + 简答 AI 评分）**
- `backend/app/core/llm.py`：新增 `SHORT_ANSWER_TYPE` 常量、字符二元组工具
  `_char_bigrams/_point_coverage`、`LLMClient.score_short_answer`（mock 确定性 / deepseek 真实 + 兜底）。
- `backend/app/services/quiz.py`：`submit` 综合判分（客观 + 简答 AI 折算）、回包追加 `shortAnswers[]`；
  `_list_questions` 排序修正（简答恒置末尾，客观按题号自然序）。
- `backend/app/core/init_db.py`：`_QUIZ_QUESTIONS` 每 KP 扩到 **10 题**（含末尾 1 道 short_answer）。
- `backend/tests/test_contract_snapshot.py`、`backend/tests/test_c2_learning_flow.py`：契约/回归断言适配。
- `frontend/src/components/QuizRenderer.tsx`：支持 short_answer（textarea 作答 + AI 评分/点评卡）；
  `grade` prop 回填综合判分。
- `frontend/src/services/resource.ts`：`QuizSubmitResult` 追加 `shortAnswers`。
- `frontend/src/pages/LearningResource.tsx`：mock 题库扩到 10 题 + 本地综合判分 `gradeQuizLocally`。
- `frontend/src/pages/LearningResource.css`：简答输入框 + AI 评分卡样式。

**任务 2（难度收成讲义专属，UI 诚实化）**
- `frontend/src/pages/LearningResource.tsx`：难度控件本就已在「定制讲义」详情内（`level-switch`，
  问题 5 已归位）；顶部徽章 `适配难度` → **`讲义难度`**；副标题「难度自适应」→「讲义按难度自适应生成」。

**任务 3（岗位匹配进诊断，静态数据）**
- `backend/app/services/job_market.py`：新增 `match_job`（画像 ability + Mastery 抬升 vs 岗位 radar）、
  `_user_ability`、`_resolve_job`（按学习目标文本映射现有静态岗位库，不联网）。
- `backend/app/api/v1/job_market.py`：新增 `POST /job-market/match`（套信封；无法解析 → 1004）。
- `frontend/src/services/jobMatch.ts`（新增）：`getJobMatch`（联调走后端 / mock 本地对标，同口径）。
- `frontend/src/components/ProfileDialogue.tsx`：对话采集目标岗位后算匹配，传入确认弹窗 + 完成流程。
- `frontend/src/components/ProfileConfirmModal.tsx`（+`.css`）：展示目标岗位 + 匹配度 + 能力缺口。
- `frontend/src/pages/ProfileBuilder.tsx`：`finish(jobInfo?)` 透传对话路径岗位匹配到 `completeDiagnosis`。

## 接口文档增量（`docs/后端接口文档.md`，追加不重排）
- 2.5 QuizQuestion：`question_type` 增 `short_answer`（options 空 / correct_answer=参考要点 / explanation=参考答案）。
- 9.1 提交作答：题量 10 含简答、综合判分口径、回包追加 `shortAnswers[]`。
- 5.3（新增）`POST /job-market/match`：岗位匹配度 + 能力缺口（静态对标，不联网）。
- 13 接口总览表：新增第 9b 行。

## 验证结果（live 实测 + 测试）
1. **测试加量加类型 + 简答 AI 评分**：`GET /quiz/nn` 返回 10 题
   `{single:4, multiple:2, boolean:3, short_answer:1}`，**末题为 short_answer**（顺序修正后 q1→q10）。
   `POST /quiz/nn/submit` 客观全对 + 简答按要点作答 → `score:100 passed:true correctCount:9/10`，
   `shortAnswers:[{questionId:nn_q10, score:100, comment:"完整覆盖前向/反向传播…"}]`，
   `masteryUpdated:{id:nn,status:passed}`；简答空作答 → 该题 0 分、综合 90 仍通过（客观 9/10）。
2. **难度诚实化**：难度控件在「定制讲义」详情内；顶部徽章标注为「讲义难度」，副标题不再泛指全资源分级。
3. **岗位匹配**：`POST /job-market/match {goal:"想转大模型应用方向…"}` →
   `大模型应用工程师 matchPct:50%`，gaps top3（大模型微调 20/88、Transformer 30/92、注意力机制 45/85），
   用户能力 `[85,82,82,45,30,20]`（神经网络/深度学习经已掌握 Mastery 抬升至 82）vs 岗位需求
   `[70,72,78,85,92,88]`；无目标岗位文本 → `code 1004`；`/job-market/hot`、`/job-market/{id}` 回归未变。
4. **全量**：`pytest` **182 passed, 1 skipped, 0 失败**；`tsc --noEmit` **0 报错**；mock 模式（无 Key）简答确定性兜底可跑。

## 红线自检
- 既有接口签名未改：仅**追加** `shortAnswers` 字段、**新增** `POST /job-market/match`，路径/字段名/枚举值未动。
- 统一信封：新增接口套 `{code,message,data,traceId}`。
- 复用优先：复用 quiz/QuizRenderer/job-market/ability-portrait/portrait/设计令牌，无重建。
- Mock/真实双模式：简答评分、岗位匹配均双模式；无 API Key 不崩（确定性兜底）。
- 任务 3 仅用现有静态岗位库，**未触发任何联网/爬取**。
