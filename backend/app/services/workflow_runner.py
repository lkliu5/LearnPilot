"""工作流实时运行器（B7-a，接口文档 11 章）。

职责：
- POST /workflow/execute → start_workflow()：后台线程跑 B5 LangGraph 真实工作流，
  立即返回预分配 workflowId；
- 每个节点完成（含重试轮）经 run_learning_workflow 的 on_update 回调组装一帧
  11.2 快照（workflowId/phase/step/agents[]/messages[]/stats，严格无多余键），
  发布给 GET 轮询（最新快照）与 WS 订阅者（asyncio.Queue，跨线程经
  loop.call_soon_threadsafe 投递）；
- 运行结束后内存注册表保留最近 _MAX_RUNS 条；淘汰/重启后 GET 兜底消费
  WorkflowTrace 持久化行（B5-a 即按 11.2 渲染结构落库）。

轻量栈：进程内 OrderedDict 注册表 + threading（CLAUDE.md 内存取向）；
生产替换 Redis pub/sub + 任务队列，路径写 README。
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.entities import WorkflowTrace
from app.workflows.learning_workflow import (
    AGENT_ORDER,
    WorkflowState,
    run_learning_workflow,
)

# 11.2 固定 3 Agent 的缺省展示名（与 PromptTemplate 种子逐字一致；
# 节点已执行时以 node_log 中的实际 name 为准——消费 B4-b 热更新）
_AGENT_NAMES = {
    "diagnosis": "学情诊断Agent",
    "generation": "领域知识生成Agent",
    "critic": "内容审核校验Agent",
}
_IDLE_ACTION = {
    "diagnosis": "等待诊断任务",
    "generation": "等待生成任务",
    "critic": "等待校验任务",
}
_RUNNING_ACTION = {
    "diagnosis": "正在分析学习者画像...",
    "generation": "正在生成学习资源...",
    "critic": "正在校验内容质量...",
}
# phase → progress %（11.2 stats.progress）
_PROGRESS = {"idle": 0, "diagnosis": 25, "generation": 50, "validation": 75, "complete": 100}

# 内存注册表：workflowId → WorkflowRun（FIFO 淘汰，淘汰后 GET 兜底 WorkflowTrace 行）
_runs: "OrderedDict[str, WorkflowRun]" = OrderedDict()
_MAX_RUNS = 200


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- 11.2 快照组装 -------------------------------------------------------------

def _phase_step_active(state: WorkflowState) -> tuple[str, int, str | None]:
    """由「刚完成的节点」推导当前 phase/step 与正在运行的 Agent。

    state.current_node 为 stream 产出时刚执行完的节点；下一活动随拓扑确定
    （validation 的 retry 分支回 generation）。
    """
    node = state.get("current_node")
    if not node:
        return "diagnosis", 1, "diagnosis"  # 起跑帧：诊断进行中
    if node in ("diagnostic", "retrieval"):
        return "generation", 2, "generation"
    if node == "generation":
        return "validation", 3, "critic"
    if node == "validation":
        action = (state.get("validation_result") or {}).get("action")
        if action == "retry":
            return "generation", 2, "generation"  # 重试帧：生成 Agent 重新点亮
        return "validation", 3, None  # accept/fallback → decision 待落定
    return "complete", 4, None  # decision


def _agents_from_state(state: WorkflowState, active: str | None) -> list[dict[str, Any]]:
    """11.2 agents[]：固定 3 项 id 顺序；running/idle/success/error 四态。"""
    log = state.get("node_execution_log") or []
    degraded = state.get("workflow_status") == "degraded"
    finished = state.get("current_node") == "decision"
    action = (state.get("validation_result") or {}).get("action")
    agents: list[dict[str, Any]] = []
    for agent_id in AGENT_ORDER:
        entries = [n for n in log if n["agent"] == agent_id]
        name = entries[-1]["name"] if entries else _AGENT_NAMES[agent_id]
        if agent_id == active:
            status, last_action = "running", _RUNNING_ACTION[agent_id]
        elif not entries:
            status, last_action = "idle", _IDLE_ACTION[agent_id]
        else:
            status, last_action = "success", entries[-1]["outputSummary"]
            # critic 红灯：终态降级，或运行中校验未通过（retry/fallback 刚落定）
            if agent_id == "critic" and (
                degraded if finished else action in ("retry", "fallback")
            ):
                status = "error"
        agents.append(
            {"id": agent_id, "name": name, "status": status, "lastAction": last_action}
        )
    return agents


def _snapshot_from_state(workflow_id: str, state: WorkflowState) -> dict[str, Any]:
    """组装一帧 11.2 快照（GET 轮询与 WS 推送同结构）。"""
    phase, step, active = _phase_step_active(state)
    messages = [
        {"id": i + 1, **m} for i, m in enumerate(state.get("messages") or [])
    ]
    agents = _agents_from_state(state, active)
    return {
        "workflowId": workflow_id,
        "phase": phase,
        "step": step,
        "agents": agents,
        "messages": messages,
        "stats": {
            "completedAgents": sum(1 for a in agents if a["status"] == "success"),
            "messageCount": len(messages),
            "progress": _PROGRESS[phase],
        },
    }


def snapshot_from_trace(row: WorkflowTrace) -> dict[str, Any]:
    """WorkflowTrace 持久化行 → 11.2 完成态快照（注册表淘汰/重启后的兜底）。"""
    agents = row.agents or []
    messages = row.messages or []
    return {
        "workflowId": row.id,
        "phase": "complete",
        "step": 4,
        "agents": agents,
        "messages": messages,
        "stats": {
            "completedAgents": sum(1 for a in agents if a["status"] == "success"),
            "messageCount": len(messages),
            "progress": 100,
        },
    }


# ---- 运行态与发布 ---------------------------------------------------------------

class WorkflowRun:
    """单次工作流运行态：最新快照 + WS 订阅队列（发布经事件循环线程投递）。"""

    def __init__(self, workflow_id: str, loop: asyncio.AbstractEventLoop) -> None:
        self.workflow_id = workflow_id
        self.loop = loop
        self.snapshot: dict[str, Any] = _snapshot_from_state(workflow_id, {})
        self.done = False
        self._subscribers: set[asyncio.Queue] = set()

    # WS 侧（事件循环线程）
    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    # 工作线程侧：更新快照并向所有订阅者投递一帧；final 帧后投 None 哨兵收尾
    def publish(self, snapshot: dict[str, Any], *, final: bool = False) -> None:
        self.snapshot = snapshot
        if final:
            self.done = True

        def _fanout() -> None:
            for queue in list(self._subscribers):
                queue.put_nowait(snapshot)
                if final:
                    queue.put_nowait(None)

        self.loop.call_soon_threadsafe(_fanout)


def get_run(workflow_id: str) -> WorkflowRun | None:
    return _runs.get(workflow_id)


def start_workflow(
    *,
    user_id: str,
    kp_id: str,
    target_job: str,
    difficulty: str = "初级",
    loop: asyncio.AbstractEventLoop,
) -> str:
    """预分配 workflowId 并后台线程执行，立即返回（11.1）。"""
    workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
    run = WorkflowRun(workflow_id, loop)
    _runs[workflow_id] = run
    while len(_runs) > _MAX_RUNS:
        _runs.popitem(last=False)
    threading.Thread(
        target=_worker,
        args=(run, user_id, kp_id, difficulty, target_job),
        daemon=True,
        name=f"workflow-{workflow_id}",
    ).start()
    return workflow_id


def _worker(
    run: WorkflowRun, user_id: str, kp_id: str, difficulty: str, target_job: str
) -> None:
    """后台线程：自管 DB 会话，逐节点发布快照帧（演示延迟见 config）。"""

    def _delay() -> None:
        if settings.workflow_step_delay_ms > 0:
            time.sleep(settings.workflow_step_delay_ms / 1000)

    def on_update(state: WorkflowState) -> None:
        final = state.get("current_node") == "decision"
        run.publish(_snapshot_from_state(run.workflow_id, state), final=final)
        if not final:
            _delay()

    db = SessionLocal()
    try:
        # 起跑帧（诊断 running）已在 __init__ 置入快照；留一个轮询观察窗
        _delay()
        run_learning_workflow(
            db,
            user_id=user_id,
            kp_id=kp_id,
            difficulty=difficulty,
            target_job=target_job,
            workflow_id=run.workflow_id,
            on_update=on_update,
        )
    except Exception as exc:  # noqa: BLE001 兜底失败帧（messages 追加 error）
        snapshot = {key: value for key, value in run.snapshot.items()}
        messages = list(snapshot["messages"])
        messages.append(
            {
                "id": len(messages) + 1,
                "from": "系统",
                "to": "用户",
                "message": f"工作流执行失败:{exc}",
                "type": "error",
                "timestamp": _now_iso(),
            }
        )
        snapshot["messages"] = messages
        snapshot["stats"] = {**snapshot["stats"], "messageCount": len(messages)}
        run.publish(snapshot, final=True)
    finally:
        db.close()
        if not run.done:  # 正常路径在 decision 帧已 final；此处仅兜底
            run.publish(run.snapshot, final=True)
