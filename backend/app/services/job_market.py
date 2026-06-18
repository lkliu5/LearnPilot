"""岗位市场服务（B6）。

覆盖接口文档第 5 章 / 15.5 数据管线约定：
- 5.1 hot_jobs：热门岗位列表 [{id, name}]，固定契约顺序（种子 sort_order）。
- 5.2 get_snapshot：岗位市场快照（2.4 JobMarket 完整结构）。
  - demo 阶段：后端托管预置快照（种子自 frontend/public/data/job-market/*.json），
    JobSnapshot 表即数据源；
  - 降级（15.5）：实时数据源不可用（settings.job_market_offline 模拟故障开关）→
    返回最近快照并置 code 2002 / data.offline=true（HTTP 200），对齐前端
    JobMarketResult.offline「离线快照」标记；
  - 生产路径：离线采集管线（聚合 BOSS直聘/拉勾/智联公开 JD 样本 + LLM 抽取
    技能频率与雷达维度）定期刷新 JobSnapshot，接口签名不变（写 README，不在 demo 实现）。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm import ABILITY_DIMENSIONS, _MOCK_BASELINE
from app.models.entities import JobSnapshot, User
from app.services import mastery as mastery_service
from app.services import profile as profile_service


class UnknownJob(Exception):
    """岗位不存在（→ code 1004 / 404）。"""


# KP → 岗位雷达能力维（与 planner_agent._KP_TO_ABILITY 同口径）：掌握度并入对标
_KP_TO_ABILITY: dict[str, str] = {
    "ml": "机器学习基础",
    "nn": "神经网络",
    "dl": "深度学习",
    "cnn": "深度学习",
    "transformer": "Transformer",
    "finetune": "大模型微调",
}
# 已掌握某 KP → 对应能力维至少达到此水平（让"掌握度"体现在岗位匹配上）
_MASTERED_FLOOR = 82

# 目标岗位推断同义词（接口文档 5.3，C-fix 批2）：对话诊断仅得"学习目标"自由文本时，
# 映射到现有静态岗位库（不联网采集）。键 = JobSnapshot.id。
_JOB_KEYWORDS: dict[str, tuple[str, ...]] = {
    "llm-app": ("大模型", "llm", "应用", "prompt", "rag", "agent", "gpt", "aigc", "生成式"),
    "algo-engineer": ("算法",),
    "ml-engineer": ("机器学习", "建模", "训练"),
    "data-analyst": ("数据分析", "数据", "分析", "bi", "报表", "可视化"),
}


def hot_jobs(db: Session) -> list[dict[str, str]]:
    """热门岗位列表（接口文档 5.1）。按种子 sort_order（契约示例序）排序。"""
    rows = (
        db.query(JobSnapshot)
        .order_by(JobSnapshot.sort_order, JobSnapshot.id)
        .all()
    )
    return [{"id": row.id, "name": row.name} for row in rows]


def get_snapshot(db: Session, job_id: str) -> tuple[dict[str, Any], bool]:
    """岗位市场快照（接口文档 5.2）。返回 (payload, offline)。

    - 数据源正常：返回 (JobMarket, False)，路由套 code 0；
    - 数据源不可用（job_market_offline=True 模拟）：返回最近快照
      (JobMarket + offline:true, True)，路由套 code 2002（降级而非 500）；
    - 岗位不存在（含降级时无任何快照可回退）：抛 UnknownJob → 1004。
    """
    row = db.get(JobSnapshot, job_id)
    if row is None:
        raise UnknownJob(job_id)
    payload = dict(row.payload)
    if settings.job_market_offline:
        # 最近快照 + 离线标记（payload.fetchedAt 不变，前端 timeAgo 显示快照年龄）
        payload["offline"] = True
        return payload, True
    return payload, False


def _user_ability(db: Session, user_id: str) -> dict[str, int]:
    """用户 6 维能力（画像 + 掌握度）：ability-portrait 基线，已掌握 KP 抬升对应维。

    复用既有 profile.ability_portrait（4.4 雷达，最近 parse 优先、否则基线）+ Mastery
    （已 passed → 对应能力维并入 _MASTERED_FLOOR），体现"画像维度/掌握度"参与对标。
    """
    user = db.get(User, user_id)
    values = (
        list(profile_service.ability_portrait(user)["values"])
        if user is not None
        else list(_MOCK_BASELINE)
    )
    levels = {dim: int(v) for dim, v in zip(ABILITY_DIMENSIONS, values)}
    for kp_id, status in mastery_service.get_status_map(db, user_id).items():
        if status == mastery_service.STATUS_PASSED:
            dim = _KP_TO_ABILITY.get(kp_id)
            if dim:
                levels[dim] = max(levels.get(dim, 0), _MASTERED_FLOOR)
    return levels


def _resolve_job(
    db: Session, job_id: str | None, goal: str | None
) -> JobSnapshot | None:
    """解析目标岗位：优先 job_id；否则按学习目标文本关键词匹配现有静态岗位库。"""
    if job_id:
        snap = db.get(JobSnapshot, job_id)
        if snap is not None:
            return snap
    text = (goal or "").lower()
    if not text:
        return None
    best: JobSnapshot | None = None
    best_score = 0
    for snap in db.query(JobSnapshot).order_by(JobSnapshot.sort_order, JobSnapshot.id).all():
        score = 0
        name = snap.name or ""
        core = name.replace("工程师", "").replace("分析师", "")
        for kw in (name.lower(), core.lower()):
            if len(kw) >= 2 and kw in text:
                score += 2
        for kw in _JOB_KEYWORDS.get(snap.id, ()):  # noqa: SIM110
            if kw in text:
                score += 1
        if score > best_score:
            best_score, best = score, snap
    return best if best_score > 0 else None


def match_job(
    db: Session,
    user_id: str,
    *,
    job_id: str | None = None,
    goal: str | None = None,
) -> dict[str, Any]:
    """岗位匹配度 + 能力缺口（接口文档 5.3，C-fix 批2）。

    用现有静态岗位库（JobSnapshot.radar 6 维需求）与用户能力（画像 + 掌握度）对标：
    - matchPct = 达标维度占比 × 100（达标 = 用户该维 ≥ 岗位需求），与前端岗位对标同口径；
    - gaps = 未达标维度 [{dimension, level, demand, gap}]，按缺口降序；
    - radar = {dimensions, values(用户), demand(岗位)} 供雷达对比渲染。
    岗位无法解析（job_id 不存在且 goal 未命中任何岗位）→ 抛 UnknownJob（→ 1004）。
    **仅用现有静态数据，不触发任何联网采集。**
    """
    snap = _resolve_job(db, job_id, goal)
    if snap is None:
        raise UnknownJob(job_id or goal or "")

    radar = {
        k: int(v)
        for k, v in ((snap.payload or {}).get("radar") or {}).items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }
    levels = _user_ability(db, user_id)

    values: list[int] = []
    demand: list[int] = []
    gaps: list[dict[str, Any]] = []
    met = 0
    for dim in ABILITY_DIMENSIONS:
        lvl = int(levels.get(dim, 0))
        dem = int(radar.get(dim, 0))
        values.append(lvl)
        demand.append(dem)
        if lvl >= dem:
            met += 1
        else:
            gaps.append({"dimension": dim, "level": lvl, "demand": dem, "gap": dem - lvl})
    gaps.sort(key=lambda g: g["gap"], reverse=True)
    match_pct = round(met / len(ABILITY_DIMENSIONS) * 100) if ABILITY_DIMENSIONS else 0

    return {
        "jobId": snap.id,
        "jobName": snap.name,
        "matchPct": match_pct,
        "gaps": gaps,
        "radar": {"dimensions": list(ABILITY_DIMENSIONS), "values": values, "demand": demand},
    }
