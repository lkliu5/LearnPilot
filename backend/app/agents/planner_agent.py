"""个性化学习路径规划 Agent（赛题功能 3，接口文档 6.2 真实化）。

输入 = 真实 StudentPortrait（6 维异质画像）+ 真实 Mastery（知识掌握度）+ 学习目标/
目标岗位（Journey.target_job_name / 请求 targetJobId → JobSnapshot.radar 需求）；
输出 = **科学、有先修顺序的个性化路径**：每步明确「学什么、什么顺序、为什么这样排」，
并整合该知识点系统已生成的资源（讲义/思维导图/图解/视频/题库/外部精选）。

设计要点：
- **排序确定性、可解释、可测**：优先级打分在本 Agent 内（不依赖随机/网络），
  保证「无密钥 mock 也能跑通且不同画像/掌握度生成不同路径」；理由叙述层经
  LLMClient.plan_path（mock 模板 / deepseek 真实生成，见 core.llm）。
- **薄弱点优先、已掌握后置**：未掌握(weak)不加惩罚 → 前置；passed 大幅后移 →
  路径末段复习。先修依赖以 KnowledgePoint.lesson_seq 为骨架（ml→nn→dl→cnn→
  transformer→finetune），避免「把 Transformer 排在神经网络之前」。
- **画像联动**：knowledge_base 基础分低 → 难度下调一档、加固基础；高 → 难度上调
  一档、基础课可略读后置。目标岗位需求高的知识点在满足先修后前置强化。
- **资源精准推送**：每步 resources 指向该 kpId 真实存在的生成资源端点（能点开）。

复用既有服务：student_portrait / mastery / job_market / resource，不重建。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.llm import PATH_DIFFICULTIES, get_llm
from app.models.entities import JobSnapshot, Journey, KnowledgePoint, Lesson
from app.services import mastery as mastery_service
from app.services import student_portrait as portrait_service

# 掌握状态 → 路径步骤展示状态/进度（接口文档 2.3 status/progress；2.2 掌握枚举）
_STATUS_TO_STEP: dict[str, tuple[str, int]] = {
    mastery_service.STATUS_PASSED: ("completed", 100),
    mastery_service.STATUS_PENDING_CHECK: ("in_progress", 70),
    mastery_service.STATUS_LEARNING: ("in_progress", 40),
}
_STEP_NOT_STARTED = ("pending", 0)

# KP → 岗位雷达能力维名（core.llm.ABILITY_DIMENSIONS 口径）：用于读 JobSnapshot.radar
# 的该知识点岗位需求值（cnn 无独立能力维，回落「深度学习」需求）。
_KP_TO_ABILITY: dict[str, str] = {
    "ml": "机器学习基础",
    "nn": "神经网络",
    "dl": "深度学习",
    "cnn": "深度学习",
    "transformer": "Transformer",
    "finetune": "大模型微调",
}

# 每步推送的系统已生成资源（按 kpId 真实存在，端点对齐接口文档 8.x/9.1，可点开）。
# (kind, 标题模板, 端点, 是否带难度参数)
_RESOURCE_SPECS: list[tuple[str, str, str, bool]] = [
    ("lecture", "《{topic}》自适应讲义", "/resource/lecture", True),
    ("mindmap", "{topic} · 思维导图", "/resource/mindmap", False),
    ("diagram", "{topic} · 知识图解", "/resource/diagram", False),
    ("video", "{topic} · 讲解视频", "/resource/video", True),
    ("quiz", "{topic} · 巩固测验", "/quiz", False),
    ("external", "{topic} · 精选外部资源", "/resource/external", False),
]

# 资源页讲义/视频难度档（入门|初级|高级）；路径难度档更细（含中级/精通）需映射回 8.2 档
_LECTURE_DIFF_FALLBACK = "初级"


def _foundation_score(dims: list[dict[str, Any]]) -> int | None:
    """从画像维度取 knowledge_base 基础分（0-100）；缺失返回 None（中性）。"""
    for d in dims:
        if d.get("key") == "knowledge_base":
            score = d.get("score")
            if isinstance(score, (int, float)) and not isinstance(score, bool):
                return int(score)
    return None


def _dim_value(dims: list[dict[str, Any]], key: str) -> str:
    for d in dims:
        if d.get("key") == key:
            return str(d.get("value") or "")
    return ""


def _foundation_label(score: int | None) -> str:
    if score is None:
        return "中等（未量化）"
    if score >= 75:
        return "扎实"
    if score < 40:
        return "薄弱"
    return "一般"


def _lecture_difficulty(path_difficulty: str) -> str:
    """路径难度档（5 档）→ 资源讲义/视频难度档（入门|初级|高级，接口文档 8.2）。"""
    mapping = {
        "入门": "入门",
        "初级": "初级",
        "中级": "初级",
        "高级": "高级",
        "精通": "高级",
    }
    return mapping.get(path_difficulty, _LECTURE_DIFF_FALLBACK)


def _adapt_difficulty(base: str, foundation: int | None) -> str:
    """按画像基础分上下浮动一档（接口文档 2.3 难度阶梯）。"""
    try:
        idx = PATH_DIFFICULTIES.index(base)
    except ValueError:
        idx = 1
    if foundation is not None:
        if foundation >= 75:
            idx = min(len(PATH_DIFFICULTIES) - 1, idx + 1)  # 基础扎实 → 拔高
        elif foundation < 40:
            idx = max(0, idx - 1)  # 零基础 → 降档加固
    return PATH_DIFFICULTIES[idx]


def _job_demand(db: Session, job_id: str | None, job_name: str | None) -> dict[str, int]:
    """读目标岗位 6 能力维需求（接口文档 2.4 radar）。无岗位 → 空（不加权）。"""
    snap: JobSnapshot | None = None
    if job_id:
        snap = db.get(JobSnapshot, job_id)
    if snap is None and job_name:
        snap = (
            db.query(JobSnapshot).filter(JobSnapshot.name == job_name).one_or_none()
        )
    if snap is None:
        return {}
    radar = (snap.payload or {}).get("radar") or {}
    return {k: int(v) for k, v in radar.items() if isinstance(v, (int, float))}


def _build_resources(kp_id: str, topic: str, path_difficulty: str) -> list[dict[str, Any]]:
    """每步推送的资源清单：指向该 kpId 真实存在的生成资源端点（能点开）。"""
    lecture_diff = _lecture_difficulty(path_difficulty)
    resources: list[dict[str, Any]] = []
    for kind, title_tpl, endpoint, with_diff in _RESOURCE_SPECS:
        item: dict[str, Any] = {
            "kind": kind,
            "title": title_tpl.format(topic=topic),
            "kpId": kp_id,
            "endpoint": endpoint,
        }
        if with_diff:
            item["difficulty"] = lecture_diff
        resources.append(item)
    return resources


def plan_path(
    db: Session, *, user_id: str, target_job_id: str | None = None
) -> dict[str, Any]:
    """生成该用户的个性化学习路径（接口文档 6.2，真实规划）。

    Returns:
        {lessons, summary}：
        - lessons：Lesson[]（接口文档 2.3 六字段）+ additive kpId/reason/resources，
          sequence 1..N 为**真实学习顺序**（按薄弱优先/先修依赖/岗位需求重排）；
        - summary：整体规划说明（驱动前端路径头部叙述）。
    """
    # ---- 1. 真实输入源（全部复用既有服务，不重建） ----
    dims = list(portrait_service.get_portrait(db, user_id).get("dimensions") or [])
    foundation = _foundation_score(dims)
    status_map = mastery_service.get_status_map(db, user_id)
    journey = db.get(Journey, user_id)
    job_name = journey.target_job_name if journey else None
    demand = _job_demand(db, target_job_id, job_name)

    kps = db.query(KnowledgePoint).order_by(KnowledgePoint.lesson_seq).all()
    # 基础难度/描述取自全局种子课程（按 lesson_seq == Lesson.sequence 对应）
    lessons_by_seq = {ls.sequence: ls for ls in db.query(Lesson).all()}

    # ---- 2. 优先级打分（lower = 越早学；科学排程） ----
    scored: list[dict[str, Any]] = []
    for kp in kps:
        status = status_map.get(kp.id)  # None = 未开始（薄弱）
        mastered = status == mastery_service.STATUS_PASSED
        weak = not mastered  # 未通过即薄弱/待强化
        foundational = kp.lesson_seq <= 2  # ml/nn 为后续基础
        ability = _KP_TO_ABILITY.get(kp.id, "")
        job_boost = bool(weak and demand.get(ability, 0) >= 80)

        score = float(kp.lesson_seq)  # 先修骨架（保证依赖顺序）
        if mastered:
            score += 100.0  # 已掌握 → 大幅后置（路径末段复习）
        elif status == mastery_service.STATUS_PENDING_CHECK:
            score += 0.3
        elif status == mastery_service.STATUS_LEARNING:
            score += 0.1
        # 画像基础联动：基础扎实可略读基础课（后移），零基础先固基础（前移）
        if foundational and not mastered:
            if foundation is not None and foundation >= 75:
                score += 0.5
            elif foundation is not None and foundation < 40:
                score -= 0.5
        # 目标岗位高需求 → 满足先修后小幅前置（不足以越过先修骨架的整数差）
        if ability and demand:
            score -= min(0.8, demand.get(ability, 0) / 100.0 * 0.8)

        scored.append(
            {
                "kp": kp,
                "status": status,
                "score": score,
                "signals": {
                    "weak": weak,
                    "mastered": mastered,
                    "foundational": foundational,
                    "jobBoost": job_boost,
                },
            }
        )

    # 稳定排序：分数升序，先修序兜底（同分保持课程骨架顺序）
    scored.sort(key=lambda e: (e["score"], e["kp"].lesson_seq))

    # ---- 3. 组装步骤（含难度自适应、状态/进度派生、资源推送） ----
    steps_ctx: list[dict[str, Any]] = []
    lessons: list[dict[str, Any]] = []
    for order, entry in enumerate(scored, start=1):
        kp: KnowledgePoint = entry["kp"]
        seed = lessons_by_seq.get(kp.lesson_seq)
        base_diff = seed.difficulty if seed is not None else "初级"
        difficulty = _adapt_difficulty(base_diff, foundation)
        status, progress = _STATUS_TO_STEP.get(entry["status"], _STEP_NOT_STARTED)
        description = (seed.description if seed is not None else "") or kp.description

        lesson: dict[str, Any] = {
            "sequence": order,
            "topic": kp.name,
            "difficulty": difficulty,
            "status": status,
            "progress": progress,
            "description": description,
            # ---- additive（接口文档 6.3 增量，向后兼容） ----
            "kpId": kp.id,
            "reason": "",  # 由 LLMClient.plan_path 回填
            "resources": _build_resources(kp.id, kp.name, difficulty),
        }
        lessons.append(lesson)
        steps_ctx.append(
            {
                "kpId": kp.id,
                "topic": kp.name,
                "order": order,
                "status": entry["status"] or "not-started",
                "signals": entry["signals"],
            }
        )

    # ---- 4. 理由 + 摘要叙述层（经 LLMClient：mock 模板 / deepseek 真实） ----
    profile = {
        "foundationLevel": _foundation_label(foundation),
        "goal": _dim_value(dims, "learning_goal"),
        "pace": _dim_value(dims, "learning_pace"),
        "jobName": job_name or "",
    }
    annotated = get_llm().plan_path(profile=profile, steps=steps_ctx)
    reasons = annotated.get("reasons") or {}
    for lesson in lessons:
        lesson["reason"] = reasons.get(lesson["kpId"], "")

    return {"lessons": lessons, "summary": annotated.get("summary", "")}
