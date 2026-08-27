# TASK-006-G 岗位、外部资源与动态图谱真实化

## 完成状态

已完成。在保持现有接口路径、字段、枚举、统一信封及 Mock-first 约束不变的前提下，补齐岗位可信刷新、外部资源真实搜索缓存和知识图谱数据驱动投影。

本阶段新增 2 个文件，符合每阶段新增文件不超过 8 个的约束；未修改前端业务逻辑、Store、路由或服务层。

## 业务结果

### 岗位市场

- 新增可信采集器 HTTP feed 与本地目录两种刷新入口，支持单快照、快照数组和 `{snapshots:[...]}`。
- 写入前严格校验接口固定字段、岗位 ID、热度枚举、时区、技能频率及固定六维雷达；整批先校验后写入，非法批次不产生部分覆盖。
- 只允许更新批次覆盖旧快照，旧 `fetchedAt` 自动跳过。
- `JobSnapshot` 作为最近成功快照缓存；超过默认 12 小时、显式离线或采集器不可用时继续返回最近快照，但按既有契约置 `code=2002/offline=true`，不冒充实时数据。
- 应用启动不主动访问外部岗位站点，避免启动阻塞和抓取合规风险。

### 外部资源

- 保留既有 Tavily Provider、URL 防幻觉校验、聚合 Agent 和 critic 评分。
- 新增 SQLite `external_resource_cache`，真实搜索排序结果按知识点、Provider 和检索式缓存，默认 TTL 12 小时。
- 有效真实缓存直接复用；当前联网失败或无 Key 时优先返回最近真实缓存并置 `online=false`；无缓存才回落精选种子。
- 缓存属于增强项，缓存写入失败不会让已取得的真实搜索结果失败。

### 动态知识图谱

- 默认响应继续严格保持 12 节点、14 边和既有字段结构。
- 12 个聚焦节点全部映射到 78 点 `KnowledgePoint` 目录真实条目；拓展节点产生 Mastery 后也能实时联动。
- 先修主边由 `KnowledgePoint.prerequisites` 动态折叠，另保留三条明确的跨路线教学关联。
- `value` 改取真实 Mastery 实测分；未测节点为 0/待学习，不再展示硬编码掌握分。低于 20 的真实测分才判为知识盲区。
- 知识目录读取异常时回落兼容拓扑，维持图谱可展示。

## 文件清单

新增：

- `backend/tests/test_task006_g.py`
- `docs/progress/TASK-006-G.md`

修改：

- `backend/app/core/config.py`
- `backend/app/core/migrations.py`
- `backend/app/models/entities.py`
- `backend/app/services/job_market.py`
- `backend/app/services/resource_search.py`
- `backend/app/services/knowledge_graph.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_b6.py`
- `backend/tests/test_contract_snapshot.py`
- `docs/后端接口文档.md`
- `docs/维护/工作任务清单.md`
- `docs/维护/当前工程状态.md`

未修改 OpenAPI 快照：本阶段没有新增或改变 HTTP 操作、请求 Schema 或响应 Schema。工作区原有前端、PPT、截图及其他文档改动均保留且不纳入提交。

## 启动与真实刷新命令

```powershell
cd backend
python -m app.core.migrations upgrade
uvicorn app.main:app --port 8000
```

岗位本地采集结果导入：

```powershell
python -m app.services.job_market --directory .\data\job-market-collected
```

可信采集器 feed 导入：

```powershell
python -m app.services.job_market --url https://collector.example/api/job-snapshots
```

也可通过环境变量配置 `JOB_MARKET_FEED_URL`、`JOB_MARKET_FEED_TOKEN` 后直接执行 `python -m app.services.job_market`。外部资源真实搜索继续使用 `SEARCH_PROVIDER=tavily` 与 `SEARCH_API_KEY`；没有 Key 时自动降级。

## 验证命令与实测结果

语法检查与专项回归：

```powershell
cd backend
python -m compileall -q app tests
python -m pytest -q tests/test_migrations.py tests/test_task006_g.py tests/test_resource_search.py tests/test_b6.py tests/test_contract_snapshot.py tests/test_openapi_snapshot.py
```

结果：语法检查退出码 0；专项测试 `79 passed, 1 warning in 7.56s`，0 failed。唯一 warning 为既有 Starlette/httpx 弃用提示。

全量回归：

```powershell
cd backend
python -m pytest -q
```

结果：`596 passed, 1 skipped, 1 warning in 93.01s`，0 failed、0 errors。

真实外网调用未在本机伪造：当前测试环境按约束强制 `SEARCH_PROVIDER=none` 且没有岗位采集器凭据；真实搜索缓存链路使用确定性 Provider 替身验证调用次数、缓存命中和联网失败回落。待提供合法 feed/Key 后只需执行上述刷新命令，无需修改接口或业务代码。

## 验收结论

- 真实来源入口、缓存新鲜度和失败降级边界均已明确并实现。
- 无 Key/离线情况下，岗位最近快照、资源种子和数据驱动图谱仍可跑通。
- 接口契约与 OpenAPI 快照无漂移，全量测试 0 error。
- TASK-006-G 验收完成；未启动新的开发阶段。
