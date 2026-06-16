"""学习路径模块 Learning Path（接口文档第 6 章；6.2 真实规划 Agent）。

接口 10/11：
- GET  /learning-path           个性化路径 + milestones + summary（实时计算）
- POST /learning-path/generate  异步 taskId，真实规划 Agent 生成并落库

均需登录。生成走 core.tasks 异步任务（轮询 GET /tasks/{taskId}）。

路径来源（接口文档 6.3 增量说明）：
- 首次未生成 → GET 回落全局种子 6 课（向后兼容，演示稳定）；
- POST generate → agents.planner_agent 按**真实 StudentPortrait + Mastery + 目标
  岗位**规划个性化路径（薄弱优先/先修依赖/岗位需求重排，每步带 reason 与配套
  resources），落 Journey.path_plan 缓存；其后 GET 命中该缓存（同画像不重复规划）。
- 无密钥（mock provider）仍可跑通：排序确定性、理由走模板，演示兜底。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.planner_agent import plan_path
from app.core.database import SessionLocal, get_db
from app.core.envelope import success
from app.core.security import get_current_user
from app.core.tasks import Task, submit
from app.models.entities import Journey, Lesson, User
from app.schemas.profile import GeneratePathRequest

router = APIRouter(tags=["learning-path"])

# Lesson 契约六字段（接口文档 2.3）；GET 回包对种子路径只暴露这六字段（向后兼容）
_LESSON_FIELDS = ("sequence", "topic", "difficulty", "status", "progress", "description")


def _seed_lessons(db: Session) -> list[dict[str, Any]]:
    """全局种子 6 课（接口文档 2.3），按 sequence 升序——未生成个性化路径时的回落。"""
    lessons = db.query(Lesson).order_by(Lesson.sequence).all()
    return [{f: getattr(ls, f) for f in _LESSON_FIELDS} for ls in lessons]


def _resolve_lessons(db: Session, journey: Journey | None) -> list[dict[str, Any]]:
    """优先返回该用户个性化路径（Journey.path_plan）；未生成 → 全局种子路径。"""
    if journey is not None and journey.path_plan:
        return list(journey.path_plan)
    return _seed_lessons(db)


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
    """获取个性化学习路径（接口文档 6.1）。已生成则返回个性化路径，否则种子路径。"""
    journey = db.get(Journey, user.id)
    lessons = _resolve_lessons(db, journey)
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
    """异步生成 / 重新规划路径（接口文档 6.2）。返回 taskId 供轮询。

    真实规划：planner_agent 据该用户 StudentPortrait + Mastery + 目标岗位生成
    个性化路径并落 Journey.path_plan；任务 result 回 {lessons}（含 reason/resources）。
    """
    user_id = user.id
    target_job_id = body.targetJobId if body is not None else None

    async def worker(task: Task) -> dict[str, Any]:
        task.progress = 10
        # 后台任务自管理 DB 会话（不复用请求级 Session）
        db = SessionLocal()
        try:
            plan = plan_path(db, user_id=user_id, target_job_id=target_job_id)
            task.progress = 80
            journey = db.get(Journey, user_id)
            if journey is None:
                journey = Journey(user_id=user_id)
                db.add(journey)
            journey.has_generated_path = True
            journey.path_plan = plan["lessons"]
            db.commit()
            # 任务产物严格对齐接口文档 15.2「{lessons}」（规划摘要不入 result，
            # 每步 reason 已承载「为什么这样排」；摘要内部计算用于日志/可观测）。
            return {"lessons": plan["lessons"]}
        finally:
            db.close()

    task = submit(worker)
    return success({"taskId": task.task_id})
