"""TASK-005-B 知识状态查询、确定性更新与历史服务。

该服务是独立领域层，不接入 API、Agent、Workflow、RAG，也不改写对外 Mastery。
迟到事件会按时间顺序重放该用户/节点的完整事件序列，结果可确定性复现。
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    KnowledgePoint,
    LearningEventRecord,
    User,
    UserKnowledgeStateRecord,
)
from app.schemas.knowledge_state import LearningEvent, UserKnowledgeState

ALGORITHM_VERSION = "ks-logodds-v1"
NEUTRAL_MASTERY = 0.5
LEARNING_RATE = 2.0
CONFIDENCE_RATE = 1.0
MASTERY_DECAY_DAYS = 30.0
CONFIDENCE_DECAY_DAYS = 60.0
EPSILON = 1e-6

EVENT_WEIGHTS = {
    "quiz": 1.00,
    "practice": 0.90,
    "feynman": 0.70,
    "diagnostic": 0.55,
    "retrieval": 0.50,
    "learning_step": 0.15,
    "self_report": 0.10,
}


class KnowledgeStateError(ValueError):
    """知识状态服务领域错误基类。"""


class UnknownUser(KnowledgeStateError):
    pass


class UnknownKnowledgeNode(KnowledgeStateError):
    pass


class KnowledgeStateServiceProtocol(Protocol):
    """供 TASK-005-C 及后续调用方依赖的最小协议；本阶段不接入调用方。"""

    def get_state(self, user_id: str, knowledge_id: str) -> UserKnowledgeState | None: ...

    def update_state(self, event: LearningEvent) -> UserKnowledgeState: ...

    def get_history(
        self, user_id: str, knowledge_id: str | None = None
    ) -> list[LearningEvent]: ...


def _utc_naive(value: datetime) -> datetime:
    """SQLite 统一存 UTC naive；领域协议输入仍强制携带时区。"""
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _advance(
    mastery: float,
    confidence: float,
    previous_at: datetime | None,
    event: LearningEventRecord,
) -> tuple[float, float]:
    if previous_at is not None:
        elapsed_days = max(0.0, (event.timestamp - previous_at).total_seconds() / 86400.0)
        mastery = NEUTRAL_MASTERY + (mastery - NEUTRAL_MASTERY) * math.exp(
            -elapsed_days / MASTERY_DECAY_DAYS
        )
        confidence *= math.exp(-elapsed_days / CONFIDENCE_DECAY_DAYS)

    weight = EVENT_WEIGHTS[event.event_type]
    bounded = min(1.0 - EPSILON, max(EPSILON, mastery))
    log_odds = math.log(bounded / (1.0 - bounded))
    mastery = _sigmoid(log_odds + LEARNING_RATE * weight * (2.0 * event.score - 1.0))
    confidence = 1.0 - (1.0 - confidence) * math.exp(-CONFIDENCE_RATE * weight)
    return mastery, confidence


class KnowledgeStateService:
    """基于 SQLAlchemy Session 的知识状态服务协议实现。"""

    def __init__(self, db: Session):
        self.db = db

    def get_state(self, user_id: str, knowledge_id: str) -> UserKnowledgeState | None:
        row = self.db.scalar(
            select(UserKnowledgeStateRecord).where(
                UserKnowledgeStateRecord.user_id == user_id,
                UserKnowledgeStateRecord.knowledge_id == knowledge_id,
            )
        )
        return self._state_model(row) if row is not None else None

    def update_state(self, event: LearningEvent) -> UserKnowledgeState:
        self._validate_references(event.user_id, event.knowledge_id)
        event_row = LearningEventRecord(
            user_id=event.user_id,
            knowledge_id=event.knowledge_id,
            event_type=event.event_type.value,
            score=event.score,
            timestamp=_utc_naive(event.timestamp),
        )
        self.db.add(event_row)
        self.db.flush()

        history = self._history_rows(event.user_id, event.knowledge_id)
        mastery = NEUTRAL_MASTERY
        confidence = 0.0
        previous_at: datetime | None = None
        for item in history:
            mastery, confidence = _advance(mastery, confidence, previous_at, item)
            previous_at = item.timestamp

        state_row = self.db.scalar(
            select(UserKnowledgeStateRecord).where(
                UserKnowledgeStateRecord.user_id == event.user_id,
                UserKnowledgeStateRecord.knowledge_id == event.knowledge_id,
            )
        )
        assert previous_at is not None
        if state_row is None:
            state_row = UserKnowledgeStateRecord(
                user_id=event.user_id,
                knowledge_id=event.knowledge_id,
                mastery_score=mastery,
                confidence=confidence,
                last_updated=previous_at,
            )
            self.db.add(state_row)
        else:
            state_row.mastery_score = mastery
            state_row.confidence = confidence
            state_row.last_updated = previous_at
        self.db.commit()
        self.db.refresh(state_row)
        return self._state_model(state_row)

    def get_history(
        self, user_id: str, knowledge_id: str | None = None
    ) -> list[LearningEvent]:
        query = select(LearningEventRecord).where(LearningEventRecord.user_id == user_id)
        if knowledge_id is not None:
            query = query.where(LearningEventRecord.knowledge_id == knowledge_id)
        rows = self.db.scalars(
            query.order_by(LearningEventRecord.timestamp, LearningEventRecord.id)
        ).all()
        return [
            LearningEvent(
                user_id=row.user_id,
                knowledge_id=row.knowledge_id,
                event_type=row.event_type,
                score=row.score,
                timestamp=_utc_aware(row.timestamp),
            )
            for row in rows
        ]

    def _history_rows(self, user_id: str, knowledge_id: str) -> list[LearningEventRecord]:
        return list(
            self.db.scalars(
                select(LearningEventRecord)
                .where(
                    LearningEventRecord.user_id == user_id,
                    LearningEventRecord.knowledge_id == knowledge_id,
                )
                .order_by(LearningEventRecord.timestamp, LearningEventRecord.id)
            ).all()
        )

    def _validate_references(self, user_id: str, knowledge_id: str) -> None:
        if self.db.get(User, user_id) is None:
            raise UnknownUser(user_id)
        if self.db.get(KnowledgePoint, knowledge_id) is None:
            raise UnknownKnowledgeNode(knowledge_id)

    @staticmethod
    def _state_model(row: UserKnowledgeStateRecord) -> UserKnowledgeState:
        return UserKnowledgeState(
            user_id=row.user_id,
            knowledge_id=row.knowledge_id,
            mastery_score=row.mastery_score,
            confidence=row.confidence,
            last_updated=_utc_aware(row.last_updated),
        )
