# TASK-003-C2 完成总结

## 文件清单

- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/rag/embeddings.py`
- `backend/app/rag/evaluation.py`
- `backend/app/rag/evaluation_protocol.py`
- `backend/app/rag/pipeline.py`
- `backend/app/rag/text_quality.py`
- `backend/app/rag/vector_store.py`
- `backend/evaluation/retrieval_cases.json`
- `backend/scripts/evaluate_retrieval.py`
- `backend/scripts/rebuild_clean_collection.py`
- `backend/tests/test_rag_environment_governance.py`
- `backend/tests/test_retrieval_evaluation.py`
- `docs/RAG数据环境修复报告.md`
- `docs/RAG检索稳态基线报告.md`

## 启动命令

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

启动日志会明确输出 `real_embedding`、`hash_fallback` 或 `unavailable`。

## 重建与评测命令

```powershell
cd backend
python scripts/rebuild_clean_collection.py --target kb_chunks__hash_d512__utf8_v2 --provider hash --audit-existing kb_chunks
python scripts/rebuild_clean_collection.py --target kb_chunks__hash_d512__utf8_v2 --provider hash --execute
python scripts/evaluate_retrieval.py --collection kb_chunks__hash_d512__utf8_v2 --embedding-mode hash --steady-rounds 10 --output hash-baseline.json
python scripts/evaluate_retrieval.py --collection kb_chunks__bge_d512__utf8_v2 --embedding-mode real --require-real --output real-baseline.json
```

实测结果：

- dry-run：35篇UTF-8源文档、178个Chunk、0乱码、0空文本、0重复Chunk组。
- 新Collection：`kb_chunks__hash_d512__utf8_v2`，35篇文档、178个Chunk、512维；旧`kb_chunks`保持29篇/147个Chunk且可独立打开。
- Hash基线：Recall@1/3/5为0.4619/0.8357/0.8905，MRR为0.7581，nDCG@1/3/5为0.5184/0.7181/0.7439。
- Real BGE：blocked；强制真实模式退出码2，Torch加载`torch_python.dll`或依赖DLL时返回WinError 5，未生成伪指标。
- 稳态10轮：旧Retriever均值/中位数/P95为9.1727/9.1561/10.1775 ms；Pipeline为9.6413/9.7444/10.3823 ms。

## 验证命令与结果

```powershell
cd backend
python -m pytest -q --basetemp=.pytest_task003_c2_full4
```

实测：`342 passed, 1 skipped, 1 warning in 136.15s`，0报错。warning为Starlette/httpx弃用提示，与本阶段无关。

生产默认Collection未切换；未修改Agent、Workflow、API路由、前端或旧Retriever排序算法。
