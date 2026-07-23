# TASK-005-D 学习事件真实旁路接入与知识状态 Shadow 积累

## 完成范围

- Quiz、Diagnostic、Feynman、Learning Step 四类真实业务成功点接入 LearningEvent 旁路；
- 固化四类 source_id 与确定性 event_id 规则；
- 新增用户数、节点数、Event 数、来源分布、mastery/confidence 变化统计；
- 新增重复证据、event_id 载荷冲突、短窗口证据冲突治理和异常审计表；
- 冲突只降低 Shadow confidence，不改变 Shadow mastery，更不写线上 Mastery；
- 未修改 Agent、Workflow、RAG、前端、接口路径/字段/枚举或响应行为。

## 修改文件

### 新增（3 个）

- `backend/tests/test_learning_event_sidecar.py`
- `docs/Learning-State Shadow积累报告.md`
- `docs/progress/TASK-005-D.md`

### 修改

- `backend/app/api/v1/learning.py`（仅向内部费曼服务透传已鉴权 user id，响应不变）
- `backend/app/models/entities.py`
- `backend/app/services/knowledge_state.py`
- `backend/app/services/knowledge_state_shadow.py`
- `backend/app/services/learning_evidence.py`
- `backend/app/services/learning_flow.py`
- `backend/app/services/profile_dialogue.py`
- `backend/app/services/quiz.py`
- `backend/tests/test_learning_evidence_shadow.py`

本阶段新增文件 3 个，符合每阶段新增文件不超过 8 个的约束。

## 启动命令

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

应用启动时 `init_db()` 会幂等创建 Shadow Event、状态及异常审计表。无 API Key、Mock 模式可运行全部链路。

## 验证命令与实测结果

定向知识状态/旁路测试：

```bash
python -m pytest -q tests/test_knowledge_state.py tests/test_learning_evidence_shadow.py tests/test_learning_event_sidecar.py --basetemp F:\软件杯\backend\.pytest_task005_d_focus
```

```text
11 passed in 2.38s
```

学习流程、诊断与契约回归：

```bash
python -m pytest -q tests/test_c2_learning_flow.py tests/test_dialogue_profile.py tests/test_contract_snapshot.py --basetemp F:\软件杯\backend\.pytest_task005_d_integration
```

```text
72 passed, 1 warning in 14.29s
```

全量后端测试：

```bash
python -m pytest -q --basetemp F:\软件杯\backend\.pytest_task005_d_full
```

```text
467 passed, 1 skipped, 1 warning in 109.44s (0:01:49)
```

0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

## Shadow 实测统计

- 用户数量：1；用户-知识节点数量：1；Event 数量：4；四来源各 1；
- mastery：0.780000 → 0.945410，变化 +0.165410；
- confidence：0.450000 → 0.909267，变化 +0.459267；
- 冲突用例确认 confidence 乘 0.75，mastery 计算值不变；
- 重复投递确认 2 次调用只落 1 个 Event；
- Shadow 采集前后线上 `Mastery` 全表快照一致。

## TASK-005-E 建议

下一阶段只做 7/30 天 Shadow 观测与校准门槛：增加按来源/节点/活跃度分层的漂移和阈值迁移报告，评估 session 内证据聚合上限与冲突参数，并建立跨阈值人工抽样清单。未通过离线回放和人工评审前，继续禁止写回 Mastery、驱动学习路径或改变 API 行为。
