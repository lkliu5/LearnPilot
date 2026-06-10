"""掌握度与学习旅程服务（B2-b）。

覆盖接口文档第 7 章：
- 7.1 get_status_map：Record<kpId, KPStatus>（未出现的知识点视为未开始）。
- 7.2 mark_check：learning → pending-check（已 passed 保持不变）。
- 7.3 mark_pass：置 passed（幂等）。通常由测验 ≥60 分联动触发（见 9.1）。
- 7.4 derive_current_step：按规则推导 currentStep（diagnose|generate-path|learn|review）。

后端为掌握度权威数据源（前端 Zustand 退化为缓存）。状态枚举严格为
`learning | pending-check | passed`（连字符，禁止下划线）——见接口文档 2.2。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import Journey, KnowledgePoint, Mastery

# 掌握状态枚举（接口文档 2.2，连字符形式，全局唯一来源）
STATUS_LEARNING = "learning"
STATUS_PENDING_CHECK = "pending-check"
STATUS_PASSED = "passed"


def get_status_map(db: Session, user_id: str) -> dict[str, str]:
    """掌握度全集（接口文档 7.1）。仅返回已存在的行；未出现 = 未开始。"""
    rows = db.query(Mastery).filter(Mastery.user_id == user_id).all()
    return {r.kp_id: r.status for r in rows}


def _current_status(db: Session, user_id: str, kp_id: str) -> str | None:
    row = (
        db.query(Mastery)
        .filter(Mastery.user_id == user_id, Mastery.kp_id == kp_id)
        .one_or_none()
    )
    return row.status if row else None


def set_status(db: Session, user_id: str, kp_id: str, status: str) -> str:
    """写入/更新掌握状态（建行或改行），提交并返回最终状态。"""
    row = (
        db.query(Mastery)
        .filter(Mastery.user_id == user_id, Mastery.kp_id == kp_id)
        .one_or_none()
    )
    if row is None:
        row = Mastery(user_id=user_id, kp_id=kp_id, status=status)
        db.add(row)
    else:
        row.status = status
    db.commit()
    return status


def ensure_learning(db: Session, user_id: str, kp_id: str) -> str:
    """学习行为（如生成讲义）触发：未开始 → learning；已有状态保持不变。"""
    current = _current_status(db, user_id, kp_id)
    if current is None:
        return set_status(db, user_id, kp_id, STATUS_LEARNING)
    return current


def mark_check(db: Session, user_id: str, kp_id: str) -> str:
    """去检验（接口文档 7.2）：learning（及未开始）→ pending-check；passed 保持不变。"""
    if _current_status(db, user_id, kp_id) == STATUS_PASSED:
        return STATUS_PASSED
    return set_status(db, user_id, kp_id, STATUS_PENDING_CHECK)


def mark_pass(db: Session, user_id: str, kp_id: str) -> str:
    """标记通过（接口文档 7.3，幂等）：置 passed。"""
    return set_status(db, user_id, kp_id, STATUS_PASSED)


def derive_current_step(
    db: Session, journey: Journey | None, status_map: dict[str, str]
) -> str:
    """推导旅程当前步骤（接口文档 7.4，与前端 getJourneyStep 一致）。

    未诊断 → diagnose；已诊断未生成路径 → generate-path；
    全部核心知识点 passed → review；否则 learn。
    （「全部课程完成」以核心知识点全 passed 推导——前端学习路径/图谱均由掌握度派生。）
    """
    if journey is None or not journey.has_diagnosed:
        return "diagnose"
    if not journey.has_generated_path:
        return "generate-path"
    core_ids = [kp.id for kp in db.query(KnowledgePoint).all()]
    if core_ids and all(status_map.get(kid) == STATUS_PASSED for kid in core_ids):
        return "review"
    return "learn"
