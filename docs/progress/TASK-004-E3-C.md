# TASK-004-E3-C 完成记录

## 文件清单

- `backend/app/rag/evidence_quality_gate.py`
- `backend/app/rag/retriever.py`
- `backend/tests/test_evidence_quality_gate.py`
- `backend/tests/test_hybrid_retrieval_optimization.py`
- `backend/evaluation/trusted_rag_shadow_e3c_optimized.json`
- `backend/evaluation/trusted_rag_quality_e3c.json`
- `backend/evaluation/trusted_rag_gate_decision_e3c.json`
- `docs/Trusted-RAG质量优化报告.md`

## 启动命令

本阶段不修改 API 或生产入口。如需启动既有后端：

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

## 验证命令与实测结果

```powershell
cd backend
python scripts/freeze_trusted_rag_shadow_dataset.py --output evaluation/trusted_rag_shadow_e3c_optimized.json
python scripts/evaluate_trusted_rag_quality.py --shadow-dataset evaluation/trusted_rag_shadow_e3c_optimized.json --output evaluation/trusted_rag_quality_e3c.json
python scripts/evaluate_trusted_rag_gate.py --shadow-metrics evaluation/trusted_rag_shadow_e3c_optimized.json --quality-results evaluation/trusted_rag_quality_e3c.json --output evaluation/trusted_rag_gate_decision_e3c.json
pytest -q -p no:cacheprovider --basetemp .pytest_task004_e3c_full
```

- Shadow 完整性：100 条，五类各 20，0 timeout，0 error。
- 专项测试：`32 passed in 0.67s`。
- 全量测试：`438 passed, 1 skipped, 1 warning in 143.44s`，0 error；warning 为既有
  FastAPI TestClient 的 Starlette 弃用提示。
- Gate：Quality BLOCK、Latency BLOCK、Reliability PASS、Rerank BLOCK；Final BLOCK。
- Canary：未开启，推荐动作仍为 `keep_legacy_and_set_canary_weight_to_zero`。
