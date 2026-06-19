# CC 指令 · 批3 — 学习过程评估能力（评估 Agent + 行为数据 + UI）

> 新增「学习过程评估」：行为数据层 + 评估 Agent（经 LLMClient，mock 兜底）+ 学情概览评估面板。
> 全局纪律：已联调接口签名禁改、统一信封、Mock/真实双模式、复用优先、完成即停、0 报错。

═══════════════════════════════════════════════════════════════

## 现状说明（修复前）
- **无专门的学习评估 Agent**：`app/agents/` 仅有 critic / diagnostic / dialogue / feynman /
  generator / planner。
- **无学习行为跟踪数据**：`quiz.submit` 判分后**不落库**（无做题历史）；无资源使用 / 停留 /
  进度事件表。仅有 Mastery（三态）、Journey（诊断/路径标志 + 目标岗位）、LearningStepProgress
  （6 步完成）、LearningNote（康奈尔笔记）、StudentPortrait（6 维画像）、WorkflowTrace。
- **学情概览**（`GET /dashboard/overview`）只聚合 Mastery + 画像，**非过程评估**。

## 改动文件清单
**新增（6）**
- `backend/app/services/learning_eval.py`：行为数据层——`gather_signals`（复用 Mastery/Journey/
  QuizAttempt/Steps/Notes 汇总真实信号）+ `compute_metrics`（确定性多维指标 + 综合分 + 趋势 + 薄弱点）。
- `backend/app/agents/evaluation_agent.py`：学习评估 Agent——编排 信号 → 指标 → LLM 叙述。
- `backend/tests/test_learning_eval.py`：契约 + 因人而异 + 埋点 三用例。
- `frontend/src/services/learningEval.ts`：`getLearningEvaluation`（联调）+ `synthesizeEvaluation`（mock 兜底）。
- `frontend/src/components/LearningEvalPanel.tsx`（+ `.css`）：学情概览「学习评估」面板。

**修改**
- `backend/app/models/entities.py`：新增 `QuizAttempt` 埋点表（无外键耦合，不改既有表）。
- `backend/app/services/quiz.py`：`submit` 落一行 `QuizAttempt`（与判分解耦）。
- `backend/app/core/llm.py`：新增 `LLMClient.evaluate_learning`（综述 + 方法建议 mock/deepseek，
  动态调整确定性派生）。
- `backend/app/api/v1/dashboard.py`：新增 `GET /dashboard/evaluation`（套信封）。
- `frontend/src/pages/Dashboard.tsx`：加载评估 + 渲染评估面板（联调取后端 / mock 合成）。

## 接口文档增量（`docs/后端接口文档.md`，追加不重排）
- 12.2（新增）`GET /dashboard/evaluation`：多维评估 + 方法建议 + 动态调整，行为数据来源说明。
- 13 接口总览表：新增第 29b 行。

## 验证结果（live 实测 + 测试 + UI）
1. **因人而异（真实行为驱动）**：
   - 零行为新用户 → `overallScore 10 / 刚刚起步`，四维 `[0,0,50,0]`，薄弱点=前 3 个核心知识点，
     `attemptCount 0`、下一步=机器学习基础。
   - 同用户做题通过 nn 后 → `overallScore 56`，四维 `[mastery 17, quiz 99, eff 100, engage 4]`，
     `attemptCount 1 / masteredCount 1`（**埋点生效**），nn 退出薄弱点，下一步=机器学习基础；
     综述/建议由 deepseek 真实生成，动态调整确定性派生。
2. **UI 出现评估卡**：学情概览顶部「学习过程评估」面板渲染——综合分 + 等级 + 趋势、四维指标条、
   学习综述、学习方法建议、薄弱点 chips、动态调整建议（含「去学『CNN架构』→」跳转）。learner_001
   实测：3/6 已掌握、13 步骤、5 份笔记 → overall 42 / 起步阶段（浏览器 0 console error）。
3. **mock 可跑**：`test_learning_eval.py` 在 mock provider 下 3 用例通过（确定性兜底、无 Key）。
4. **回归 + 类型**：`pytest` **185 passed, 1 skipped, 0 失败**；`tsc --noEmit` **0 报错**。

## 红线自检
- 既有接口签名未改：仅**新增** `GET /dashboard/evaluation` + **新增** `quiz_attempts` 埋点表
  （无外键、不改既有表）；`quiz.submit` 仅追加埋点写入，回包字段不变。
- 统一信封：新增接口套 `{code,message,data,traceId}`。
- 复用优先：评估信号全部复用既有 Mastery/Journey/Steps/Notes，未重建数据链路。
- Mock/真实双模式：评估综述/建议 mock 确定性 / deepseek 真实，动态调整恒确定性；无 Key 不崩。
- **全部评估数值由真实行为派生、因人而异，禁止臆造**（新用户归 0 / 中性）。
