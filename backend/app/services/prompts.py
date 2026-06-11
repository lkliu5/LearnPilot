"""Prompt 模板服务（B4-b，接口文档 14.5）。

- agentId 固定 3 项：diagnosis / generation / critic（与 11.2 agents[].id 对齐）；
- 默认模板懒种子（get-or-create，幂等），版本从 1 起；
- PUT 保存即热更新：模板存 SQLite，B5 生成链路经 get_template() 每次现读，
  无进程内缓存 → 保存后下一次生成调用立即生效（无需重启）；
- variables 为该 Agent 的必需占位符清单（契约定死），更新时校验全部保留。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import PromptTemplate

# 占位符语法：{varName}
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

# 默认模板（agentId -> (name, template, variables)）。
# name 与接口文档 11.2 agents[].name 逐字一致；generation 模板与 14.5 示例同构。
_DEFAULTS: dict[str, tuple[str, str, list[str]]] = {
    "diagnosis": (
        "学情诊断Agent",
        "你是学情诊断专家，负责从学习者画像与掌握度数据中定位薄弱知识点。\n"
        "学习者画像：{profileSummary}\n"
        "知识点掌握度：{masteryStatus}\n"
        "目标岗位：{targetJob}\n"
        "请输出：薄弱知识点清单（按优先级排序）、诊断依据、建议学习顺序。",
        ["profileSummary", "masteryStatus", "targetJob"],
    ),
    "generation": (
        "领域知识生成Agent",
        "你是领域知识讲义生成专家，依据检索上下文生成与学习者难度适配的讲义，"
        "禁止编造检索上下文之外的事实。\n"
        "知识点：{kpName}\n"
        "难度：{difficulty}\n"
        "检索上下文：{ragContext}\n"
        "请输出 Markdown 讲义：概念讲解、示例（初级及以上含代码）、要点小结。",
        ["kpName", "difficulty", "ragContext"],
    ),
    "critic": (
        "内容审核校验Agent",
        "你是内容审核校验专家，对生成的讲义逐句做 RAG 交叉校验，标记未接地句子。\n"
        "待审内容：{draftContent}\n"
        "检索来源切片：{ragContext}\n"
        "请输出：逐句接地判定、疑似幻觉句清单、整体幻觉率（未接地句数/总句数）。",
        ["draftContent", "ragContext"],
    ),
}

AGENT_IDS: tuple[str, ...] = tuple(_DEFAULTS)


class MissingPlaceholderError(ValueError):
    """新模板缺失必需占位符（→ 1001/400）。"""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"模板缺失必需占位符：{', '.join(missing)}")


def _get_or_seed(db: Session, agent_id: str) -> PromptTemplate | None:
    """按 agentId 取模板；首次访问时落默认种子（幂等）。未知 agentId → None。"""
    if agent_id not in _DEFAULTS:
        return None
    row = db.get(PromptTemplate, agent_id)
    if row is None:
        name, template, variables = _DEFAULTS[agent_id]
        row = PromptTemplate(
            agent_id=agent_id,
            name=name,
            template=template,
            variables=list(variables),
            version=1,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _to_dict(row: PromptTemplate) -> dict[str, Any]:
    """PromptTemplate → 接口文档 14.5 响应 data（camelCase）。"""
    return {
        "agentId": row.agent_id,
        "name": row.name,
        "template": row.template,
        "variables": list(row.variables or []),
        "version": row.version,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def get_prompt(db: Session, agent_id: str) -> dict[str, Any] | None:
    """14.5 GET：完整 PromptTemplate。未知 agentId → None。"""
    row = _get_or_seed(db, agent_id)
    return _to_dict(row) if row is not None else None


def get_template(db: Session, agent_id: str) -> str | None:
    """供 B5 生成链路消费的读取路径：每次现读 DB，PUT 后立即生效（热更新）。"""
    row = _get_or_seed(db, agent_id)
    return row.template if row is not None else None


def update_prompt(db: Session, agent_id: str, template: str) -> dict[str, Any] | None:
    """14.5 PUT：校验占位符 → 版本自增 → 保存即热更新。

    Returns:
        None：未知 agentId（→ 1004）；
        dict：{agentId, version, updatedAt, hotReloaded}。
    Raises:
        MissingPlaceholderError：缺失必需占位符（→ 1001）。
    """
    row = _get_or_seed(db, agent_id)
    if row is None:
        return None
    present = set(_PLACEHOLDER_RE.findall(template))
    missing = [v for v in (row.variables or []) if v not in present]
    if missing:
        raise MissingPlaceholderError(missing)
    row.template = template
    row.version += 1
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return {
        "agentId": row.agent_id,
        "version": row.version,
        "updatedAt": row.updated_at.isoformat(),
        "hotReloaded": True,
    }
