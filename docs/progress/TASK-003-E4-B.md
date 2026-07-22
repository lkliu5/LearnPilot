# TASK-003-E4-B 完成总结

## 任务

`TASK-003-E4-B Agent-RAG Shadow 指标采集体系`

前置：`TASK-003-E3`（`2c3aec2`）。本阶段只采集和分析，不切换生产。

## 修改文件

- `backend/app/agents/resource_rag_shadow.py`：标准化 `shadow.*` 事件、三层耗时采集、错误根因类型、独立 worker 内 Tool 创建和可选指标 Sink。
- `backend/app/agents/shadow_metrics.py`：线程安全有界指标收集器及性能/质量聚合协议。
- `backend/tests/test_resource_rag_shadow.py`：更新 E4-B 标准事件、敏感正文禁止和 Legacy 权威性断言。
- `backend/tests/test_agent_rag_shadow_metrics.py`：指标统计、真实 SQLAlchemy Session 隔离、并发、Sink 故障隔离和容量边界测试。
- `docs/Agent-RAG Shadow指标报告.md`：指标设计、采集方案、当前样例结果和接入门槛建议。
- `docs/progress/TASK-003-E4-B.md`：本阶段完成记录。

## 指标体系

- Event：`shadow.request`、`shadow.result`、`shadow.error`。
- 性能：total/RAG/Tool latency、P50、P95、timeout rate、error rate。
- 质量：Evidence overlap、Source coverage、Confidence distribution、Reason codes。
- 安全：不记录 query、用户信息、知识/Evidence/Legacy 正文或异常消息。
- 隔离：Tool 与其会话型依赖在 Shadow worker 内创建；采集失败不影响 Legacy 结果。

## 验证

定向测试命令：

```bash
cd backend
python -m pytest -q \
  tests/test_resource_rag_shadow.py \
  tests/test_agent_rag_shadow_metrics.py \
  tests/test_agent_rag_dependency_constraints.py
```

最终定向实测：`12 passed in 3.64s`，0 failed、0 errors。

全量测试命令：

```bash
cd backend
python -m pytest -q --basetemp=.pytest_task003_e4b_shadow_final
```

实测结果：`389 passed, 1 skipped, 1 warning in 120.30s`，0 failed、0 errors。warning 为既有 Starlette/httpx 弃用提示。
