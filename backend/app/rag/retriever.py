"""混合检索（B3，需求文档 4.3.2：BM25 + 向量 RRF 融合）。

流程：
1. 向量检索（dense）：query 经 Embedder 向量化 → 向量库 top-k*2；
2. 关键词检索（sparse）：rank_bm25 在全量 chunk 语料上检索 top-k*2；
3. RRF 融合：按 4.3.2 倒数排名融合（dense_weight/sparse_weight、rrf_k），返回 top-k。

BM25 语料来自向量库当前全量 chunk，**每次检索按库内容计数惰性重建**——库小、检索测试
低频，避免维护增量索引的复杂度与陈旧风险。中文分词用「字 + 英数词」简易切分（不引入 jieba）。

返回候选含：chunkId / content / metadata / vectorScore / bm25Score / rrfScore，
交由上层 reranker 重排或降级直接用 rrfScore。
"""
from __future__ import annotations

import re
from typing import Any, Callable

from app.core.config import settings
from app.rag.embeddings import get_embedder
from app.rag.protocol import RetrievalCandidate
from app.rag.vector_store import get_collection_store, get_vector_store

_TOKEN_RE = re.compile(r"[a-z0-9]+|[一-鿿]")


def _tokenize(text: str) -> list[str]:
    """简易中英混合分词：英文/数字按词，中文按单字。"""
    return _TOKEN_RE.findall((text or "").lower())


