"""TASK-005-C Learning Evidence 统一适配层。

只负责把既有业务结果转换为 LearningEvent；不接入在线 API，也不改写 Mastery。
调用方必须提供来源记录的稳定 ID，事件 ID 因而可跨重试确定性复现。
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.models.entities import LearningStepProgress, QuizAttempt
from app.schemas.knowledge_state import LearningEvent
from app.services.knowledge_state import ALGORITHM_VERSION


class EvidenceAdapterError(ValueError):
    """原始证据无法安全转换。"""


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _event_id(source_type: str, source_id: str) -> str:
    if not source_id.strip():
        raise EvidenceAdapterError("source_id 不能为空")
    digest = hashlib.sha256(f"{source_type}:{source_id}".encode("utf-8")).hexdigest()[:24]
    return f"le_{digest}"


def _build(
    *,
    user_id: str,
    knowledge_id: str,
    event_type: str,
    source_type: str,
    source_id: str,
    score: float,
    occurred_at: datetime,
) -> LearningEvent:
    return LearningEvent(
        event_id=_event_id(source_type, source_id),
        user_id=user_id,
        knowledge_id=knowledge_id,
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        algorithm_version=ALGORITHM_VERSION,
        score=max(0.0, min(1.0, float(score))),
        timestamp=_aware_utc(occurred_at),
    )


def from_quiz_result(attempt: QuizAttempt) -> LearningEvent:
    """QuizAttempt → 强能力证据。记录必须先 flush/落库以取得稳定主键。"""
    if attempt.id is None:
        raise EvidenceAdapterError("QuizAttempt 尚无稳定 id")
    return _build(
        user_id=attempt.user_id,
        knowledge_id=attempt.kp_id,
        event_type="quiz",
        source_type="quiz_result",
        source_id=f"quiz_attempt:{attempt.id}",
        score=attempt.score / 100.0,
        occurred_at=attempt.created_at,
    )


def from_diagnostic(
    *,
    user_id: str,
    result: dict[str, Any],
    source_id: str,
    occurred_at: datetime,
) -> LearningEvent:
    """诊断单题结果 → 低权重能力基线；跳过题不产生事件。"""
    correct = result.get("correct")
    if correct is None:
        raise EvidenceAdapterError("未作答诊断结果不能转换为 LearningEvent")
    kp_id = str(result.get("kpId") or "")
    if not kp_id:
        raise EvidenceAdapterError("诊断结果缺少 kpId")
    return _build(
        user_id=user_id,
        knowledge_id=kp_id,
        event_type="diagnostic",
        source_type="diagnostic",
        source_id=source_id,
        score=0.78 if bool(correct) else 0.32,
        occurred_at=occurred_at,
    )


def from_feynman(
    *,
    user_id: str,
    knowledge_id: str,
    result: dict[str, Any],
    source_id: str,
    occurred_at: datetime,
) -> LearningEvent:
    """费曼评估结果 → 概念理解证据，采用既有 0-100 score。"""
    if "score" not in result:
        raise EvidenceAdapterError("费曼结果缺少 score")
    return _build(
        user_id=user_id,
        knowledge_id=knowledge_id,
        event_type="feynman",
        source_type="feynman",
        source_id=source_id,
        score=float(result["score"]) / 100.0,
        occurred_at=occurred_at,
    )


def from_learning_step(progress: LearningStepProgress) -> LearningEvent:
    """已完成学习步骤 → 弱过程证据；取消完成不是正向证据。"""
    if progress.id is None:
        raise EvidenceAdapterError("LearningStepProgress 尚无稳定 id")
    if not progress.done:
        raise EvidenceAdapterError("未完成或取消完成的步骤不能转换为 LearningEvent")
    return _build(
        user_id=progress.user_id,
        knowledge_id=progress.kp_id,
        event_type="learning_step",
        source_type="learning_step",
        source_id=f"learning_step:{progress.id}:{progress.step}",
        score=1.0,
        occurred_at=progress.updated_at,
    )
