"""讲义图文增强（图解优先 + 真实图片补充，防幻觉 / mock 占位）。

把「纯文字讲义」加工成「图文并茂」，双来源 + 兜底，**禁止 AI 生成图片**：

1. **图解优先（最稳）**：结构 / 流程类小节复用既有 Mermaid 图解能力
   （``LLMClient.generate_diagram``，mock 确定性、离线可跑），以 ```mermaid 围栏嵌入
   「核心原理」小节末尾，前端 MarkdownRenderer 识别 ```mermaid 走 MermaidDiagram 渲染。
2. **真实图片补充**：适合配真实图处用已接入的 Tavily 图片搜索
   （``web_search.search_images``）。**URL 一律取自搜索结果**（沿用「URL 只取真实候选、
   防幻觉」原则，绝不让 LLM 编造图片链接），并标注来源域名（出处链接）。无合适图 → 不插。
3. **mock 模式不发真实搜索**：用确定性 base64 内联 SVG 占位图（自包含、永不 404、无网络），
   既演示前端图片渲染 + 来源标注 + 裂图兜底，又满足「mock 占位、不发真实请求」。

接口签名不变：增强只作用于 ``/resource/lecture`` 返回的 ``markdown`` 字段内容
（仍是一段 Markdown 字符串），不新增字段、不改路径。幂等：已增强过的 markdown 直接返回。
"""
from __future__ import annotations

import base64
import logging
import re
from typing import Any

from app.core.config import settings

logger = logging.getLogger("app.core.lecture_media")

# 已增强标记（幂等：避免缓存回写 / 二次调用重复插图）
_ENRICHED_MARK = "<!-- media:enriched -->"

# 章节定位（compose_lecture 产出 `## 二、核心原理` / `## 一、概念引入…`；真实模式 LLM
# 产出结构相近，匹配不到则各自走兜底，不强插、不报错）。
_PRINCIPLE_RE = re.compile(r"^#{2,3}\s*.*(原理|机制|结构)")
_INTRO_RE = re.compile(r"^#{2,3}\s*.*(引入|概念|背景|是什么|简介)")
_HEADING_RE = re.compile(r"^#{1,6}\s")


def enrich_lecture(
    markdown: str,
    *,
    kp_id: str,
    kp_name: str,
    description: str,
    llm: Any,
) -> str:
    """为讲义 Markdown 注入图解（图解优先）与一张配图（真实图 / mock 占位）。

    Args:
        markdown: 原始讲义正文（compose_lecture / 工作流产出）。
        kp_id/kp_name/description: 知识点上下文（图解模板按 kp_id 命中、配图按主题搜索）。
        llm: 当前 LLMClient（``is_mock`` 决定走占位还是真实搜索；图解复用其 generate_diagram）。

    Returns:
        增强后的 Markdown；无可插内容时原样返回。已增强（含标记）→ 直接返回（幂等）。
    """
    if not markdown or not markdown.strip():
        return markdown
    if _ENRICHED_MARK in markdown:
        return markdown  # 幂等：已增强过不重复插图

    md = markdown

    # —— 图解优先：嵌入 Mermaid 结构 / 流程示意 ——
    diagram = _diagram_block(kp_id, kp_name, description, llm)
    if diagram:
        md, ok = _insert_after_section(md, _PRINCIPLE_RE, diagram)
        if not ok:  # 未匹配到原理小节 → 末尾追加独立「结构图解」节（保证图解可见）
            md = md.rstrip() + "\n\n## 结构图解\n\n" + diagram

    # —— 真实图片补充 / mock 占位：放在「概念引入」小节末尾 ——
    image = _image_block(kp_name, description, llm)
    if image:
        md, ok = _insert_after_section(md, _INTRO_RE, image)
        # 匹配不到引入小节时不强插（宁缺毋滥；图解已提供视觉信息）

    # 标记置于**末尾**：HTML 注释不渲染，且不影响正文以 `# 标题` 开头的契约（startswith "# "）
    return f"{md}\n\n{_ENRICHED_MARK}" if md != markdown else markdown


# --------------------------------------------------------------------------- #
# 图解块（复用既有 Mermaid 图解能力，离线可跑）
# --------------------------------------------------------------------------- #
def _diagram_block(kp_id: str, kp_name: str, description: str, llm: Any) -> str:
    """复用 ``LLMClient.generate_diagram`` 取 Mermaid 源码，包成讲义内嵌图解块。"""
    try:
        mermaid = str((llm.generate_diagram(kp_id, kp_name, description) or {}).get("mermaid") or "")
    except Exception as exc:  # noqa: BLE001 图解失败不致命，讲义照常返回
        logger.warning("讲义内嵌图解生成失败，跳过图解：%s", exc)
        return ""
    mermaid = mermaid.strip()
    if not mermaid:
        return ""
    caption = f"*图：「{kp_name}」核心结构 / 流程示意（系统生成图解）*"
    return f"```mermaid\n{mermaid}\n```\n\n{caption}"


