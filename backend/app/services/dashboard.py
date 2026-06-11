"""学情概览聚合服务（B6）。

覆盖接口文档 12.1：GET /dashboard/overview——为减少首屏请求数做后端聚合，
**所有数值复用各明细接口的同一推导口径**（验收要求严格一致）：
- radar：profile.ability_portrait（与 4.4 同源同值）；
- targetSummary：Journey 行（与 7.4 同源）；
- strong/weak/overall_score/coverage：knowledge_graph.derived_nodes
  （与 10.1 同一份节点推导结果，掌握度变化两接口联动）。

口径定义：
- overall_score：6 核心知识点图谱节点掌握度（10.1 推导后的 value）等权平均，
  保留 1 位小数——「按掌握度加权」，通过任一 KP 即拉动评分；
- overall_level：overall_score 分档 入门<40≤初级<55≤中级<70≤高级<85≤精通；
- knowledge_graph_coverage：12 节点掌握度均值 /100（掌握度加权覆盖率，0-1 两位小数）；
- strong/weak_topics：12 节点按推导 value 取前/后 3（name 为图谱节点名）；
- learned_resources：ResourceCache 行数（生成过的讲义等资源产物数）；
- comparison.betterThanPct：overall_score 单调映射 min(99, round(score×1.365))，
  系数按种子基线标定为 68%（对齐前端演示展示），仅作演示性相对位次。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import Journey, KnowledgePoint, ResourceCache, User
from app.services import knowledge_graph as kg_service
from app.services import profile as profile_service

# overall_level 分档下界：(下界分, 档名)，从高到低匹配
_LEVELS = [(85, "精通"), (70, "高级"), (55, "中级"), (40, "初级"), (0, "入门")]

# betterThanPct 标定系数（种子基线 score≈49.8 → 68%，对齐前端演示）
_BETTER_THAN_FACTOR = 1.365


def _level_for(score: float) -> str:
    for floor, name in _LEVELS:
        if score >= floor:
            return name
    return "入门"


def overview(db: Session, user: User) -> dict[str, Any]:
    """学情概览聚合（接口文档 12.1）。"""
    nodes = kg_service.derived_nodes(db, user.id)

    # 6 核心知识点对应的图谱节点（graph_node_id 映射），等权平均 → 综合评分
    core_node_ids = {kp.graph_node_id for kp in db.query(KnowledgePoint).all()}
    core_values = [n["value"] for n in nodes if n["id"] in core_node_ids]
    overall_score = (
        round(sum(core_values) / len(core_values), 1) if core_values else 0.0
    )

    # 强弱项：12 节点按推导掌握度排序（同分按 id 保证确定性）
    ranked = sorted(nodes, key=lambda n: (-n["value"], n["id"]))
    strong_topics = [{"name": n["name"], "mastery": n["value"]} for n in ranked[:3]]
    weak_topics = [
        {"name": n["name"], "mastery": n["value"]} for n in ranked[-3:][::-1]
    ]

    coverage = round(sum(n["value"] for n in nodes) / (len(nodes) * 100), 2)

    journey = db.get(Journey, user.id)

    return {
        "overall_level": _level_for(overall_score),
        "overall_score": overall_score,
        "knowledge_graph_coverage": coverage,
        "learned_resources": db.query(ResourceCache).count(),
        "strong_topics": strong_topics,
        "weak_topics": weak_topics,
        "radar": profile_service.ability_portrait(user),  # 与 4.4 同源同值
        "comparison": {
            "betterThanPct": min(99, round(overall_score * _BETTER_THAN_FACTOR))
        },
        "targetSummary": {  # 与 7.4 Journey 同源
            "hasDiagnosed": bool(journey and journey.has_diagnosed),
            "targetJobName": journey.target_job_name if journey else None,
            "matchPct": journey.match_pct if journey else None,
        },
    }
