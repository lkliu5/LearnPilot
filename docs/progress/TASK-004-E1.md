# TASK-004-E1 完成总结

## 任务

Trusted RAG 灰度准入 Gate 实现。仅新增 Gate、离线评估、测试与文档，没有修改生产入口。

## 修改文件

- `backend/app/rag/trusted_rag_gate.py`：Shadow、Fault、Rerank 输入模型与 fail-closed `TrustedRAGGate`。
- `backend/scripts/evaluate_trusted_rag_gate.py`：离线准入 CLI。
- `backend/evaluation/trusted_rag_gate_decision.json`：当前证据的机器可读 Canary Decision。
- `backend/tests/test_trusted_rag_canary_gate.py`：6 类 Gate 测试。
- `docs/Trusted-RAG灰度准入方案.md`：阈值、阻断、当前结论与 E2 建议。
- `docs/progress/TASK-004-E1.md`：本阶段完成记录。

## Gate 结果

当前 `quality_pass=false`、`latency_pass=false`、`reliability_pass=false`、`rerank_pass=false`，最终 `BLOCK`。

主要原因：正式 Shadow 指标与目标环境 P95 缺失；故障注入 `10 PASS / 1 BLOCK`、失败率 `9.0909%`；硬挂死场景未隔离；Rerank 指标仍为 provisional、人工复核未完成且有 2 个退化案例。

回滚建议为 `keep_legacy_and_set_canary_weight_to_zero`。该建议不会由离线 Gate 自动执行。

## 验证命令与实测

定向测试：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q tests/test_trusted_rag_canary_gate.py
```

实测：`6 passed in 0.78s`，0 failed、0 errors。

离线评估：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/evaluate_trusted_rag_gate.py
```

实测：退出码 0，生成 `evaluation/trusted_rag_gate_decision.json`，`final_decision=BLOCK`，`rollback_recommended=true`。

相关回归：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q `
  tests/test_trusted_rag_canary_gate.py `
  tests/test_trusted_rag_fault_injection.py `
  tests/test_rerank_blind_evaluation.py `
  tests/test_agent_rag_shadow_metrics.py
```

实测：`24 passed in 0.72s`，0 failed、0 errors。

全量回归：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q --basetemp='.pytest_task004_e1_full'
```

实测：`420 passed, 1 skipped, 1 warning in 114.93s`，0 failed、0 errors。warning 为既有 Starlette/httpx 弃用提示。

## 未修改范围

- 未修改 API；
- 未修改 Agent；
- 未修改 Workflow；
- 未修改生产 RAG 入口；
- 未修改 frontend；
- 未执行 Canary 切流或回滚动作。
