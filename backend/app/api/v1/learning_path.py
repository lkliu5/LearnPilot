"""学习路径模块 Learning Path（接口文档第 6 章，B2-a）。

接口 10/11：
- GET  /learning-path           种子 6 课 + milestones + summary（实时计算）
- POST /learning-path/generate  异步 taskId，mock 1.5s 完成后写 hasGeneratedPath

均需登录。生成走 core.tasks 异步任务（轮询 GET /tasks/{taskId}）。
本阶段路径内容用 DB 种子（B1 已灌 6 课）；B5 替换为真实生成 Agent，签名不变。
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.envelope import success
from app.core.security import get_current_user
from app.core.tasks import Task, submit
from app.models.entities import Journey, Lesson, User
from app.schemas.profile import GeneratePathRequest

router = APIRouter(tags=["learning-path"])

# mock 生成耗时（接口文档 6.2 / 方案 B2：约 1.5s）
_GENERATE_DELAY_SECONDS = 1.5


def _serialize_lessons(db: Session) -> list[dict[str, Any]]:
    """读取 6 课并转 Lesson 契约结构（接口文档 2.3），按 sequence 升序。"""
    lessons = db.query(Lesson).order_by(Lesson.sequence).all()
    return [
        {
            "sequence": ls.sequence,
            "topic": ls.topic,
            "difficulty": ls.difficulty,
            "status": ls.status,
            "progress": ls.progress,
            "description": ls.description,
        }
        for ls in lessons
    ]


def _build_milestones(journey: Journey | None, lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """据旅程与课程进度推导里程碑（接口文档 6.1 milestones）。

    completed 由真实状态推导；date 为完成里程碑的占位展示日期（mock）。
    """
    has_diagnosed = bool(journey and journey.has_diagnosed)
    has_generated = bool(journey and journey.has_generated_path)
    completed_lessons = sum(1 for ls in lessons if ls["status"] == "completed")
    all_done = bool(lessons) and completed_lessons == len(lessons)

    specs = [
        (1, "完成画像诊断", has_diagnosed, "2026-05-20"),
        (2, "生成学习路径", has_generated, "2026-05-22"),
        (3, "完成基础课程", completed_lessons >= 2, "2026-05-28"),
        (4, "掌握核心架构", all_done, None),
    ]
    return [
        {"id": mid, "title": title, "completed": done, "date": date if done else None}
        for mid, title, done, date in specs
    ]


def _build_summary(lessons: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总进度（接口文档 6.1 summary）。overallProgress = sum(progress)/课程数。"""
    completed = sum(1 for ls in lessons if ls["status"] == "completed")
    in_progress = sum(1 for ls in lessons if ls["status"] == "in_progress")
    total = len(lessons)
    overall = round(sum(ls["progress"] for ls in lessons) / total) if total else 0
    return {
        "completedCount": completed,
        "inProgressCount": in_progress,
        "overallProgress": overall,
    }


@router.get("/learning-path")
async def get_learning_path(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取个性化学习路径（接口文档 6.1）。"""
    lessons = _serialize_lessons(db)
    journey = db.get(Journey, user.id)
    return success(
        {
            "lessons": lessons,
            "milestones": _build_milestones(journey, lessons),
            "summary": _build_summary(lessons),
        }
    )


@router.post("/learning-path/generate")
async def generate_learning_path(
    body: GeneratePathRequest | None = None,
    user: User = Depends(get_current_user),
):
    """异步生成 / 重新规划路径（接口文档 6.2）。返回 taskId 供轮询。"""
    user_id = user.id

    async def worker(task: Task) -> dict[str, Any]:
        task.progress = 10
        await asyncio.sleep(_GENERATE_DELAY_SECONDS)
        # 后台任务自管理 DB 会话（不复用请求级 Session）
        db = SessionLocal()
        try:
            journey = db.get(Journey, user_id)
            if journey is None:
                journey = Journey(user_id=user_id)
                db.add(journey)
            journey.has_generated_path = True
            db.commit()
            return {"lessons": _serialize_lessons(db)}
        finally:
            db.close()

    task = submit(worker)
    return success({"taskId": task.task_id})
