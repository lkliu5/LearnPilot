# TASK-003-D2-B 完成记录

## 文件清单

- `backend/app/rag/calibration.py`：五桶分析、ECE、阈值建议、Shadow Gate。
- `backend/app/rag/protocol.py`：新增 CalibrationProfile、TrustReport。
- `backend/app/rag/pipeline.py`：输出内部 TrustReport，不改变 API 或回答流程。
- `backend/scripts/evaluate_retrieval.py`：增加显式 Profile 阈值参数与 confidence 离线分析。
- `backend/tests/test_retrieval_confidence_calibration.py`：校准协议与统计测试。
- `backend/tests/test_trusted_retrieval_pipeline.py`：TrustReport 回归断言。
- `docs/RAG-Confidence校准报告.md`：评估结果与结论边界。
- `docs/progress/TASK-003-D2-B.md`：本记录。

## 验证命令

```powershell
cd backend
python scripts/evaluate_retrieval.py --dataset evaluation/retrieval_cases.json --collection kb_chunks__hash_d512__utf8_v2 --embedding-mode hash --confidence-analysis --calibration-threshold 0.9883 --calibration-version hash-c2-40-v1 --steady-rounds 5 --output .task003_d2b_confidence.json
python -m pytest -q tests/test_retrieval_confidence_calibration.py tests/test_trusted_retrieval_pipeline.py tests/test_hybrid_retrieval_optimization.py tests/test_retrieval_evaluation.py --basetemp=.pytest_task003_d2b_target
python -m pytest -q --basetemp=.pytest_task003_d2b_full
```

## 实测结果

- 评测集：40 条；五桶 ECE：0.09014。
- 建议阈值：0.9883；Shadow pass 30，block 10；未改变真实回答流程。
- 定向测试：32 passed。
- 全量回归：361 passed，1 skipped，1 warning，0 failed（249.66s）。warning 为既有 Starlette/httpx 弃用提示。
