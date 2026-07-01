"""基于文档的内容生成（「文档学习」平行链路核心）。

以**上传文档**为知识源（该文档专属向量集合检索），复用现有生成/审核/防幻觉/内容安全
引擎产出：讲义 / 视频分镜 / 图解 / 思维导图 / 练习题 / 闪卡。与内置课程主线（画像/诊断/
路径/掌握度/既有生成接口）**完全解耦**——不读画像、不写掌握度、不碰 KnowledgePoint。

复用点（不重造）：
- 检索：rag.retriever.get_document_retriever（文档专属集合）+ rag.reranker 重排；
- 讲义生成：agents.generator_agent.run_generator（RAG 上下文驱动，mock/real 双模）；
- 防幻觉：rag.grounding.sentence_grounding（逐句 vs 文档切片，mock 环境亦生效）；
- 图解/视频/练习题/闪卡：core.llm.LLMClient 对应方法（内容安全已在 llm 层统一钝化）；
- 内容安全：LLM 生成方法均经 content_safety.guarded；非 LLM 产物（思维导图）显式 guard；
- 资源库：generation_log.record_document 带文档来源标识写入「我的资源库」。
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.agents.generator_agent import run_generator
from app.core import content_safety, lecture_media
from app.core.llm import LECTURE_DIFFICULTIES, get_llm
from app.models.entities import Document
from app.rag.grounding import sentence_grounding
from app.rag.reranker import get_reranker
from app.rag.retriever import get_document_retriever
from app.rag.vector_store import get_collection_store
from app.services import document_store, generation_log

# 检索候选池 / 注入生成的切片数（与内置讲义 _RETRIEVE_POOL/TOP_K 同量级）
_RETRIEVE_POOL = 12
_RETRIEVE_TOP_K = 6
# 视频分镜铺帧参数（与 services.resource 内置视频、前端 Remotion 组件一致）
_VIDEO_FPS = 30
_VIDEO_WIDTH = 1280
_VIDEO_HEIGHT = 720
_SCENE_FRAMES = 180

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")


class DocumentNotReady(Exception):
    """文档尚未完成入库（status != indexed）→ code 1001 / 400。"""


class InvalidDifficulty(Exception):
    """难度档非法 → code 1001 / 400。"""


# ---- 文档检索（专属集合，隔离内置库） --------------------------------------
def _retrieve(doc: Document, query: str, top_k: int = _RETRIEVE_TOP_K) -> list[dict[str, Any]]:
    """在文档专属向量集合上混合检索 + 重排；空结果回落按 chunk 顺序取前 top_k。"""
    candidates = get_document_retriever(doc.collection).search(query, top_k=_RETRIEVE_POOL)
    if candidates:
        ranked, _used = get_reranker().rerank(query, candidates, top_k=top_k)
        chunks = ranked
    else:
        # 检索为空（如降级嵌入 + 极短文档）→ 直接取集合内切片，保证生成始终有文档上下文
        chunks = get_collection_store(doc.collection).get_all()[:top_k]
    return [
        {
            "id": c.get("id", ""),
            "content": c.get("content", ""),
            "metadata": c.get("metadata") or {},
            "score": float(c.get("score", 0.0)),
        }
        for c in chunks
        if c.get("content")
    ]


def _contexts(chunks: list[dict[str, Any]]) -> list[str]:
    return [c["content"] for c in chunks if c.get("content")]


def _summary(chunks: list[dict[str, Any]], *, limit: int = 1200) -> str:
    """文档要点摘要（拼接命中切片，供 description 驱动图解/视频生成，内容来自文档）。"""
    return "\n".join(_contexts(chunks))[:limit]


def _sources(doc: Document, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """检索切片 → 来源标注（按文档切片位置，confidence=重排分）。始终标注为本文档来源。"""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in chunks:
        meta = c.get("metadata") or {}
        loc = meta.get("source_location") or "正文"
        title = f"{doc.title} · {loc}"
        if title in seen:
            continue
        seen.add(title)
        out.append(
            {
                "title": title,
                "type": "文档",
                "confidence": round(min(max(float(c.get("score", 0.0)), 0.0), 1.0), 2),
            }
        )
    return out


def _require_ready(doc: Document) -> None:
    if doc.status != "indexed":
        raise DocumentNotReady(doc.status)


# ---- 讲义（复用生成 Agent + 逐句接地防幻觉） --------------------------------
def generate_lecture(
    db: Session, user_id: str, doc_id: str, difficulty: str = "初级"
) -> dict[str, Any]:
    """基于文档生成自适应讲义。复用 generator_agent（RAG 驱动）+ sentence_grounding（防幻觉）。"""
    doc = document_store.require_document(db, user_id, doc_id)
    _require_ready(doc)
    if difficulty not in LECTURE_DIFFICULTIES:
        raise InvalidDifficulty(difficulty)

    chunks = _retrieve(doc, f"{doc.title} 核心概念 重点", top_k=_RETRIEVE_TOP_K)
    res = run_generator(
        db,
        kp_name=doc.title,
        difficulty=difficulty,
        rag_context=chunks,
        description=_summary(chunks),
    )
    markdown = res["output"]["markdown"]
    # 图文增强（复用讲义配图/图解注入；kp_id 传文档专属标识，不与内置知识点冲突）
    markdown = lecture_media.enrich_lecture(
        markdown, kp_id=f"doc:{doc_id}", kp_name=doc.title, description=_summary(chunks), llm=get_llm()
    )
    # 防幻觉：逐句 vs 文档切片接地校验（对文档而非内置课程，mock/降级环境同样生效）
    grounding = sentence_grounding(markdown, _contexts(chunks))
    payload = {
        "docId": doc_id,
        "difficulty": difficulty,
        "markdown": markdown,
        "sources": _sources(doc, chunks),
        "hallucinationRate": grounding["hallucinationRate"],
    }
    generation_log.record_document(db, user_id, doc_id, doc.title, "lecture", difficulty=difficulty)
    return payload


# ---- 图解（复用 LLMClient.generate_diagram，文档内容驱动） ------------------
def generate_diagram(db: Session, user_id: str, doc_id: str) -> dict[str, Any]:
    doc = document_store.require_document(db, user_id, doc_id)
    _require_ready(doc)
    chunks = _retrieve(doc, f"{doc.title} 结构 流程 关系")
    payload = get_llm().generate_diagram(f"doc:{doc_id}", doc.title, _summary(chunks))
    generation_log.record_document(db, user_id, doc_id, doc.title, "diagram")
    return {"docId": doc_id, "mermaid": payload["mermaid"], "sources": _sources(doc, chunks)}


# ---- 思维导图（从文档标题/结构确定性抽取，内容来自文档） --------------------
def generate_mindmap(db: Session, user_id: str, doc_id: str) -> dict[str, Any]:
    doc = document_store.require_document(db, user_id, doc_id)
    _require_ready(doc)
    markdown = _build_mindmap(doc)
    markdown = content_safety.guard(markdown, where="document_mindmap")
    generation_log.record_document(db, user_id, doc_id, doc.title, "mindmap")
    return {"docId": doc_id, "markdown": markdown}


def _build_mindmap(doc: Document) -> str:
    """优先按文档 Markdown 标题层级构建 Markmap 大纲；无标题则用要点句作二级节点。"""
    lines = [f"# {doc.title}"]
    headings = [
        (len(m.group(1)), m.group(2).strip())
        for raw in (doc.content or "").splitlines()
        if (m := _HEADING_RE.match(raw.strip()))
    ]
    if len(headings) >= 2:
        base = min(lv for lv, _ in headings)
        for lv, title in headings[:40]:
            # 归一到二级起（# 已占一级）：相对深度 + 1
            depth = min(lv - base + 2, 6)
            lines.append(f"{'#' * depth} {title[:40]}")
        return "\n".join(lines)
    # 无标题结构 → 取文档要点句作二级节点（内容来自文档）
    chunks = _retrieve(doc, f"{doc.title} 要点", top_k=6)
    from app.core.llm import _doc_key_sentences  # 复用确定性要点抽取

    for sent in _doc_key_sentences(_contexts(chunks), max_n=8):
        lines.append(f"## {sent[:36]}")
    if len(lines) == 1:
        lines.append("## 核心概念")
        lines.append("## 实践应用")
    return "\n".join(lines)


# ---- 视频分镜（复用 LLMClient.generate_video_script + 铺帧） ----------------
def generate_video(
    db: Session, user_id: str, doc_id: str, difficulty: str = "初级"
) -> dict[str, Any]:
    doc = document_store.require_document(db, user_id, doc_id)
    _require_ready(doc)
    if difficulty not in LECTURE_DIFFICULTIES:
        raise InvalidDifficulty(difficulty)
    chunks = _retrieve(doc, f"{doc.title} 讲解 要点")
    script = get_llm().generate_video_script(
        f"doc:{doc_id}", doc.title, difficulty, _summary(chunks)
    )
    scenes: list[dict[str, Any]] = []
    narration: list[dict[str, Any]] = []
    for i, s in enumerate(script["scenes"]):
        frame = i * _SCENE_FRAMES
        scenes.append(
            {"frame": frame, "title": s["title"], "points": list(s["points"]), "narration": s["narration"]}
        )
        narration.append({"frame": frame, "text": s["narration"]})
    generation_log.record_document(db, user_id, doc_id, doc.title, "video", difficulty=difficulty)
    return {
        "docId": doc_id,
        "difficulty": difficulty,
        "videoUrl": None,  # 无服务端渲染 → 前端 Remotion Player + TTS（与内置 8.3 同口径）
        "title": script["title"],
        "scenes": scenes,
        "narration": narration,
        "fps": _VIDEO_FPS,
        "width": _VIDEO_WIDTH,
        "height": _VIDEO_HEIGHT,
        "durationInFrames": len(scenes) * _SCENE_FRAMES,
        "sources": _sources(doc, chunks),
    }


# ---- 练习题（复用 LLMClient.generate_doc_quiz + audit_practice 审核） -------
def generate_quiz(
    db: Session, user_id: str, doc_id: str, count: int = 5
) -> dict[str, Any]:
    doc = document_store.require_document(db, user_id, doc_id)
    _require_ready(doc)
    chunks = _retrieve(doc, f"{doc.title} 重点 考点", top_k=_RETRIEVE_TOP_K)
    result = get_llm().generate_doc_quiz(doc.title, _contexts(chunks), count=count)
    generation_log.record_document(db, user_id, doc_id, doc.title, "quiz")
    return {"docId": doc_id, "questions": result["questions"], "sources": _sources(doc, chunks)}


# ---- 闪卡（新做，走 LLMClient，mock 确定性兜底） ---------------------------
def generate_flashcards(
    db: Session, user_id: str, doc_id: str, count: int = 8
) -> dict[str, Any]:
    doc = document_store.require_document(db, user_id, doc_id)
    _require_ready(doc)
    chunks = _retrieve(doc, f"{doc.title} 要点 概念", top_k=_RETRIEVE_TOP_K)
    result = get_llm().generate_flashcards(doc.title, _contexts(chunks), count=count)
    generation_log.record_document(db, user_id, doc_id, doc.title, "flashcard")
    return {"docId": doc_id, "cards": result["cards"], "sources": _sources(doc, chunks)}
