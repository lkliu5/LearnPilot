"""学习资源服务（B2-b mock 数据源 / B5-b 真实生成替换）。

覆盖接口文档第 8 章前两个接口：
- 8.1 knowledge_point_meta：知识点元信息 { id, name, description, status }，
  status 取自掌握度（未开始默认 learning，与前端资源页初始一致）。
- 8.2 generate_lecture：自适应讲义 markdown + sources + hallucinationRate；
  生成讲义同时把该知识点置为 learning。
  - mock：经 LLMClient.generate_lecture 确定性产出（与 B2 逐字等价，演示兜底）；
  - 真实模式（B5-b）：run_learning_workflow「B3 混合检索+重排 → 生成 Agent →
    审核 Agent（15.3 接地口径）」，sources 由真实命中切片回填
    （document_title/source_location → title，文档 category → type，
    重排分 → confidence），hallucinationRate 为逐句接地计算值。

讲义结果写入 ResourceCache（按 kp+difficulty+kind 唯一），命中则直接返回缓存，
体现「同档不重复再生成」；真实模式 kind 带 provider 后缀（lecture@deepseek），
与 mock 缓存互不污染——切换 provider 后演示数据不串。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.llm import LECTURE_DIFFICULTIES, get_llm
from app.models.entities import (
    ExternalResource,
    KnowledgeDocument,
    KnowledgePoint,
    ResourceCache,
)
from app.rag.reranker import get_reranker
from app.rag.retriever import get_retriever
from app.services import mastery as mastery_service
from app.workflows.learning_workflow import run_learning_workflow

# 接口文档 8.2 sources[].type 合法取值；文档 category 不在其中时回落「文档」
_SOURCE_TYPES = {"教材", "论文", "文档", "课程"}
# 讲义检索参数：候选池与最终注入生成的切片数
_RETRIEVE_POOL = 8
_RETRIEVE_TOP_K = 4


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


def external_resources(db: Session, kp_id: str) -> list[dict[str, Any]]:
    """外部资源聚合（接口文档 8.6，B6）。按相关度降序返回精选资源种子。

    demo 阶段读 ExternalResource 精选库（init_db 种子，6 核心 KP 各 3-4 条，
    relevance/credibility 为审核 Agent 评分口径预置值）；生产路径：聚合 Agent
    调 YouTube Data API / B 站 / arXiv / 慕课等搜索 API 检索候选 → critic Agent
    按相关性 + 来源可信度评分过滤 → 写回 ExternalResource 表，本函数与接口签名不变。
    embed/duration 为可选字段，仅在有值时返回（契约 8.6）。
    """
    _require_kp(db, kp_id)
    rows = (
        db.query(ExternalResource)
        .filter(ExternalResource.kp_id == kp_id)
        .order_by(ExternalResource.relevance.desc(), ExternalResource.id)
        .all()
    )
    items: list[dict[str, Any]] = []
    for r in rows:
        item: dict[str, Any] = {
            "id": r.id,
            "type": r.type,
            "title": r.title,
            "source": r.source,
            "url": r.url,
            "relevance": r.relevance,
            "credibility": r.credibility,
            "reason": r.reason,
        }
        if r.embed:
            item["embed"] = r.embed
        if r.duration:
            item["duration"] = r.duration
        items.append(item)
    return items


# ---- 视频讲解（接口文档 8.3，B7-a） --------------------------------------------
# 视频参数与前端 Remotion 组件逐一对齐（frontend/src/remotion/LectureVideo.tsx：
# VIDEO_FPS/W/H/DURATION 与 5 个 Sequence 场景起始帧）。videoUrl 返回 null →
# 前端走 Remotion Player + TTS（契约 8.3）；服务端渲染 mp4 为可选加分项，
# 生产路径：Remotion server-side rendering 产出 mp4 回填 videoUrl，写 README。
_VIDEO_FPS = 30
_VIDEO_WIDTH = 1280
_VIDEO_HEIGHT = 720
_VIDEO_DURATION_FRAMES = 900
# 5 段帧-旁白映射的起始帧：封面/神经元三步/前向传播/激活函数/小结闭环
_NARRATION_FRAMES = [0, 90, 300, 540, 720]
# nn 知识点旁白与前端 LectureVideo.NARRATION 逐字一致（场景画面为 nn 定制）
_NARRATION_NN = [
    "欢迎学习神经网络基础。本视频由领域知识生成智能体为你定制。",
    "一个神经元完成三步运算：加权求和、加上偏置、再经过激活函数输出。",
    "前向传播时，输入与权重相乘求和，加偏置得到 z，再用 ReLU 激活得到输出。",
    "常见激活函数有 ReLU、Sigmoid 和 Tanh，其中 ReLU 计算快、最常用。",
    "神经元、前向传播、激活、反向传播更新，构成了神经网络学习的完整闭环。",
]


def generate_video(
    db: Session, user_id: str, kp_id: str, difficulty: str
) -> dict[str, Any]:
    """生成视频讲解（接口文档 8.3）。videoUrl:null + narration[] 帧-旁白映射。

    确定性产出（无 LLM 成本，不走缓存）：nn 用与前端场景逐字对齐的旁白，
    其余知识点按相同 5 段结构模板化生成。
    """
    kp = _require_kp(db, kp_id)
    if difficulty not in LECTURE_DIFFICULTIES:
        raise InvalidDifficulty(difficulty)
    mastery_service.ensure_learning(db, user_id, kp_id)

    if kp_id == "nn":
        texts = list(_NARRATION_NN)
    else:
        texts = [
            f"欢迎学习{kp.name}。本视频由领域知识生成智能体按「{difficulty}」难度为你定制。",
            f"我们先拆解{kp.name}的核心构成，建立整体认知框架。",
            f"接着通过一个{difficulty}难度的典型示例，看看{kp.name}在实践中如何运作。",
            f"再对比{kp.name}相关的常见方法与适用场景，避免典型误区。",
            f"最后回顾要点，把{kp.name}纳入完整的学习闭环。建议完成测验巩固理解。",
        ]
    return {
        "videoUrl": None,  # 无服务端渲染产物 → 前端 Remotion Player + TTS
        "narration": [
            {"frame": frame, "text": text}
            for frame, text in zip(_NARRATION_FRAMES, texts)
        ],
        "fps": _VIDEO_FPS,
        "width": _VIDEO_WIDTH,
        "height": _VIDEO_HEIGHT,
        "durationInFrames": _VIDEO_DURATION_FRAMES,
    }


def _retrieve_for_lecture(
    kp_id: str, kp_name: str, difficulty: str
) -> list[dict[str, Any]]:
    """讲义检索（B3 混合检索 → 重排），适配工作流 retriever 注入点签名。

    返回结构对齐 B5-a 约定：{id, content, metadata, score}（score 为重排分 0-1，
    重排降级时为 RRF 归一化分，回填 sources[].confidence）。
    """
    query = f"{kp_name} {difficulty}"
    candidates = get_retriever().search(query, top_k=_RETRIEVE_POOL)
    ranked, _used = get_reranker().rerank(query, candidates, top_k=_RETRIEVE_TOP_K)
    return [
        {
            "id": c["id"],
            "content": c["content"],
            "metadata": c.get("metadata") or {},
            "score": float(c.get("score", 0.0)),
        }
        for c in ranked
    ]


def _map_sources(db: Session, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """检索切片 → 接口文档 8.2 sources[]（按文档去重，取该文档最高分切片）。

    title = document_title · source_location；type = 文档 category（白名单外回落
    「文档」）；confidence = 该文档命中切片的最高重排分（0-1 截断）。
    """
    best_by_doc: dict[str, dict[str, Any]] = {}
    for c in chunks:
        meta = c.get("metadata") or {}
        doc_id = meta.get("document_id") or c.get("id", "")
        score = float(c.get("score", 0.0))
        if doc_id not in best_by_doc or score > best_by_doc[doc_id]["score"]:
            best_by_doc[doc_id] = {"meta": meta, "score": score}
    sources: list[dict[str, Any]] = []
    for doc_id, best in best_by_doc.items():
        meta = best["meta"]
        title = meta.get("document_title") or "知识库文档"
        location = meta.get("source_location")
        if location:
            title = f"{title} · {location}"
        doc = db.get(KnowledgeDocument, meta.get("document_id") or "")
        category = doc.category if doc is not None else None
        sources.append(
            {
                "title": title,
                "type": category if category in _SOURCE_TYPES else "文档",
                "confidence": round(min(max(best["score"], 0.0), 1.0), 2),
            }
        )
    return sources


def generate_lecture(
    db: Session, user_id: str, kp_id: str, difficulty: str
) -> dict[str, Any]:
    """生成自适应讲义（接口文档 8.2）。命中缓存直接返回。

    mock：LLMClient 确定性产出（B2 等价）；真实模式：RAG 检索 → 生成 Agent →
    审核 Agent 工作流，sources/hallucinationRate 为真实计算值。
    """
    kp = _require_kp(db, kp_id)
    if difficulty not in LECTURE_DIFFICULTIES:
        raise InvalidDifficulty(difficulty)

    # 学习该知识点 → 掌握度置 learning（未开始时）
    mastery_service.ensure_learning(db, user_id, kp_id)

    llm = get_llm()
    # mock 缓存 kind 与 B2 完全一致；真实模式按 provider 隔离，互不污染
    kind = "lecture" if llm.is_mock else f"lecture@{llm.provider}"
    cached = (
        db.query(ResourceCache)
        .filter(
            ResourceCache.kp_id == kp_id,
            ResourceCache.difficulty == difficulty,
            ResourceCache.kind == kind,
        )
        .one_or_none()
    )
    if cached is not None:
        return cached.payload

    if llm.is_mock:
        generated = llm.generate_lecture(kp.id, kp.name, difficulty, kp.description)
        markdown = generated["markdown"]
        sources = generated["sources"]
        rate = generated["hallucinationRate"]
    else:
        result = run_learning_workflow(
            db,
            user_id=user_id,
            kp_id=kp_id,
            difficulty=difficulty,
            retriever=_retrieve_for_lecture,
        )
        final = result["finalOutput"]
        markdown = final["markdown"]
        sources = _map_sources(db, result["trace"]["ragContextUsed"])
        rate = final["hallucinationRate"]

    payload = {
        "kpId": kp.id,
        "difficulty": difficulty,
        "markdown": markdown,
        "sources": sources,
        "hallucinationRate": rate,
    }
    db.add(
        ResourceCache(
            kp_id=kp_id,
            difficulty=difficulty,
            kind=kind,
            payload=payload,
            hallucination_rate=rate,
        )
    )
    db.commit()
    return payload
