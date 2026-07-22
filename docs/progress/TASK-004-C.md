# TASK-004-C 完成总结

## 任务

`TASK-004-C Rerank Blind Evaluation`。

本阶段建立独立、固定候选、匿名 ID 的离线 Rerank 盲测体系。没有修改生产排序、已有 Gate 或任何业务路径。

## 修改文件

- `backend/app/rag/rerank_blind_evaluation.py`：严格盲测协议、Recall/MRR/nDCG、Human Preference 状态、退化检测和 BLOCK 决策。
- `backend/scripts/evaluate_rerank_blind.py`：只允许本地真实 CrossEncoder 的离线评估 CLI，记录模型版本、权重 Hash、参数和延迟。
- `backend/evaluation/rerank_blind_dataset.json`：20 条独立 query、每条 5 个固定候选、100 个全局唯一匿名 ID。
- `backend/evaluation/rerank_blind_results.json`：真实 `BAAI/bge-reranker-base` 完整结果。
- `backend/tests/test_rerank_blind_evaluation.py`：独立性、匿名性、标签隔离、Human Preference BLOCK、退化和结果产物测试。
- `docs/Rerank盲测报告.md`：设计、环境、指标、人工状态、退化案例与结论。
- `docs/progress/TASK-004-C.md`：本阶段完成记录。

## 独立性与人工状态

- dataset version：`rerank-blind-independent-v1`；
- query count：20；fixed candidate count：100；
- 与 TASK-003 40 条 query 标准化精确重合数：0；
- 未复用 TASK-003 D3-B/D3-C 候选快照或策略选择结果；
- 模型只读取匿名 ID 与候选正文，不读取文档映射、相关性等级或偏好；
- relevance labels：`pending_independent_human_review`；
- Human Preference：`pending_independent_human_review`，0/20 已复核；
- 自动指标没有用于推断 Human Preference。

## 真实模型环境

- model：`BAAI/bge-reranker-base`；
- revision：`2cfc18c9415c912f9d8155881c133215df768a70`；
- weight SHA-256：`ced967c45fd1902eb92716c9ceeca7c95a936770ea9db611f5a841b926e33fbd`；
- CPU，batch size 4，max length 256；
- model load：4989.515 ms；
- inference total：13523.681 ms；mean：676.184 ms/query；P95：828.989 ms/query；
- `productionPerformance=false`。

本次使用本地缓存真实模型，没有用 Mock 产物替代。Torch DLL 需要沙箱外只读加载权限；没有联网或下载模型。

## 评估摘要

| 指标 | Baseline | Rerank | Delta |
|---|---:|---:|---:|
| Recall@1 | 0.141667 | 0.591667 | +0.450000 |
| Recall@3 | 0.608333 | 0.925000 | +0.316667 |
| Recall@5 | 1.000000 | 1.000000 | 0.000000 |
| MRR | 0.564167 | 1.000000 | +0.435833 |
| nDCG@3 | 0.267762 | 0.971078 | +0.703316 |
| nDCG@5 | 0.510888 | 0.979257 | +0.468369 |

自动指标为 provisional，因为相关性标签尚未经过独立人工复核。

退化案例 2 条：

- `t004c_blind_11`：Recall@3 下降；
- `t004c_blind_20`：Recall@3 下降。

最终结论：`BLOCK`。原因是相关性标签待人工复核、Human Preference 待人工复核、存在退化案例。`gateEvidence.independentValidation=false`，Legacy 继续保持生产权威路径。

## 真实模型运行命令

```powershell
cd backend
$env:PYTHONPATH='F:\软件杯\backend\.bge-c3a-venv\Lib\site-packages'
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/evaluate_rerank_blind.py `
  --dataset evaluation/rerank_blind_dataset.json `
  --output evaluation/rerank_blind_results.json `
  --model BAAI/bge-reranker-base `
  --device cpu `
  --batch-size 4 `
  --max-length 256
```

实测：退出码 0，20/20 条 query 完成真实模型排序，结果 JSON 成功写入。

## 测试命令与结果

定向回归：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q `
  tests/test_rerank_blind_evaluation.py `
  tests/test_rerank_evaluation.py `
  tests/test_rerank_gate.py `
  tests/test_trusted_rag_gate.py
```

实测：`14 passed in 1.16s`，0 failed、0 errors。

全量回归：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q --basetemp='.pytest_task004_c_full'
```

实测：`408 passed, 1 skipped, 1 warning in 120.72s`，0 failed、0 errors。warning 为既有 Starlette/httpx 弃用提示。

## 未修改范围

- 未修改 `frontend/`；
- 未修改 API 或 API Contract；
- 未修改 Legacy Agent；
- 未修改任何 Workflow；
- 未修改 Trusted RAG Service；
- 未修改已有 Gate；
- 未改变生产默认路径；
- 未接入或切换生产流量。

本阶段完成后停止，不开始 TASK-004-D。
