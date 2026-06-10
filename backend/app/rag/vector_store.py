"""向量库（B3，Chroma 持久化集合 + 降级内存库）。

优先使用 Chroma 持久化集合（`PersistentClient(path=chroma_dir)`）；当 chromadb 未安装
或初始化失败时，降级为进程内 numpy 余弦库（仍按 chroma_dir 持久化为 JSON），打 WARNING，
保证全链路可跑（CLAUDE.md「轻量优先 / 无密钥可跑通」纪律）。

两种实现暴露同一接口：add / query / delete_by_document / get_all / count。
距离统一转为「相似度分数」（0-1，越大越相关），便于上层 RRF 与展示。
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading

from app.core.config import settings

logger = logging.getLogger("app.rag.vector_store")

_COLLECTION = "kb_chunks"


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class _NumpyStore:
    """降级内存向量库：JSON 持久化 + 余弦检索。"""

    def __init__(self, path: str) -> None:
        self._path = os.path.join(path, "fallback_store.json")
        os.makedirs(path, exist_ok=True)
        self._items: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._path):
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._items = json.load(f)
            except (OSError, ValueError):
                self._items = {}

    def _persist(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._items, f, ensure_ascii=False)

    def add(self, ids, embeddings, documents, metadatas) -> None:
        with self._lock:
            for i, cid in enumerate(ids):
                self._items[cid] = {
                    "embedding": embeddings[i],
                    "document": documents[i],
                    "metadata": metadatas[i],
                }
            self._persist()

    def query(self, embedding, n_results):
        scored = [
            (cid, _cosine(embedding, it["embedding"]), it)
            for cid, it in self._items.items()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        out = []
        for cid, sim, it in scored[:n_results]:
            out.append(
                {
                    "id": cid,
                    "content": it["document"],
                    "metadata": it["metadata"],
                    "score": max(0.0, min(1.0, sim)),
                }
            )
        return out

    def delete_by_document(self, document_id: str) -> int:
        with self._lock:
            victims = [
                cid
                for cid, it in self._items.items()
                if it["metadata"].get("document_id") == document_id
            ]
            for cid in victims:
                del self._items[cid]
            self._persist()
            return len(victims)

    def get_all(self):
        return [
            {"id": cid, "content": it["document"], "metadata": it["metadata"]}
            for cid, it in self._items.items()
        ]

    def count(self) -> int:
        return len(self._items)


class _ChromaStore:
    """Chroma 持久化集合封装。"""

    def __init__(self, path: str) -> None:
        import chromadb

        os.makedirs(path, exist_ok=True)
        self._client = chromadb.PersistentClient(path=path)
        # 余弦空间；嵌入由本层显式提供（不使用 chroma 内置 embedding function）
        self._col = self._client.get_or_create_collection(
            name=_COLLECTION, metadata={"hnsw:space": "cosine"}
        )

    def add(self, ids, embeddings, documents, metadatas) -> None:
        self._col.add(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def query(self, embedding, n_results):
        n = min(n_results, max(1, self._col.count()))
        res = self._col.query(
            query_embeddings=[embedding],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )
        out = []
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for i, cid in enumerate(ids):
            # cosine distance ∈ [0,2] → 相似度 1 - d，裁剪到 [0,1]
            sim = 1.0 - float(dists[i])
            out.append(
                {
                    "id": cid,
                    "content": docs[i],
                    "metadata": metas[i],
                    "score": max(0.0, min(1.0, sim)),
                }
            )
        return out

    def delete_by_document(self, document_id: str) -> int:
        existing = self._col.get(where={"document_id": document_id})
        ids = existing.get("ids", [])
        if ids:
            self._col.delete(ids=ids)
        return len(ids)

    def get_all(self):
        got = self._col.get(include=["documents", "metadatas"])
        ids = got.get("ids", [])
        docs = got.get("documents", [])
        metas = got.get("metadatas", [])
        return [
            {"id": ids[i], "content": docs[i], "metadata": metas[i]}
            for i in range(len(ids))
        ]

    def count(self) -> int:
        return self._col.count()


_store = None
_store_lock = threading.Lock()


def get_vector_store():
    """返回向量库单例：优先 Chroma，失败降级 numpy 库。"""
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        path = settings.chroma_dir
        try:
            _store = _ChromaStore(path)
            logger.info("向量库：Chroma 持久化集合就绪（path=%s）", path)
        except Exception as exc:  # noqa: BLE001 chromadb 不可用 → 降级
            logger.warning(
                "Chroma 初始化失败，降级为内存余弦向量库（JSON 持久化）：%s", exc
            )
            _store = _NumpyStore(path)
        return _store
