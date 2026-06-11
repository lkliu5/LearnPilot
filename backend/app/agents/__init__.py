"""Agent 层（B5-a）。

三 Agent（diagnostic / generator / critic）共用约定：
- prompt 一律经 services.prompts.get_template(db, agent_id) **每次现读**
  （消费 B4-b 热更新：管理端 PUT 后下一次调用立即生效，禁止进程内缓存）；
- 占位符按 `{var}` 直替（与 PromptTemplate.variables 契约一致），渲染后交
  app.core.llm.LLMClient.complete() 调用；
- 每个 run_* 返回统一结构 {agentId, name, prompt, output}，供工作流记录
  trace（节点日志含 promptExcerpt，热更新可验证）。
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.llm import get_llm
from app.services.prompts import get_prompt

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def render_template(template: str, variables: dict[str, Any]) -> str:
    """`{var}` 占位符直替渲染。

    只替换 variables 中存在的键（值转 str）；未知占位符原样保留，
    不用 str.format 以免模板中的普通花括号（如 JSON 示例）抛 KeyError。
    """

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(variables[key]) if key in variables else match.group(0)

    return _PLACEHOLDER_RE.sub(_sub, template)


def run_agent(
    db: Session, agent_id: str, variables: dict[str, Any]
) -> dict[str, Any]:
    """统一执行入口：现读模板 → 渲染 → LLMClient.complete。"""
    prompt_row = get_prompt(db, agent_id)
    if prompt_row is None:
        raise ValueError(f"未知 agentId：{agent_id}")
    prompt = render_template(prompt_row["template"], variables)
    output = get_llm().complete(prompt, agent_id=agent_id, variables=variables)
    return {
        "agentId": agent_id,
        "name": prompt_row["name"],  # 11.2 agents[].name（与模板表逐字一致）
        "prompt": prompt,
        "output": output,
    }
