# TASK-004-A 完成总结

## 任务

`TASK-004-A Shadow Dataset Construction`。

本阶段只建立离线代表性评测数据集，不接入生产请求，不修改生产入口。由于仓库当前没有经过授权和脱敏的真实生产请求，本数据集明确标记为 `representative_evaluation_dataset`，不得表述为真实生产 Shadow 数据。

## 修改文件

- `backend/evaluation/trusted_rag_shadow_dataset.json`：100 条版本化代表性用例，概念解释、流程说明、代码/技术问题、多跳推理和无答案拒答各 20 条。
- `backend/tests/test_trusted_rag_shadow_dataset.py`：数据来源声明、分类数量、字段契约、Evidence 文件、拒答规则和明显 PII 模式测试。
- `docs/Trusted-RAG评测数据集说明.md`：数据定位、结构、评分口径、来源限制和后续真实请求准入规则。
- `docs/progress/TASK-004-A.md`：本阶段完成记录。

## 数据集结论

- dataset version：`trusted-rag-shadow-representative-v1`；
- case count：100；
- 五类各 20 条；
- `productionShadowData=false`；
- `provenance.containsProductionQueries=false`；
- 每条 case 均含标准答案、Expected Evidence、answerable/refusal、正确性标准、Evidence coverage 标准、难度和版本；
- 质量标签状态为 `pending_independent_human_review`，没有伪称已经完成独立人工复核；
- 真实生产 Shadow 数据仍缺失，不能据此解除 Gate 的 NO-GO。

## 验证命令与实测结果

定向测试：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q tests/test_trusted_rag_shadow_dataset.py
```

实测：`5 passed in 1.52s`，0 failed、0 errors。

全量回归：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q --basetemp='.pytest_task004_a_full'
```

实测：`398 passed, 1 skipped, 1 warning in 120.29s`，0 failed、0 errors。warning 为既有 Starlette/httpx 弃用提示。

## 未修改范围

- 未修改 `frontend/`；
- 未修改 API 路由、Contract 或响应信封；
- 未修改 Legacy Agent；
- 未修改任何 Workflow；
- 未修改 Trusted RAG Service 主逻辑；
- 未接入或切换生产流量；
- Legacy 继续保持唯一生产权威路径。

## 后续边界

本提交完成后停止，不开始 TASK-004-B。后续真实生产请求必须经过授权、脱敏、独立版本化和人工复核，且不得与本 representative dataset 混淆来源。
