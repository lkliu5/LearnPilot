# TASK-003-E3 完成总结

## 文件清单

- `backend/app/agents/tools/registry.py`：集中注册并创建 `RAGTool`，保留通用扩展入口。
- `backend/app/agents/tools/__init__.py`：导出 Registry 能力。
- `backend/app/agents/resource_rag_shadow.py`：Resource Agent Legacy/Trusted RAG 并行 Shadow Adapter、事件与差异协议。
- `backend/tests/test_resource_rag_shadow.py`：并发、Legacy 权威性、事件、TrustReport、差异和 Tool 错误测试。
- `backend/tests/test_agent_rag_dependency_constraints.py`：Agent 目录 RAG 底层依赖静态检查。
- `docs/Agent-RAG Shadow接入报告.md`：Shadow 架构、对比、延迟、Evidence 与接入结论。
- `docs/progress/TASK-003-E3.md`：本阶段完成记录。

## 架构与范围

`ResourceGenerationRAGShadowAdapter` 并行执行 Legacy Resource Agent 和 Registry 提供的 RAGTool。Legacy `AgentMessage` 始终为权威结果；Trusted RAG 只生成 `tool.request`、`tool.result` 或 `tool.error` 事件以及无正文的 Evidence 引用差异。未修改 Workflow、API、前端和旧 Agent 业务逻辑。

## 验证

定向测试：

```bash
cd backend
python -m pytest -q tests/test_resource_rag_shadow.py tests/test_agent_rag_dependency_constraints.py tests/test_agent_rag_tool.py
```

实测结果：`11 passed in 0.82s`。

全量测试（Windows 沙箱内将 pytest 临时目录置于工作区）：

```bash
cd backend
python -m pytest -q --basetemp=.pytest_task003_e3_full
```

实测结果：`382 passed, 1 skipped, 1 warning in 155.34s`，0 failed、0 errors。warning 为既有 Starlette/httpx 弃用提示。

## TASK-003-E4 建议

1. 在独立执行器中采集真实 Resource 任务 Shadow 样本，避免在线请求线程和 SQLAlchemy Session 跨线程共享。
2. 增加 Tool 超时、并发/队列上限、熔断、取消和隔离舱，并把失败映射为结构化 WorkflowError。
3. 建立 Evidence 人工盲评与生成质量对照，联合评估引用准确率、接地率和内容质量。
4. 定义正式接入门槛：错误率、P95 延迟、来源覆盖、引用重合/差异和关键类型不退化。
5. 门槛通过后仅做小比例、可回滚灰度；E4 仍不建议一次性替换所有 Legacy `rag_context`。
