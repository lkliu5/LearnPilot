"""Trusted Retrieval Pipeline统一入口（TASK-003-B2）。

本阶段只建立协议、流程和旧Retriever适配，不改变现有检索算法。
"""
from __future__ import annotations

import re
from typing import Any, Protocol

from app.rag.protocol import EvidenceItem, QueryPlan, RAGRequest, RAGResponse
from app.rag.retriever import get_retriever

_KEYWORD_RE = re.compile(r"[A-Za-z0-9_+#.-]+|[一-鿿]+")


class Retriever(Protocol):
    """兼容现有HybridRetriever的最小检索接口。"""

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]: ...


class QueryPlanner(Protocol):
    def plan(self, request: RAGRequest) -> QueryPlan: ...


class BasicQueryPlanner:
    """零LLM的基础规划器；后续可替换为Query理解组件。"""

    def plan(self, request: RAGRequest) -> QueryPlan:
        filters: dict[str, Any] = {}
        if request.knowledge_scope is not None:
            filters["knowledge_scope"] = request.knowledge_scope
        keywords = list(dict.fromkeys(_KEYWORD_RE.findall(request.query.lower())))
        return QueryPlan(intent="retrieve", keywords=keywords, filters=filters)


class TrustedRetrievalPipeline:
    """Request → QueryPlan → Retriever → Evidence → Response。"""

    schema_version = "rag-response-v1"

    def __init__(
        self,
        retriever: Retriever | None = None,
        planner: QueryPlanner | None = None,
    ) -> None:
        self.retriever = retriever or get_retriever()
        self.planner = planner or BasicQueryPlanner()

    @staticmethod
    def _score(candidate: dict[str, Any]) -> float:
        raw = candidate.get("score")
        if raw is None:
            raw = candidate.get("rrfScore")
        if raw is None:
            raw = candidate.get("vectorScore", 0.0)
        return round(max(0.0, min(1.0, float(raw))), 4)

    @classmethod
    def _evidence(cls, candidate: dict[str, Any]) -> EvidenceItem:
        metadata = dict(candidate.get("metadata") or {})
        source = {
            "chunkId": candidate.get("id"),
            "documentId": metadata.get("document_id") or metadata.get("docId"),
            "title": metadata.get("document_title") or metadata.get("title"),
            "location": metadata.get("source_location"),
        }
        source = {key: value for key, value in source.items() if value is not None}
        retrieval_metadata = {
            **metadata,
            "vectorScore": candidate.get("vectorScore"),
            "bm25Score": candidate.get("bm25Score"),
            "rrfScore": candidate.get("rrfScore"),
        }
        retrieval_metadata = {
            key: value for key, value in retrieval_metadata.items() if value is not None
        }
        return EvidenceItem(
            content=str(candidate.get("content") or ""),
            source=source,
            score=cls._score(candidate),
            metadata=retrieval_metadata,
        )

    def execute(self, request: RAGRequest | dict[str, Any]) -> RAGResponse:
        validated_request = RAGRequest.model_validate(request)
        plan = self.planner.plan(validated_request)
        candidates = self.retriever.search(
            validated_request.query,
            top_k=validated_request.top_k,
        )
        evidence = [self._evidence(candidate) for candidate in candidates]
        confidence = max((item.score for item in evidence), default=0.0)
        return RAGResponse(
            evidence=evidence,
            confidence=confidence,
            metadata={
                "schemaVersion": self.schema_version,
                "queryPlan": plan.model_dump(mode="json"),
                "resultCount": len(evidence),
                "retriever": type(self.retriever).__name__,
            },
        )


_pipeline: TrustedRetrievalPipeline | None = None


def get_trusted_retrieval_pipeline() -> TrustedRetrievalPipeline:
    """未来RAG调用的统一默认入口。"""
    global _pipeline
    if _pipeline is None:
        _pipeline = TrustedRetrievalPipeline()
    return _pipeline
