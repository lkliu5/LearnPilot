# TASK-003-D3-B 完成总结

## 文件清单

- `backend/app/rag/reranker.py`：新增 offline-only 真实 CrossEncoder Adapter。
- `backend/app/rag/rerank_evaluation.py`：新增 query type 分层与 rank change 统计。
- `backend/scripts/evaluate_rerank.py`：真实模型实验、环境记录、权重哈希和候选快照。
- `backend/tests/test_rerank_evaluation.py`：补充新统计回归断言。
- `backend/evaluation/rerank_real_candidates_d3b.json`：40 条固定 Hybrid Top20 候选快照。
- `backend/evaluation/rerank_real_results_d3b.json`：真实实验完整结果。
- `docs/Real-Reranker离线实验报告.md`：实验报告与接入结论。

## 验证结果

- 真实模型实验：成功，40/40 query 完成，未使用 Mock 或降级。
- 定向测试：`2 passed in 0.61s`。
- 完整测试：`363 passed, 1 skipped, 1 warning in 188.75s`，0 failed。
- 范围核对：未修改 Agent、Workflow、API、生产 Retriever 或生产 RAG 入口。
