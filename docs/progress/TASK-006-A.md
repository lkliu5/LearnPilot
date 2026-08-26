# TASK-006-A 后端测试依赖固化与一键验证

## 完成范围

- 将生产依赖与开发测试依赖分离，固定已验收的 pytest 版本；
- 新增 Windows 一键后端验证入口，默认执行项目规定的完整 `pytest -q` 测试发现；
- 支持自动发现 `py -3` / `python`、显式指定 Python、按需安装依赖和定向测试；
- 使用仓库内唯一 basetemp，结束后仅清理经过路径校验的本轮临时目录；
- 忽略历史 pytest/评估临时产物，避免验证污染 Git 状态；
- 整理剩余工作任务及依赖顺序；
- 未修改业务代码、API、Agent、Workflow、RAG、数据库模型或前端业务逻辑。

## 文件清单

### 新增（5 个）

- `backend/requirements-dev.txt`
- `scripts/verify-backend.ps1`
- `scripts/verify-backend.bat`
- `docs/维护/工作任务清单.md`
- `docs/progress/TASK-006-A.md`

### 修改

- `backend/.gitignore`：忽略 pytest basetemp 和任务评估临时 JSON；
- `README.md`：增加一键验证与开发依赖说明；
- `docs/维护/当前工程状态.md`：同步验证状态和下一步；

本阶段新增文件 5 个，符合每阶段新增文件不超过 8 个的约束。

## 使用命令

```powershell
# 默认完整后端测试（自动发现 py -3 或 python）
.\scripts\verify-backend.bat

# 首次安装开发依赖后验证
.\scripts\verify-backend.bat -Install

# Python 未加入 PATH
.\scripts\verify-backend.bat -Python C:\path\to\python.exe

# 定向测试
.\scripts\verify-backend.bat -Tests tests/test_contract_snapshot.py
```

## 验证过程与实测结果

PowerShell 语法检查通过。首次直接执行 `.ps1` 暴露 Windows ExecutionPolicy 限制，因此新增 `.bat` 入口以当前进程级 Bypass 启动，不修改系统策略。

定向验证：

```text
Python 3.12.13
3 passed in 0.63s
```

首次全量尝试显式传入 `tests`，只发现 453 个通过用例，遗漏 `app/agents` 与 `app/workflows` 内置测试；该结果未作为验收。修正为默认不限制路径、与项目 `pytest -q` 标准一致后重新执行：

```text
Python 3.12.13
470 passed, 1 skipped, 1 warning in 128.19s (0:02:08)
```

0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。脚本退出码为 0，验证临时目录已清理。

## 性能与运行影响

- 不进入应用运行时，不增加生产进程依赖；
- 默认 Mock 测试，无 API Key、无网络调用；
- 完整验证本机耗时约 128 秒；
- 只有显式传入 `-Install` 时才执行依赖安装。

## 阶段结论

TASK-006-A 已完成。真实 Learning-State Shadow 数据积累仍处于等待状态；下一可执行阶段为 TASK-006-B OpenAPI/接口契约快照与扩展接口文档补齐，但按单阶段纪律本轮不继续实施。
