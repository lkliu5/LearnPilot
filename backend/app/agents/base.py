"""Agent抽象基类（TASK-002-B1）。

新框架与现有函数式Agent并行存在；本阶段不迁移任何业务逻辑。
"""
from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.agents.protocol import AgentMessage
from app.agents.state import AgentState
from app.core.envelope import current_trace_id

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """带Schema校验、统一日志和traceId的Agent执行模板。"""

    agent_name: str
    description: str
    input_schema: type[InputT]
    output_schema: type[OutputT]

    def __init__(
        self,
        *,
        trace_id: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.trace_id = trace_id or current_trace_id() or f"agt_{uuid.uuid4().hex[:12]}"
        self.logger = logger or logging.getLogger(
            f"app.agents.{getattr(self, 'agent_name', type(self).__name__)}"
        )
        self._validate_definition()

    def _validate_definition(self) -> None:
        for name in ("agent_name", "description", "input_schema", "output_schema"):
            if not hasattr(self, name):
                raise TypeError(f"{type(self).__name__} must define {name}")
        if not self.agent_name.strip() or not self.description.strip():
            raise TypeError("agent_name and description must not be blank")
        if not issubclass(self.input_schema, BaseModel):
            raise TypeError("input_schema must be a Pydantic BaseModel")
        if not issubclass(self.output_schema, BaseModel):
            raise TypeError("output_schema must be a Pydantic BaseModel")

    def log_event(self, event: str, **details: Any) -> None:
        """统一Agent日志接口；不记录完整输入输出，避免隐私和大文本泄漏。"""
        suffix = " ".join(f"{key}={value}" for key, value in sorted(details.items()))
        self.logger.info(
            "agent_event event=%s agent=%s traceId=%s%s",
            event,
            self.agent_name,
            self.trace_id,
            f" {suffix}" if suffix else "",
        )

    @abstractmethod
    def execute(self, agent_input: InputT, state: AgentState) -> OutputT:
        """实现单次Agent能力；不得绕过声明的输入输出Schema。"""
        raise NotImplementedError

    def run(
        self,
        *,
        task_id: str,
        agent_input: InputT | dict[str, Any],
        state: AgentState | dict[str, Any] | None = None,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> AgentMessage:
        """校验输入和状态，执行Agent并生成统一消息。"""
        validated_input = self.input_schema.model_validate(agent_input)
        validated_state = AgentState.model_validate(state or {})
        self.log_event("started", task_id=task_id)
        try:
            raw_output = self.execute(validated_input, validated_state)
            validated_output = self.output_schema.model_validate(raw_output)
        except Exception:
            self.logger.exception(
                "agent_event event=failed agent=%s traceId=%s task_id=%s",
                self.agent_name,
                self.trace_id,
                task_id,
            )
            raise
        self.log_event("completed", task_id=task_id)
        message_metadata = dict(metadata or {})
        message_metadata.setdefault("traceId", self.trace_id)
        message_metadata.setdefault("description", self.description)
        return AgentMessage(
            task_id=task_id,
            agent_name=self.agent_name,
            input=validated_input.model_dump(mode="json"),
            output=validated_output.model_dump(mode="json"),
            confidence=confidence,
            metadata=message_metadata,
        )

