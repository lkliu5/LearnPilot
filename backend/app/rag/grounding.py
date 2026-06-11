"""逐句接地校验（B5-b，接口文档 15.3 幻觉率统一口径）。

口径：生成内容按句切分，每句与本次 RAG 检索命中的来源切片做 embedding 相似度
比对取最大值；低于阈值（settings.grounding_threshold，默认 0.75）的句子视为
「未接地（疑似幻觉）」，hallucinationRate = 未接地句数 / 总句数（0-1）。
无任何 RAG 来源（纯模板/兜底）时按约定置 0，不参与质量统计。

工程细节：
- Markdown 预处理：代码块整体剔除（非自然语言句，不应计为幻觉）、
  标题/引用/列表/加粗等语法符号剥离后保留正文；
- 比对单元 = 来源切片全文 + 切片内逐句（细粒度子片段提升长切片的召回保真，
  仍属「与来源切片比对」口径）；
- 向量经 Embedder（bge 或降级哈希嵌入）均已 L2 归一化 → 点积即余弦相似度。
"""
from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.rag.embeddings import get_embedder

# 代码块（``` 围栏）整体剔除
_CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
# 行内 Markdown 语法符号：标题/引用/列表前缀、加粗斜体、行内代码
_MD_PREFIX_RE = re.compile(r"^\s*(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.、]\s+)")
_MD_INLINE_RE = re.compile(r"[*_`]+")
# 句子切分：中英句末标点 / 换行
_SENT_SPLIT_RE = re.compile(r"[。！？；!?;\n]+")
# 过短片段（标题残文、连接词等）不计为句子
_MIN_SENT_CHARS = 6


def split_sentences(text: str) -> list[str]:
    """Markdown → 自然语言句子列表（剔代码块、剥语法符号、滤过短片段）。"""
    if not text:
        return []
    cleaned = _CODE_FENCE_RE.sub("", text)
    lines = [_MD_PREFIX_RE.sub("", line) for line in cleaned.split("\n")]
    cleaned = _MD_INLINE_RE.sub("", "\n".join(lines))
    sentences = []
    for raw in _SENT_SPLIT_RE.split(cleaned):
        s = raw.strip()
        if len(s) >= _MIN_SENT_CHARS:
            sentences.append(s)
    return sentences


def sentence_grounding(
    text: str,
    contexts: list[str],
    threshold: float | None = None,
) -> dict[str, Any]:
    """逐句接地校验（15.3）。

    Args:
        text: 生成内容（Markdown）。
        contexts: 本次 RAG 检索命中的来源切片内容列表。
        threshold: 接地阈值，缺省取 settings.grounding_threshold。

    Returns:
        {hallucinationRate, totalSentences, ungroundedSentences}
    """
    if threshold is None:
        threshold = settings.grounding_threshold
    sentences = split_sentences(text)
    contexts = [c for c in contexts if c and c.strip()]
    if not sentences or not contexts:
        # 15.3：无来源（纯模板/兜底）或无可判句子 → 置 0，不参与质量统计
        return {
            "hallucinationRate": 0.0,
            "totalSentences": len(sentences),
            "ungroundedSentences": [],
        }

    # 比对单元：切片全文 + 切片内逐句（去重）
    units: list[str] = []
    seen: set[str] = set()
    for ctx in contexts:
        for unit in [ctx, *split_sentences(ctx)]:
            u = unit.strip()
            if u and u not in seen:
                seen.add(u)
                units.append(u)

    embedder = get_embedder()
    sent_vecs = embedder.embed_texts(sentences)
    unit_vecs = embedder.embed_texts(units)

    ungrounded: list[str] = []
    for sentence, sv in zip(sentences, sent_vecs):
        best = max(sum(a * b for a, b in zip(sv, uv)) for uv in unit_vecs)
        if best < threshold:
            ungrounded.append(sentence)

    return {
        "hallucinationRate": round(len(ungrounded) / len(sentences), 4),
        "totalSentences": len(sentences),
        "ungroundedSentences": ungrounded,
    }
