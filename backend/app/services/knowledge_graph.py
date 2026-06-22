"""知识图谱服务（B6）。

覆盖接口文档 10.1：
- 12 节点 / 14 边静态种子结构（与前端 KnowledgeGraph.tsx 实际拓扑逐条一致；
  文档注释「13 条」为前端逆向笔误，已与需求方确认按 14 条口径）；
- category 不入库、每次请求按 mastery 实时推导（10.1 备注）：
    passed                  → 0 已掌握（value=100）
    learning|pending-check  → 1 学习中（value=min(种子值, 60)，与前端派生规则一致）
    未开始且种子值较高       → 2 待学习
    未开始且种子值极低(<20)  → 3 知识盲区
- value 取掌握度 %（前端据此算 symbolSize）。

6 核心知识点经 KnowledgePoint.graph_node_id 映射到图谱节点；其余 6 个拓展节点
（rnn/attn/bertgpt/prompt/rag/agent）无掌握度行，恒按种子值推导。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import KnowledgePoint
from app.services import mastery as mastery_service

logger = logging.getLogger(__name__)

# 知识盲区阈值：未开始且种子掌握度低于该值 → category 3
BLIND_SPOT_THRESHOLD = 20

# 学习中节点的掌握度上限（与前端派生规则 min(value, 60) 一致）
_LEARNING_VALUE_CAP = 60

# 12 节点种子：(id, name, 基线掌握度 %)。名称/数值与前端 KnowledgeGraph.tsx 一致。
_NODES: list[tuple[str, str, int]] = [
    ("ml", "机器学习基础", 92),
    ("nn", "神经网络基础", 85),
    ("dl", "深度学习原理", 65),
    ("cnn", "CNN架构", 30),
    ("rnn", "RNN架构", 28),
    ("attn", "注意力机制", 18),
    ("transformer", "Transformer", 15),
    ("bertgpt", "BERT与GPT", 22),
    ("finetune", "大模型微调", 12),
    ("prompt", "Prompt工程", 58),
    ("rag", "RAG检索增强", 35),
    ("agent", "AI Agent开发", 20),
]

# 14 条依赖边：source 是 target 的前置知识（与前端逐条一致）
_LINKS: list[tuple[str, str]] = [
    ("ml", "nn"),
    ("nn", "dl"),
    ("dl", "cnn"),
    ("dl", "rnn"),
    ("dl", "attn"),
    ("attn", "transformer"),
    ("rnn", "transformer"),
    ("transformer", "bertgpt"),
    ("bertgpt", "finetune"),
    ("transformer", "prompt"),
    ("bertgpt", "rag"),
    ("rag", "agent"),
    ("prompt", "agent"),
    ("finetune", "agent"),
]

_CATEGORIES = [
    {"name": "已掌握"},
    {"name": "学习中"},
    {"name": "待学习"},
    {"name": "知识盲区"},
]


def derive_node(status: str | None, base_value: int) -> tuple[int, int]:
    """按掌握状态推导 (category, value)（接口文档 10.1 备注口径）。

    status 为该节点对应核心知识点的 KPStatus；None 表示无映射或未开始。
    """
    if status == mastery_service.STATUS_PASSED:
        return 0, 100
    if status in (mastery_service.STATUS_LEARNING, mastery_service.STATUS_PENDING_CHECK):
        return 1, min(base_value, _LEARNING_VALUE_CAP)
    if base_value < BLIND_SPOT_THRESHOLD:
        return 3, base_value
    return 2, base_value


def derived_nodes(db: Session, user_id: str) -> list[dict[str, Any]]:
    """12 节点 + 实时推导的 category/value（dashboard 聚合复用，保证口径严格一致）。

    防御：12 节点为静态种子恒存在；掌握度/知识点映射查询若遇空数据或瞬时库异常，
    回落为「全部未开始」推导（而非抛 500），保证新用户/空数据恒得 200 空态图谱（任务4）。
    """
    try:
        status_map = mastery_service.get_status_map(db, user_id)
        kp_by_node = {kp.graph_node_id: kp.id for kp in db.query(KnowledgePoint).all()}
    except Exception:  # noqa: BLE001 读接口降级：用户态查询失败 → 按全未开始推导
        logger.warning("知识图谱掌握度查询失败，按全未开始推导（user_id=%s）", user_id, exc_info=True)
        status_map, kp_by_node = {}, {}
    nodes: list[dict[str, Any]] = []
    for node_id, name, base_value in _NODES:
        status = status_map.get(kp_by_node.get(node_id, ""))
        category, value = derive_node(status, base_value)
        nodes.append(
            {"id": node_id, "name": name, "category": category, "value": value}
        )
    return nodes


def get_graph(db: Session, user_id: str) -> dict[str, Any]:
    """知识图谱（接口文档 10.1）：nodes / links / categories。"""
    return {
        "nodes": derived_nodes(db, user_id),
        "links": [{"source": s, "target": t} for s, t in _LINKS],
        "categories": [dict(c) for c in _CATEGORIES],
    }
