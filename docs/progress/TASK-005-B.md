# TASK-005-B 知识状态模型工程实现

## 完成范围

本阶段只实现知识状态数据模型、持久化记录、服务协议与测试；未修改 API 入口、Agent、Workflow、RAG 或前端。

## 文件清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `backend/app/models/entities.py` | 修改 | 新增知识状态快照表与学习事件历史表 |
| `backend/app/schemas/knowledge_state.py` | 新增 | 定义 `KnowledgeNode`、`UserKnowledgeState`、`LearningEvent` 及事件枚举 |
| `backend/app/services/knowledge_state.py` | 新增 | 定义服务 Protocol，并实现查询、更新、历史记录和乱序事件重放 |
| `backend/tests/test_knowledge_state.py` | 新增 | 覆盖状态创建、更新计算、历史记录、数据完整性 |
| `docs/progress/TASK-005-B.md` | 新增 | 本阶段完成总结 |

本阶段新增文件 4 个，符合单阶段新增文件不超过 8 个的约束。

## 数据模型设计

### KnowledgeNode

- `id`：知识节点唯一标识。
- `name`：知识节点名称。
- `description`：知识节点说明。
- `difficulty`：归一化难度，范围 `[0, 1]`。
- `prerequisites`：先修节点 id 列表；禁止空值、重复和自依赖。

该模型是现有 `KnowledgePoint` 的算法层视图，不新增重复知识目录表，也不改变既有接口字段。

### UserKnowledgeState

- `user_id`、`knowledge_id`：共同唯一定位一个用户的节点状态。
- `mastery_score`：连续掌握度，范围 `[0, 1]`。
- `confidence`：证据置信度，范围 `[0, 1]`，与掌握度分离。
- `last_updated`：最近有效事件时间，领域协议统一为 UTC 时区时间。

数据库表 `user_knowledge_states` 保存最新快照，具有用户/节点唯一约束、引用约束和数值 CheckConstraint；不替换或改写既有对外 `Mastery` 三态。

### LearningEvent

- `user_id`、`knowledge_id`：事件归属。
- `event_type`：`quiz | practice | feynman | diagnostic | retrieval | learning_step | self_report`。
- `score`：归一化表现，范围 `[0, 1]`。
- `timestamp`：事件发生时间，输入必须携带时区。

数据库表 `learning_events` 采用追加式历史，保留每次状态变化的原始依据；事件类型、分数和引用关系均有约束。

## 服务协议

`KnowledgeStateServiceProtocol` 与 `KnowledgeStateService` 提供：

- `get_state(user_id, knowledge_id)`：查询节点最新状态，无快照返回 `None`。
- `update_state(event)`：校验用户和知识节点，追加事件，按完整时间序列重放并创建/更新快照。
- `get_history(user_id, knowledge_id=None)`：按事件时间与内部序号稳定排序，可查询单节点或用户全部历史。

服务保持独立，当前没有注册到 API，也没有注入 AgentState 或任何 Workflow。

## 更新算法

算法版本为 `ks-logodds-v1`，参数集中在服务模块。初始掌握度取中性先验 `0.5`，初始置信度取 `0`。相邻事件间按固定时间尺度向中性先验衰减：

```text
p_prior = 0.5 + (p_previous - 0.5) * exp(-days / 30)
c_prior = c_previous * exp(-days / 60)
```

再按 TASK-005-A 的事件权重执行确定性 log-odds 更新：

```text
L_post = logit(p_prior) + 2.0 * event_weight * (2 * score - 1)
p_post = sigmoid(L_post)
c_post = 1 - (1 - c_prior) * exp(-event_weight)
```

权重为 quiz `1.00`、practice `0.90`、feynman `0.70`、diagnostic `0.55`、retrieval `0.50`、learning_step `0.15`、self_report `0.10`。因此测验/实操是强证据，学习步骤和自述只能产生弱更新。迟到事件会按时间顺序重放，避免直接覆盖最新快照。

这些参数是工程初值，不宣称已经过教育数据校准。

## 启动命令

本阶段不新增独立进程，沿用后端启动方式：

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

应用现有 `init_db()` 会通过 SQLAlchemy metadata 自动创建新增表。

## 验证命令与实测结果

定向测试：

```powershell
cd backend
python -m pytest -q tests/test_knowledge_state.py --basetemp=.pytest_task005_b_focus
```

实测：`4 passed in 2.79s`。

全量回归：

```powershell
cd backend
python -m pytest -q --basetemp=.pytest_task005_b_final
```

实测：`460 passed, 1 skipped, 1 warning in 165.90s`，0 error。唯一 warning 为既有 FastAPI TestClient 的 Starlette/httpx 弃用提示。

首次未指定 `--basetemp` 的全量运行因 Windows 中文用户名临时目录权限产生 9 个 setup error；显式使用仓库内可写临时目录后连续两轮全量回归均为 0 error，最终结果以上述末轮为准。

## TASK-005-C 建议

下一阶段建议只做“现有学习证据适配与影子计算”，仍不直接替换线上 `Mastery`：

1. 为 `QuizAttempt`、诊断微测、费曼结果和学习步骤建立到 `LearningEvent` 的确定性适配器。
2. 增加来源事件幂等键和算法版本落库，支持重复投递去重与跨版本回放对比。
3. 用历史 `QuizAttempt` 离线回放，评估 Brier Score、校准曲线和下一次测验通过预测。
4. 以 shadow 模式对比新状态与现有 Mastery/路径结果，只记录差异，不影响 API、Agent 或 Workflow。
5. 校准通过后，再单独评审是否进入 Agent Workflow 事件接入和 KAP 局部重规划。
