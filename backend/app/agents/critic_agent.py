"""内容审核校验 Agent（B5-a）。

职责（需求文档 4.1）：对生成讲义逐句做 RAG 交叉校验，输出整体校验分与
幻觉率；评分低于阈值时工作流回 generator 重试（≤2 次），仍不过则降级。
prompt 模板 agentId=critic，必需占位符：draftContent / ragContext。
B5-a 为 MockLLM 确定性输出；测试钩子 app.core.llm.set_force_critic_low(True)
可强制低分以验证重试→降级路径。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents import run_agent
from app.agents.generator_agent import _format_rag_context

AGENT_ID = "critic"


def run_critic(
    db: Session,
    *,
    draft_content: str,
    rag_context: list[dict[str, Any]],
) -> dict[str, Any]:
    """执行审核：现读模板 → 渲染 → MockLLM 返回校验结果。

    Returns:
        {agentId, name, prompt, output}，
        output 含 passed / validationScore / hallucinationRate / issues。
    """
    return run_agent(
        db,
        AGENT_ID,
        {
            "draftContent": draft_content,
            "ragContext": _format_rag_context(rag_context),
        },
    )
