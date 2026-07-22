"""Central Agent tool registry (TASK-003-E3)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from app.agents.tools.rag_tool import AgentRAGPort, RAGTool

ToolFactory = Callable[..., object]
RAG_TOOL_NAME = "trusted_rag"


class ToolRegistry:
    """Small extensible registry; RAGTool is the first built-in capability."""

    def __init__(self) -> None:
        self._factories: dict[str, ToolFactory] = {RAG_TOOL_NAME: RAGTool}

    @property
    def available_tools(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    def register(
        self, name: str, factory: ToolFactory, *, replace: bool = False
    ) -> None:
        normalized = name.strip()
        if not normalized:
            raise ValueError("tool name must not be blank")
        if normalized in self._factories and not replace:
            raise ValueError(f"tool already registered: {normalized}")
        self._factories[normalized] = factory

    def create(self, name: str, **kwargs: Any) -> object:
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc
        return factory(**kwargs)

    def create_rag_tool(self, *, user_id: str, trace_id: str) -> AgentRAGPort:
        tool = self.create(RAG_TOOL_NAME, user_id=user_id, trace_id=trace_id)
        if not isinstance(tool, AgentRAGPort):
            raise TypeError("registered trusted_rag tool does not implement AgentRAGPort")
        return cast(AgentRAGPort, tool)


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
