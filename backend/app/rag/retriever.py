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
from typing import Callable

from app.core.config import settings
from app.rag.embeddings import get_embedder
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
        for i in ranked[:k]:
            d = self._bm25_docs[i]
            out.append(
                {
                    "id": d["id"],
                    "content": d["content"],
                    "metadata": d["metadata"],
                    "bm25Score": float(scores[i]),
                }
            )
        return out

    def _dense_search(self, query: str, k: int) -> list[dict]:
        vec = get_embedder().embed_query(query)
        results = self._store_getter().query(vec, k)
        for r in results:
            r["vectorScore"] = r.pop("score")
        return results

    # ---- RRF 融合（需求文档 4.3.2） --------------------------------------
    def _rrf(self, dense: list[dict], sparse: list[dict], top_k: int) -> list[dict]:
        merged: dict[str, dict] = {}

        def ensure(item: dict) -> dict:
            cid = item["id"]
            if cid not in merged:
                merged[cid] = {
                    "id": cid,
                    "content": item["content"],
                    "metadata": item["metadata"],
                    "vectorScore": 0.0,
                    "bm25Score": 0.0,
                    "rrfScore": 0.0,
                }
            return merged[cid]

        for rank, item in enumerate(dense):
            row = ensure(item)
            row["vectorScore"] = item.get("vectorScore", 0.0)
            row["rrfScore"] += self.dense_weight / (self.rrf_k + rank + 1)
        for rank, item in enumerate(sparse):
            row = ensure(item)
            row["bm25Score"] = item.get("bm25Score", 0.0)
            row["rrfScore"] += self.sparse_weight / (self.rrf_k + rank + 1)

        fused = sorted(merged.values(), key=lambda x: x["rrfScore"], reverse=True)
        return fused[:top_k]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """执行混合检索，返回融合后的候选（已含 vector/bm25/rrf 分数）。"""
        pool = max(top_k * 2, top_k)
        dense = self._dense_search(query, pool)
        sparse = self._sparse_search(query, pool)
        return self._rrf(dense, sparse, top_k)


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
