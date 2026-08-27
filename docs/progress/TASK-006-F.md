# TASK-006-F 轻量数据库迁移与异步任务恢复

## 完成状态

已完成。新增 SQLite 版本化迁移账本和异步任务持久化，不引入 Alembic、Redis、Celery、PostgreSQL 等额外基础设施，不改变现有接口路径、字段名、统一响应信封或任务四态枚举。

按项目最新优先级，TASK-006-E 已在 E1–E14 的既有成果上收口，后续不再投入代码瘦身；下一阶段转入 TASK-006-G 的业务数据真实化。

本阶段新增 4 个文件，符合每阶段新增文件不超过 8 个的约束。

## 业务行为

- 应用启动时先自动执行未应用迁移，再执行既有幂等建表与种子初始化。
- `schema_migrations` 记录版本、名称和应用时间；迁移支持升级、重复升级、回滚与再次升级。
- 新建任务在返回 `taskId` 前写入 SQLite，running、succeeded、failed 的关键状态转换均持久化。
- 服务重启后，succeeded/failed 任务恢复到内存并可继续通过既有 `GET /api/v1/tasks/{taskId}` 查询。
- 无法安全序列化和重放的 pending/running 闭包任务在重启时收敛为 failed，错误码保持 `2001`，提示“服务重启导致任务中断，请重新提交”，避免前端永久轮询。
- 任务执行期间直接更新的 progress 会在轮询时同步持久化，任务完成时统一保存为 100。
- 当前执行器仍是单机 `asyncio`，本阶段解决状态丢失与悬挂问题，不宣称支持多实例抢占或进程间续跑。

## 文件清单

新增：

- `backend/app/core/migrations.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_task_recovery.py`
- `docs/progress/TASK-006-F.md`

修改：

- `backend/app/models/entities.py`
- `backend/app/core/init_db.py`
- `backend/app/core/tasks.py`
- `backend/app/main.py`
- `docs/维护/工作任务清单.md`
- `docs/维护/当前工程状态.md`

未修改前端、接口文档、OpenAPI 快照和根 README；现有启动命令及依赖均未变化。工作区原有欢迎页、登录页、侧边栏、PPT、截图及其他文档改动均保留且不纳入提交。

## 启动与迁移命令

```powershell
cd backend
python -m app.core.migrations current
python -m app.core.migrations upgrade
uvicorn app.main:app --port 8000
```

显式回滚仅用于已备份的维护窗口或临时验证库：

```powershell
python -m app.core.migrations downgrade --target 0
```

## 验证命令与实测结果

语法检查与专项回归：

```powershell
cd backend
python -m compileall -q app tests
python -m pytest -q tests/test_migrations.py tests/test_task_recovery.py tests/test_document_learning.py tests/test_resource_artifact.py tests/test_contract_snapshot.py
```

结果：语法检查退出码 0；专项测试 `67 passed, 1 warning in 60.50s`，0 failed。唯一 warning 为既有 Starlette/httpx 弃用提示。

全量回归：

```powershell
cd backend
python -m pytest -q
```

结果：`592 passed, 1 skipped, 1 warning in 112.93s`，0 failed、0 errors。

## 验收结论

- SQLite 迁移已实测首次升级、幂等重跑、回滚、重复回滚和再次升级。
- 异步任务已实测成功终态持久化、跨内存恢复，以及运行中任务重启后的明确失败收敛。
- 文档入库、资源产物与契约快照专项回归通过，全量测试 0 error。
- TASK-006-F 验收完成；未进入 TASK-006-G。
