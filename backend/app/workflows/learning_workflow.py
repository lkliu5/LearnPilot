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

import json
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
from app.services import mastery as mastery_service
from app.services import student_portrait as portrait_service

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


def _portrait_summary(portrait: dict[str, Any]) -> str:
    """异质学生画像 → 诊断 prompt 用的 profileSummary 文本（因人而异）。

    可量化维度（带 score）渲染「标签 N分」，定性维度渲染「标签：取值」；
    空画像（尚未诊断）落通用基线占位，使 Mock 模式仍可由该用户掌握度派生差异。
    """
    dims = portrait.get("dimensions") or []
    parts: list[str] = []
    for d in dims:
        label = d.get("label") or d.get("key") or ""
        if not label:
            continue
        score = d.get("score")
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            parts.append(f"{label} {int(score)}分")
        else:
            value = (d.get("value") or "").strip()
            if value:
                parts.append(f"{label}：{value}")
    return "；".join(parts) if parts else "画像尚未采集（按通用基线诊断）"


# 知识点 → 画像能力维度（用于据当前用户在该维度的掌握分派生讲义深度档）
_KP_ABILITY: dict[str, str] = {
    "ml": "机器学习基础", "nn": "神经网络", "dl": "深度学习",
    "cnn": "深度学习", "transformer": "Transformer",
    "finetune": "大模型微调", "attention": "注意力机制",
}


def _ability_tier(portrait: dict[str, Any], kp_id: str, kp_name: str) -> str | None:
    """据画像能力维度派生当前知识点的讲义深度档：advanced / beginner / basic / None。

    优先取与本知识点对应的能力维度分数；无对应维度则退化为全部能力维度均分；
    完全无能力信号（空画像）→ None（按难度基线，不强加个性化，保证直出/工作流同档一致）。
    使「同一知识点、同一难度」对能力强（≥70→advanced）与零基础（≤35→beginner）用户产出
    深度不同的讲义——这是「真个性化」的又一硬证据。
    """
    dims = portrait.get("dimensions") or []
    ability = [
        d for d in dims
        if isinstance(d.get("score"), (int, float)) and not isinstance(d.get("score"), bool)
    ]
    if not ability:
        return None
    target_label = _KP_ABILITY.get(kp_id)
    score: float | None = None
    if target_label:
        for d in ability:
            label = d.get("label") or d.get("key") or ""
            if target_label in label or (label and label in target_label) or target_label in kp_name:
                score = float(d["score"])
                break
    if score is None:
        score = sum(float(d["score"]) for d in ability) / len(ability)
    if score >= 70:
        return "advanced"
    if score <= 35:
        return "beginner"
    return "basic"


def _list_reducer(left: list | None, right: list | None) -> list:
    """追加而非覆盖（需求文档 9.3 messages_reducer / error_reducer）。"""
    return (left or []) + (right or [])


class WorkflowState(TypedDict, total=False):
    """工作流状态（按需求文档 9.3.1 定义，B5-a 取本阶段用到的字段子集）。"""

    # ========== 输入数据 ==========
    user_id: str
    kp_id: str
    kp_name: str
    kp_description: str  # 核心概念清单（B8：注入 generation 模板 {description}）
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

