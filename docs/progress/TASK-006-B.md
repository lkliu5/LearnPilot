# TASK-006-B OpenAPI 契约快照与扩展接口文档补齐

## 完成范围

- 审计 FastAPI 实际 OpenAPI：83 个 HTTP 操作、原始 54 个组件 Schema；
- 审计接口总览：原覆盖 55 个 HTTP 操作，缺少 28 个已实现扩展操作，无陈旧操作；
- 补齐接口文档 V1.4 总览、19–22 章目录和 OpenAPI 契约治理规则；
- OpenAPI 显式声明统一 `{code, message, data, traceId}` 信封，组件 Schema 增至 55；
- 将 FastAPI 默认 422 文档修正为项目实际 `HTTP 400 + code 1001`；
- 为四个 JSON/SSE 双模式端点补充 `text/event-stream` 声明；
- 新增可复现 JSON 快照、显式生成/只读校验工具以及文档双向覆盖测试；
- 未修改任何业务接口路径、请求字段、枚举、运行时响应、数据库或前端。

## 文件清单

### 新增（5 个）

- `backend/app/core/openapi_contract.py`
- `backend/scripts/export_openapi_snapshot.py`
- `backend/contracts/openapi-v1.snapshot.json`
- `backend/tests/test_openapi_snapshot.py`
- `docs/progress/TASK-006-B.md`

### 修改

- `backend/app/main.py`：所有路由挂载完成后安装 OpenAPI 文档后处理器；
- `docs/后端接口文档.md`：升级 V1.4，补齐 28 个操作与契约治理章节；
- `docs/维护/工作任务清单.md`：TASK-006-B 标记完成；
- `docs/维护/当前工程状态.md`：同步契约基线与下一步；
- `README.md`：增加 OpenAPI 快照只读校验命令，并修正全量 pytest 命令说明。

本阶段新增文件 5 个，符合每阶段新增文件不超过 8 个的约束。

## 契约基线

```text
HTTP operations: 83
Component schemas: 55（含 UnifiedEnvelope）
Documented HTTP operations: 83
Undocumented operations: 0
Stale documented operations: 0
Default 422 responses: 0
JSON/SSE dual-mode operations: 4
```

快照不会由测试自动覆盖。只有接口变更获批准且已先同步权威接口文档后，才允许显式执行生成命令。

## 验证命令与实测结果

快照生成与只读校验：

```powershell
cd backend
python scripts/export_openapi_snapshot.py
python scripts/export_openapi_snapshot.py --check
```

```text
OpenAPI snapshot is current
```

定向契约测试：

```powershell
python -m pytest -q tests/test_openapi_snapshot.py tests/test_contract_snapshot.py --basetemp=.pytest_task006_b_focus
```

```text
45 passed, 1 warning in 12.76s
```

全量后端回归：

```powershell
.\scripts\verify-backend.bat -Python C:\path\to\python.exe
```

```text
474 passed, 1 skipped, 1 warning in 147.20s (0:02:27)
```

0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

## curl 实测

独立启动 `uvicorn app.main:app --host 127.0.0.1 --port 8765` 后：

```powershell
curl.exe http://127.0.0.1:8765/api/v1/health
curl.exe http://127.0.0.1:8765/openapi.json
```

实测摘要：

```text
health HTTP: 200
health code: 0
health keys: code,data,message,traceId
OpenAPI contract: openapi-v1
operation count: 83
has 422: false
UnifiedEnvelope required: code,message,data,traceId
profile/dialogue content: application/json,text/event-stream
```

验证后服务进程已停止，端口 8765 无残留监听。

## 性能与风险

- 只在首次请求 `/openapi.json` 时规范化文档字典并缓存，不进入正常业务请求路径；
- 快照约 110 KB，只在测试/显式校验时读取；
- OpenAPI 的 `data` 保持泛型，各接口具体 data 字段仍以权威接口章节和 TypeScript 类型为准；
- 现有核心运行时字段测试继续保留，新快照负责补足未覆盖扩展路由的路径、方法和 Schema 防漂移。

## 阶段结论

TASK-006-B 已完成。下一可执行阶段为 TASK-006-C 生成结果溯源元数据统一；按单阶段纪律本轮不继续实施。
