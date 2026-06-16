"""学情概览聚合服务（B6；C1-c 真实化）。

覆盖接口文档 12.1：GET /dashboard/overview——为减少首屏请求数做后端聚合。
**全部数值由该用户真实数据派生（禁止臆造）**，与前端 services/dashboard.ts 的
`synthesizeOverview` 逐位同口径，使「首页 overview」与「确认弹窗（前端合成）」一致：

- 雷达 / 优势 / 盲区 / 综合分 / 水平 ← 该用户真实 StudentPortrait（17.2）的异质维度：
    - 轴值：可量化维度（带 score）取 score，其余取 confidence×100（前端 axisOf 同口径）；
    - 优势：source≠inferred 且取值高的维度（降序前 3）；
    - 盲区：inferred 或取值 <60 的维度（升序前 3）；
    - 综合分：各维轴值均值（保留 1 位，前端 Math.round(mean*10)/10 同口径）；
    - 水平：综合分分档（前端阈值 <40 初学 / <60 入门 / <80 中级 / ≥80 高级）；
    - 空画像（尚未诊断）→ 雷达/优势/盲区为空、综合分 0、水平「初学」（不杜撰）。
- 知识图谱覆盖率 / 已学资源 ← 该用户真实 Mastery（7.1）：已通过的核心知识点占比 / 计数，
  属「学习活动」指标，**未学习的新用户恒为 0**（与前端 masteredCore 口径一致，绝不臆造）。
- comparison.betterThanPct ← 综合分单调映射（演示性相对位次，结构保留；综合分 0 即 0）。
- targetSummary ← Journey（与 7.4 同源）。

口径权威：前端 synthesizeOverview / CANONICAL_DIMS。雷达轴次序对齐前端 CANONICAL 顺序，
保证两处展示逐项一致（响应字段名/层级不变，仅数据来源真实化）。
"""
from __future__ import annotations

import math
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import Journey, KnowledgePoint, StudentPortrait, User
from app.services import mastery as mastery_service

# 与前端 services/profileDialogue.ts CANONICAL_DIMS 同序——雷达轴次序口径对齐，
# 保证「确认弹窗（synthesizeOverview）」与「首页 overview（本服务）」逐项一致。
_CANONICAL_DIM_KEYS: list[str] = [
    "knowledge_base",
    "cognitive_style",
    "error_preference",
    "learning_goal",
    "prior_experience",
    "learning_pace",
]
_CANONICAL_DIM_SET = set(_CANONICAL_DIM_KEYS)

# betterThanPct 标定系数（演示性相对位次；综合分为 0 时即 0，不杜撰）
_BETTER_THAN_FACTOR = 1.365


def _round_half_up(x: float) -> int:
    """JS Math.round 语义（正数 .5 向上），与前端 synthesizeOverview 逐位对齐。"""
    return math.floor(x + 0.5)


def _axis_of(dim: dict[str, Any]) -> int:
    """画像维度 → 雷达轴值：可量化维度取 score，否则 confidence×100（前端 axisOf 同口径）。"""
    score = dim.get("score")
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        return int(score)
    try:
        confidence = float(dim.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    return _round_half_up(confidence * 100)


def _level_for(score: float) -> str:
    """综合分 → 水平档（前端 synthesizeOverview 同阈值）。"""
    if score >= 80:
        return "高级"
    if score >= 60:
        return "中级"
    if score >= 40:
        return "入门"
    return "初学"


def _ordered_dims(dimensions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 CANONICAL 顺序排列画像维度，其余维度顺次附后（前端同序，雷达轴稳定不丢维）。"""
    by_key = {d.get("key"): d for d in dimensions if d.get("key")}
    canon = [by_key[k] for k in _CANONICAL_DIM_KEYS if k in by_key]
    extras = [d for d in dimensions if d.get("key") not in _CANONICAL_DIM_SET]
    return canon + extras


def overview(db: Session, user: User) -> dict[str, Any]:
    """学情概览聚合（接口文档 12.1）。全部数值由该用户真实数据派生（见模块文档）。"""
    row = db.get(StudentPortrait, user.id)
    dimensions: list[dict[str, Any]] = list(row.dimensions or []) if row else []
    ordered = _ordered_dims(dimensions)

    # 画像维度 → (展示名, 轴值, 是否推断)；雷达 / 优势 / 盲区 / 综合分均由此派生
    scored = [
        {
            "name": d.get("label") or d.get("key") or "",
            "mastery": _axis_of(d),
            "inferred": d.get("source") == "inferred",
        }
        for d in ordered
    ]

    radar = {
        "dimensions": [s["name"] for s in scored],
        "values": [s["mastery"] for s in scored],
    }

    # 优势：非 inferred，按轴值降序前 3（稳定排序，同分保持 CANONICAL 次序）
    strong_topics = [
        {"name": s["name"], "mastery": s["mastery"]}
        for s in sorted(
            (s for s in scored if not s["inferred"]), key=lambda s: -s["mastery"]
        )
    ][:3]
    # 盲区：inferred 或轴值 <60，按轴值升序前 3
    weak_topics = [
        {"name": s["name"], "mastery": s["mastery"]}
        for s in sorted(
            (s for s in scored if s["inferred"] or s["mastery"] < 60),
            key=lambda s: s["mastery"],
        )
    ][:3]

    # 综合分：各维轴值均值（前端 Math.round(mean*10)/10 同口径）；无维度 → 0
    overall_score = (
        _round_half_up(sum(s["mastery"] for s in scored) / len(scored) * 10) / 10
        if scored
        else 0.0
    )

    # 知识图谱覆盖率 / 已学资源：真实 Mastery 派生——已通过的核心知识点占比 / 计数。
    # 未学习的新用户无 Mastery 行 → passed=0 → 覆盖率 0、已学资源 0（与前端 masteredCore 一致）。
    core_kp_ids = [kp.id for kp in db.query(KnowledgePoint).all()]
    status_map = mastery_service.get_status_map(db, user.id)
    passed_core = sum(
        1 for kid in core_kp_ids if status_map.get(kid) == mastery_service.STATUS_PASSED
    )
    coverage = round(passed_core / len(core_kp_ids), 2) if core_kp_ids else 0.0

    journey = db.get(Journey, user.id)

    return {
        "overall_level": _level_for(overall_score),
        "overall_score": overall_score,
        "knowledge_graph_coverage": coverage,
        "learned_resources": passed_core,
        "strong_topics": strong_topics,
        "weak_topics": weak_topics,
        "radar": radar,
        "comparison": {
            "betterThanPct": min(99, round(overall_score * _BETTER_THAN_FACTOR))
        },
        "targetSummary": {  # 与 7.4 Journey 同源
            "hasDiagnosed": bool(journey and journey.has_diagnosed),
            "targetJobName": journey.target_job_name if journey else None,
            "matchPct": journey.match_pct if journey else None,
        },
    }