class HybridRetriever:
    """BM25 + 向量 RRF 混合检索。

    store_getter 可注入（默认内置库 kb_chunks 单例）：「文档学习」传入指向文档专属
    集合的 getter，即可在**隔离集合**上做同样的混合检索，不污染内置知识库。
    """

    def __init__(self, store_getter: Callable[[], object] | None = None) -> None:
        self.dense_weight = settings.rrf_dense_weight
        self.sparse_weight = settings.rrf_sparse_weight
        self.rrf_k = settings.rrf_k
        self.candidate_top_k = settings.retrieval_candidate_top_k
        self.final_top_k = settings.retrieval_final_top_k
        self.max_chunks_per_source = settings.retrieval_max_chunks_per_source
        self.min_dense_score = settings.retrieval_min_dense_score
        self.min_query_overlap = settings.retrieval_min_query_overlap
        self.min_strong_keyword_overlap = settings.retrieval_min_strong_keyword_overlap
        self._store_getter = store_getter or get_vector_store
        # BM25 缓存：(库计数, 索引, 语料元数据)
        self._bm25 = None
        self._bm25_count = -1
        self._bm25_docs: list[dict] = []

    # ---- BM25 索引（惰性、按库计数失效重建） -----------------------------
    def _ensure_bm25(self) -> None:
        store = self._store_getter()
        count = store.count()
        if self._bm25 is not None and count == self._bm25_count:
            return
        from rank_bm25 import BM25Okapi

        self._bm25_docs = store.get_all()
        corpus = [_tokenize(d["content"]) for d in self._bm25_docs]
        # 空语料时给一个占位 token，避免 BM25Okapi 对空集报错
        self._bm25 = BM25Okapi(corpus or [["_"]])
        self._bm25_count = count

    def _sparse_search(self, query: str, k: int) -> list[dict]:
        self._ensure_bm25()
        if not self._bm25_docs:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(
            range(len(self._bm25_docs)), key=lambda i: scores[i], reverse=True
        )
        out = []
        for i in ranked:
            if float(scores[i]) <= 0.0:
                continue
            d = self._bm25_docs[i]
            out.append(
                {
                    "id": d["id"],
                    "content": d["content"],
                    "metadata": d["metadata"],
                    "bm25Score": float(scores[i]),
                }
            )
            if len(out) >= k:
                break
        return out

    def _dense_search(self, query: str, k: int) -> list[dict]:
        vec = get_embedder().embed_query(query)
        results = self._store_getter().query(vec, k)
        for r in results:
            r["vectorScore"] = r.pop("score")
        return results

    # ---- RRF 融合（需求文档 4.3.2） --------------------------------------
    @staticmethod
    def _source(item: dict[str, Any]) -> dict[str, Any]:
        metadata = item.get("metadata") or {}
        return {
            key: value
            for key, value in {
                "chunkId": item.get("id"),
                "documentId": metadata.get("document_id") or metadata.get("docId"),
                "title": metadata.get("document_title") or metadata.get("title"),
                "location": metadata.get("source_location"),
            }.items()
            if value is not None
        }

    @classmethod
    def _candidate_dict(cls, candidate: RetrievalCandidate) -> dict[str, Any]:
        """输出新协议，同时保留旧调用方使用的camelCase字段。"""
        row = candidate.model_dump(mode="json")
        row.update(
            {
                "vectorScore": candidate.dense_score,
                "bm25Score": candidate.keyword_score,
                "rrfScore": candidate.fusion_score,
            }
        )
        return row

    def _rrf(self, dense: list[dict], sparse: list[dict]) -> list[RetrievalCandidate]:
        merged: dict[str, RetrievalCandidate] = {}

        def ensure(item: dict) -> RetrievalCandidate:
            cid = item["id"]
            if cid not in merged:
                merged[cid] = RetrievalCandidate(
                    id=cid,
                    content=item["content"],
                    source=self._source(item),
                    metadata=item.get("metadata") or {},
                )
            return merged[cid]

        for rank, item in enumerate(dense):
            row = ensure(item)
            row.dense_score = float(item.get("vectorScore", 0.0))
            row.fusion_score += self.dense_weight / (self.rrf_k + rank + 1)
        for rank, item in enumerate(sparse):
            row = ensure(item)
            row.keyword_score = float(item.get("bm25Score", 0.0))
            row.fusion_score += self.sparse_weight / (self.rrf_k + rank + 1)

        return sorted(merged.values(), key=lambda item: item.fusion_score, reverse=True)

    @staticmethod
    def _document_filter(filters: dict[str, Any] | None) -> set[str] | None:
        if not filters:
            return None
        scope = filters.get("knowledge_scope", filters)
        if isinstance(scope, dict):
            values = scope.get("document_ids") or scope.get("documentIds")
            return set(values) if values else None
        if isinstance(scope, list):
            return set(scope)
        return None

    @staticmethod
    def _metadata_matches(candidate: RetrievalCandidate, filters: dict[str, Any] | None) -> bool:
        if not filters:
            return True
        expected = {key: value for key, value in filters.items() if key != "knowledge_scope"}
        scope = filters.get("knowledge_scope")
        if isinstance(scope, dict):
            expected.update(
                {
                    key: value
                    for key, value in scope.items()
                    if key not in {"document_ids", "documentIds"}
                }
            )
        for key, value in expected.items():
            actual = candidate.metadata.get(key)
            if isinstance(value, list):
                if actual not in value:
                    return False
            elif actual != value:
                return False
        return True

    @staticmethod
    def _query_overlap(query: str, content: str) -> float:
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return 0.0
        return len(query_tokens & set(_tokenize(content))) / len(query_tokens)

    def _govern(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        *,
        final_top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        allowed_documents = self._document_filter(filters)
        selected: list[RetrievalCandidate] = []
        seen_content: set[str] = set()
        source_counts: dict[str, int] = {}
        for candidate in candidates:
            document_id = str(candidate.source.get("documentId") or "")
            if allowed_documents is not None and document_id not in allowed_documents:
                continue
            if not self._metadata_matches(candidate, filters):
                continue
            normalized_content = " ".join(candidate.content.split()).lower()
            if normalized_content in seen_content:
                continue
            if source_counts.get(document_id, 0) >= self.max_chunks_per_source:
                continue
            overlap = self._query_overlap(query, candidate.content)
            general_relevance = (
                candidate.dense_score >= self.min_dense_score
                and overlap >= self.min_query_overlap
            )
            scoped_keyword_relevance = (
                allowed_documents is not None
                and candidate.keyword_score > 0.0
                and overlap >= self.min_query_overlap
            )
            strong_keyword_relevance = (
                candidate.keyword_score > 0.0
                and overlap >= self.min_strong_keyword_overlap
            )
            if not (
                general_relevance
                or scoped_keyword_relevance
                or strong_keyword_relevance
            ):
                continue
            candidate.metadata["queryOverlap"] = round(overlap, 6)
            selected.append(candidate)
            seen_content.add(normalized_content)
            source_counts[document_id] = source_counts.get(document_id, 0) + 1
            if len(selected) >= final_top_k:
                break
        return [self._candidate_dict(candidate) for candidate in selected]

    def search(
        self,
        query: str,
        top_k: int | None = None,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行混合检索，返回融合后的候选（已含 vector/bm25/rrf 分数）。"""
        final_top_k = top_k or self.final_top_k
        pool = max(self.candidate_top_k, final_top_k)
        dense = self._dense_search(query, pool)
        sparse = self._sparse_search(query, pool)
        return self._govern(
            query,
            self._rrf(dense, sparse),
            final_top_k=final_top_k,
            filters=filters,
        )


class LegacyHybridRetriever(HybridRetriever):
    """TASK-003-C1算法快照，仅供离线before/after评测。"""

    def _sparse_search(self, query: str, k: int) -> list[dict]:
        self._ensure_bm25()
        if not self._bm25_docs:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(self._bm25_docs)), key=lambda i: scores[i], reverse=True)
        return [
            {
                "id": self._bm25_docs[i]["id"],
                "content": self._bm25_docs[i]["content"],
                "metadata": self._bm25_docs[i]["metadata"],
                "bm25Score": float(scores[i]),
            }
            for i in ranked[:k]
        ]

    def search(self, query: str, top_k: int = 5, **_: Any) -> list[dict]:
        pool = max(top_k * 2, top_k)
        dense = self._dense_search(query, pool)
        sparse = self._sparse_search(query, pool)
        return [self._candidate_dict(item) for item in self._rrf(dense, sparse)[:top_k]]


_retriever: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever


def get_document_retriever(collection: str) -> HybridRetriever:
    """「文档学习」专属检索器：在文档专属向量集合上做混合检索（隔离内置库）。

    每次新建实例（各自 BM25 缓存，绑定各自集合）——文档检索低频、集合小，无需缓存单例。
    """
    return HybridRetriever(store_getter=lambda: get_collection_store(collection))
