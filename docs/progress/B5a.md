# B5-a — LangGraph 工作流骨架（纯 Mock provider）· 完成总结

> 阶段：B5 前半（B5-a）｜状态：✅ 完成（0 报错）｜日期：2026-06-11
> 范围：诊断/生成/审核三 Agent + LangGraph StateGraph + 审核低分重试 ≤2 / 降级标记
> + 全程 workflow trace 持久化（满足接口文档 11.2 渲染，B7 直接消费）。
> **不触碰任何既有 API 路由**：lecture/parse/narrative 仍走 B2 Mock service（B5-b 替换）。

## 1. 交付内容

### 三 Agent（`app/agents/`）

- 共用约定（`agents/__init__.py`）：prompt 一律经 `services.prompts.get_template()`
  **每次现读 DB**（消费 B4-b 热更新，管理端 PUT 后下一次调用立即生效，无进程内缓存）；
  占位符 `{var}` 直替渲染（`render_template`，不用 `str.format` 以免模板中普通花括号抛错）；
  渲染后 prompt 交 `LLMClient.complete()`，统一返回 `{agentId, name, prompt, output}`。
- `diagnostic_agent.py`：学情诊断（agentId=diagnosis），输出薄弱点清单 + 诊断摘要；
- `generator_agent.py`：讲义生成（agentId=generation），输入含 RAG 上下文；
  重试轮把上一轮 critic 反馈追加进 prompt（需求文档 4.2.2 `_construct_feedback` 思路）；
- `critic_agent.py`：内容审核（agentId=critic），输出
  `{passed, validationScore, hallucinationRate, issues}`。

### LangGraph 工作流（`app/workflows/learning_workflow.py`）

- **State**：TypedDict 按需求文档 9.3.1 定义（B5-a 用到的字段子集），
  `messages` / `error_details` 用追加 reducer、`node_execution_log` 用 `operator.add`，
  其余覆盖语义（9.3.2 规则）。
- **拓扑**（需求文档 4.2.1 / 9.3.3）：
  `diagnostic → retrieval → generation → validation` + 条件边
  `validation --retry--> generation`（评分 < 阈值 `0.8`，重试 ≤ `MAX_RETRIES=2`）、
  `accept/fallback → decision → END`；路由决策在 validation 节点落定
  （`validation_result.action`），`retry_count` 手动 +1 写回。
- **降级**：重试 2 次仍不过 → 仍交付最后一稿，`final_output` 标记
  `validation_score`（实测 0.42）与 `degraded: true` + `requiresReview: true`。
- **retrieval 节点**：B5-a 为确定性 mock 切片（结构对齐 B3 检索器
  `{id, content, metadata, score}`），retriever 可注入——B5-b 换真实 HybridRetriever
  与真实 LLM 时拓扑与 trace 结构不变。

### MockLLM 扩展（`app/core/llm.py`）

- 新增通用 `complete(prompt, *, agent_id, variables)`：mock 按 agent 类型返回
  **确定性结构化输出**（diagnosis→薄弱点清单；generation→复用 B2 讲义 markdown；
  critic→`validationScore=0.93 / hallucinationRate=0.021` 通过）。
- **测试钩子** `set_force_critic_low(True)`：强制 critic 恒返回低分
  （`validationScore=0.42, passed=False`），用于验证重试→降级路径；仅影响 mock。

### trace 持久化（`models/entities.py` 新增 `WorkflowTrace` 表）

每次运行落一行（`wf_xxx` 主键），结构满足接口文档 11.2 渲染（B7 `/workflow/{id}` 直接消费）：

| 字段 | 内容 |
|---|---|
| `agents`(JSON) | 11.2 `agents[]`：3 项固定 id/name（name 与 PromptTemplate 表逐字一致）/status/lastAction；降级时 critic 标 `error`（红灯） |
| `messages`(JSON) | 11.2 `messages[]`：id 从 1 自增、from/to/message/type(request\|response\|error)/timestamp |
| `node_log`(JSON) | 每节点 `{agent, name, startedAt, endedAt, durationMs, retryIndex, outputSummary, promptExcerpt}` |
| `rag_context_used`(JSON) | 本次生成实际使用的检索切片 |
| 标量列 | status(success\|degraded\|failed) / degraded / validation_score / hallucination_rate / retry_count / started_at / ended_at |

## 2. 文件清单

新增 7 个（≤8 上限）：

