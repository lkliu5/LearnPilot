# TASK-003-E2 完成总结

## 文件清单

- `backend/app/agents/tools/__init__.py`：导出 Agent RAG Port、Tool 与标准化错误。
- `backend/app/agents/tools/rag_tool.py`：新增 `AgentRAGPort`、`RAGTool` 和 `RAGToolError`。
- `backend/tests/test_agent_rag_tool.py`：新增 Tool 调用、响应透传、TrustReport、traceId 与错误处理测试。
- `docs/progress/TASK-003-E2.md`：本阶段完成记录。

## Agent-RAG Tool 架构

`AgentRAGPort` 是 Agent 侧最小能力协议，只公开：

```text
search(query, knowledge_scope, top_k) -> RAGResponse
```

`RAGTool` 是该 Port 的默认适配器。它在构造时绑定 `user_id` 与 traceId，将 `search()` 参数转换为严格的 `RAGRequest`，再调用 `RAGService.retrieve()`。成功响应保持 `RAGResponse` 类型，Evidence、TrustReport、traceId、Pipeline observability 和 Service observability 均不重组、不丢失。

Tool 会校验 Service、Tool 与响应 traceId 一致。请求校验、Service 调用或响应契约发生异常时，统一抛出 `RAGToolError` 并保留原异常链；对外错误和日志只包含 traceId 与异常类型，不记录 query、user_id、Evidence 正文或可能携带正文的异常消息。

## 依赖关系变化

```text
未来业务 Agent（本阶段未迁移）
  -> AgentRAGPort.search(...)
     -> RAGTool
        -> RAGService.retrieve(RAGRequest)
           -> TrustedRetrievalPipeline
  <- RAGResponse
```

依赖规则：

- Agent 只面向 `AgentRAGPort` / `RAGTool.search()`。
- `RAGTool` 只依赖 `RAGService` 与 RAG 请求/响应协议。
- Agent Tool 层不依赖 Retriever、VectorStore、Embedding 或 Reranker。
- 现有 Agent、Workflow、API 与前端调用链均未修改。

## 启动与验证

启动命令：

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

定向测试：

```bash
cd backend
python -m pytest -q tests/test_agent_rag_tool.py tests/test_rag_service.py app/agents/test_framework.py
```

实测结果：`16 passed in 0.62s`。

全量测试（Windows 沙箱内将 pytest 临时目录置于工作区）：

```bash
cd backend
python -m pytest -q --basetemp=.pytest_task003_e2_verify
```

实测结果：`377 passed, 1 skipped, 1 warning in 88.70s`，0 failed、0 errors。warning 为既有 Starlette/httpx 弃用提示。

## TASK-003-E3 建议

1. 建立 Tool Registry/Factory，按任务上下文统一绑定 userId、traceId、权限和知识范围，禁止 Agent 自行实例化底层 RAG 组件。
2. 先选择一个非关键或新建 Agent Adapter 做单点 shadow 接入，旧 `rag_context` 主链保持不变并对比 Evidence 差异。
3. 将 Tool 调用投影为版本化 `tool.request` / `tool.result` / `task.failed` 事件，只保存 Evidence 引用和可观测指标。
4. 增加权限范围、超时、取消、重试预算及 Tool 错误到 `WorkflowError` 的映射测试。
5. 在迁移任何业务 Agent 前冻结 `AgentRAGPort` 契约快照，并增加静态依赖检查，阻止 Agent 直接导入 RAG 底层组件。
