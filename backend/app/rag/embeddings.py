"""文本向量化（B3，bge-small-zh-v1.5 本地加载 + 降级）。

设计要点（对齐任务约束）：
- **延迟加载不阻塞 uvicorn**：进程启动时不加载模型；首次 `embed_*` 调用时才尝试
  `SentenceTransformer(model_name, cache_folder=model_cache_dir)`。
- **加载失败自动降级**：sentence-transformers 未安装 / 模型下载失败 / 加载异常时，
  切换为确定性哈希嵌入（char-ngram 散列到固定维度并 L2 归一化），打 WARNING 日志，
  保证全链路在无网络、无模型文件时仍可跑通（CLAUDE.md「无密钥可跑通」纪律）。
- 单例：`get_embedder()` 返回进程内单例。
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import threading

from app.core.config import settings

logger = logging.getLogger("app.rag.embeddings")

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[一-鿿]")


def model_is_cached(model_name: str) -> bool:
    """模型是否已下载到本地缓存（HF 缓存目录命名 models--ORG--NAME）。

    已缓存时以 local_files_only 离线加载，避免运行时网络调用（uvicorn/async 环境下
    huggingface_hub 的 httpx 客户端可能已关闭，导致联网加载报错而误降级）。
    """
    safe = "models--" + model_name.replace("/", "--")
    return os.path.isdir(os.path.join(settings.model_cache_dir, safe))


class Embedder:
    """向量化适配层：优先 bge-small-zh，失败降级为哈希嵌入。"""

    def __init__(self) -> None:
        self.model_name = settings.embedding_model_name
        self.fallback_dim = settings.embedding_fallback_dim
        self._model = None  # type: ignore[var-annotated]
        self._loaded = False  # 是否已尝试加载（无论成功失败）
        self.degraded = False  # True 表示当前走哈希降级
        self._lock = threading.Lock()

    # ---- 模型加载（延迟、线程安全、失败降级） ----------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            try:
                from sentence_transformers import SentenceTransformer

                cached = model_is_cached(self.model_name)
                self._model = SentenceTransformer(
                    self.model_name,
                    cache_folder=settings.model_cache_dir,
                    local_files_only=cached,  # 已缓存则离线加载，避免运行时联网
                )
                self.degraded = False
                logger.info(
                    "嵌入模型加载成功：%s（%s）",
                    self.model_name,
                    "离线缓存" if cached else "在线下载",
                )
            except Exception as exc:  # noqa: BLE001 任何失败都降级，不阻断
                self._model = None
                self.degraded = True
                logger.warning(
                    "嵌入模型 '%s' 加载失败，降级为确定性哈希嵌入（dim=%d）：%s",
                    self.model_name,
                    self.fallback_dim,
                    exc,
                )
            finally:
                self._loaded = True

    # ---- 对外 API ---------------------------------------------------------
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量向量化。返回与输入等长的向量列表。"""
        self._ensure_loaded()
        if not texts:
            return []
        if self._model is not None:
            vecs = self._model.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            )
            return [list(map(float, v)) for v in vecs]
        return [self._hash_embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        """单条查询向量化。"""
        return self.embed_texts([text])[0]

    @property
    def dim(self) -> int:
        """当前向量维度（降级模式下为 fallback_dim）。"""
        self._ensure_loaded()
        if self._model is not None:
            return int(self._model.get_sentence_embedding_dimension())
        return self.fallback_dim

    # ---- 降级哈希嵌入 -----------------------------------------------------
    def _hash_embed(self, text: str) -> list[float]:
        """确定性 char/词 散列嵌入：token 经 md5 落桶累加，再 L2 归一化。

        非语义但稳定、含一定词面信号——足以让向量检索在降级时返回合理排序，
        并保证同一文本每次得到相同向量（可复现）。
        """
        dim = self.fallback_dim
        vec = [0.0] * dim
        tokens = _TOKEN_RE.findall((text or "").lower())
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder:
    """返回进程内 Embedder 单例。"""
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                _embedder = Embedder()
    return _embedder
