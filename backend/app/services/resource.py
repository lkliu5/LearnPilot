"""学习资源服务（B2-b，mock 数据源）。

覆盖接口文档第 8 章前两个接口：
- 8.1 knowledge_point_meta：知识点元信息 { id, name, description, status }，
  status 取自掌握度（未开始默认 learning，与前端资源页初始一致）。
- 8.2 generate_lecture：自适应讲义，经 LLMClient.generate_lecture 产出
  markdown + sources + hallucinationRate；生成讲义同时把该知识点置为 learning。

生成调用统一经 `app.core.llm.LLMClient`（CLAUDE.md 工程纪律）；B5 替换为真实
RAG + 生成/审核 Agent，签名不变。讲义结果写入 ResourceCache（按 kp+difficulty+kind
唯一），命中则直接返回缓存，体现「同档不重复再生成」。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.llm import LECTURE_DIFFICULTIES, get_llm
from app.models.entities import KnowledgePoint, ResourceCache
from app.services import mastery as mastery_service


class UnknownKnowledgePoint(Exception):
    """知识点不存在（→ code 1004 / 404）。"""


class InvalidDifficulty(Exception):
    """难度档非法（→ code 1001 / 400）。"""


def _require_kp(db: Session, kp_id: str) -> KnowledgePoint:
    kp = db.get(KnowledgePoint, kp_id)
    if kp is None:
        raise UnknownKnowledgePoint(kp_id)
    return kp


def knowledge_point_meta(db: Session, user_id: str, kp_id: str) -> dict[str, Any]:
    """知识点元信息（接口文档 8.1）。status 取自掌握度，未开始默认 learning。"""
    kp = _require_kp(db, kp_id)
    status = mastery_service.get_status_map(db, user_id).get(
        kp_id, mastery_service.STATUS_LEARNING
    )
    return {
        "id": kp.id,
        "name": kp.name,
        "description": kp.description,
        "status": status,
    }


def generate_lecture(
    db: Session, user_id: str, kp_id: str, difficulty: str
) -> dict[str, Any]:
    """生成自适应讲义（接口文档 8.2）。命中缓存直接返回，否则经 LLMClient 生成。"""
    kp = _require_kp(db, kp_id)
    if difficulty not in LECTURE_DIFFICULTIES:
        raise InvalidDifficulty(difficulty)

    # 学习该知识点 → 掌握度置 learning（未开始时）
    mastery_service.ensure_learning(db, user_id, kp_id)

    cached = (
        db.query(ResourceCache)
        .filter(
            ResourceCache.kp_id == kp_id,
            ResourceCache.difficulty == difficulty,
            ResourceCache.kind == "lecture",
        )
        .one_or_none()
    )
    if cached is not None:
        return cached.payload

    generated = get_llm().generate_lecture(kp.id, kp.name, difficulty, kp.description)
    payload = {
        "kpId": kp.id,
        "difficulty": difficulty,
        "markdown": generated["markdown"],
        "sources": generated["sources"],
        "hallucinationRate": generated["hallucinationRate"],
    }
    db.add(
        ResourceCache(
            kp_id=kp_id,
            difficulty=difficulty,
            kind="lecture",
            payload=payload,
            hallucination_rate=generated["hallucinationRate"],
        )
    )
    db.commit()
    return payload
