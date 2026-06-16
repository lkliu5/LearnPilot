"""对话式学情诊断 Agent（接口文档 17.1，C1-b）。

职责（赛题功能 1）：通过自然语言多轮对话自动抽取学生特征，逐步构建 ≥6 维
异质学生动态画像（StudentPortrait，17.2）。与第 8 章苏格拉底辅导（8.7/15.4）
一脉相承——抽取经 LLMClient（mock/deepseek 双模式），**追问编排策略在 Agent
侧确定性实现**（开放提问 → 逐维定位 → 收敛），不依赖 LLM 以免追问跑题。

防幻觉（17.1）：维度抽取的契约清洗（key 白名单、source 枚举、inferred 低
confidence、无信号不编造）在 LLMClient.extract_portrait 内完成，本 Agent 只
负责「问什么」与「何时收尾」。
"""
from __future__ import annotations

from typing import Any

from app.core.llm import PORTRAIT_DIMENSIONS, get_llm

AGENT_ID = "dialogue"
AGENT_NAME = "对话式学情诊断Agent"

# 探查顺序 = PORTRAIT_DIMENSIONS 顺序；每维一句开放/针对性追问 + 快捷回复建议。
_QUESTIONS: dict[str, str] = {
    "knowledge_base": "先了解一下你的基础——相关课程你学过哪些，掌握到什么程度？",
    "prior_experience": "你做过哪些相关的项目或实践？可以聊聊具体做了什么。",
    "learning_goal": "这次学习你最想达成的目标是什么？",
    "cognitive_style": "你更习惯先动手实践、还是先把原理和推导弄清楚？",
    "learning_pace": "你计划投入的学习节奏是怎样的，时间紧不紧？",
    "error_preference": "回想以往学习，你最容易卡在哪类问题上——概念、计算推导、还是代码实现？",
}
_SUGGESTIONS: dict[str, list[str]] = {
    "knowledge_base": ["系统学过，基础扎实", "学过一些，理解一般", "基本零基础"],
    "prior_experience": ["做过相关项目", "只在课程里练过", "还没有实践"],
    "learning_goal": ["转岗/求职", "考试/认证", "兴趣自学"],
    "cognitive_style": ["喜欢先动手实践", "喜欢先弄懂原理", "两者都要"],
    "learning_pace": ["时间充裕，稳扎稳打", "节奏适中", "时间紧，想快速突破"],
    "error_preference": ["概念容易混淆", "计算/推导易错", "代码实现卡壳"],
}

_PROBE_ORDER: list[str] = [k for k, _ in PORTRAIT_DIMENSIONS]
# 收敛阈值：采集到 ≥6 维（赛题「≥6 维异质画像」口径，与前端「满 6 维」门控一致）。
# 维度计数含 inferred 推断维度（error_preference 多为 inferred）——既满足 ≥6 维，
# 又借「探查顺序耗尽（focus 为 None）」兜底，避免某维难采集时诊断永不收敛（17.1）。
_COMPLETE_THRESHOLD: int = len(_PROBE_ORDER)

_CLOSING_REPLY = (
    "画像维度已基本采集完整，我已据此生成你的动态学习画像，"
    "接下来就可以进入个性化学习路径了。"
)


def _next_focus(filled: set[str], asked: set[str]) -> str | None:
    """选下一个要追问的维度。

    优先按探查顺序取「既未采集、又未问过」的维度（推进对话、不重复追问）；若所有
    维度都已问过但仍有缺口，回头重问首个「未采集」维度——保证向 ≥6 维收敛，不因某
    维已问过即放弃采集（真实模式下 LLM 偶把某维归到别处，需再问一次才补齐）；全部
    维度均已采集 → None（此时调用方已按 ≥阈值判定收尾）。
    """
    for key in _PROBE_ORDER:
        if key not in filled and key not in asked:
            return key
    for key in _PROBE_ORDER:  # 均已问过仍有缺口 → 重问首个未采集维度，驱动 ≥6 维收敛
        if key not in filled:
            return key
    return None


def _compose_reply(updates: list[dict[str, Any]], focus: str, first_turn: bool) -> str:
    """组装回复：对本轮抽取的简短确认 + 针对下一维度的追问。"""
    if updates:
        ack = "了解了。"
    elif first_turn:
        ack = "好的，我们开始吧。"
    else:
        ack = "好的。"
    return f"{ack}{_QUESTIONS[focus]}"


def respond(
    *,
    context: dict[str, Any] | None,
    history: list[dict[str, str]],
    message: str,
    known_keys: list[str],
    asked_keys: list[str],
    first_turn: bool,
) -> dict[str, Any]:
    """执行一轮对话诊断。

    Args:
        context: 首轮可带的已知信息（major/goal），非首轮忽略。
        history: 既往多轮 [{role, content}]（真实模式透传给抽取，可用于消歧）。
        message: 学生本轮自然语言输入。
        known_keys: 本轮之前画像已有的维度 key（采集进度）。
        asked_keys: 既往各轮已追问过的维度 key（推进进度，避免重复追问）。
        first_turn: 是否首轮（决定是否吸收 context、开场白措辞）。

    Returns:
        {reply, updates, suggestions, diagnosisComplete, focus}——updates 已经过
        LLMClient 契约清洗；focus 为本轮追问的维度 key（None 表示收尾，供调用方
        记入 asked）；diagnosisComplete 由 Agent 按采集/推进进度确定性判定。
    """
    updates = get_llm().extract_portrait(
        message=message, context=context if first_turn else None, first_turn=first_turn
    )
    # 采集进度 = 本轮前已有维度 ∪ 本轮新抽取维度
    filled = set(known_keys) | {u["key"] for u in updates}
    # 收尾判定：画像维度数 ≥ 阈值（≥6，含 inferred 计数）才完成——与赛题「≥6 维异质
    # 画像」及前端「满 6 维」门控严格一致；未达 6 维则继续追问缺口维度，**不因 focus
    # 耗尽（某维已问过但未采集）提前收尾**，避免「满 5 维即收敛」的口径漂移。
    done = len(filled) >= _COMPLETE_THRESHOLD
    focus = None if done else _next_focus(filled, set(asked_keys))
    if done:
        reply, suggestions = _CLOSING_REPLY, []
    else:
        reply = _compose_reply(updates, focus, first_turn)
        suggestions = list(_SUGGESTIONS[focus])
    return {
        "reply": reply,
        "updates": updates,
        "suggestions": suggestions,
        "diagnosisComplete": done,
        "focus": focus,
    }
