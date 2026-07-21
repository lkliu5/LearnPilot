"""并行学习任务Agent子图（TASK-002-B3）。

本图只消费新BaseAgent/Adapter体系，不替换也不导入旧learning_workflow。
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import ConfigDict, Field
from sqlalchemy.orm import Session

from app.agents.adapters import (
    EvaluationAgentAdapter,
    LearningDiagnosisAgentAdapter,
    ResourceGenerationAgentAdapter,
)
from app.agents.protocol import AgentMessage
from app.agents.state import AgentState
from app.core.envelope import current_trace_id
from app.workflows.base import BaseWorkflow


class LearningGraphState(AgentState):
    """第一个学习任务子图状态；扩展B1基础状态而不改变其公共契约。"""

    model_config = ConfigDict(extra="forbid")

    resources: list[dict[str, Any]] = Field(default_factory=list)
    evaluation: dict[str, Any] = Field(default_factory=dict)


class LearningTaskWorkflow(BaseWorkflow[LearningGraphState]):
    """Diagnosis → Resource → Evaluation 的并行实验子图。"""

    workflow_name = "learning_task_agent_graph"
    state_schema = LearningGraphState

    def __init__(self, db: Session, *, trace_id: str | None = None) -> None:
        self.db = db
        self.trace_id = (
            trace_id or current_trace_id() or f"lwf_{uuid.uuid4().hex[:12]}"
        )
        self._graph = None
        super().__init__()

    @staticmethod
    def _required(mapping: dict[str, Any], key: str) -> Any:
        value = mapping.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"学习子图缺少必要上下文：{key}")
        return value

    @staticmethod
    def _history(
        state: LearningGraphState, message: AgentMessage
    ) -> list[AgentMessage]:
        return [*state.execution_history, message]

    def _task_id(self, state: LearningGraphState, stage: str) -> str:
        root = str(state.task_context.get("task_id") or self.trace_id)
        return f"{root}:{stage}"

    def diagnosis_node(self, state: LearningGraphState) -> dict[str, Any]:
        task = state.task_context
        user = state.user_context
        mastery = task.get("mastery_status", state.knowledge_state)
        if not isinstance(mastery, str):
            mastery = json.dumps(mastery, ensure_ascii=False, default=str)
        message = LearningDiagnosisAgentAdapter(
            self.db, trace_id=self.trace_id
        ).run(
            task_id=self._task_id(state, "diagnosis"),
            agent_input={
                "kp_id": self._required(task, "kp_id"),
                "kp_name": task.get("kp_name", ""),
                "profile_summary": user.get(
                    "profile_summary", "画像尚未采集（按通用基线诊断）"
                ),
                "mastery_status": mastery,
                "target_job": task.get("target_job", "大模型应用工程师"),
            },
            state=state,
            metadata={"workflow": self.workflow_name, "node": "diagnosis"},
        )
        knowledge_state = dict(state.knowledge_state)
        knowledge_state["diagnosis"] = message.output
        return {
            "knowledge_state": knowledge_state,
            "execution_history": self._history(state, message),
        }

    def resource_node(self, state: LearningGraphState) -> dict[str, Any]:
        task = state.task_context
        user = state.user_context
        message = ResourceGenerationAgentAdapter(
            self.db, trace_id=self.trace_id
        ).run(
            task_id=self._task_id(state, "resource"),
            agent_input={
                "kp_name": self._required(task, "kp_name"),
                "difficulty": self._required(task, "difficulty"),
                "rag_context": task.get("rag_context", []),
                "feedback": task.get("feedback"),
                "description": task.get("description", ""),
                "learner_profile": user.get("profile_summary", ""),
                "depth_tier": task.get("depth_tier"),
            },
            state=state,
            metadata={"workflow": self.workflow_name, "node": "resource"},
        )
        return {
            "resources": [*state.resources, message.output],
            "execution_history": self._history(state, message),
        }

    def evaluation_node(self, state: LearningGraphState) -> dict[str, Any]:
        user_id = self._required(state.user_context, "user_id")
        message = EvaluationAgentAdapter(
            self.db, trace_id=self.trace_id
        ).run(
            task_id=self._task_id(state, "evaluation"),
            agent_input={"user_id": user_id},
            state=state,
            metadata={"workflow": self.workflow_name, "node": "evaluation"},
        )
        return {
            "evaluation": message.output,
            "execution_history": self._history(state, message),
        }

    def build(self):
        if self._graph is None:
            builder = StateGraph(LearningGraphState)
            builder.add_node("diagnosis", self.diagnosis_node)
            builder.add_node("resource", self.resource_node)
            builder.add_node("evaluation", self.evaluation_node)
            builder.add_edge(START, "diagnosis")
            builder.add_edge("diagnosis", "resource")
            builder.add_edge("resource", "evaluation")
            builder.add_edge("evaluation", END)
            self._graph = builder.compile()
        return self._graph

    def execute(
        self, state: LearningGraphState | dict[str, Any]
    ) -> LearningGraphState:
        initial = self.validate_state(state)
        result = self.build().invoke(initial)
        return self.state_schema.model_validate(result)

