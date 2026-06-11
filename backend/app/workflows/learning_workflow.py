"""学习资源生成工作流（B5-a，LangGraph StateGraph）。

依据：
- 需求文档 4.2.1 DAG 状态机 / 4.2.2 重试与降级、9.3 LangGraph 状态结构；
- 接口文档 11.2：trace 的 agents/messages 结构直接满足前端渲染（B7 消费）。

拓扑：diagnostic → retrieval → generation → validation ─┬→ decision → END
                                          ▲             │
                                          └── retry ≤2 ──┘（评分 < 阈值）
仍不过 → 降级输出：final_output 标记 validation_score 与 degraded:true。

B5-a 边界：纯 Mock provider；retrieval 为确定性 mock 切片（可注入替换），
B5-b 接入真实 RAG 检索与真实 LLM，本文件拓扑与 trace 结构不变。
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from operator import add
from typing import Annotated, Any, Callable, Optional, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.critic_agent import run_critic
from app.agents.diagnostic_agent import run_diagnostic
from app.agents.generator_agent import run_generator
from app.models.entities import KnowledgePoint, WorkflowTrace

# critic 评分阈值：validationScore < 阈值 → 回 generator 重试
VALIDATION_THRESHOLD = 0.8
# 最大重试次数（首次生成不计）：重试 2 次仍不过 → 降级
MAX_RETRIES = 2
# 节点日志中渲染后 prompt 的截取长度（热更新验证 / B7 展示用）
PROMPT_EXCERPT_LEN = 400

# 11.2 agents[].id 固定顺序
AGENT_ORDER = ("diagnosis", "generation", "critic")

Retriever = Callable[[str, str, str], list[dict[str, Any]]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _list_reducer(left: list | None, right: list | None) -> list:
    """追加而非覆盖（需求文档 9.3 messages_reducer / error_reducer）。"""
    return (left or []) + (right or [])


class WorkflowState(TypedDict, total=False):
    """工作流状态（按需求文档 9.3.1 定义，B5-a 取本阶段用到的字段子集）。"""

    # ========== 输入数据 ==========
    user_id: str
    kp_id: str
    kp_name: str
    difficulty: str
    target_job: str

    # ========== 消息历史（11.2 messages，追加） ==========
    messages: Annotated[list[dict], _list_reducer]

    # ========== 学情诊断阶段 ==========
    profile: Optional[dict]

    # ========== RAG 检索阶段 ==========
    reranked_context: Optional[list[dict]]

    # ========== 内容生成阶段 ==========
    generated_content: Optional[str]
    generation_feedback: Optional[str]

    # ========== 内容校验阶段 ==========
    validation_result: Optional[dict]
    hallucination_rate: Optional[float]
    error_details: Annotated[list[dict], _list_reducer]

    # ========== 流程控制 ==========
    retry_count: int
    max_retries: int
    current_node: str
    workflow_status: str  # pending|running|success|degraded

    # ========== 输出结果 ==========
    final_output: Optional[dict]

    # ========== 元数据 ==========
    node_execution_log: Annotated[list[dict], add]


# ---- B5-a 确定性 mock 检索（B5-b 注入真实 HybridRetriever 替换） ---------------

def _mock_retriever(kp_id: str, kp_name: str, difficulty: str) -> list[dict[str, Any]]:
    """确定性 mock 切片：结构对齐 B3 检索器输出（id/content/metadata/score）。"""
    sources = [
        ("doc_001", "《深度学习》(花书) 相关章节", f"{kp_name}的核心概念与数学定义：输入经参数化变换映射为输出表示。"),
        ("doc_002", "Stanford 公开课讲义", f"{kp_name}的典型实现与{difficulty}难度示例代码讲解。"),
        ("doc_003", "领域权威综述", f"{kp_name}的工程实践要点、常见误区与调优建议。"),
    ]
    return [
        {
            "id": f"{kp_id}_chunk_{i + 1}",
            "content": content,
            "metadata": {"docId": doc_id, "title": title, "kpId": kp_id},
            "score": round(0.92 - i * 0.05, 2),
        }
        for i, (doc_id, title, content) in enumerate(sources)
    ]


# ---- 节点日志 / 消息构造 -------------------------------------------------------

def _node_entry(
    agent: str,
    name: str,
    started_at: str,
    t0: float,
    retry_index: int,
    output_summary: str,
    prompt: str | None = None,
) -> dict[str, Any]:
    entry = {
        "agent": agent,
        "name": name,
        "startedAt": started_at,
        "endedAt": _now_iso(),
        "durationMs": round((time.perf_counter() - t0) * 1000, 2),
        "retryIndex": retry_index,
        "outputSummary": output_summary,
    }
    if prompt is not None:
        entry["promptExcerpt"] = prompt[:PROMPT_EXCERPT_LEN]
    return entry


def _msg(sender: str, to: str, message: str, type_: str = "response") -> dict[str, Any]:
    """11.2 messages[] 单条（id 由 runner 统一编号）。"""
    return {
        "from": sender,
        "to": to,
        "message": message,
        "type": type_,
        "timestamp": _now_iso(),
    }


# ---- 图构建（节点为闭包，捕获 db / retriever） ---------------------------------

def _build_graph(db: Session, retriever: Retriever):
    def diagnostic_node(state: WorkflowState) -> dict:
        started, t0 = _now_iso(), time.perf_counter()
        res = run_diagnostic(
            db,
            kp_id=state["kp_id"],
            kp_name=state["kp_name"],
            target_job=state.get("target_job", ""),
        )
        summary = res["output"]["summary"]
        return {
            "profile": res["output"],
            "current_node": "diagnostic",
            "workflow_status": "running",
            "messages": [
                _msg("用户", res["name"], f"发起「{state['kp_name']}」学习资源生成请求", "request"),
                _msg(res["name"], "领域知识生成Agent", summary),
            ],
            "node_execution_log": [
                _node_entry("diagnosis", res["name"], started, t0, 0, summary, res["prompt"])
            ],
        }

    def retrieval_node(state: WorkflowState) -> dict:
        started, t0 = _now_iso(), time.perf_counter()
        chunks = retriever(state["kp_id"], state["kp_name"], state["difficulty"])
        summary = f"检索到 {len(chunks)} 条相关知识切片"
        return {
            "reranked_context": chunks,
            "current_node": "retrieval",
            "messages": [_msg("RAG系统", "领域知识生成Agent", summary)],
            "node_execution_log": [
                _node_entry("rag", "RAG系统", started, t0, 0, summary)
            ],
        }

    def generation_node(state: WorkflowState) -> dict:
        started, t0 = _now_iso(), time.perf_counter()
        retry_index = state.get("retry_count", 0)
        res = run_generator(
            db,
            kp_name=state["kp_name"],
            difficulty=state["difficulty"],
            rag_context=state.get("reranked_context") or [],
            feedback=state.get("generation_feedback"),
        )
        markdown = res["output"]["markdown"]
        nth = f"第 {retry_index + 1} 次" if retry_index else "首次"
        summary = f"讲义草稿生成完成（{nth}，{len(markdown)} 字符）"
        return {
            "generated_content": markdown,
            "current_node": "generation",
            "messages": [
                _msg(res["name"], "内容审核校验Agent", f"{summary}，请校验", "request")
            ],
            "node_execution_log": [
                _node_entry("generation", res["name"], started, t0, retry_index, summary, res["prompt"])
            ],
        }

    def validation_node(state: WorkflowState) -> dict:
        started, t0 = _now_iso(), time.perf_counter()
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", MAX_RETRIES)
        res = run_critic(
            db,
            draft_content=state.get("generated_content") or "",
            rag_context=state.get("reranked_context") or [],
        )
        out = res["output"]
        score = out["validationScore"]
        passed = out["passed"] and score >= VALIDATION_THRESHOLD

        update: dict[str, Any] = {
            "validation_result": {**out, "passed": passed},
            "hallucination_rate": out["hallucinationRate"],
            "current_node": "validation",
        }
        if passed:
            update["validation_result"]["action"] = "accept"
            summary = f"校验通过（评分 {score}，幻觉率 {out['hallucinationRate']}）"
            update["messages"] = [_msg(res["name"], "领域知识生成Agent", summary)]
        elif retry_count < max_retries:
            update["validation_result"]["action"] = "retry"
            update["retry_count"] = retry_count + 1  # 9.3.2：手动 +1 后写回
            update["generation_feedback"] = "\n".join(out.get("issues") or ["校验未通过"])
            summary = (
                f"校验未通过（评分 {score} < 阈值 {VALIDATION_THRESHOLD}），"
                f"发起第 {retry_count + 1} 次重试"
            )
            update["messages"] = [_msg(res["name"], "领域知识生成Agent", summary, "error")]
            update["error_details"] = [
                {"retryIndex": retry_count, "score": score, "issues": out.get("issues") or []}
            ]
        else:
            update["validation_result"]["action"] = "fallback"
            summary = f"校验仍未通过（评分 {score}），已达最大重试次数 {max_retries}，触发降级输出"
            update["messages"] = [_msg(res["name"], "用户", summary, "error")]
            update["error_details"] = [
                {"retryIndex": retry_count, "score": score, "issues": out.get("issues") or []}
            ]
        update["node_execution_log"] = [
            _node_entry("critic", res["name"], started, t0, retry_count, summary, res["prompt"])
        ]
        return update

    def decision_node(state: WorkflowState) -> dict:
        validation = state.get("validation_result") or {}
        degraded = not validation.get("passed", False)
        final_output = {
            "markdown": state.get("generated_content") or "",
            "validationScore": validation.get("validationScore"),
            "hallucinationRate": state.get("hallucination_rate"),
            "degraded": degraded,
            "retryCount": state.get("retry_count", 0),
        }
        if degraded:
            # 降级策略（需求文档 4.2.2）：交付最后一稿并标记待人工复核
            final_output["requiresReview"] = True
            msg = _msg(
                "内容审核校验Agent",
                "用户",
                f"已降级交付（validationScore={validation.get('validationScore')}，待人工复核）",
            )
        else:
            msg = _msg("内容审核校验Agent", "用户", "校验通过，学习资源已交付")
        return {
            "final_output": final_output,
            "current_node": "decision",
            "workflow_status": "degraded" if degraded else "success",
            "messages": [msg],
        }

    def route_after_validation(state: WorkflowState) -> str:
        """条件路由（需求文档 4.2.1 should_retry）：决策在 validation 节点落定。"""
        return (state.get("validation_result") or {}).get("action", "accept")

    graph = StateGraph(WorkflowState)
    graph.add_node("diagnostic", diagnostic_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("generation", generation_node)
    graph.add_node("validation", validation_node)
    graph.add_node("decision", decision_node)

    graph.add_edge("diagnostic", "retrieval")
    graph.add_edge("retrieval", "generation")
    graph.add_edge("generation", "validation")
    graph.add_conditional_edges(
        "validation",
        route_after_validation,
        {"retry": "generation", "accept": "decision", "fallback": "decision"},
    )
    graph.add_edge("decision", END)
    graph.set_entry_point("diagnostic")
    return graph.compile()


# ---- trace 组装（11.2 渲染结构） ----------------------------------------------

def _build_agents_summary(node_log: list[dict], degraded: bool) -> list[dict]:
    """11.2 agents[]：固定 3 项；降级时 critic 标 error（红灯）。"""
    agents: list[dict] = []
    for agent_id in AGENT_ORDER:
        entries = [n for n in node_log if n["agent"] == agent_id]
        name = entries[-1]["name"] if entries else agent_id
        status = "error" if (degraded and agent_id == "critic") else "success"
        last_action = entries[-1]["outputSummary"] if entries else ""
        agents.append(
            {"id": agent_id, "name": name, "status": status, "lastAction": last_action}
        )
    return agents


def run_learning_workflow(
    db: Session,
    *,
    user_id: str,
    kp_id: str,
    difficulty: str = "初级",
    target_job: str = "大模型应用工程师",
    retriever: Retriever | None = None,
) -> dict[str, Any]:
    """执行完整工作流并持久化 trace。

    Returns:
        {workflowId, finalOutput, trace}；trace 含 11.2 的 agents/messages/stats
        + 节点日志 nodes + ragContextUsed，B7 的 /workflow/{id} 直接消费。
    """
    workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc)
    kp = db.get(KnowledgePoint, kp_id)
    kp_name = kp.name if kp is not None else kp_id

    app_graph = _build_graph(db, retriever or _mock_retriever)
    final_state: WorkflowState = app_graph.invoke(
        {
            "user_id": user_id,
            "kp_id": kp_id,
            "kp_name": kp_name,
            "difficulty": difficulty,
            "target_job": target_job,
            "messages": [],
            "error_details": [],
            "retry_count": 0,
            "max_retries": MAX_RETRIES,
            "workflow_status": "pending",
            "node_execution_log": [],
        },
        config={"recursion_limit": 50},
    )

    final_output = final_state["final_output"]
    degraded = bool(final_output["degraded"])
    node_log = list(final_state.get("node_execution_log") or [])
    # messages 统一编号（11.2 id 从 1 自增）
    messages = [
        {"id": i + 1, **m} for i, m in enumerate(final_state.get("messages") or [])
    ]
    agents = _build_agents_summary(node_log, degraded)
    rag_context_used = list(final_state.get("reranked_context") or [])
    status = "degraded" if degraded else "success"

    trace: dict[str, Any] = {
        "workflowId": workflow_id,
        "phase": "complete",  # 11.2：idle|diagnosis|generation|validation|complete
        "step": 4,
        "agents": agents,
        "messages": messages,
        "nodes": node_log,
        "ragContextUsed": rag_context_used,
        "stats": {
            "completedAgents": sum(1 for a in agents if a["status"] == "success"),
            "messageCount": len(messages),
            "progress": 100,
        },
    }

    # 持久化（接口文档 11.2 渲染结构 + rag_context_used，B7 直接消费）
    row = WorkflowTrace(
        id=workflow_id,
        user_id=user_id,
        kp_id=kp_id,
        status=status,
        degraded=degraded,
        validation_score=final_output["validationScore"],
        hallucination_rate=final_output["hallucinationRate"],
        retry_count=final_output["retryCount"],
        agents=agents,
        messages=messages,
        node_log=node_log,
        rag_context_used=rag_context_used,
        started_at=started_at,
        ended_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()

    return {"workflowId": workflow_id, "finalOutput": final_output, "trace": trace}
