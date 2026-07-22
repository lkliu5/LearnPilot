# TASK-003-E1 完成总结

## 文件清单

- `backend/app/rag/service.py`：新增 `RAGService`，统一适配 `TrustedRetrievalPipeline`，保留 traceId、阶段耗时与 Rerank Gate shadow 决策。
- `backend/tests/test_rag_service.py`：新增 Service 层 Pipeline、Evidence、TrustReport、shadow、traceId、耗时与日志安全测试。
- `docs/progress/TASK-003-E1.md`：本阶段完成记录。

## RAG Service 架构

`RAGService.retrieve(RAGRequest) -> RAGResponse` 是未来 Agent 与 Trusted Retrieval Pipeline 之间的稳定服务边界。Service 只负责编排和可观测性，不复制检索逻辑，也不修改 Evidence 或 TrustReport。默认 Pipeline 由 `get_trusted_retrieval_pipeline()` 提供；测试和后续集成可注入兼容 `execute()` 的实现。

Rerank Gate 仅以 shadow 模式运行：根据查询类型与 Pipeline 返回的 retrieval confidence 记录决策，但 `applied=false`，不改变 Evidence 内容和顺序。未提供分类器时查询类型为 `unclassified`，避免把未经验证的分类推断用于排序。

Service 从显式参数或当前请求上下文继承 traceId，并在 `RAGResponse.metadata.traceId` 中返回。`serviceObservability` 记录 Pipeline、shadow Gate 和 Service 总耗时；日志只记录 traceId、耗时、证据数量和模式，不记录 query、user_id 或知识正文。

## 调用链变化

```text
未来 Agent / Workflow（本阶段未接入）
  -> RAGService.retrieve(RAGRequest)
     -> TrustedRetrievalPipeline.execute(RAGRequest)
        -> QueryPlan -> Retriever -> Evidence -> TrustReport
     -> OfflineRerankGate.decide(...) [可选 shadow，旁路不生效]
  <- RAGResponse + traceId + serviceObservability + rerankShadow
```

现有 Agent、Workflow、API 和前端调用链均未修改。

## 启动与验证

启动命令：

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

定向测试：

```bash
cd backend
python -m pytest -q tests/test_rag_service.py tests/test_trusted_retrieval_pipeline.py tests/test_rerank_gate.py
```

实测结果：`14 passed in 0.60s`。

全量测试（Windows 沙箱内将 pytest 临时目录置于工作区）：

```bash
cd backend
python -m pytest -q --basetemp=.pytest_task003_e1_full
```

实测结果：`371 passed, 1 skipped, 1 warning in 109.64s`，0 failed、0 errors。warning 为既有 Starlette/httpx 弃用提示。

## TASK-003-E2 建议

1. 在不改变 Agent 业务行为的前提下，先定义 Agent 侧 RAG Tool/Port 协议与依赖注入方式。
2. 为 query type 分类建立独立、可版本化的组件，避免把当前 40 条评测集规则固化到 Service。
3. 接入 shadow 指标聚合：Gate 启用率、reason 分布、增量耗时 P50/P95、分类分布与 trace 关联。
4. 增加超时、并发上限、熔断和异常回退测试后，再评审是否允许 Rerank 影响生产排序。
5. 保持 Agent 只消费 `RAGResponse` 的 Evidence 与 TrustReport，不直接访问 Retriever 或 Reranker。
