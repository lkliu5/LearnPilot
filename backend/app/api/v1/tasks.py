"""异步任务通用模块 Task（接口文档 30 + 15.2，B2-a）。

GET /tasks/{taskId} —— 轮询任务状态 { taskId, status, progress?, result?, error? }。
任务不存在 → code 1004 / HTTP 404。WS 推送通道（15.2）在 B7 落地。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.envelope import fail, success
from app.core.security import get_current_user
from app.core.tasks import get_task
from app.models.entities import User

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, user: User = Depends(get_current_user)):
    """查询异步任务状态（接口文档 15.2）。"""
    task = get_task(task_id)
    if task is None:
        return fail(code=1004, message="任务不存在", status_code=404)
    return success(task.to_data())
