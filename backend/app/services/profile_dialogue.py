"""对话式学习画像诊断服务（接口文档 17.1，C1-b）。

编排 DialogueDiagnosticAgent 的一轮对话，并把抽取的画像维度增量写入
StudentPortrait（随学随新）。SSE / JSON 双模式与 8.7/15.4 苏格拉底辅导一脉
相承，复用同一套 _sse_block 流式封装：

- 会话上下文：进程内存 dict，TTL 30 分钟（CLAUDE.md 内存 TTL 会话；生产替换
  Redis，写 README）。过期/未知 sessionId → 以该 id（或新 id，前缀 d_）重建空
  上下文（前端无感知，历史自然清零）；
- JSON 模式（17.1）：{sessionId, reply, portraitUpdates, suggestions, diagnosisComplete}；
- SSE 模式（17.1）：data:{"delta":..} 逐句下发追问 → event: portrait 携带本轮维度
  增量 → event: done 携带 sessionId/suggestions/diagnosisComplete；
  生成异常 → event: error {code:2001,...}（前端保留已渲染片段与已抽取维度）。

SSE 生成器在自有 SQLAlchemy 会话内完成「读画像 → Agent → 写画像」（请求级 db
依赖在 StreamingResponse 消费生成器前已关闭，故不能复用），保证流式期间 DB 可用。
"""
from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from app.agents import dialogue_agent
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.llm import LLMGenerationError
from app.services import student_portrait

# 会话 TTL：30 分钟（与 8.7 苏格拉底辅导同口径）
SESSION_TTL_SECONDS = 30 * 60

# sessionId → {sessionId, userId, history:[{role,content}], expiresAt(monotonic)}
_sessions: dict[str, dict[str, Any]] = {}

# 按句切分回复用于 SSE 逐条下发（保留句末标点，贴合 17.1「逐条下发追问语」）
_SENTENCE_RE = re.compile(r"[^。！？!?]*[。！？!?]|[^。！？!?]+")


def _gc() -> None:
    """惰性清理过期会话（访问时触发，无后台线程）。"""
    now = time.monotonic()
    for sid in [s for s, v in _sessions.items() if v["expiresAt"] < now]:
        _sessions.pop(sid, None)


def _get_session(session_id: str | None, user_id: str) -> dict[str, Any]:
    """取/建会话并续期。过期或未知 id → 以该 id（或新 d_ 前缀 id）重建空上下文。"""
    _gc()
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        session["expiresAt"] = time.monotonic() + SESSION_TTL_SECONDS
        return session
    sid = session_id or f"d_{uuid.uuid4().hex[:10]}"
    session = {
        "sessionId": sid,
        "userId": user_id,
        "history": [],
        "asked": [],  # 已追问过的维度 key（推进对话，避免重复追问）
        "expiresAt": time.monotonic() + SESSION_TTL_SECONDS,
    }
    _sessions[sid] = session
    return session


def _append_turn(session: dict[str, Any], message: str, reply: str) -> None:
    session["history"].append({"role": "user", "content": message})
    session["history"].append({"role": "assistant", "content": reply})


def _run_turn(
    db: Session, session: dict[str, Any], message: str, context: dict[str, Any] | None
) -> dict[str, Any]:
    """单轮诊断：读当前画像 → Agent 抽取/追问 → 写回画像增量 → 记会话历史。"""
    first_turn = not session["history"]
    portrait = student_portrait.get_portrait(db, session["userId"])
    known_keys = [d["key"] for d in portrait["dimensions"]]
    result = dialogue_agent.respond(
        context=context,
        history=list(session["history"]),
        message=message,
        known_keys=known_keys,
        asked_keys=list(session["asked"]),
        first_turn=first_turn,
    )
    if result["updates"]:  # 随学随新：抽取增量即时落库
        student_portrait.apply_updates(db, session["userId"], result["updates"])
    if result["focus"]:  # 记录本轮追问维度，推进对话
        session["asked"].append(result["focus"])
    _append_turn(session, message, result["reply"])
    return result


def dialogue(
    db: Session,
    *,
    user_id: str,
    session_id: str | None,
    message: str,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    """JSON 整体回复（接口文档 17.1 非流式）。"""
    session = _get_session(session_id, user_id)
    result = _run_turn(db, session, message, context)
    return {
        "sessionId": session["sessionId"],
        "reply": result["reply"],
        "portraitUpdates": result["updates"],
        "suggestions": result["suggestions"],
        "diagnosisComplete": result["diagnosisComplete"],
    }


def _sse_block(payload: dict[str, Any], event: str | None = None) -> str:
    """SSE 块（17.1/15.4）：可选 event 行 + data 行 + 空行分隔。"""
    data = json.dumps(payload, ensure_ascii=False)
    if event:
        return f"event: {event}\ndata: {data}\n\n"
    return f"data: {data}\n\n"


def _chunk_reply(reply: str) -> list[str]:
    """按句切分回复供 delta 逐条下发；空回复兜底为单块。"""
    chunks = [m.group(0) for m in _SENTENCE_RE.finditer(reply) if m.group(0).strip()]
    return chunks or [reply]


def sse_stream(
    *,
    user_id: str,
    session_id: str | None,
    message: str,
    context: dict[str, Any] | None,
) -> Iterator[str]:
    """SSE 流式回复（接口文档 17.1）。

    逐句 delta → event: portrait（本轮维度增量，有则发）→ event: done
    （sessionId/suggestions/diagnosisComplete）；生成异常 → event: error
    {code:2001,...}，已发 delta 与已写入画像由前端保留。
    """
    session = _get_session(session_id, user_id)

    def _events() -> Iterator[str]:
        db = SessionLocal()
        try:
            result = _run_turn(db, session, message, context)
            delay = settings.tutor_stream_delay_ms / 1000
            for chunk in _chunk_reply(result["reply"]):
                if delay > 0:
                    time.sleep(delay)
                yield _sse_block({"delta": chunk})
            if result["updates"]:
                yield _sse_block({"updates": result["updates"]}, event="portrait")
            yield _sse_block(
                {
                    "sessionId": session["sessionId"],
                    "suggestions": result["suggestions"],
                    "diagnosisComplete": result["diagnosisComplete"],
                },
                event="done",
            )
        except LLMGenerationError as exc:
            yield _sse_block({"code": 2001, "message": str(exc)}, event="error")
        finally:
            db.close()

    return _events()