| 文件 | 说明 |
|---|---|
| `backend/app/agents/__init__.py` | Agent 共用：模板现读 + `{var}` 渲染 + 统一执行入口 `run_agent` |
| `backend/app/agents/diagnostic_agent.py` | 学情诊断 Agent |
| `backend/app/agents/generator_agent.py` | 领域知识生成 Agent（含重试反馈追加、RAG 上下文格式化） |
| `backend/app/agents/critic_agent.py` | 内容审核校验 Agent |
| `backend/app/workflows/__init__.py` | workflows 包说明 |
| `backend/app/workflows/learning_workflow.py` | StateGraph + 条件重试/降级 + trace 组装与持久化 |
| `backend/tests/test_workflow_b5a.py` | 5 条契约测试（TDD：先实测 RED 再实现转绿） |

既有文件改动：

| 文件 | 改动 | 既有路由影响 |
|---|---|---|
| `backend/app/core/llm.py` | 追加 `complete()` 通用补全 + 三类 mock 结构化输出 + `set_force_critic_low` 测试钩子 | 无（既有语义化方法未动） |
| `backend/app/models/entities.py` | 新增 `WorkflowTrace` 表（`create_all` 幂等自动建表） | 无 |
| `backend/requirements.txt` | 追加 `langgraph` | — |

## 3. 启动 / 验证命令

```bash
cd backend && pip install -r requirements.txt   # 新增 langgraph
cd backend && python -m pytest tests/ -q
cd backend && uvicorn app.main:app --port 8000  # 既有 30 接口不变
```

## 4. 验证实测（0 报错）

### ① pytest（TDD：先 RED——`set_force_critic_low` ImportError，实现后全绿）

```
$ python -m pytest tests/ -q
24 passed in 2.34s     （5 条 B5-a 新增 + 19 条既有，全绿）
```

5 条新增用例：MockLLM 按类型结构化输出与低分钩子 / happy path（trace 3 Agent
节点+耗时+11.2 结构+持久化）/ 强制低分→重试 2 次→降级标记 / PUT 模板热更新
后再跑新 prompt 生效 / 既有 `/resource/lecture` 无回归。

### ② 真实 DB 直跑（脚本实测输出，已捕获后删除临时脚本）

```
workflowId: wf_7f8addf906c1
degraded: False | score: 0.93 | retry: 0
nodes:
  diagnosis  retry=0 3.01ms  检测到 3 处知识盲区，建议优先学习「神经网络基础」
  rag        retry=0 0.09ms  检索到 3 条相关知识切片
  generation retry=0 0.73ms  讲义草稿生成完成（首次，418 字符）
  critic     retry=0 0.74ms  校验通过（评分 0.93，幻觉率 0.021）
agents[].name：学情诊断Agent / 领域知识生成Agent / 内容审核校验Agent（全 success）
messages: 6  ragChunks: 3  stats: {completedAgents: 3, messageCount: 6, progress: 100}

--- 强制低分（set_force_critic_low 测试钩子） ---
degraded: True | score: 0.42 | retry: 2
gen retryIndex: [0, 1, 2]            ← 首次 + 2 次重试
critic agent status: ['error']       ← 降级红灯
error messages: 第 1 次重试 / 第 2 次重试 / 已达最大重试次数 2，触发降级输出
persisted: degraded True 0.42 msgs: 10 rag: 3   ← WorkflowTrace 行持久化
```

### ③ 热更新（pytest 同口径）

PUT `generation` 模板（含哨兵串）→ 再跑工作流 → generation 节点
`promptExcerpt` 含哨兵且占位符已渲染（`{kpName}` 无残留）→ finally 还原模板。
证明 B5 生成链路与管理端 GET 走同一 `get_template` 现读路径。

## 5. 边界确认 / 给 B5-b 的约定

- **本阶段未改任何 API 路由**：`/resource/lecture`、`/profile/parse|narrative`
  仍由 B2 Mock service 提供（回归用例已覆盖）；B5-b 在 service 层换成
  `run_learning_workflow`，接口签名零改动。
- `run_learning_workflow(db, *, user_id, kp_id, difficulty, target_job, retriever)`：
  - `retriever` 注入点：B5-b 传 `HybridRetriever.search` 适配函数即可；
  - 返回 `{workflowId, finalOutput, trace}`，trace 即 11.2 响应 data 的超集
    （多 `nodes` / `ragContextUsed`），B7 `/workflow/{id}` 可直接取
    `WorkflowTrace` 行组装。
- `LLMClient.complete()` 的 `variables` 参数仅供 mock 产出确定性内容，
  真实 provider（B5-b）只发 prompt、忽略该参数。
- 阈值/重试常量在 `learning_workflow.py` 顶部
  （`VALIDATION_THRESHOLD=0.8`、`MAX_RETRIES=2`），B5-b 接 15.3 逐句接地
  口径时仅替换 critic 实现，路由逻辑不变。
- pytest 用例若使用 `set_force_critic_low`，必须在 fixture/finally 中复位 False。
