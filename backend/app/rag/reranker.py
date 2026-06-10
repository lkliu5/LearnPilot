"""重排（B3，需求文档 4.3.3：bge-reranker-base CrossEncoder 二次打分）。

降级约定（任务硬性要求 + 接口文档 14.4）：当 bge-reranker 加载失败 / 超时 / 推理异常时，
`rerank()` 返回 `used=False`，候选退化为仅按 RRF 分数排序（归一化到 0-1），并打 **WARNING**
日志；接口仍正常返回 code 0。模型延迟加载（首次 rerank 时才加载），不阻塞 uvicorn 启动。
"""
from __future__ import annotations

import logging
import math
import threading

from app.core.config import settings

logger = logging.getLogger("app.rag.reranker")


def _sigmoid(x: float) -> float:
    """CrossEncoder logit → (0,1) 分数。"""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


class Reranker:
    """bge-reranker-base 重排器，失败降级为仅 RRF。"""

    def __init__(self) -> None:
        self.model_name = settings.reranker_model_name
        self._model = None  # type: ignore[var-annotated]
        self._loaded = False
        self.degraded = False
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            try:
                from sentence_transformers import CrossEncoder

                from app.rag.embeddings import model_is_cached

                cached = model_is_cached(self.model_name)
                self._model = CrossEncoder(
                    self.model_name,
                    cache_folder=settings.model_cache_dir,
                    local_files_only=cached,  # 已缓存则离线加载，避免运行时联网
                )
                self.degraded = False
                logger.info(
                    "重排模型加载成功：%s（%s）",
                    self.model_name,
                    "离线缓存" if cached else "在线下载",
                )
            except Exception as exc:  # noqa: BLE001 任何失败 → 降级仅 RRF
                self._model = None
                self.degraded = True
                logger.warning(
                    "重排模型 '%s' 加载失败，降级为仅 RRF 排序：%s",
                    self.model_name,
                    exc,
                )
            finally:
                self._loaded = True

    def rerank(
        self, query: str, candidates: list[dict], top_k: int = 5
    ) -> tuple[list[dict], bool]:
        """对候选重排，返回 (排序后候选, rerankerUsed)。

        成功：写入 `score`=sigmoid(rerank logit)，按其降序；
        降级：`score`=RRF 分数归一化（除以最大值），按 rrfScore 降序。
        """
        if not candidates:
            return [], False

        self._ensure_loaded()

        if self._model is not None:
            try:
                pairs = [(query, c["content"]) for c in candidates]
                scores = self._model.predict(pairs)
                for c, s in zip(candidates, scores):
                    c["score"] = round(_sigmoid(float(s)), 4)
                ranked = sorted(candidates, key=lambda x: x["score"], reverse=True)
                return ranked[:top_k], True
            except Exception as exc:  # noqa: BLE001 推理异常 → 本次降级
                logger.warning("重排推理失败，本次降级为仅 RRF 排序：%s", exc)

        # 降级：RRF 归一化分
        max_rrf = max((c.get("rrfScore", 0.0) for c in candidates), default=0.0) or 1.0
        for c in candidates:
            c["score"] = round(c.get("rrfScore", 0.0) / max_rrf, 4)
        ranked = sorted(candidates, key=lambda x: x.get("rrfScore", 0.0), reverse=True)
        return ranked[:top_k], False


_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def reset_reranker() -> None:
    """清除单例（供测试模拟「重排模型加载失败」后重新加载）。"""
    global _reranker
    _reranker = None
