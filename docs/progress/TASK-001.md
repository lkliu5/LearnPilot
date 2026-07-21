# TASK-001 基础工程整理

完成日期：2026-07-21

## 完成范围

- 梳理后端八类模块的职责、依赖方向和禁止事项。
- 将日志级别、日志格式和请求完成日志开关纳入统一 Settings。
- 统一应用与 Uvicorn 日志的格式、级别、traceId 和敏感信息脱敏。
- 为请求完成和未处理异常增加不包含请求正文的结构化日志。
- 补充日志配置、脱敏、traceId 和初始化幂等性测试。

未修改 API 路径、响应字段、数据库模型、前端代码、Agent、RAG 或个性化算法。

## 文件清单

- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/core/envelope.py`
- `backend/.env.example`
- `backend/tests/test_logging.py`
- `docs/技术架构模块边界.md`
- `docs/技术优化路线规划.md`
- `docs/progress/TASK-001.md`

## 配置说明

```env
LOG_LEVEL=INFO
LOG_FORMAT=text
LOG_REQUEST_COMPLETED=true
```

`LOG_FORMAT`支持`text`和`json`；默认值不改变零配置启动能力。

## 验证结果

```text
python -m py_compile app/core/config.py app/core/logging.py app/core/envelope.py tests/test_logging.py
通过（0语法错误）

python -m pytest tests/test_logging.py tests/test_content_safety.py -q
37 passed in 0.49s

python -m pytest tests/test_contract_snapshot.py -q -k "not test_34_admin_kb_search_test"
40 passed, 1 deselected, 1 warning in 3.17s
```

完整契约测试的既有`test_34_admin_kb_search_test`在本机持久化Chroma集合上失败：集合维度为512，当前无模型降级嵌入为256；使用空临时集合时因没有种子文档而返回空结果。该问题属于RAG测试数据隔离与运行环境一致性，不由TASK-001修改引入，本任务遵守范围约束未修改RAG实现。

## 性能影响

每个请求新增一次耗时计算和一条可关闭的完成日志；无新增网络、数据库或模型调用。JSON格式仅在显式配置时启用。
