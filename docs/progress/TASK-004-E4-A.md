# TASK-004-E4-A 完成记录

## 文件清单

- `backend/app/rag/trusted_rag_validation.py`
- `backend/scripts/evaluate_trusted_rag_validation.py`
- `backend/tests/test_trusted_rag_validation.py`
- `backend/evaluation/trusted_rag_validation_dataset.json`
- `backend/evaluation/trusted_rag_final_validation.json`
- `backend/evaluation/trusted_rag_gate_decision_e4a.json`
- `docs/Trusted-RAG最终准入评估报告.md`
- `docs/progress/TASK-004-E4-A.md`

本阶段恰好新增 8 个文件，未修改生产入口、Agent、Workflow、API 或前端，未开启 Canary。

## 运行命令

```powershell
cd backend
# 主运行时可执行 Hash retrieval；Windows 沙箱内 Torch DLL 受限时，BGE rerank 使用项目
# 已有 .bge-c3a-venv，并在进程内补入主运行时的 NumPy/Pydantic 搜索路径。
python scripts/evaluate_trusted_rag_validation.py
```

## 验证命令与实测结果

```powershell
cd backend
python -m pytest -q -p no:cacheprovider tests/test_trusted_rag_validation.py \
  --basetemp .pytest_task004_e4a_focus
python -m pytest -q -p no:cacheprovider --basetemp .pytest_task004_e4a_full
```

- 数据集 schema 专项测试：`3 passed in 0.41s`。
- Trusted RAG 专项回归：`22 passed in 0.54s`。
- 全量测试：`441 passed, 1 skipped, 1 warning in 96.06s`；warning 为既有
  FastAPI TestClient 的 Starlette 弃用提示，不是测试错误。
- Validation：125 条，五类各 25；与 E3 100 条 query 指纹重合 0。
- Quality：relevance 0.701657、support 0.896000、completeness 0.316759、
  source coverage 1.000000、evidence overlap 0.057410。
- Embedding：`kb_chunks`，`hash:deterministic_hash_v1:d512`，512 维，Hash。
- Latency：P50 22.880900 ms、P95 26.405200 ms、0 timeout、0 error；fallback
  overhead mean 0.176618 ms、P95 0.276100 ms。
- Reliability：PASS，故障注入 11/11 PASS。
- Rerank：Always 在操作步骤/综合问题各退化 1 条；Conditional 仍有 2 条退化，保留策略
  方向但当前不启用。
- Gate：Quality BLOCK、Latency BLOCK、Reliability PASS、Rerank BLOCK；Final BLOCK。
- Canary：未开启；当前不满足 Canary 评审条件。
