# TASK-003-D3-A 完成记录

## 文件清单

- 修改 `backend/app/rag/reranker.py`：新增离线 `BaseReranker`、`RerankResult`、`MockReranker`，保留既有生产 Reranker；
- 新增 `backend/app/rag/rerank_evaluation.py`：固定候选比较、协议校验、指标与排序变化输出；
- 新增 `backend/scripts/evaluate_rerank.py`：40 条 C2 集离线实验入口；
- 新增 `backend/tests/test_rerank_evaluation.py`：恒等排序和零指标变化测试；
- 新增 `docs/Rerank离线实验设计.md`：实验设计、固定策略、指标及后续模型方案；
- 新增本记录。

未修改生产 Pipeline、Agent、Workflow、API 或前端。

## 启动与验证命令

```powershell
cd backend
python -m pytest -q tests/test_rerank_evaluation.py
python scripts/evaluate_rerank.py --collection kb_chunks__hash_d512__utf8_v2
python -m pytest -q --basetemp=.pytest_task003_d3a_full
```

## 实测结果

- 专项测试：`2 passed`；
- 40 条 Mock 离线实验成功，MRR、nDCG@3、nDCG@5、Top1 变化均为 `0.0`，排序变化案例 0；
- 完整后端测试：`363 passed, 1 skipped, 1 warning in 223.35s`，0 failed、0 error；warning 为既有 Starlette/httpx 弃用提示。

直接使用系统临时目录时，当前 Windows 运行时会把中文用户名错误解码并导致 pytest `tmp_path` 权限错误，因此完整验证显式使用工作区内的独立 `--basetemp`；该环境问题不涉及业务代码。

实验环境为 `hash:deterministic_hash_v1:d512` 与 `kb_chunks__hash_d512__utf8_v2`，不冒充 Real BGE 结果。
