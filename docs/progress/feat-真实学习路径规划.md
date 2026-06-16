# feat：真实学习路径规划 Agent（接口文档 6.2 真实化）

## 背景 / 现状（改造前）

`/learning-path/generate` 为**写死的假完成**：worker `await asyncio.sleep(1.5)` 后仅置
`journey.has_generated_path=True`，返回 B1 全局种子 6 课（`init_db._LESSONS`，所有用户
一模一样）。GET `/learning-path` 同样读全局种子表，**与画像/掌握度无关**，不同学生路径相同。

真实规划所需输入源均已就绪、本次全部复用（不重建）：
- StudentPortrait（6 维画像，含 knowledge_base.score）：`services/student_portrait.py`
- Mastery（kpId→learning/pending-check/passed）：`services/mastery.py`
- 目标岗位需求（2.4 radar）：`Journey.target_job_name` + `targetJobId` → `JobSnapshot.payload.radar`
- 已生成资源（讲义/思维导图/图解/视频/题库/外部精选）：`services/resource.py`、`services/quiz.py`
- LLM 适配层：`core/llm.py` `LLMClient`（mock 默认 / deepseek 可选）

## 改动文件清单

**新增（2）**
- `app/agents/planner_agent.py`：个性化规划 Agent。确定性优先级打分（先修骨架=lesson_seq；
  passed +100 后置；未掌握不惩罚 → 前置；基础分低降难度加固、高升难度略读；岗位高需求标重点）
  → 重排 sequence 1..6、按掌握度派生 status/progress、按基础分自适应难度、每步推送 6 类资源；
  理由叙述经 `LLMClient.plan_path`。
- `tests/test_learning_path_planner.py`：5 用例（路径形态/双画像差异/薄弱优先后置/岗位影响/资源可点开）。

**修改（5）**
- `app/core/llm.py`：新增 `LLMClient.plan_path()`（mock 模板 / deepseek 真实生成+契约清洗+回落）；
  新增 `PATH_DIFFICULTIES` 常量。
- `app/api/v1/learning_path.py`：generate 改调 `planner_agent.plan_path` 并落 `Journey.path_plan`；
  GET 优先返回个性化路径，未生成回落种子路径。任务 `result` 仍严格 `{lessons}`（15.2 不变）。
- `app/models/entities.py`：`Journey` 新增 `path_plan`(JSON, nullable) 存个性化路径快照（缓存）。
- `app/core/init_db.py`：新增 `_migrate_path_plan()` 轻量迁移（既有库补 path_plan 列，幂等）。
- `docs/后端接口文档.md`：新增 6.3「真实规划增量」，文档化 Lesson 的 additive 字段
  `kpId/reason/resources`（仅追加不重排）。

## 接口文档增量

- 路径/层级/原字段**全部不变**；Lesson 在路径接口新增 3 个 **additive** 字段：
  `kpId`、`reason`、`resources[]`（见接口文档 6.3）。任务 `result` 仍 `{lessons}`。
- 未生成个性化路径的用户 → GET 回落全局种子 6 课（仅原六字段，向后兼容）。

## 启动 / 验证命令

```bash
cd backend && pytest -q                                   # 全量回归
cd backend && pytest tests/test_learning_path_planner.py -q  # 本特性
cd backend && uvicorn app.main:app --reload --port 8000   # 联调
```

## 验证结果（实测）

1. **双画像差异 → 路径不同**（mock，无密钥）：
   - A（零基础+目标 llm-app，全未掌握）：`机器学习基础→神经网络基础→深度学习原理→CNN架构→Transformer架构→大模型微调技术`，难度入门起。
   - B（基础扎实+ml/nn 已掌握）：`深度学习原理→CNN架构→Transformer架构→大模型微调技术→机器学习基础→神经网络基础`，难度更高。
   - 顺序不同 = True。
2. **薄弱优先 / 已掌握后置**：B 中 passed 的 ml/nn → status=completed 且排到末段（第 5、6 步），
   未掌握点占据前 4 步；`min(已掌握 seq) > max(未掌握 seq)` 成立。
3. **资源可点开**：每步 6 类资源指向真实 kpId；实测 GET /quiz/{kp}=3 题、/resource/external/{kp}=4 条、
   POST /resource/lecture markdown 长度 422，均 200。
4. **顺序 + 理由**：sequence 1..6 连续，每步 `reason` 非空且扣住信号（基础/薄弱/已掌握/岗位重点）。
5. **mock 无密钥跑通**：`llm_provider=mock` 全链路 generate→poll(succeeded)→GET 正常。
6. **全量测试**：`138 passed, 1 skipped`（既有 137 + 新增 5，无回归；contract 快照 test_10/11/30 不变）。

## 红线自检

- ✅ `/learning-path/generate` 请求体、响应 `{taskId}`、任务 `result {lessons}` 字段/层级不变。
- ✅ GET 三键 `{lessons,milestones,summary}` 结构不变；Lesson 原六字段不变，新增字段仅追加并写入接口文档 6.3。
- ✅ 仅改 `services/`→无（数据来源切换在 agent/api 层）；未动 `frontend/src`。
- ✅ 复用 portrait/mastery/job/resource/quiz 既有服务，未重建。
- ✅ 保留 mock 兜底：无密钥确定性可跑通，演示稳定优先；deepseek 失败回落模板。
- ✅ 缓存：首次生成落 `Journey.path_plan`，其后 GET 命中（同画像不重复规划）。
