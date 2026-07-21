"""TASK-003-D1候选协议、融合与治理测试。"""
from __future__ import annotations

from app.core.config import settings
from app.rag.protocol import RetrievalCandidate
from app.rag.retriever import HybridRetriever


def _item(chunk_id: str, document_id: str, content: str, score: float) -> dict:
    return {
        "id": chunk_id,
        "content": content,
        "metadata": {
            "document_id": document_id,
            "document_title": document_id,
        },
        "vectorScore": score,
    }


class _ControlledRetriever(HybridRetriever):
    def __init__(self, dense: list[dict], sparse: list[dict]):
        super().__init__(store_getter=lambda: None)
        self._dense = dense
        self._sparse = sparse

    def _dense_search(self, query: str, k: int) -> list[dict]:
        return self._dense[:k]

    def _sparse_search(self, query: str, k: int) -> list[dict]:
        return self._sparse[:k]


def test_retrieval_candidate_protocol_contains_all_stage_scores():
    candidate = RetrievalCandidate(
        id="doc_a#0",
        content="反向传播使用链式法则",
        source={"documentId": "doc_a"},
        metadata={"document_id": "doc_a"},
        dense_score=0.8,
        keyword_score=3.0,
        fusion_score=0.02,
    )
    assert set(candidate.model_dump()) == {
        "id", "content", "source", "metadata",
        "dense_score", "keyword_score", "fusion_score",
    }


def test_candidate_pool_and_rrf_are_configured_not_derived_from_final_k():
    retriever = _ControlledRetriever([], [])
    assert retriever.candidate_top_k == settings.retrieval_candidate_top_k
    assert retriever.final_top_k == settings.retrieval_final_top_k
    assert retriever.rrf_k == settings.rrf_k


def test_merge_deduplicates_chunk_and_exposes_new_and_legacy_scores():
    dense = [_item("doc_a#0", "doc_a", "反向传播链式法则梯度", 0.8)]
    sparse = [
        {
            "id": "doc_a#0",
            "content": dense[0]["content"],
            "metadata": dense[0]["metadata"],
            "bm25Score": 5.0,
        }
    ]
    retriever = _ControlledRetriever(dense, sparse)
    retriever.min_dense_score = 0.0
    retriever.min_query_overlap = 0.0
    results = retriever.search("反向传播", top_k=5)
    assert len(results) == 1
    assert results[0]["dense_score"] == results[0]["vectorScore"] == 0.8
    assert results[0]["keyword_score"] == results[0]["bm25Score"] == 5.0
    assert results[0]["fusion_score"] == results[0]["rrfScore"]


def test_metadata_filter_and_source_diversity_are_enforced():
    dense = [
        _item("doc_a#0", "doc_a", "注意力机制查询键和值", 0.9),
        _item("doc_a#1", "doc_a", "注意力机制计算权重", 0.8),
        _item("doc_b#0", "doc_b", "注意力机制多头并行", 0.7),
    ]
    retriever = _ControlledRetriever(dense, [])
    retriever.min_dense_score = 0.0
    retriever.min_query_overlap = 0.0
    retriever.max_chunks_per_source = 1
    results = retriever.search(
        "注意力机制",
        top_k=3,
        filters={"knowledge_scope": {"document_ids": ["doc_a"]}},
    )
    assert [item["id"] for item in results] == ["doc_a#0"]


def test_explicit_scope_can_use_strong_keyword_candidate_below_dense_threshold():
    dense = [_item("doc_a#0", "doc_a", "LoRA低秩参数微调", 0.2)]
    sparse = [
        {
            "id": "doc_a#0",
            "content": dense[0]["content"],
            "metadata": dense[0]["metadata"],
            "bm25Score": 4.0,
        }
    ]
    retriever = _ControlledRetriever(dense, sparse)
    retriever.min_dense_score = 0.35
    retriever.min_query_overlap = 0.35
    results = retriever.search(
        "LoRA低秩参数",
        filters={"knowledge_scope": {"document_ids": ["doc_a"]}},
    )
    assert [item["id"] for item in results] == ["doc_a#0"]


def test_arbitrary_metadata_filter_uses_exact_or_allowlist_match():
    dense = [_item("doc_a#0", "doc_a", "注意力机制", 0.9)]
    dense[0]["metadata"]["category"] = "教材"
    retriever = _ControlledRetriever(dense, [])
    retriever.min_dense_score = retriever.min_query_overlap = 0.0
    assert retriever.search("注意力", filters={"category": ["教材", "讲义"]})
    assert retriever.search("注意力", filters={"category": "视频"}) == []


def test_strong_keyword_overlap_can_recover_legacy_collection_candidate():
    dense = [_item("doc_a#0", "doc_a", "反向传播通过链式法则计算梯度", 0.1)]
    sparse = [
        {
            "id": "doc_a#0",
            "content": dense[0]["content"],
            "metadata": dense[0]["metadata"],
            "bm25Score": 12.0,
        }
    ]
    retriever = _ControlledRetriever(dense, sparse)
    retriever.min_dense_score = 0.35
    retriever.min_query_overlap = 0.35
    retriever.min_strong_keyword_overlap = 0.6
    assert retriever.search("反向传播梯度计算")


def test_low_relevance_candidates_produce_explicit_empty_result():
    retriever = _ControlledRetriever(
        [_item("doc_a#0", "doc_a", "完全无关的教学正文", 0.1)],
        [],
    )
    retriever.min_dense_score = 0.35
    retriever.min_query_overlap = 0.35
    assert retriever.search("量子纠错表面码", top_k=5) == []