# --------------------------------------------------------------------------- #
# 配图块（mock 确定性占位 / 真实 Tavily 图片，URL 防幻觉）
# --------------------------------------------------------------------------- #
def _image_block(kp_name: str, description: str, llm: Any) -> str | None:
    """生成一张配图的 Markdown（``![alt](url)`` + 来源标注）。无合适图 → None。"""
    if getattr(llm, "is_mock", False):
        # mock：确定性内联 SVG 占位，自包含、不发任何真实搜索请求
        url = _placeholder_data_uri(kp_name)
        alt = _md_escape(f"{kp_name} 示意图")
        return f"![{alt}]({url})\n\n*示意图（mock 占位，未发起真实搜索）*"

    # 真实模式：Tavily 图片搜索，URL 只取自搜索结果（防幻觉），并标注来源
    hit = _search_real_image(kp_name, description)
    if not hit:
        return None  # 无真实可用图 → 不强插（宁缺毋滥）
    url = hit["url"]
    source = hit["source"]
    # 第三方图片描述文本同样过内容安全（不绕过）：核心讲义/图解已在 LLMClient 层被 guard 包裹，
    # 此处的 alt 来自外部搜索结果，故显式再过一次 guard。
    from app.core import content_safety

    alt_raw = hit.get("description") or f"{kp_name} 配图"
    alt = _md_escape(content_safety.guard(alt_raw, where="lecture_image_alt"))
    return f"![{alt}]({url})\n\n*图片来源：[{source}]({url})*"


def _search_real_image(kp_name: str, description: str) -> dict[str, Any] | None:
    """经可插拔搜索 Provider 取一张真实配图；URL 必须为搜索返回的真实 http(s) 链接。"""
    from app.services import web_search

    provider = web_search.get_provider()
    if not getattr(provider, "online", False):
        return None  # 无联网能力 → 不插真实图
    query = f"{kp_name} 原理 示意图 diagram"
    try:
        hits = provider.search_images(query, max_results=settings.search_max_results)
    except Exception as exc:  # noqa: BLE001 搜索失败不致命 → 不插图
        logger.warning("讲义配图搜索失败，跳过配图：%s", exc)
        return None
    for h in hits or []:
        url = str((h or {}).get("url") or "").strip()
        # 防幻觉二次校验：仅接受真实 http(s) URL（链接来自 Provider，非 LLM 编造）
        if url.startswith("http://") or url.startswith("https://"):
            return {"url": url, "source": _domain(url), "description": (h or {}).get("description")}
    return None


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _insert_after_section(markdown: str, heading_re: re.Pattern[str], block: str) -> tuple[str, bool]:
    """把 block 插到 heading_re 命中小节的末尾（下一个标题前）。未命中 → 原样 + False。"""
    lines = markdown.split("\n")
    start = next((i for i, ln in enumerate(lines) if heading_re.match(ln)), None)
    if start is None:
        return markdown, False
    end = next((j for j in range(start + 1, len(lines)) if _HEADING_RE.match(lines[j])), len(lines))
    new_lines = lines[:end] + ["", block, ""] + lines[end:]
    return "\n".join(new_lines), True


def _placeholder_data_uri(kp_name: str) -> str:
    """确定性内联 SVG 占位图（base64 data URI，自包含、离线、无网络）。"""
    label = _xml_escape((kp_name or "知识点").strip()[:16])
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='720' height='360' viewBox='0 0 720 360'>"
        "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0' stop-color='#eff6ff'/><stop offset='1' stop-color='#dbeafe'/>"
        "</linearGradient></defs>"
        "<rect width='720' height='360' rx='18' fill='url(#g)'/>"
        "<rect x='12' y='12' width='696' height='336' rx='14' fill='none' "
        "stroke='#93c5fd' stroke-width='2' stroke-dasharray='8 6'/>"
        "<circle cx='360' cy='150' r='46' fill='none' stroke='#2563eb' stroke-width='4'/>"
        "<path d='M338 150 h44 M360 128 v44' stroke='#2563eb' stroke-width='4' stroke-linecap='round'/>"
        f"<text x='360' y='250' text-anchor='middle' font-family='sans-serif' "
        f"font-size='30' font-weight='700' fill='#1e3a8a'>{label}</text>"
        "<text x='360' y='292' text-anchor='middle' font-family='sans-serif' "
        "font-size='18' fill='#3b82f6'>示意图 · 占位</text>"
        "</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def _domain(url: str) -> str:
    """从 URL 提取来源域名（展示用）。"""
    u = (url or "").split("//", 1)[-1]
    return u.split("/", 1)[0] or "web"


def _md_escape(text: str) -> str:
    """转义 Markdown 图片 alt 文本里会破坏语法的字符。"""
    return str(text or "").replace("]", "）").replace("[", "（").replace("\n", " ").strip()


def _xml_escape(text: str) -> str:
    """转义内联 SVG 文本中的 XML 特殊字符。"""
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
