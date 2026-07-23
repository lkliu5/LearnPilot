# TASK-004-E4-C 完成记录

## 文件清单

- `backend/app/rag/trusted_rag_canary.py`
- `backend/tests/test_trusted_rag_canary_state.py`
- `docs/Trusted-RAG-Canary评审方案.md`
- `docs/progress/TASK-004-E4-C.md`

共新增 4 个文件，未修改 API、Agent、Workflow、前端或生产 RAG 入口。

## 设计结果

- 定义 `LEGACY_ONLY -> SHADOW_ONLY -> CANARY_1 -> CANARY_5 -> CANARY_20 -> FULL_TRUSTED`
  逐级状态链，以及自动安全态 `ROLLBACK`。
- 定义 `CanaryPolicyProtocol`，包含 `current_state`、`target_weight`、`quality_gate`、
  `rollback_condition`，并强校验状态与权重一致性。
- 非零权重升档要求 Gate 为 `PASS_READY`、观测存在且不少于 100 条；跳级和缺失证据均保持原状态。
- error rate `>2%`、timeout rate `>1%`、P95 `>1500 ms` 或任一 QualityGate v2
  指标较基线下降 `>0.05` 时，非零权重状态自动建议进入 `ROLLBACK`，目标权重归零。
- 状态机为纯评审器，只产出建议，不具备修改生产流量的能力。

## 验证命令

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q -p no:cacheprovider tests/test_trusted_rag_canary_state.py tests/test_trusted_rag_canary_gate.py tests/test_trusted_rag_validation.py
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q -p no:cacheprovider --basetemp .pytest_task004_e4c_full
```

## 实测结果

- 专项：`27 passed in 0.59s`。
- 全量：`456 passed, 1 skipped, 1 warning in 86.68s`。
- warning 为既有 FastAPI TestClient 的 Starlette 弃用提示，不是测试错误。
- 生产权重仍为 0；Canary 未开启，未修改任何生产入口。

## TASK-004-E 总结建议

TASK-004-E 已完成从离线 Gate、Shadow 数据冻结、Evidence 质量优化、最终准入验证，到 Canary
协议和回滚状态机设计的证据闭环。建议将总体结论冻结为
`DESIGN_READY / PASS_READY / PRODUCTION_NOT_ENABLED`。

后续如申请真实 Canary，应另立生产变更任务：先完成目标环境并发与长窗口观测、独立控制面接入
和回滚演练，再经人工审批从 0% 进入 1%；不得在本任务中直接切流。Real BGE、Rerank v2 或
collection/Profile 变化必须重新运行完整准入，不能复用 Hash Profile 的 PASS_READY。