def _build_graph(db: Session, retriever: Retriever, disable_critic: bool = False):
    # disable_critic 仅供 B11 消融实验脚本使用（业务路径恒为 False）：True 时审核节点
    # 直接放行首版生成、不做接地校验与重试/降级，用于度量「去掉审核闭环」的幻觉率。
    def diagnostic_node(state: WorkflowState) -> dict:
        started, t0 = _now_iso(), time.perf_counter()
        # 读当前用户真实画像 + 掌握度 → 因人而异的学情诊断（不再用写死的通用模板）。
        # user_id 缺省（极端兜底）时退化为空画像 / 空掌握度，仍可跑通。
        user_id = state.get("user_id") or ""
        portrait = (
            portrait_service.get_portrait(db, user_id) if user_id else {"dimensions": []}
        )
        status_map = mastery_service.get_status_map(db, user_id) if user_id else {}
        res = run_diagnostic(
            db,
            kp_id=state["kp_id"],
            kp_name=state["kp_name"],
            profile_summary=_portrait_summary(portrait),
            mastery_status=json.dumps(status_map, ensure_ascii=False),
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
        # 读当前用户画像 → 派生讲义深度档（能力强/零基础产出深度不同的讲义），并把画像文本
        # 注入生成 prompt（真实模式据此调节深度）。空画像 → tier=None 落难度基线（不强加个性化）。
        user_id = state.get("user_id") or ""
        portrait = (
            portrait_service.get_portrait(db, user_id) if user_id else {"dimensions": []}
        )
        # 空画像用生成专用的中性占位（避免诊断专用措辞混入生成 prompt）。
        learner_profile = (
            _portrait_summary(portrait)
            if (portrait.get("dimensions") or [])
            else "画像尚未采集（按通用基线）"
        )
        res = run_generator(
            db,
            kp_name=state["kp_name"],
            difficulty=state["difficulty"],
            rag_context=state.get("reranked_context") or [],
            feedback=state.get("generation_feedback"),
            description=state.get("kp_description", ""),
            learner_profile=learner_profile,
            depth_tier=_ability_tier(portrait, state["kp_id"], state["kp_name"]),
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
        if disable_critic:
            # 消融「去审核」：不做接地校验，直接接受首版生成（无重试、无降级）。
            summary = "审核已禁用（消融实验），首版生成直接交付"
            return {
                "validation_result": {
                    "passed": True, "validationScore": None,
                    "hallucinationRate": None, "issues": [], "action": "accept",
                },
                "hallucination_rate": None,
                "current_node": "validation",
                "messages": [_msg("内容审核校验Agent", "领域知识生成Agent", summary)],
                "node_execution_log": [
                    _node_entry("critic", "内容审核校验Agent", started, t0, retry_count, summary)
                ],
            }
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
    workflow_id: str | None = None,
    on_update: Callable[[WorkflowState], None] | None = None,
    max_retries: int = MAX_RETRIES,
    disable_critic: bool = False,
) -> dict[str, Any]:
    """执行完整工作流并持久化 trace。

    B11 消融实验参数（**仅实验脚本可用，业务接口恒用默认值**，不进生产配置）：
    - retriever 传空检索器 → 去 RAG；disable_critic=True → 去审核闭环（首版直接交付）；
    - max_retries=0 → 去重试（低分即降级，不再回炉）。

    B7-a 增补（拓扑 / trace 结构不变）：
    - workflow_id 可由调用方预分配（execute 立即返回 id、后台运行）；
    - on_update：每个节点完成（含重试轮）后回调一次当前累积 State，
      供 workflow_runner 组装 11.2 实时快照推 WS / 轮询。

    Returns:
        {workflowId, finalOutput, trace}；trace 含 11.2 的 agents/messages/stats
        + 节点日志 nodes + ragContextUsed，B7 的 /workflow/{id} 直接消费。
    """
    workflow_id = workflow_id or f"wf_{uuid.uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc)
    kp = db.get(KnowledgePoint, kp_id)
    kp_name = kp.name if kp is not None else kp_id
    kp_description = (kp.description or "") if kp is not None else ""

    app_graph = _build_graph(db, retriever or _mock_retriever, disable_critic=disable_critic)
    initial_state: WorkflowState = {
        "user_id": user_id,
        "kp_id": kp_id,
        "kp_name": kp_name,
        "kp_description": kp_description,
        "difficulty": difficulty,
        "target_job": target_job,
        "messages": [],
        "error_details": [],
        "retry_count": 0,
        "max_retries": max_retries,
        "workflow_status": "pending",
        "node_execution_log": [],
    }
    # stream(values)：每个超步（顺序图 = 每个节点）后产出累积 State，
    # 终态与 invoke() 等价；首个产出为输入态（无 current_node），跳过不回调。
    final_state: WorkflowState | None = None
    for state in app_graph.stream(
        initial_state, config={"recursion_limit": 50}, stream_mode="values"
    ):
        final_state = state
        if on_update is not None and state.get("current_node"):
            on_update(state)
    if final_state is None or final_state.get("final_output") is None:
        raise RuntimeError("工作流未产出 final_output")

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
