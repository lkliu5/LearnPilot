"""内存异步任务基建（B2-a）。

契约依据：接口文档 1.4 异步任务约定 + 15.2 任务响应结构。

状态机：`pending → running → succeeded / failed`。
- 提交耗时操作返回 taskId；
- `GET /tasks/{taskId}` 轮询 `{ taskId, status, progress?, result?, error? }`。

轻量栈：进程内字典（CLAUDE.md「内存 TTL 会话」取向）；生产替换 Redis/Celery，
路径写 README。任务通过 asyncio.create_task 在当前事件循环后台执行——worker 内自
管理 DB 会话（不复用请求级 Session，避免请求结束后会话关闭）。
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

# worker 接收 Task（可写 progress），返回值落入 task.result
TaskWorker = Callable[["Task"], Awaitable[Any]]


@dataclass
class Task:
    """单个异步任务的运行态。"""

    task_id: str
    status: str = "pending"  # pending | running | succeeded | failed
    progress: int | None = None
    result: Any = None
    error: dict[str, Any] | None = None

    def to_data(self) -> dict[str, Any]:
        """转接口文档 15.2 响应结构；progress 不支持时省略。"""
        data: dict[str, Any] = {
            "taskId": self.task_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }
        if self.progress is not None:
            data["progress"] = self.progress
        return data


# 进程内任务表
_tasks: dict[str, Task] = {}


def _new_task_id() -> str:
    return "t_" + uuid.uuid4().hex[:12]


def get_task(task_id: str) -> Task | None:
    return _tasks.get(task_id)


async def _runner(task: Task, worker: TaskWorker) -> None:
    """驱动任务状态机：running → succeeded/failed。"""
    task.status = "running"
    try:
        task.result = await worker(task)
        task.progress = 100
        task.status = "succeeded"
    except Exception as exc:  # noqa: BLE001 兜底为 failed，错误码对齐 2001
        task.error = {"code": 2001, "message": str(exc) or "任务执行失败"}
        task.status = "failed"


def submit(worker: TaskWorker) -> Task:
    """登记并后台调度一个异步任务，立即返回 pending 态 Task。

    必须在运行中的事件循环内调用（FastAPI async 端点天然满足）。
    """
    task = Task(task_id=_new_task_id())
    _tasks[task.task_id] = task
    asyncio.create_task(_runner(task, worker))
    return task
