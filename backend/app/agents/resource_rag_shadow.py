"""Resource Agent Trusted RAG shadow adapter (TASK-003-E3)."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.agents.adapters import ResourceGenerationInput
from app.agents.protocol import AgentMessage
from app.agents.state import AgentState
from app.agents.tools.rag_tool import RAGToolError
from app.agents.tools.registry import RAG_TOOL_NAME, ToolRegistry, get_tool_registry
from app.rag.protocol import RAGResponse, TrustReport


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResultDifference(_StrictModel):
    legacy_evidence_count: int = Field(ge=0)
    trusted_evidence_count: int = Field(ge=0)
    evidence_count_delta: int
    shared_reference_count: int = Field(ge=0)
    legacy_only_count: int = Field(ge=0)
    trusted_only_count: int = Field(ge=0)
    reference_jaccard: float = Field(ge=0.0, le=1.0)


class ToolEvent(_StrictModel):
    """Content-free event safe for logs and audit streams."""

    type: Literal["tool.request", "tool.result", "tool.error"]
    timestamp: datetime = Field(default_factory=_utc_now)
    traceId: str
    task_id: str
    agent: str
    tool: str
    latency_ms: float | None = Field(default=None, ge=0.0)
    evidence_count: int | None = Field(default=None, ge=0)
    trust_report: TrustReport | None = None
    result_difference: ResultDifference | None = None
    error_type: str | None = None


class ResourceRAGShadowResult(_StrictModel):
    """Legacy output remains authoritative; shadow data is observational only."""

    legacy_result: AgentMessage
    events: list[ToolEvent]
    legacy_latency_ms: float = Field(ge=0.0)
    tool_latency_ms: float = Field(ge=0.0)
    tool_failed: bool = False


class LegacyResourceAgent(Protocol):
    agent_name: str

    def run(
        self,
        *,
        task_id: str,
        agent_input: ResourceGenerationInput,
        state: AgentState | dict[str, Any] | None = None,
    ) -> AgentMessage: ...


class ResourceGenerationRAGShadowAdapter:
    """Run Legacy generation and Trusted RAG concurrently without cutover."""

    def __init__(
        self,
        legacy_agent: LegacyResourceAgent,
        *,
        user_id: str,
        trace_id: str,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.legacy_agent = legacy_agent
        self.user_id = user_id
        self.trace_id = trace_id
        self.registry = registry or get_tool_registry()

    @staticmethod
    def _legacy_references(agent_input: ResourceGenerationInput) -> set[str]:
        references: set[str] = set()
        for item in agent_input.rag_context:
            metadata = item.get("metadata") if isinstance(item, dict) else None
            metadata = metadata if isinstance(metadata, dict) else {}
            reference = (
                metadata.get("document_id")
                or metadata.get("docId")
                or item.get("documentId")
                or item.get("id")
            )
            if reference is not None:
                references.add(str(reference))
        return references

    @staticmethod
    def _trusted_references(response: RAGResponse) -> set[str]:
        references: set[str] = set()
        for evidence in response.evidence:
            reference = evidence.source.get("documentId") or evidence.source.get("chunkId")
            if reference is not None:
                references.add(str(reference))
        return references

    @classmethod
    def _difference(
        cls, agent_input: ResourceGenerationInput, response: RAGResponse
    ) -> ResultDifference:
        legacy = cls._legacy_references(agent_input)
        trusted = cls._trusted_references(response)
        union = legacy | trusted
        shared = legacy & trusted
        return ResultDifference(
            legacy_evidence_count=len(agent_input.rag_context),
            trusted_evidence_count=response.evidence_count,
            evidence_count_delta=response.evidence_count - len(agent_input.rag_context),
            shared_reference_count=len(shared),
            legacy_only_count=len(legacy - trusted),
            trusted_only_count=len(trusted - legacy),
            reference_jaccard=(len(shared) / len(union)) if union else 1.0,
        )

    @staticmethod
    def _timed(call):
        started = time.perf_counter()
        try:
            return call(), (time.perf_counter() - started) * 1000, None
        except Exception as exc:  # result is inspected and handled by the caller
            return None, (time.perf_counter() - started) * 1000, exc

    def run(
        self,
        *,
        task_id: str,
        agent_input: ResourceGenerationInput | dict[str, Any],
        state: AgentState | dict[str, Any] | None = None,
        knowledge_scope: str | list[str] | dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> ResourceRAGShadowResult:
        validated_input = ResourceGenerationInput.model_validate(agent_input)
        tool = self.registry.create_rag_tool(user_id=self.user_id, trace_id=self.trace_id)
        query = " ".join(
            part
            for part in (
                validated_input.kp_name,
                validated_input.description,
                validated_input.difficulty,
            )
            if part
        )
        events = [
            ToolEvent(
                type="tool.request",
                traceId=self.trace_id,
                task_id=task_id,
                agent=self.legacy_agent.agent_name,
                tool=RAG_TOOL_NAME,
            )
        ]

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="resource-rag-shadow") as pool:
            legacy_future = pool.submit(
                self._timed,
                lambda: self.legacy_agent.run(
                    task_id=task_id, agent_input=validated_input, state=state
                ),
            )
            tool_future = pool.submit(
                self._timed,
                lambda: tool.search(query, knowledge_scope, top_k),
            )
            legacy_result, legacy_ms, legacy_error = legacy_future.result()
            tool_result, tool_ms, tool_error = tool_future.result()

        if legacy_error is not None:
            raise legacy_error
        if not isinstance(legacy_result, AgentMessage):
            raise TypeError("legacy Resource Agent returned an invalid result")

        if tool_error is not None:
            events.append(
                ToolEvent(
                    type="tool.error",
                    traceId=self.trace_id,
                    task_id=task_id,
                    agent=self.legacy_agent.agent_name,
                    tool=RAG_TOOL_NAME,
                    latency_ms=round(tool_ms, 4),
                    error_type=type(tool_error).__name__,
                )
            )
            return ResourceRAGShadowResult(
                legacy_result=legacy_result,
                events=events,
                legacy_latency_ms=round(legacy_ms, 4),
                tool_latency_ms=round(tool_ms, 4),
                tool_failed=True,
            )

        if not isinstance(tool_result, RAGResponse):
            raise RAGToolError(self.trace_id)
        difference = self._difference(validated_input, tool_result)
        events.append(
            ToolEvent(
                type="tool.result",
                traceId=self.trace_id,
                task_id=task_id,
                agent=self.legacy_agent.agent_name,
                tool=RAG_TOOL_NAME,
                latency_ms=round(tool_ms, 4),
                evidence_count=tool_result.evidence_count,
                trust_report=tool_result.trust_report,
                result_difference=difference,
            )
        )
        return ResourceRAGShadowResult(
            legacy_result=legacy_result,
            events=events,
            legacy_latency_ms=round(legacy_ms, 4),
            tool_latency_ms=round(tool_ms, 4),
        )
