"""现有Agent到BaseAgent框架的适配层（TASK-002-B2）。

本模块只转换输入输出并委托旧函数，不复制或改写任何业务逻辑。数据库会话由调用方
管理；Adapter不创建、不提交、不关闭Session。
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel
from sqlalchemy.orm import Session

from app.agents import critic_agent, diagnostic_agent, evaluation_agent, generator_agent
from app.agents.base import BaseAgent
from app.agents.state import AgentState


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LearningDiagnosisInput(_StrictModel):
    kp_id: str
    kp_name: str = ""
    profile_summary: str = (
        "六维能力画像：机器学习基础/神经网络较强，注意力机制/Transformer/大模型微调偏弱"
    )
    mastery_status: str = "{}"
    target_job: str = "大模型应用工程师"


class LegacyAgentOutput(_StrictModel):
    """diagnostic/generator旧入口共同的四字段返回结构。"""

    agentId: str
    name: str
    prompt: str
    output: dict[str, Any]


class ResourceGenerationInput(_StrictModel):
    kp_name: str
    difficulty: str
    rag_context: list[dict[str, Any]] = Field(default_factory=list)
    feedback: str | None = None
    description: str = ""
    learner_profile: str = ""
    depth_tier: str | None = None


class EvaluationInput(_StrictModel):
    user_id: str


class EvaluationOutput(RootModel[dict[str, Any]]):
    """保留旧Dashboard评估结果的顶层字典形状。"""


class QualityDecision(str, Enum):
    """资源质量路由决定；值保持大写，便于审计与条件边显式匹配。"""

    PASS = "PASS"
    REVISE = "REVISE"
    FALLBACK = "FALLBACK"


class CriticInput(_StrictModel):
    learning_goal: str
    knowledge_state: dict[str, Any] = Field(default_factory=dict)
    resources: list[dict[str, Any]] = Field(min_length=1)


class QualityDecisionOutput(_StrictModel):
    decision: QualityDecision
    passed: bool
    validation_score: float
    hallucination_rate: float
    issues: list[str] = Field(default_factory=list)
    reason: str


class LearningDiagnosisAgentAdapter(
    BaseAgent[LearningDiagnosisInput, LegacyAgentOutput]
):
    agent_name = "learning_diagnosis"
    description = "适配现有学情诊断Agent，不改变诊断业务逻辑"
    input_schema = LearningDiagnosisInput
    output_schema = LegacyAgentOutput

    def __init__(self, db: Session, **kwargs: Any) -> None:
        self.db = db
        super().__init__(**kwargs)

    def execute(
        self, agent_input: LearningDiagnosisInput, state: AgentState
    ) -> LegacyAgentOutput:
        result = diagnostic_agent.run_diagnostic(
            self.db,
            kp_id=agent_input.kp_id,
            kp_name=agent_input.kp_name,
            profile_summary=agent_input.profile_summary,
            mastery_status=agent_input.mastery_status,
            target_job=agent_input.target_job,
        )
        return LegacyAgentOutput.model_validate(result)


class ResourceGenerationAgentAdapter(
    BaseAgent[ResourceGenerationInput, LegacyAgentOutput]
):
    agent_name = "resource_generation"
    description = "适配现有资源生成Agent，不改变RAG约束和生成业务逻辑"
    input_schema = ResourceGenerationInput
    output_schema = LegacyAgentOutput

    def __init__(self, db: Session, **kwargs: Any) -> None:
        self.db = db
        super().__init__(**kwargs)

    def execute(
        self, agent_input: ResourceGenerationInput, state: AgentState
    ) -> LegacyAgentOutput:
        result = generator_agent.run_generator(
            self.db,
            kp_name=agent_input.kp_name,
            difficulty=agent_input.difficulty,
            rag_context=agent_input.rag_context,
            feedback=agent_input.feedback,
            description=agent_input.description,
            learner_profile=agent_input.learner_profile,
            depth_tier=agent_input.depth_tier,
        )
        return LegacyAgentOutput.model_validate(result)


class EvaluationAgentAdapter(BaseAgent[EvaluationInput, EvaluationOutput]):
    agent_name = "evaluation"
    description = "适配现有学习过程评估Agent，不改变指标和建议生成逻辑"
    input_schema = EvaluationInput
    output_schema = EvaluationOutput

    def __init__(self, db: Session, **kwargs: Any) -> None:
        self.db = db
        super().__init__(**kwargs)

    def execute(
        self, agent_input: EvaluationInput, state: AgentState
    ) -> EvaluationOutput:
        result = evaluation_agent.evaluate(self.db, agent_input.user_id)
        return EvaluationOutput.model_validate(result)


class CriticAgentAdapter(BaseAgent[CriticInput, QualityDecisionOutput]):
    agent_name = "quality_critic"
    description = "适配现有内容审核Agent并输出结构化质量路由决定"
    input_schema = CriticInput
    output_schema = QualityDecisionOutput

    def __init__(self, db: Session, **kwargs: Any) -> None:
        self.db = db
        super().__init__(**kwargs)

    @staticmethod
    def _draft_content(resources: list[dict[str, Any]]) -> str:
        latest = resources[-1]
        output = latest.get("output") if isinstance(latest, dict) else None
        markdown = output.get("markdown") if isinstance(output, dict) else None
        if not isinstance(markdown, str) or not markdown.strip():
            raise ValueError("Critic Adapter无法从最新Resource提取markdown")
        return markdown

    def execute(
        self, agent_input: CriticInput, state: AgentState
    ) -> QualityDecisionOutput:
        rag_context = agent_input.knowledge_state.get("rag_context", [])
        if not isinstance(rag_context, list):
            raise ValueError("knowledge_state.rag_context必须为列表")
        result = critic_agent.run_critic(
            self.db,
            draft_content=self._draft_content(agent_input.resources),
            rag_context=rag_context,
        )
        output = result["output"]
        passed = bool(output.get("passed"))
        decision = QualityDecision.PASS if passed else QualityDecision.REVISE
        score = float(output.get("validationScore", 0.0))
        rate = float(output.get("hallucinationRate", 1.0))
        issues = [str(item) for item in output.get("issues", [])]
        reason = (
            f"质量校验通过，评分{score:.4f}"
            if passed
            else f"质量校验未通过，评分{score:.4f}，需要修订"
        )
        return QualityDecisionOutput(
            decision=decision,
            passed=passed,
            validation_score=score,
            hallucination_rate=rate,
            issues=issues,
            reason=reason,
        )
