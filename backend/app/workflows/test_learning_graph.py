"""TASK-002-B3 学习任务Agent子图测试。"""
from __future__ import annotations

import pytest

from app.agents import diagnostic_agent, evaluation_agent, generator_agent
from app.workflows.learning_graph import LearningGraphState, LearningTaskWorkflow


def _state() -> LearningGraphState:
    return LearningGraphState(
        user_context={"user_id": "u_1", "profile_summary": "基础一般"},
        learning_goal="掌握神经网络",
        knowledge_state={"nn": "weak"},
        task_context={
            "task_id": "task_1",
            "kp_id": "nn",
            "kp_name": "神经网络",
            "difficulty": "初级",
            "target_job": "算法工程师",
            "rag_context": [{"id": "c1", "content": "神经网络证据"}],
        },
    )


def _install_legacy_stubs(monkeypatch, calls):
    def diagnosis(db, **kwargs):
        calls.append(("diagnosis", kwargs))
        return {
            "agentId": "diagnosis",
            "name": "学情诊断Agent",
            "prompt": "diagnosis prompt",
            "output": {"summary": "优先学习nn", "weakKpIds": ["nn"]},
        }

    def generation(db, **kwargs):
        calls.append(("resource", kwargs))
        return {
            "agentId": "generation",
            "name": "资源生成Agent",
            "prompt": "generation prompt",
            "output": {"markdown": "# 神经网络"},
        }

    def evaluation(db, user_id):
        calls.append(("evaluation", {"user_id": user_id}))
        return {
            "overallScore": 60,
            "level": "成长中",
            "trend": "stable",
            "dimensions": [],
            "weakPoints": [{"kpId": "nn"}],
            "summary": "继续学习",
            "suggestions": ["完成练习"],
            "adjustment": {"nextKpId": "nn"},
            "generatedBy": "mock",
            "signals": {"attemptCount": 0},
        }

    monkeypatch.setattr(diagnostic_agent, "run_diagnostic", diagnosis)
    monkeypatch.setattr(generator_agent, "run_generator", generation)
    monkeypatch.setattr(evaluation_agent, "evaluate", evaluation)


def test_workflow_builds_required_nodes_and_edges():
    compiled = LearningTaskWorkflow(object(), trace_id="trace-graph").build()
    graph = compiled.get_graph()
    assert {"diagnosis", "resource", "evaluation"}.issubset(graph.nodes)
    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("__start__", "diagnosis") in edges
    assert ("diagnosis", "resource") in edges
    assert ("resource", "evaluation") in edges
    assert ("evaluation", "__end__") in edges


def test_state_flows_through_adapters_in_order(monkeypatch):
    calls = []
    _install_legacy_stubs(monkeypatch, calls)
    result = LearningTaskWorkflow(object(), trace_id="trace-flow").execute(_state())

    assert [name for name, _ in calls] == ["diagnosis", "resource", "evaluation"]
    assert result.knowledge_state["diagnosis"]["output"]["weakKpIds"] == ["nn"]
    assert result.resources[0]["output"]["markdown"] == "# 神经网络"
    assert result.evaluation["overallScore"] == 60
    assert [m.agent_name for m in result.execution_history] == [
        "learning_diagnosis",
        "resource_generation",
        "evaluation",
    ]


def test_each_node_records_shared_trace_and_task_identity(monkeypatch):
    calls = []
    _install_legacy_stubs(monkeypatch, calls)
    result = LearningTaskWorkflow(object(), trace_id="trace-shared").execute(_state())

    assert len(result.execution_history) == 3
    assert {m.metadata["traceId"] for m in result.execution_history} == {
        "trace-shared"
    }
    assert [m.task_id for m in result.execution_history] == [
        "task_1:diagnosis",
        "task_1:resource",
        "task_1:evaluation",
    ]
    assert [m.metadata["node"] for m in result.execution_history] == [
        "diagnosis",
        "resource",
        "evaluation",
    ]


def test_missing_required_context_fails_explicitly(monkeypatch):
    calls = []
    _install_legacy_stubs(monkeypatch, calls)
    state = _state().model_copy(
        update={"task_context": {"kp_id": "nn", "kp_name": "神经网络"}}
    )
    with pytest.raises(ValueError, match="difficulty"):
        LearningTaskWorkflow(object()).execute(state)

