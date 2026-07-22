"""TASK-004-E1 Trusted RAG canary Gate tests."""
from __future__ import annotations

from app.rag.trusted_rag_gate import (
    CanaryDecisionValue,
    FaultInjectionResults,
    FaultScenarioResult,
    RerankMetrics,
    ShadowMetrics,
    TrustedRAGGate,
)
from app.rag.shadow_admission import ShadowEvaluationDataset


def _rerank(**overrides) -> RerankMetrics:
    values = {
        "independent_validation": True,
        "metrics_provisional": False,
        "human_review_complete": True,
        "mrr_delta": 0.03,
        "ndcg_at_3_delta": 0.02,
        "ndcg_at_5_delta": 0.01,
        "degraded_case_count": 0,
    }
    values.update(overrides)
    return RerankMetrics(**values)


def _shadow(**overrides) -> ShadowMetrics:
    values = {
        "sample_count": 100,
        "evidence_overlap_mean": 0.75,
        "source_coverage_mean": 0.85,
        "confidence_mean": 0.90,
        "p95_latency_ms": 1200.0,
        "timeout_rate": 0.01,
        "error_rate": 0.02,
        "performance_verified": True,
        "rerank": _rerank(),
    }
    values.update(overrides)
    return ShadowMetrics(**values)


def _faults(*, blocked: bool = False) -> FaultInjectionResults:
    scenario = FaultScenarioResult(
        scenario_id="hard_hang" if blocked else "timeout_exception",
        status="BLOCK" if blocked else "PASS",
        legacy_preserved=True,
        trusted_isolated=not blocked,
        rollback_path="legacy",
        content_safe=True,
        structured_reason=(
            "timeout.hard_hang_no_hard_deadline"
            if blocked
            else "retriever.timeout_exception"
        ),
    )
    return FaultInjectionResults(
        scenario_count=1,
        pass_count=0 if blocked else 1,
        block_count=1 if blocked else 0,
        scenarios=[scenario],
    )


def test_all_gate_checks_pass():
    result = TrustedRAGGate().evaluate(_shadow(), _faults())

    assert result.quality_pass
    assert result.latency_pass
    assert result.reliability_pass
    assert result.rerank_pass
    assert result.final_decision is CanaryDecisionValue.PASS
    assert result.block_reasons == []
    assert result.remediation == []
    assert result.rollback_recommended is False


def test_single_metric_failure_blocks_p95():
    result = TrustedRAGGate().evaluate(_shadow(p95_latency_ms=1500.01), _faults())

    assert result.quality_pass and result.reliability_pass and result.rerank_pass
    assert result.latency_pass is False
    assert result.block_reasons == ["latency.p95_exceeded"]


def test_multiple_metric_failures_are_all_reported():
    result = TrustedRAGGate().evaluate(
        _shadow(
            evidence_overlap_mean=0.60,
            p95_latency_ms=1600.0,
            timeout_rate=0.02,
            error_rate=0.03,
            rerank=_rerank(degraded_case_count=1),
        ),
        _faults(blocked=True),
    )

    assert not result.quality_pass
    assert not result.latency_pass
    assert not result.reliability_pass
    assert not result.rerank_pass
    assert "reliability.fault_failure_rate_exceeded" in result.block_reasons
    assert "reliability.fault_blocked:timeout.hard_hang_no_hard_deadline" in result.block_reasons
    assert "rerank.degraded_cases_exceeded" in result.block_reasons


def test_missing_inputs_fail_closed():
    result = TrustedRAGGate().evaluate(None, None)

    assert result.final_decision is CanaryDecisionValue.BLOCK
    assert result.block_reasons == [
        "quality.shadow_metrics_missing",
        "latency.shadow_metrics_missing",
        "reliability.shadow_metrics_missing",
        "reliability.fault_results_missing",
        "rerank.metrics_missing",
    ]


def test_block_decision_recommends_automatic_rollback():
    result = TrustedRAGGate().evaluate(_shadow(), _faults(blocked=True))

    assert result.final_decision is CanaryDecisionValue.BLOCK
    assert result.rollback_recommended is True
    assert result.recommended_action == "keep_legacy_and_set_canary_weight_to_zero"


def test_task004_reports_are_supported_without_trusting_provisional_rerank():
    rerank = RerankMetrics.from_blind_evaluation(
        {
            "evaluationType": "offline_independent_blind_candidate_ranking",
            "metricsProvisional": True,
            "delta": {"mrr": 0.4, "ndcg@3": 0.5, "ndcg@5": 0.3},
            "degradedCaseCount": 2,
            "humanPreference": {"status": "pending_independent_human_review"},
            "relevanceReview": {"status": "pending_independent_human_review"},
        }
    )

    result = TrustedRAGGate().evaluate(_shadow(rerank=rerank), _faults())

    assert result.rerank_pass is False
    assert set(result.block_reasons) >= {
        "rerank.metrics_still_provisional",
        "rerank.human_review_incomplete",
        "rerank.degraded_cases_exceeded",
    }


def test_gate_accepts_complete_shadow_evaluation_dataset():
    query_types = (
        "concept_explanation", "method_comparison", "operation_steps",
        "programming_practice", "comprehensive_question",
    )
    samples = []
    for query_type in query_types:
        for index in range(20):
            samples.append({
                "request_id": f"{query_type}-{index}",
                "query_type": query_type,
                "latency_metrics": {
                    "total_ms": 100 + index,
                    "rag_ms": 90 + index,
                    "tool_ms": 0,
                },
                "quality_metrics": {
                    "evidence_overlap": 0.75,
                    "source_coverage": 0.85,
                    "confidence": 0.9,
                },
                "reliability_metrics": {
                    "timed_out": False,
                    "error_type": None,
                    "timeout_reason": None,
                    "cancellation_requested": False,
                    "worker_isolated": False,
                    "legacy_preserved": True,
                },
                "gate_features": {
                    "quality_metrics_complete": True,
                    "latency_metrics_complete": True,
                    "reliability_metrics_complete": True,
                    "target_environment_sample": True,
                },
            })
    dataset = ShadowEvaluationDataset(
        environment="target-canary-review",
        evaluation_window="frozen-window-v1",
        performance_verified=True,
        samples=samples,
    )

    result = TrustedRAGGate().evaluate(dataset, _faults(), rerank_metrics=_rerank())

    assert result.final_decision is CanaryDecisionValue.PASS
    assert result.snapshot.shadow_input_type == "dataset"
    assert result.snapshot.query_type_counts == {name: 20 for name in sorted(query_types)}


def test_dataset_underrepresented_query_type_blocks_with_remediation():
    dataset = ShadowEvaluationDataset(
        environment="fixture",
        evaluation_window="fixture",
        samples=[],
    )
    result = TrustedRAGGate().evaluate(dataset, _faults(), rerank_metrics=_rerank())

    assert result.final_decision is CanaryDecisionValue.BLOCK
    assert "complete_stratified_shadow_dataset" in result.remediation
