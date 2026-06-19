"""外部资源·联网搜索聚合 Agent（接口文档 8.6 增量，C-fix 批3-bonus）。

把"资源推荐"从静态种子库升级为 **AI 联网搜索聚合**：
1. 按当前知识点 + 用户薄弱点构造检索式；
2. 经可插拔 `web_search` Provider **联网搜索**（无能力/失败 → 回落 ExternalResource 种子作
   候选池，`online=False`，保证可跑）；
3. 候选交 **聚合 Agent（LLMClient.aggregate_resources）整理 + critic 评分**（相关度/可信度/
   推荐理由），按相关度降序返回 8.6 同结构清单（前端 ResourceAggregator 直接渲染）。

后端代理联网，规避前端配额/跨域。薄弱点缺省由该用户真实 Mastery（未通过知识点）派生，
使推荐**因人而异**。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.llm import get_llm
from app.models.entities import ExternalResource, KnowledgePoint
from app.services import mastery as mastery_service
from app.services import resource as resource_service
from app.services import web_search


def _derive_weak_points(db: Session, user_id: str, kp_id: str) -> list[str]:
    """缺省薄弱点：该用户未通过的核心知识点名（含当前 kp），最多 4 个。"""
    status_map = mastery_service.get_status_map(db, user_id)
    kps = db.query(KnowledgePoint).order_by(KnowledgePoint.lesson_seq).all()
    weak = [
        kp.name
        for kp in kps
        if status_map.get(kp.id) != mastery_service.STATUS_PASSED
    ]
    cur = next((kp.name for kp in kps if kp.id == kp_id), None)
    if cur and cur not in weak:
        weak.insert(0, cur)
    return weak[:4]


def _seed_candidates(db: Session, kp_id: str) -> list[dict[str, Any]]:
    """种子兜底候选池（无联网能力时）：ExternalResource 精选库 → 候选结构。"""
    rows = (
        db.query(ExternalResource)
        .filter(ExternalResource.kp_id == kp_id)
        .order_by(ExternalResource.relevance.desc(), ExternalResource.id)
        .all()
    )
    candidates: list[dict[str, Any]] = []
    for r in rows:
        item: dict[str, Any] = {
            "title": r.title,
            "url": r.url,
            "source": r.source,
            "snippet": r.reason or "",
            "type": r.type,
        }
        if r.embed:
            item["embed"] = r.embed
        if r.duration:
            item["duration"] = r.duration
        candidates.append(item)
    return candidates


def aggregate(
    db: Session,
    user_id: str,
    kp_id: str,
    query: str | None = None,
    weak_points: list[str] | None = None,
) -> dict[str, Any]:
    """联网搜索聚合外部资源（接口文档 8.6 增量）。知识点不存在 → 抛 UnknownKnowledgePoint。"""
    kp = resource_service._require_kp(db, kp_id)
    weak = [w for w in (weak_points or []) if isinstance(w, str) and w.strip()] or \
        _derive_weak_points(db, user_id, kp_id)
    search_query = (query or "").strip() or f"{kp.name} {' '.join(weak[:3])} 教程 讲解 论文".strip()

    provider = web_search.get_provider()
    hits = provider.search(search_query, max_results=8) if provider.online else []
    online = bool(hits)
    if not hits:  # 无联网能力 / 联网失败 → 种子兜底候选池
        hits = _seed_candidates(db, kp_id)

    items = get_llm().aggregate_resources(kp.name, weak, hits)
    return {
        "kpId": kp.id,
        "kpName": kp.name,
        "provider": provider.name,
        "online": online,
        "items": items,
    }
