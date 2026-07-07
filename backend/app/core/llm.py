"""LLM 调用适配层（B2-a 落地 mock；B5-b 接入 deepseek 真实 provider）。

CLAUDE.md 工程纪律：所有生成类接口必须经本层调用，provider 可配
`mock / deepseek / qwen / anthropic`。
- **mock**：按接口契约返回确定性结构化假数据，无任何 API Key 即可跑通全链路
  （前端演示兜底，B5-b 后行为仍与 B2 逐字等价）；
- **deepseek**（B5-b）：经 app.core.llm_deepseek.chat（openai 兼容 SDK）真实生成，
  结构化输出做契约清洗（枚举校验 / level 截断 / sourceId 白名单 / JSON 容错解析），
  上游异常统一 LLMGenerationError → 路由映射 code 2001；
- qwen / anthropic：仍留占位，抛 NotImplementedError。

设计：
- 语义化方法（extract_profile / generate_narrative）而非裸 `complete()`，因为各生成
  接口需返回与接口文档逐字对齐的结构化数据；
- `complete()` 供 Agent 节点调用（B5-a 工作流）；真实模式只发渲染后 prompt；
- `get_llm()` 返回进程内单例，按 settings.llm_provider 选择实现。

字段口径依据《后端接口文档》4.1（ParsedProfile.skills / 枚举）、4.2（Narrative）、
2.4（雷达 6 维固定键名）、15.3（幻觉率口径，critic 真实实现在 agents.critic_agent）。
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterator
from typing import Any

from app.core import llm_transport
from app.core.config import settings
from app.core.llm_deepseek import LLMGenerationError  # 路由层从本模块导入（re-export）

logger = logging.getLogger("app.core.llm")

__all__ = [
    "LLMClient",
    "LLMGenerationError",
    "audit_practice",
    "get_llm",
    "set_force_critic_low",
]

# 雷达 / 画像 6 维固定键名（接口文档 2.4，画像与岗位共用以便对标）
ABILITY_DIMENSIONS: list[str] = [
    "机器学习基础",
    "神经网络",
    "深度学习",
    "注意力机制",
    "Transformer",
    "大模型微调",
]

# mock 基线能力值（接口文档 4.1/4.4 示例：85/72/68/45/30/20）
_MOCK_BASELINE: list[int] = [85, 72, 68, 45, 30, 20]

# 讲义资源页难度档：入门|初级|中级|高级|精通（五档，与文档学习/路径难度档对齐）。
# 每档对应 lecture_content 的一个递进 depth（0–4），中级/精通与相邻档产出深度可区分。
LECTURE_DIFFICULTIES: list[str] = ["入门", "初级", "中级", "高级", "精通"]

# 学习路径难度阶梯（接口文档 2.3 Lesson.difficulty）：规划 Agent 按画像基础上下浮动
PATH_DIFFICULTIES: list[str] = ["入门", "初级", "中级", "高级", "精通"]

# 异质学生画像维度（接口文档 17.2，C1-b）：(key, 中文 label)，顺序即对话探查顺序。
# 与 4.4 固定 6 知识点雷达「并存、互不替换」（key 稳定，后端可扩展更多维度）。
PORTRAIT_DIMENSIONS: list[tuple[str, str]] = [
    ("knowledge_base", "知识基础"),
    ("prior_experience", "先验经验"),
    ("learning_goal", "学习目标"),
    ("cognitive_style", "认知风格"),
    ("learning_pace", "学习节奏"),
    ("error_preference", "易错点偏好"),
]
_PORTRAIT_LABELS: dict[str, str] = dict(PORTRAIT_DIMENSIONS)
_PORTRAIT_KEYS: tuple[str, ...] = tuple(k for k, _ in PORTRAIT_DIMENSIONS)
# source 枚举（17.1 防幻觉约束）：dialogue 明确陈述 / manual 显式填写 / inferred 间接推断
# diagnostic 诊断微测「测」出（行为反推，非自陈）——能力维度专用，带依据 basis。
_PORTRAIT_SOURCES: tuple[str, ...] = ("dialogue", "manual", "inferred", "diagnostic")
# inferred（推断）维度 confidence 上限（17.1：inferred 须给较低 confidence）
_INFERRED_CONFIDENCE_CAP: float = 0.6

# ── 画像三分类（C2 重构：能力靠测、偏好归类型、主观靠对话） ──────────────────
# 把 17.2 六维严格分为三类，各用各的测法，杜绝「把能力与偏好混进同一 0-100 轴」：
#   ability    能力维：可打分(0-100)，由「诊断微测」行为反推，带依据 basis，不靠自陈；
#   preference 偏好维：只有类型、无高低，由「偏好选择题」归类，禁止打分/上 0-100 轴；
#   subjective 主观维：描述性，对话自然采集，不强行打分。
PORTRAIT_DIM_KINDS: dict[str, str] = {
    "knowledge_base": "ability",
    "prior_experience": "subjective",
    "learning_goal": "subjective",
    "cognitive_style": "preference",
    "learning_pace": "preference",
    "error_preference": "preference",
}
ABILITY_DIM_KEYS: tuple[str, ...] = tuple(
    k for k, v in PORTRAIT_DIM_KINDS.items() if v == "ability"
)
PREFERENCE_DIM_KEYS: tuple[str, ...] = tuple(
    k for k, v in PORTRAIT_DIM_KINDS.items() if v == "preference"
)
SUBJECTIVE_DIM_KEYS: tuple[str, ...] = tuple(
    k for k, v in PORTRAIT_DIM_KINDS.items() if v == "subjective"
)
_PORTRAIT_KINDS: tuple[str, ...] = ("ability", "preference", "subjective")

# 偏好选择题选项库（17.5）：每个偏好维一组「二/三选一」，选项只归类型不打分。
# 结构：dim_key -> {prompt, options:[{optionKey, label, hint}]}；optionKey 为稳定类型码。
PREFERENCE_QUESTIONS: dict[str, dict[str, Any]] = {
    "cognitive_style": {
        "prompt": "遇到一个全新的概念，你更想先看到哪一种？",
        "options": [
            {"optionKey": "visual", "label": "图像型", "hint": "先看一张示意图/结构图"},
            {"optionKey": "textual", "label": "文字型", "hint": "先读一段准确的定义"},
            {"optionKey": "example", "label": "案例型", "hint": "先看一个具体的例子"},
        ],
    },
    "learning_pace": {
        "prompt": "拿到一章新内容，你更倾向怎么推进？",
        "options": [
            {"optionKey": "overview", "label": "快速概览型", "hint": "先快速过一遍全局，再回头补细节"},
            {"optionKey": "deepdive", "label": "稳步细钻型", "hint": "从头逐点稳稳钻透再往下"},
        ],
    },
    "error_preference": {
        "prompt": "回想以往做错的题，最常见的原因是哪一类？",
        "options": [
            {"optionKey": "concept", "label": "概念混淆", "hint": "概念记混 / 理解有偏差"},
            {"optionKey": "calculation", "label": "计算粗心", "hint": "看错条件 / 算错一步"},
            {"optionKey": "coding", "label": "代码卡壳", "hint": "思路对但实现 / 代码写不对"},
        ],
    },
}
# optionKey -> 类型中文标签（偏好维 value 取此，呈现为类型标签而非分数）
_PREFERENCE_LABELS: dict[str, dict[str, str]] = {
    dim: {o["optionKey"]: o["label"] for o in q["options"]}
    for dim, q in PREFERENCE_QUESTIONS.items()
}

# mock 讲义的 RAG 来源（接口文档 8.2 sources；type∈教材|论文|文档|课程，confidence 0-1）。
# B5 接入真实 RAG 后由检索命中切片回填，此处为确定性占位。
_LECTURE_SOURCES: list[dict[str, Any]] = [
    {"title": "《深度学习》(花书) 相关章节", "type": "教材", "confidence": 0.92},
    {"title": "Stanford CS231n / CS224n 公开课讲义", "type": "课程", "confidence": 0.88},
    {"title": "领域权威综述与官方技术文档", "type": "文档", "confidence": 0.83},
]

# mock 幻觉率（接口文档 8.2 示例 0.021，前端显示「<5%」）。
# B5 替换为 15.3 逐句接地校验口径（未接地句数/总句数）；mock 阶段确定性返回。
_LECTURE_HALLUCINATION_RATE: float = 0.021

# 神经网络分镜脚本（接口文档 8.3 scenes）：与前端 LectureVideo 原 5 场景逐字对齐，
# narration 与原 NARRATION 一致——保证 nn 视频不回归；其余知识点按相同结构参数化生成。
_VIDEO_SCRIPT_NN: list[dict[str, Any]] = [
    {
        "title": "课程导入 · 神经网络基础",
        "points": ["三步运算：求和 → 偏置 → 激活", "前向传播与反向传播", "由领域知识生成智能体定制"],
        "narration": "欢迎学习神经网络基础。本视频由领域知识生成智能体为你定制。",
    },
    {
        "title": "神经元的三步运算",
        "points": ["① 加权求和 Σ wᵢ·xᵢ", "② 加上偏置 + b", "③ 激活函数 ReLU(z)"],
        "narration": "一个神经元完成三步运算：加权求和、加上偏置、再经过激活函数输出。",
    },
    {
        "title": "前向传播",
        "points": ["输入与权重相乘求和", "加偏置得到 z", "ReLU 激活得到输出 a"],
        "narration": "前向传播时，输入与权重相乘求和，加偏置得到 z，再用 ReLU 激活得到输出。",
    },
    {
        "title": "常见激活函数",
        "points": ["ReLU：max(0,x)，最常用", "Sigmoid：压缩到 (0,1)", "Tanh：范围 (-1,1)，零均值"],
        "narration": "常见激活函数有 ReLU、Sigmoid 和 Tanh，其中 ReLU 计算快、最常用。",
    },
    {
        "title": "学习闭环",
        "points": ["神经元 → 前向传播", "激活 → 反向传播更新", "完成测验巩固理解"],
        "narration": "神经元、前向传播、激活、反向传播更新，构成了神经网络学习的完整闭环。",
    },
]

# 关键词 → 维度索引，用于在 mock 中「读到」材料文本时小幅抬升对应维度，
# 体现解析的可解释性；未命中则用基线值（不编造、不随机）。
# 接口文档 4.1 枚举（真实抽取的契约清洗白名单；非法值回落「其他」）
_EDUCATION_ENUM = ("本科", "硕士", "博士", "其他")
_MAJOR_ENUM = ("计算机科学", "电子信息", "人工智能", "软件工程", "数据科学", "其他")
_GOAL_ENUM = ("职业培训", "技能认证", "学术研究", "兴趣学习", "其他")

# 容错 JSON 提取：取首个 { 到末个 } 的最大块（模型常在 JSON 外包裹说明文字）
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.S)

# ---- 苏格拉底辅导（接口文档 8.7 / 15.4，B7-a） ---------------------------------

# deepseek 真实模式 system prompt：核心约束「引导式提问、不直接给答案」
_TUTOR_SYSTEM = (
    "你是「{kp_name}」的苏格拉底式导学助手。规则：只用引导式提问启发学习者自己想通，"
    "绝对不直接给出最终答案或完整结论；每次回复聚焦一个思考点并以一个问题收尾；"
    "学习者答对时先简短肯定再追问下一层；简体中文，单次回复不超过 120 字。"
)

# mock 确定性引导链：关键词分支 →（引导回复, 快捷建议）。
# 首条分支对齐接口文档 8.7 示例（激活函数之问 → 引导反问 + 三个 suggestions）；
# 链路覆盖前端 SocraticTutor 演示的「加权求和→偏置→非线性→ReLU→反向传播」闭环。
_TUTOR_BRANCHES: list[tuple[re.Pattern[str], str, list[str]]] = [
    (
        re.compile(r"激活函数|激活"),
        "好问题。先想一想：如果没有激活函数，多层网络叠加后等价于什么？",
        ["等价于线性变换", "可以拟合任意函数", "不确定"],
    ),
    (
        re.compile(r"线性|等价"),
        "对——叠加后仍是一个线性变换，这正是需要非线性的原因。那么哪个激活函数计算最快、还能缓解梯度消失？",
        ["ReLU", "Sigmoid", "Tanh"],
    ),
    (
        re.compile(r"relu", re.I),
        "正是 ReLU。它在正区间导数恒为 1——想一想：这对反向传播中的梯度意味着什么？",
        ["梯度不会被反复压缩", "梯度会消失", "不确定"],
    ),
    (
        re.compile(r"梯度|反向|backprop|损失|下降", re.I),
        "很好，你已经把前向与反向串起来了。试着用一句话说说：网络是如何利用梯度来更新权重的？",
        ["沿梯度下降方向更新", "随机调整权重", "不确定"],
    ),
    (
        re.compile(r"偏置|bias|\bb\b", re.I),
        "没错，是偏置 b。那么加权求和加偏置得到 z 之后，为什么不能直接把 z 当输出？",
        ["因为要引入非线性", "因为 z 太大", "不确定"],
    ),
    (
        re.compile(r"加权|求和|相乘|权重|乘"),
        "不错的起点。加权求和之后，为了让决策边界可以平移，还要加上一个量——它叫什么？",
        ["偏置 b", "学习率", "损失函数"],
    ),
]
_TUTOR_FALLBACK: tuple[str, list[str]] = (
    "别急，换个角度想想：神经元的本质是把多个输入「汇总」成一个值，这个汇总最直接的数学操作是什么？",
    ["加权求和", "取最大值", "不确定"],
)


def _mock_tutor_reply(message: str) -> tuple[str, list[str]]:
    """确定性引导链：命中关键词分支返回对应引导问句，否则兜底引导。"""
    for pattern, reply, suggestions in _TUTOR_BRANCHES:
        if pattern.search(message or ""):
            return reply, list(suggestions)
    return _TUTOR_FALLBACK[0], list(_TUTOR_FALLBACK[1])


# ---- 智能辅导·按需资源生成（接口文档 8.8，C-fix 批3-bonus） --------------------
# 学生提问/「我没懂」→ 识别问题点 → 给出针对性资源生成清单 → 勾选按需生成。
# 资源类型与现有生成能力一一对应：diagram(8.5) / video(8.3) / example(LLM) / lecture(8.2 片段)。
REMEDIAL_TYPES: tuple[str, ...] = ("diagram", "example", "video", "lecture")

# 问题点识别关键词 → 规范问题点短语（mock；deepseek 走真实识别）。
_REMEDIAL_KEYWORDS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"激活|relu|sigmoid|tanh|非线性", re.I), "激活函数与非线性"),
    (re.compile(r"反向|梯度|backprop|链式|求导"), "反向传播与梯度"),
    (re.compile(r"加权|求和|权重|偏置|bias", re.I), "神经元加权求和与偏置"),
    (re.compile(r"卷积|池化|感受野|卷积核"), "卷积与池化"),
    (re.compile(r"注意力|attention|qkv|q/k/v|多头", re.I), "自注意力机制"),
    (re.compile(r"位置编码|position", re.I), "位置编码"),
    (re.compile(r"过拟合|正则|泛化"), "过拟合与正则化"),
    (re.compile(r"优化器|sgd|adam|学习率", re.I), "优化器与学习率"),
    (re.compile(r"lora|微调|peft|对齐|rlhf|dpo", re.I), "大模型微调与对齐"),
]

# type → (标题模板, 预计内容模板)，{point} 占位问题点
_REMEDIAL_TYPE_META: dict[str, tuple[str, str]] = {
    "diagram": ("知识图解：{point}", "用流程图直观呈现「{point}」的关键步骤与依赖关系"),
    "example": ("例题精讲：{point}", "一道围绕「{point}」的例题 + 分步解析"),
    "video": ("短视频讲解：{point}", "3-5 个分镜的动画讲解，配旁白逐步拆解「{point}」"),
    "lecture": ("补充讲义片段：{point}", "针对「{point}」的精炼讲义片段，含要点与小结"),
}


def _mock_identify_problem(question: str, kp_name: str) -> str:
    """从学生提问识别问题点（mock 关键词匹配，未命中回落知识点核心概念）。"""
    for pattern, point in _REMEDIAL_KEYWORDS:
        if pattern.search(question or ""):
            return point
    return f"{kp_name}的核心概念"


def _build_remedial_suggestions(point: str) -> list[dict[str, Any]]:
    """据问题点构建针对性资源生成清单（4 项，对应现有生成能力）。"""
    return [
        {
            "id": f"r-{t}",
            "type": t,
            "title": _REMEDIAL_TYPE_META[t][0].format(point=point),
            "expect": _REMEDIAL_TYPE_META[t][1].format(point=point),
        }
        for t in REMEDIAL_TYPES
    ]


# ---- 外部资源·联网搜索聚合（接口文档 8.6 增量，C-fix 批3-bonus） ----------------
_AGG_TYPES: tuple[str, ...] = ("视频", "论文", "文档", "课程")
# 来源可信度启发式（critic 评分兜底口径）：命中关键词 → 基础可信分
_CREDIBILITY_HINTS: list[tuple[tuple[str, ...], int]] = [
    (("arxiv", "nature", "acm", "ieee", "openreview"), 97),
    (("stanford", "cs231n", "cs224n", ".edu", "mit", "deeplearningbook", "harvard"), 95),
    (("pytorch", "tensorflow", "huggingface", "developers.google", "scikit-learn"), 93),
    (("coursera", "3blue1brown", "bilibili", "youtube", "jalammar"), 90),
]


def _credibility_of(source: str, url: str) -> int:
    """据来源域名/URL 估可信度（mock critic 评分兜底）。"""
    s = f"{source} {url}".lower()
    for keys, score in _CREDIBILITY_HINTS:
        if any(k in s for k in keys):
            return score
    return 82


def _clamp_score(value: Any, default: int = 0) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


# ---- 对话式画像诊断（接口文档 17.1 / 17.2，C1-b） ------------------------------


def _sanitize_portrait_updates(updates: Any) -> list[dict[str, Any]]:
    """画像维度增量契约清洗（17.1/17.2 防幻觉约束，mock 与 deepseek 共用）。

    - key 必须取自固定维度集（PORTRAIT_DIMENSIONS），未知 key 丢弃（不编造维度）；
    - label 回正为该 key 的中文名；value 必须非空字符串；
    - score（可选）截断 0-100 整数；confidence 截断 0-1；
    - source ∈ dialogue|manual|inferred（非法回落 inferred）；
    - inferred（推断）维度 confidence 上限 0.6（17.1：推断须给较低 confidence）；
    - 同 key 去重（后者覆盖，保持稳定顺序）。
    """
    if not isinstance(updates, list):
        return []
    by_key: dict[str, dict[str, Any]] = {}
    for item in updates:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if key not in _PORTRAIT_KEYS:
            continue  # 防幻觉：不接受固定维度集之外的 key
        value = str(item.get("value") or "").strip()
        if not value:
            continue
        source = item.get("source")
        if source not in _PORTRAIT_SOURCES:
            source = "inferred"
        try:
            confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        if source == "inferred":
            confidence = min(confidence, _INFERRED_CONFIDENCE_CAP)
        kind = PORTRAIT_DIM_KINDS.get(key, "subjective")
        cleaned: dict[str, Any] = {
            "key": key,
            "label": _PORTRAIT_LABELS[key],
            "kind": kind,
            "value": value,
            "confidence": round(confidence, 2),
            "source": source,
        }
        # score 仅能力维有意义（偏好/主观维严禁打分、不上 0-100 轴）；非能力维一律剥离 score
        score = item.get("score")
        if kind == "ability" and isinstance(score, (int, float)) and not isinstance(score, bool):
            cleaned["score"] = max(0, min(100, int(score)))
        basis = item.get("basis")  # 能力维「依据」：分数来自哪几道题/哪些作答（可解释、防臆造）
        if isinstance(basis, str) and basis.strip():
            cleaned["basis"] = basis.strip()
        # 偏好维类型码：归类到 PREFERENCE_QUESTIONS 的某个 optionKey（只记类型、不打分）
        option_key = item.get("optionKey")
        if kind == "preference" and isinstance(option_key, str) and option_key.strip():
            cleaned["optionKey"] = option_key.strip()
        by_key[key] = cleaned
    return list(by_key.values())


# 关键词 → 画像维度的确定性抽取规则（mock 模式；deepseek 走真实抽取）。
# 仅在文本出现明确信号时产出维度，无信号不编造（17.1 防幻觉）。
def _mock_extract_portrait(
    message: str, context: dict[str, Any] | None, first_turn: bool
) -> list[dict[str, Any]]:
    """确定性画像抽取（mock）：命中关键词产出维度增量，无信号则不产出。"""
    text = message or ""
    low = text.lower()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(key: str, value: str, confidence: float, source: str, score: int | None = None) -> None:
        if key in seen:
            return
        seen.add(key)
        item: dict[str, Any] = {"key": key, "value": value, "confidence": confidence, "source": source}
        if score is not None:
            item["score"] = score
        out.append(item)

    # 先验经验
    if "爬虫" in text:
        add("prior_experience", "有Python工程实践(爬虫)", 0.8, "dialogue")
    elif "python" in low and any(k in text for k in ("做过", "项目", "开发", "工程", "实践")):
        add("prior_experience", "有Python工程实践经验", 0.8, "dialogue")
    elif any(k in text for k in ("项目", "实践", "做过", "工作", "经验", "开发", "实习")):
        add("prior_experience", "有相关项目/工程实践经验", 0.75, "dialogue")
    # 知识基础（含可量化 score）
    if any(k in text for k in ("精通", "扎实", "很熟", "熟练")):
        add("knowledge_base", "扎实", 0.7, "dialogue", score=85)
    elif any(k in text for k in ("零基础", "没学过", "不会", "没接触", "薄弱", "刚入门", "不熟")):
        add("knowledge_base", "薄弱", 0.7, "dialogue", score=30)
    elif any(k in text for k in ("本科", "硕士", "博士", "学过", "了解", "科班", "计算机")):
        add("knowledge_base", "一般", 0.7, "dialogue", score=65)
    # 学习目标
    if any(k in text for k in ("转", "求职", "找工作", "岗位", "工程师", "职业", "入职", "面试")):
        if "大模型" in text:
            add("learning_goal", "转大模型应用方向", 0.9, "dialogue")
        else:
            add("learning_goal", "职业转型/求职", 0.9, "dialogue")
    elif any(k in text for k in ("考试", "认证", "考研", "考证")):
        add("learning_goal", "考试/认证", 0.85, "dialogue")
    elif "兴趣" in text:
        add("learning_goal", "兴趣学习", 0.8, "dialogue")
    # 认知风格
    if any(k in text for k in ("动手", "实践", "代码", "做项目", "上手")) or "爬虫" in text:
        add("cognitive_style", "偏实践/动手型", 0.6, "dialogue")
    elif any(k in text for k in ("理论", "原理", "推导", "数学", "公式", "证明")):
        add("cognitive_style", "偏理论/推导型", 0.6, "dialogue")
    # 学习节奏
    if any(k in text for k in ("时间紧", "快速", "突破", "尽快", "赶")):
        add("learning_pace", "偏快(集中突破)", 0.6, "dialogue")
    elif any(k in text for k in ("充裕", "稳", "扎实", "慢慢", "系统")):
        add("learning_pace", "稳扎稳打", 0.6, "dialogue")
    elif "适中" in text:
        add("learning_pace", "适中", 0.6, "dialogue")
    # 易错点偏好（多为推断，低 confidence）
    if any(k in text for k in ("概念", "混淆", "记不住")):
        add("error_preference", "概念易混淆", 0.5, "inferred")
    elif any(k in text for k in ("推导", "公式", "计算题")):  # 避开「计算机」误命中
        add("error_preference", "计算/推导易错", 0.5, "inferred")
    elif any(k in text for k in ("代码", "实现", "编程", "调试", "报错")):
        add("error_preference", "代码实现易卡壳", 0.5, "inferred")

    # 首轮已知上下文（表单显式填写 → source=manual）：仅补对话未覆盖的维度
    if first_turn and context:
        goal = str(context.get("goal") or "").strip()
        if goal:
            add("learning_goal", goal, 0.9, "manual")
        major = str(context.get("major") or "").strip()
        if major:
            add("knowledge_base", f"{major}专业背景", 0.6, "manual", score=65)

    return _sanitize_portrait_updates(out)


def _extract_json(text: str) -> Any | None:
    """从模型自由文本中提取 JSON 对象；解析失败返回 None（调用方兜底）。"""
    for candidate in (text, *_JSON_BLOCK_RE.findall(text or "")):
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _strip_md_fence(text: str) -> str:
    """剥离模型偶发的 ```markdown 围栏包裹，保留正文。"""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if len(lines) >= 2 and lines[-1].strip() == "```":
            t = "\n".join(lines[1:-1]).strip()
    return t


# 前端 mermaid v11 支持的图型白名单（图解丰富化：按内容选流程图/层次图/关系图/思维导图等）。
_MERMAID_HEADS: tuple[str, ...] = (
    "flowchart", "graph", "mindmap", "classdiagram", "sequencediagram",
    "statediagram", "erdiagram", "journey", "timeline", "quadrantchart",
    "gitgraph", "requirementdiagram",
)


def _clean_mermaid(raw: str) -> str:
    """Mermaid 知识图解契约清洗（接口文档 8.5）：剥围栏、校验首行为受支持图型。

    放宽到 _MERMAID_HEADS（流程图/层次图/关系图/思维导图等），让真实生成可按内容选用
    更贴切的图型；仍拒绝非图解文本。非法输出 → 抛 LLMGenerationError，由调用方回落
    确定性主题模板，保证图解始终可渲染（演示兜底，不向路由抛错）。
    """
    text = _strip_md_fence(raw or "").strip()
    if not text:
        raise LLMGenerationError("知识图解输出为空")
    head = text.splitlines()[0].strip().lower()
    if not any(head.startswith(h) for h in _MERMAID_HEADS):
        raise LLMGenerationError("知识图解输出非合法 Mermaid 图（首行图型不受支持）")
    return text


# Mermaid 知识图解模板（接口文档 8.5；mock 与 deepseek 兜底共用）。
# 图解丰富化：不同知识点选用贴合其内容结构的不同图型——
#   nn/ml/dl 训练回路用横向流程图（flowchart LR，含反馈边）；
#   cnn 层级管线用纵向流程图（flowchart TD）；
#   transformer 用带 subgraph 的编码器块结构图；
#   finetune 谱系用思维导图（mindmap）。
# 约束：nn/cnn/dl/ml 首行恒为 flowchart（契约测试 test_b7a / test_contract_snapshot 钉死）。
_DIAGRAM_TEMPLATES: dict[str, str] = {
    "nn": (
        # 论文级标准示意：多层感知机（输入层→隐藏层→输出层，全连接）+ 前向流 + 反向传播回路。
        "flowchart LR\n"
        '  subgraph IN["输入层 x"]\n'
        "    direction TB\n"
        '    I1(("x₁"))\n'
        '    I2(("x₂"))\n'
        '    I3(("x₃"))\n'
        "  end\n"
        '  subgraph HID["隐藏层<br/>z=Σwᵢxᵢ+b, a=ReLU(z)"]\n'
        "    direction TB\n"
        '    H1(("h₁"))\n'
        '    H2(("h₂"))\n'
        '    H3(("h₃"))\n'
        '    H4(("h₄"))\n'
        "  end\n"
        '  subgraph OUT["输出层 ŷ"]\n'
        "    direction TB\n"
        '    O1(("ŷ₁"))\n'
        '    O2(("ŷ₂"))\n'
        "  end\n"
        "  I1 --> H1 & H2 & H3 & H4\n"
        "  I2 --> H1 & H2 & H3 & H4\n"
        "  I3 --> H1 & H2 & H3 & H4\n"
        "  H1 --> O1 & O2\n"
        "  H2 --> O1 & O2\n"
        "  H3 --> O1 & O2\n"
        "  H4 --> O1 & O2\n"
        '  L(["损失 L(ŷ,y)"])\n'
        "  OUT --> L\n"
        "  L -. 反向传播 ∂L/∂w 逐层回传更新权重 .-> HID\n"
        "  HID -. .-> IN\n"
    ),
    "ml": (
        "flowchart LR\n"
        '  D["数据集"] --> SP{{"划分<br/>训练/验证/测试"}}\n'
        '  SP --> F(["特征工程<br/>标准化"])\n'
        '  F --> M["模型 f_θ"]\n'
        '  M --> L(["损失 + λ正则"])\n'
        '  L --> O{{"优化器"}}\n'
        "  O -. 参数更新 .-> M\n"
        '  M --> E["验证集评估<br/>看泛化"]\n'
        "  E -. 调超参/正则 .-> SP\n"
    ),
    "dl": (
        "flowchart LR\n"
        '  X["输入"] --> FW(["前向传播"])\n'
        '  FW --> P["预测 ŷ"]\n'
        '  P --> L["损失 L"]\n'
        '  Y["标签 y"] --> L\n'
        '  L --> BP(["反向传播<br/>链式法则"])\n'
        '  BP --> G["梯度 ∂L/∂θ"]\n'
        '  G --> U{{"优化器更新<br/>θ ← θ − η·g"}}\n'
        '  N["归一化 / 残差<br/>稳住深层"] --> FW\n'
        "  U -. 迭代 .-> FW\n"
    ),
    "cnn": (
        "flowchart TD\n"
        '  I["输入图像<br/>H×W×3"] --> C1(["卷积层<br/>局部+权重共享"])\n'
        '  C1 --> A1{{"ReLU"}}\n'
        '  A1 --> P1(["池化<br/>降采样·扩感受野"])\n'
        '  P1 --> C2(["卷积 ×N<br/>浅层→深层语义"])\n'
        '  C2 --> FL["展平 Flatten"]\n'
        '  FL --> FC["全连接层"]\n'
        '  FC --> SM{{"Softmax"}}\n'
        '  SM --> O["分类输出"]\n'
    ),
    "transformer": (
        "flowchart TD\n"
        '  E["输入嵌入"] --> PE["+ 位置编码"]\n'
        "  PE --> ENC\n"
        '  subgraph ENC["编码器块 ×N"]\n'
        "    direction TB\n"
        '    MHA["多头自注意力<br/>softmax(QKᵀ/√dₖ)V"] --> AN1["Add & Norm"]\n'
        '    AN1 --> FFN["前馈网络 FFN"]\n'
        '    FFN --> AN2["Add & Norm"]\n'
        "  end\n"
        '  ENC --> O["输出表示"]\n'
    ),
    "finetune": (
        "mindmap\n"
        '  root(("大模型微调"))\n'
        "    全参微调\n"
        "      更新全部权重\n"
        "      效果上限高·最贵\n"
        "    LoRA\n"
        "      冻结原权重\n"
        "      低秩增量 BA\n"
        "      省显存·可热插拔\n"
        "    指令微调 SFT\n"
        "      指令-回答数据\n"
        "      教模型听话\n"
        "    对齐\n"
        "      RLHF\n"
        "      DPO\n"
        "      更合规无害\n"
    ),
    # —— GEN 生成式模型与扩散板块（重点亮点·多图示）：13 个知识点逐一精写论文级图解。
    # 键 = kp_id（knowledge_catalog GEN-1..GEN-13）；真实模式也**模板优先**（见
    # generate_diagram），保证板块图解质量确定性达标（教材/论文级标准结构，不抽卡）。
    "GEN-1": (  # 生成式模型概述：四大家族谱系
        "mindmap\n"
        '  root(("生成式模型谱系"))\n'
        "    显式密度\n"
        "      自回归 AR\n"
        "        逐 token 连乘概率\n"
        "        GPT 系列\n"
        "      VAE\n"
        "        变分下界 ELBO\n"
        "      Flow 流模型\n"
        "        可逆变换·精确似然\n"
        "    隐式密度\n"
        "      GAN\n"
        "        生成器-判别器博弈\n"
        "    迭代去噪\n"
        "      扩散模型\n"
        "        DDPM · Score SDE\n"
        "        当前图像生成主流\n"
    ),
    "GEN-2": (  # VAE：编码-重参数化-解码 + 双损失
        "flowchart LR\n"
        '  X["输入 x"] --> ENC(["编码器 qφ"])\n'
        '  ENC --> MU["均值 μ"]\n'
        '  ENC --> SG["方差 σ²"]\n'
        '  MU --> RP{{"重参数化<br/>z = μ + σ⊙ε, ε∼N(0,I)"}}\n'
        "  SG --> RP\n"
        '  RP --> Z(("潜变量 z"))\n'
        '  Z --> DEC(["解码器 pθ"])\n'
        '  DEC --> XH["重建 x̂"]\n'
        '  XH --> REC["重建损失 ‖x−x̂‖²"]\n'
        '  PRI["先验 N(0,I)"] -. KL 散度正则 拉近 qφ 与先验 .-> Z\n'
        "  REC -. 反向传播 联合优化 ELBO .-> ENC\n"
    ),
    "GEN-3": (  # GAN：对抗博弈回路
        "flowchart LR\n"
        '  N(("噪声 z∼N(0,I)")) --> G(["生成器 G"])\n'
        '  G --> FAKE["伪样本 G(z)"]\n'
        '  REAL["真实样本 x"] --> D{{"判别器 D<br/>输出真伪概率"}}\n'
        "  FAKE --> D\n"
        '  D --> LD["判别损失<br/>分对真假"]\n'
        '  D --> LG["生成损失<br/>骗过 D"]\n'
        "  LD -. 梯度更新 D .-> D\n"
        "  LG -. 梯度更新 G .-> G\n"
        '  LG --> EQ(["纳什均衡：G 产出以假乱真样本"])\n'
    ),
    "GEN-4": (  # DDPM：前向加噪链 + 反向去噪链
        "flowchart TD\n"
        '  subgraph FWD["前向扩散 q：逐步加高斯噪声（固定过程，无参数）"]\n'
        "    direction LR\n"
        '    X0["x₀ 清晰图像"] --> X1["x₁"] --> XM["……"] --> XT["x_T ≈ 纯噪声 N(0,I)"]\n'
        "  end\n"
        '  subgraph REV["反向去噪 pθ：网络逐步还原（学习目标）"]\n'
        "    direction LR\n"
        '    YT["x_T 采样噪声"] --> YM["……"] --> Y1["x₁"] --> Y0["x̂₀ 生成图像"]\n'
        "  end\n"
        "  XT -. 训练：εθ 预测每步所加噪声 .-> YT\n"
        '  Y0 -. 目标 L = E‖ε − εθ(xₜ,t)‖² .-> X0\n'
    ),
    "GEN-5": (  # 扩散的数学基础：核心公式推导链
        "flowchart TD\n"
        '  A["单步加噪<br/>q(xₜ|xₜ₋₁) = N(√(1−βₜ)·xₜ₋₁, βₜI)"] --> B["任意步闭式采样<br/>xₜ = √ᾱₜ·x₀ + √(1−ᾱₜ)·ε"]\n'
        '  B --> C["变分下界 ELBO<br/>分解为逐步 KL 项"]\n'
        '  C --> D["简化训练目标<br/>L_simple = E‖ε − εθ(xₜ,t)‖²"]\n'
        '  D --> E["反向采样均值<br/>由 xₜ 与 εθ 反解 xₜ₋₁"]\n'
        '  E -.-> F(["得分匹配视角<br/>εθ 等价于估计 ∇log p(xₜ)"])\n'
    ),
    "GEN-6": (  # U-Net 去噪网络：编码-瓶颈-解码 + 跳连
        "flowchart TD\n"
        '  X["含噪图 xₜ ⊕ 时间嵌入 t"] --> E1["下采样块 64×64"]\n'
        '  E1 --> E2["下采样块 32×32"]\n'
        '  E2 --> E3["下采样块 16×16"]\n'
        '  E3 --> MID{{"瓶颈层<br/>ResBlock + 自注意力"}}\n'
        '  MID --> D3["上采样块 16×16"]\n'
        '  D3 --> D2["上采样块 32×32"]\n'
        '  D2 --> D1["上采样块 64×64"]\n'
        '  D1 --> OUT["预测噪声 εθ(xₜ,t)"]\n'
        "  E3 -. 跳跃连接 拼接特征 .-> D3\n"
        "  E2 -. 跳跃连接 拼接特征 .-> D2\n"
        "  E1 -. 跳跃连接 拼接特征 .-> D1\n"
    ),
    "GEN-7": (  # 条件扩散与 CFG 引导：双路预测合成
        "flowchart TD\n"
        '  XT["当前状态 xₜ"] --> CP & UP\n'
        '  C["条件 c：文本 / 类别"] --> CP(["条件预测 εθ(xₜ,t,c)"])\n'
        '  NO["空条件 ∅（训练时随机丢弃条件）"] --> UP(["无条件预测 εθ(xₜ,t,∅)"])\n'
        '  CP --> MIX{{"CFG 合成<br/>ε̃ = εᵤ + w·(εc − εᵤ)"}}\n'
        "  UP --> MIX\n"
        '  MIX --> STEP["去噪一步 → xₜ₋₁"]\n'
        '  W["引导强度 w"] -. w 越大越贴合条件·多样性下降 .-> MIX\n'
    ),
    "GEN-8": (  # 潜在扩散 LDM：像素空间 ↔ 潜空间
        "flowchart LR\n"
        '  X["像素图像<br/>512×512×3"] --> ENC(["VAE 编码器 E"])\n'
        '  ENC --> Z["潜表示 z<br/>64×64×4（约 48× 压缩）"]\n'
        '  Z --> DIFF{{"扩散过程在潜空间进行<br/>U-Net + 交叉注意力"}}\n'
        '  COND["条件：文本 / 布局 / 图像"] -. 交叉注意力注入 .-> DIFF\n'
        '  DIFF --> ZH["去噪潜码 ẑ"]\n'
        '  ZH --> DEC(["VAE 解码器 D"])\n'
        '  DEC --> OUT["生成图像 x̂"]\n'
        "  Z -. 计算量大幅降低：高效训练与采样 .-> DIFF\n"
    ),
    "GEN-9": (  # Stable Diffusion 文生图 pipeline
        "flowchart TD\n"
        '  P["文本提示词 Prompt"] --> CLIP(["CLIP 文本编码器"])\n'
        '  CLIP --> EMB["文本嵌入序列"]\n'
        '  NZ["初始潜噪声 z_T"] --> UNET\n'
        '  subgraph LOOP["潜空间去噪循环 ×20∼50 步"]\n'
        "    direction TB\n"
        '    UNET["U-Net 预测噪声 + CFG 引导"] --> SCH{{"采样调度器<br/>DDIM / DPM-Solver"}}\n'
        "    SCH -. zₜ 迭代到 zₜ₋₁ .-> UNET\n"
        "  end\n"
        "  EMB -. 交叉注意力 注入每步 .-> UNET\n"
        '  SCH --> Z0["去噪潜码 z₀"]\n'
        '  Z0 --> VAE(["VAE 解码器"])\n'
        '  VAE --> IMG["输出图像 512×512"]\n'
    ),
    "GEN-10": (  # ControlNet：冻结主干 + 可训练副本 + 零卷积
        "flowchart TD\n"
        '  COND["控制条件图<br/>边缘 / 深度 / 姿态骨架"] --> TC\n'
        '  subgraph CN["ControlNet（可训练）"]\n'
        "    direction TB\n"
        '    TC["SD 编码器的可训练副本"] --> ZC["零卷积 zero-conv<br/>初始输出为 0"]\n'
        "  end\n"
        '  P["文本提示词"] --> SD\n'
        '  subgraph SD["Stable Diffusion U-Net（权重冻结）"]\n'
        "    direction TB\n"
        '    FE["冻结编码器块"] --> FD["冻结解码器块"]\n'
        "  end\n"
        "  ZC -. 控制残差 逐层相加 .-> FD\n"
        '  FD --> OUT["受控生成<br/>构图 / 姿态 / 结构可控"]\n'
        "  ZC -. 训练初期不干扰原模型 .-> SD\n"
    ),
    "GEN-11": (  # 扩散加速采样：三条提速路线
        "flowchart LR\n"
        '  SLOW["DDPM 原始采样<br/>1000 步马尔可夫链·分钟级"] --> WHY{{"瓶颈：步数多 = 生成慢"}}\n'
        '  WHY --> DDIM(["DDIM<br/>非马尔可夫·确定性跳步<br/>50 步"])\n'
        '  WHY --> DPM(["DPM-Solver<br/>概率流 ODE 高阶求解<br/>10∼20 步"])\n'
        '  WHY --> DIST(["蒸馏 / 一致性模型<br/>LCM · Turbo<br/>1∼4 步"])\n'
        '  DDIM --> Q["质量-速度权衡"]\n'
        "  DPM --> Q\n"
        "  DIST --> Q\n"
        "  Q -. 步数越少越快·细节保真略降 .-> WHY\n"
    ),
    "GEN-12": (  # 视频与 3D 扩散：从图像基座延伸
        "flowchart TD\n"
        '  BASE["图像扩散基座<br/>Stable Diffusion 等"] --> VID(["视频扩散<br/>时间注意力·帧间一致性"])\n'
        '  BASE --> TD3(["3D 生成<br/>SDS 蒸馏 NeRF / 3D 高斯"])\n'
        '  VID --> V1["文生视频<br/>Sora · SVD"]\n'
        '  TD3 --> D1["文生 3D<br/>DreamFusion 等"]\n'
        '  V1 --> CH{{"共性挑战"}}\n'
        "  D1 --> CH\n"
        '  CH --> C1["时序 / 多视角一致性"]\n'
        '  CH --> C2["物理合理性"]\n'
        '  CH --> C3["算力与数据成本"]\n'
    ),
    "GEN-13": (  # 应用与伦理：应用-风险-治理三支
        "mindmap\n"
        '  root(("扩散模型应用与伦理"))\n'
        "    应用价值\n"
        "      文生图 / 视频创作\n"
        "      设计与游戏素材\n"
        "      医学影像重建增强\n"
        "      科研数据增广\n"
        "    风险\n"
        "      深度伪造 Deepfake\n"
        "      版权与训练数据争议\n"
        "      偏见与刻板印象放大\n"
        "    治理\n"
        "      内容水印与溯源 C2PA\n"
        "      模型卡与使用政策\n"
        "      法规合规审查\n"
    ),
}


def _generic_diagram(kp_name: str, description: str) -> str:
    """未收录知识点：按 description 内容结构动态合成 Mermaid（不同知识点产出不同图）。

    按内容选图型：含「分类/类型/组成」等 → 层次图（graph TD）；否则 → 流程图
    （flowchart LR，节点形状轮换，含反馈边）。恒以 flowchart/graph 开头，始终可渲染。
    """
    raw = description or ""
    for sep in ("、", "，", "；", "。", "/", "·", " ", "（", "）", "(", ")"):
        raw = raw.replace(sep, "\n")
    concepts = [c.strip() for c in raw.split("\n") if c.strip()][:5]
    taxonomy = any(
        k in (description or "")
        for k in ("分类", "种类", "类型", "对比", "区别", "几种", "包括", "组成", "构成")
    )
    if taxonomy and concepts:
        lines = ["graph TD", f'  ROOT["{kp_name}"]']
        for i, c in enumerate(concepts):
            lines.append(f'  ROOT --> C{i}["{c}"]')
        return "\n".join(lines) + "\n"
    # 默认流程图：输入 → 核心步骤（由概念展开，形状轮换）→ 输出，并带迭代反馈边
    shapes = (("([", "])"), ("[", "]"), ("{{", "}}"))
    steps = concepts or [f"{kp_name}核心"]
    lines = ["flowchart LR", '  IN["输入 / 前置"]']
    prev = "IN"
    for i, c in enumerate(steps):
        op, cl = shapes[i % 3]
        nid = f"S{i}"
        lines.append(f'  {prev} --> {nid}{op}"{c}"{cl}')
        prev = nid
    lines.append(f'  {prev} --> OUT["输出 / 应用"]')
    lines.append("  OUT -. 迭代优化 .-> IN")
    return "\n".join(lines) + "\n"


_QUESTION_TYPES = ("single", "multiple", "boolean")
# 简答题型（C-fix 批2，9.1 扩展）：options 为空，correct_answer 存参考要点列表，
# explanation 存参考答案；判分经 LLMClient.score_short_answer（mock 确定性兜底）。
SHORT_ANSWER_TYPE = "short_answer"


def _char_bigrams(text: str) -> set[str]:
    """字符二元组集合（简答评分用，确定性、语言无关，无需分词/Key）。"""
    t = re.sub(r"\s+", "", (text or "").lower())
    return {t[i : i + 2] for i in range(len(t) - 1)}


def _point_coverage(point: str, answer: str) -> float:
    """单个参考要点被作答覆盖的程度（0-1，字符二元组召回）。"""
    pb = _char_bigrams(point)
    if not pb:
        return 0.0
    return len(pb & _char_bigrams(answer)) / len(pb)


_DOC_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;\n])")


def _doc_key_sentences(contexts: list[str], *, max_n: int, min_chars: int = 8) -> list[str]:
    """从文档检索切片中抽取要点句（确定性、去重、限长）——供文档闪卡/练习题 mock 兜底。

    只用文档内容（防幻觉：不引入外部知识），按出现顺序取前 max_n 条有效句子。
    """
    out: list[str] = []
    seen: set[str] = set()
    for ctx in contexts or []:
        for raw in _DOC_SENT_SPLIT.split(ctx or ""):
            sent = raw.strip()
            if len(sent) < min_chars or sent in seen:
                continue
            seen.add(sent)
            out.append(sent[:120])
            if len(out) >= max_n:
                return out
    return out


# ---- 文档问答（「和文档对话」严格基于文档 + 溯源，mock 兜底） ----------------
_DOC_CHAT_SYSTEM = (
    "你是「文档问答」助手，只依据用户提供的《{source_title}》文档片段回答问题，目标是帮助用户"
    "「读懂这篇文档」。铁律：只用给定文档片段中的信息，**禁止**引入文档之外的知识或编造事实；"
    "文档片段里没有答案时，明确回答「文档中未提及该内容」。在引用具体内容处以 [n] 标注对应"
    "文档片段序号（n 从 1 起，对应给定片段顺序），便于溯源。简体中文，条理清晰、简洁作答。"
)


def _mock_doc_answer(source_title: str, contexts: list[str], message: str) -> str:
    """确定性文档问答回答：由文档要点句合成、带 [n] 溯源标记（严格来自文档、不臆造）。

    无检索片段 → 明确「文档中未提及」（防幻觉）；否则给出 lead-in + 逐条要点（每条挂 [n] 溯源），
    与下方来源列表一一对应。逐字流式由调用方 char stream 完成。
    """
    q = (message or "").strip().replace("\n", " ")
    focus = (q[:40] + "…") if len(q) > 40 else (q or "这个问题")
    sentences = _doc_key_sentences(contexts, max_n=4)
    if not sentences:
        return (
            f"关于「{focus}」，当前文档《{source_title}》中未提及相关内容。"
            "（本回答严格基于你上传的文档，不做文档之外的推测。）"
        )
    lead = f"根据你上传的《{source_title}》，就「{focus}」，文档中相关的内容如下："
    body = "\n".join(f"{i}. {sent}[{i}]" for i, sent in enumerate(sentences[:3], start=1))
    tail = "以上要点均出自文档原文（见下方「来源」标注）。若需更系统的梳理，可在右侧生成讲义或图解。"
    return f"{lead}\n{body}\n{tail}"


def audit_practice(practice: dict[str, Any]) -> list[str]:
    """critic 审核：练习题（QuizQuestion 结构）答案自洽性校验，返回问题清单。

    口径（B6 验收标准）：correct_answer 必须存在于 options 的 option_id 中
    （multiple 为全部存在且非空数组），explanation 非空；另查结构基本面
    （题型枚举、≥2 个选项、option_id 不重复、题干非空）。
    """
    issues: list[str] = []
    if practice.get("question_type") not in _QUESTION_TYPES:
        issues.append(f"question_type 非法：{practice.get('question_type')}")
    if not str(practice.get("question_text") or "").strip():
        issues.append("question_text 为空")
    option_ids = [o.get("option_id") for o in (practice.get("options") or [])]
    if len(option_ids) < 2:
        issues.append("options 少于 2 个")
    if len(set(option_ids)) != len(option_ids):
        issues.append("option_id 重复")
    correct = practice.get("correct_answer")
    if isinstance(correct, list):
        if practice.get("question_type") != "multiple":
            issues.append("correct_answer 为数组但题型不是 multiple")
        if not correct or not all(c in option_ids for c in correct):
            issues.append(f"correct_answer {correct} 未全部出现在 options 中")
    elif correct not in option_ids:
        issues.append(f"correct_answer {correct!r} 不在 options 中")
    if not str(practice.get("explanation") or "").strip():
        issues.append("explanation 为空")
    return issues


# 错题强化预置库（接口文档 9.2，B6 mock）：nn 三题与前端 WeakPointReinforce.tsx
# 演示内容对齐（question_id 按种子题库 nn_q*，practice id 按契约「{qid}-r」）。
_REINFORCE_BANK: dict[str, dict[str, Any]] = {
    "nn_q1": {
        "point": "神经元运算顺序",
        "recap": "记忆口诀：**先乘后加再激活** —— ① 输入×权重求和 → ② 加偏置 b → "
        "③ 激活函数。顺序不能颠倒，因为激活必须作用在「加权和+偏置」的结果上。",
        "practice": {
            "question_id": "nn_q1-r",
            "question_type": "single",
            "question_text": "【强化】若把激活函数放到加权求和之前，会发生什么？",
            "options": [
                {"option_id": "a", "option_text": "结果不变，顺序无所谓"},
                {"option_id": "b", "option_text": "失去对「加权和」整体的非线性变换，等价于线性模型"},
                {"option_id": "c", "option_text": "会让网络收敛更快"},
            ],
            "correct_answer": "b",
            "explanation": "激活必须作用于加权和+偏置的结果，提前激活会破坏非线性表达能力。",
        },
    },
    "nn_q2": {
        "point": "激活函数辨析",
        "recap": "激活函数 = 给神经元引入**非线性**的函数。常见三个：**ReLU**（max(0,x)）、"
        "**Sigmoid**、**Tanh**。注意「梯度 Gradient」是反向传播里的概念，**不是**激活函数。",
        "practice": {
            "question_id": "nn_q2-r",
            "question_type": "multiple",
            "question_text": "【强化】下列关于激活函数，正确的有？（多选）",
            "options": [
                {"option_id": "a", "option_text": "ReLU 在正区间梯度恒为 1"},
                {"option_id": "b", "option_text": "Sigmoid 输出范围是 (0,1)"},
                {"option_id": "c", "option_text": "Gradient 是一种激活函数"},
                {"option_id": "d", "option_text": "Tanh 输出零均值，范围 (-1,1)"},
            ],
            "correct_answer": ["a", "b", "d"],
            "explanation": "ReLU/Sigmoid/Tanh 描述均正确；Gradient（梯度）不是激活函数。",
        },
    },
    "nn_q3": {
        "point": "ReLU 与梯度消失",
        "recap": "**ReLU** 在正区间导数恒为 1，反向传播时梯度不会被反复压缩，因此能"
        "**缓解梯度消失**；而 Sigmoid/Tanh 在饱和区导数趋近 0，深层网络易梯度消失。",
        "practice": {
            "question_id": "nn_q3-r",
            "question_type": "boolean",
            "question_text": "【强化】Sigmoid 在深层网络中比 ReLU 更容易引起梯度消失。",
            "options": [
                {"option_id": "true", "option_text": "正确"},
                {"option_id": "false", "option_text": "错误"},
            ],
            "correct_answer": "true",
            "explanation": "Sigmoid 两端饱和、导数趋零，深层叠加后梯度迅速衰减，比 ReLU 更易梯度消失。",
        },
    },
}


_KEYWORD_TO_DIM: dict[str, int] = {
    "机器学习": 0,
    "machine learning": 0,
    "神经网络": 1,
    "neural": 1,
    "深度学习": 2,
    "deep learning": 2,
    "注意力": 3,
    "attention": 3,
    "transformer": 4,
    "微调": 5,
    "finetune": 5,
    "fine-tune": 5,
    "lora": 5,
}


# ---- 学习流程：康奈尔线索 / 费曼讲解评估（接口文档第 18 章，C2） ----------------

# 康奈尔笔记法线索模板（接口文档 18.1）：每核心知识点的「线索区」问题/关键词
# （5-8 条）+「主笔记区」要点预填骨架 + 总结区引导语。mock 与 deepseek 兜底共用，
# 内容紧扣各知识点（保证返回真实线索问题而非占位）；未收录知识点参数化生成。
# 结构：kp_id -> {cues:[(type, text)], outline:[(heading, [points])], summaryHint}
_CORNELL_TEMPLATES: dict[str, dict[str, Any]] = {
    "nn": {
        "cues": [
            ("question", "为什么神经网络需要激活函数？"),
            ("question", "一个神经元的前向计算分哪几步？"),
            ("question", "反向传播是如何更新权重的？"),
            ("question", "ReLU 相比 Sigmoid 有什么优势？"),
            ("keyword", "加权求和 → 偏置 → 激活"),
            ("keyword", "梯度消失"),
        ],
        "outline": [
            ("激活函数的作用", ["引入非线性表达能力", "若无激活，多层等价单层线性变换"]),
            ("神经元三步运算", ["加权求和 Σ w·x", "加偏置 + b", "激活函数得到输出"]),
            ("反向传播", ["链式法则逐层求梯度", "按梯度下降更新权重"]),
        ],
        "summaryHint": "用一句话概括：神经网络如何通过加权、激活与反向传播来学习？",
    },
    "ml": {
        "cues": [
            ("question", "监督学习和无监督学习有什么区别？"),
            ("question", "过拟合是怎么产生的，有什么表现？"),
            ("question", "正则化为什么能缓解过拟合？"),
            ("question", "训练集 / 验证集 / 测试集各有什么用？"),
            ("keyword", "特征工程 / 损失函数"),
            ("keyword", "偏差-方差权衡"),
        ],
        "outline": [
            ("监督 vs 无监督", ["分类/回归有标注目标", "聚类/降维无标注"]),
            ("过拟合与泛化", ["训练好、测试差", "模型记住了训练噪声"]),
            ("正则化", ["L1/L2 惩罚过大参数", "早停 / 交叉验证"]),
        ],
        "summaryHint": "用一句话概括：机器学习如何在拟合训练数据与保持泛化之间取得平衡？",
    },
    "dl": {
        "cues": [
            ("question", "反向传播的核心作用是什么？"),
            ("question", "梯度下降如何更新参数？"),
            ("question", "常见优化器（SGD/Adam）有什么区别？"),
            ("question", "什么是梯度消失/爆炸，如何缓解？"),
            ("keyword", "链式法则 / 计算图"),
            ("keyword", "BatchNorm / Dropout"),
        ],
        "outline": [
            ("反向传播", ["链式法则求梯度", "计算图自动求导"]),
            ("梯度下降与优化器", ["SGD / Adam / RMSprop", "学习率调度"]),
            ("训练稳定性", ["梯度消失 / 爆炸", "归一化与正则缓解"]),
        ],
        "summaryHint": "用一句话概括：深度网络如何通过反向传播与优化器迭代学习？",
    },
    "cnn": {
        "cues": [
            ("question", "卷积层为什么能提取局部特征？"),
            ("question", "权重共享带来了什么好处？"),
            ("question", "池化层的作用是什么？"),
            ("question", "感受野如何随网络加深变化？"),
            ("keyword", "卷积核 / 步长 / 填充"),
            ("keyword", "ResNet 残差连接"),
        ],
        "outline": [
            ("卷积与局部特征", ["卷积核滑动提取局部特征", "权重共享大幅减少参数"]),
            ("池化", ["下采样降低空间尺寸", "增强平移不变性"]),
            ("经典网络", ["LeNet / AlexNet / ResNet", "残差连接让网络更深"]),
        ],
        "summaryHint": "用一句话概括：CNN 如何通过卷积与池化逐层提取图像特征？",
    },
    "transformer": {
        "cues": [
            ("question", "自注意力机制解决了什么问题？"),
            ("question", "Q / K / V 分别代表什么？"),
            ("question", "为什么要用多头注意力？"),
            ("question", "位置编码为什么必要？"),
            ("keyword", "缩放点积注意力"),
            ("keyword", "残差 + LayerNorm"),
        ],
        "outline": [
            ("自注意力", ["Q/K/V 计算注意力权重", "建模长距离依赖"]),
            ("多头注意力", ["多个子空间并行", "捕捉不同类型关系"]),
            ("位置编码", ["注入序列顺序信息", "正弦 / 可学习编码"]),
        ],
        "summaryHint": "用一句话概括：Transformer 如何用自注意力建模序列中元素间的依赖？",
    },
    "finetune": {
        "cues": [
            ("question", "全参微调和参数高效微调有什么区别？"),
            ("question", "LoRA 的核心思想是什么？"),
            ("question", "指令微调（SFT）解决了什么问题？"),
            ("question", "RLHF / DPO 对齐的目标是什么？"),
            ("keyword", "低秩矩阵 / 冻结权重"),
            ("keyword", "Adapter / Prompt Tuning"),
        ],
        "outline": [
            ("微调范式", ["全参微调开销大", "PEFT 只更新少量参数"]),
            ("LoRA", ["冻结原权重", "低秩矩阵学习增量"]),
            ("对齐", ["SFT 指令微调", "RLHF / DPO 对齐人类偏好"]),
        ],
        "summaryHint": "用一句话概括：如何在低成本下让大模型适配下游任务并对齐人类偏好？",
    },
}

# 费曼讲解评估的「应覆盖核心概念」（接口文档 18.2）：mock 据此判定学生讲解
# 「讲漏」哪些关键点 → 生成 gaps。每概念：keys 命中关键词、title 缺口标题、
# detail 缺口说明、severity 严重度、ask 引导补讲的追问。deepseek 走真实评估。
_FEYNMAN_CONCEPTS: dict[str, list[dict[str, Any]]] = {
    "nn": [
        {"keys": ["激活", "非线性", "relu", "sigmoid", "tanh"], "title": "激活函数与非线性",
         "detail": "未清楚说明激活函数引入非线性——否则多层网络等价于单层线性变换。",
         "severity": "high", "ask": "如果去掉激活函数，三层网络和一层线性模型有什么区别？"},
        {"keys": ["加权", "求和", "权重", "相乘"], "title": "加权求和",
         "detail": "未说明输入与权重加权求和这一基本运算。", "severity": "medium",
         "ask": "一个神经元是如何把多个输入汇总成一个数的？"},
        {"keys": ["反向", "梯度", "误差", "更新", "backprop"], "title": "反向传播与梯度更新",
         "detail": "未讲清反向传播如何利用梯度更新权重。", "severity": "medium",
         "ask": "网络是怎样根据误差来调整权重的？"},
        {"keys": ["偏置", "bias"], "title": "偏置项",
         "detail": "未提到偏置 b 对决策边界平移的作用。", "severity": "low",
         "ask": "偏置 b 在加权求和之后起什么作用？"},
    ],
    "ml": [
        {"keys": ["过拟合", "泛化", "overfit"], "title": "过拟合与泛化",
         "detail": "未提到过拟合——模型训练集好、测试集差的泛化问题。", "severity": "high",
         "ask": "如果模型训练集表现很好但测试集很差，说明了什么？"},
        {"keys": ["监督", "标注", "分类", "回归"], "title": "监督学习",
         "detail": "未区分监督/无监督学习与典型任务（分类、回归）。", "severity": "medium",
         "ask": "分类、回归和聚类分别属于哪类学习？"},
        {"keys": ["正则", "l1", "l2", "惩罚", "早停"], "title": "正则化",
         "detail": "未说明正则化如何抑制过拟合。", "severity": "medium",
         "ask": "有哪些手段可以缓解过拟合？"},
        {"keys": ["特征", "损失"], "title": "特征与损失",
         "detail": "未提到特征与损失函数在训练中的作用。", "severity": "low",
         "ask": "模型用什么来衡量预测好坏并据此优化？"},
    ],
    "dl": [
        {"keys": ["反向", "链式", "backprop"], "title": "反向传播",
         "detail": "未讲清反向传播用链式法则求梯度。", "severity": "high",
         "ask": "梯度是怎样从输出层逐层传回每个参数的？"},
        {"keys": ["梯度下降", "优化器", "sgd", "adam", "学习率"], "title": "梯度下降与优化器",
         "detail": "未提到用梯度下降/优化器按学习率更新参数。", "severity": "medium",
         "ask": "拿到梯度之后，参数是按什么规则更新的？"},
        {"keys": ["损失", "目标函数"], "title": "损失函数",
         "detail": "未说明以损失为优化目标。", "severity": "medium",
         "ask": "训练优化的目标是什么？"},
        {"keys": ["梯度消失", "梯度爆炸", "归一化", "batchnorm", "dropout"], "title": "训练稳定性",
         "detail": "未提到梯度消失/爆炸与归一化、正则等稳定手段。", "severity": "low",
         "ask": "深层网络训练常见哪些梯度问题，如何缓解？"},
    ],
    "cnn": [
        {"keys": ["卷积", "卷积核", "局部", "特征"], "title": "卷积与局部特征",
         "detail": "未说明卷积核滑动提取局部特征。", "severity": "high",
         "ask": "卷积核是如何在图像上提取局部特征的？"},
        {"keys": ["池化", "下采样", "pool"], "title": "池化",
         "detail": "未提到池化下采样降低尺寸、增强平移不变性。", "severity": "medium",
         "ask": "池化层的作用是什么？"},
        {"keys": ["权重共享", "参数共享", "共享"], "title": "权重共享",
         "detail": "未说明卷积通过权重共享大幅减少参数。", "severity": "medium",
         "ask": "相比全连接，卷积为什么参数更少？"},
        {"keys": ["感受野"], "title": "感受野",
         "detail": "未提到感受野随网络加深而扩大。", "severity": "low",
         "ask": "为什么深层卷积能看到更大范围的信息？"},
    ],
    "transformer": [
        {"keys": ["自注意力", "注意力", "attention", "query", "q/k/v", "qkv"], "title": "自注意力机制",
         "detail": "未讲清自注意力用 Q/K/V 建模序列依赖。", "severity": "high",
         "ask": "自注意力是怎样让每个位置关注到其他位置的？"},
        {"keys": ["多头", "multi-head", "multihead"], "title": "多头注意力",
         "detail": "未提到多头在不同子空间并行建模。", "severity": "medium",
         "ask": "为什么要用多个注意力头而不是一个？"},
        {"keys": ["位置编码", "position", "顺序"], "title": "位置编码",
         "detail": "未提到位置编码为模型注入顺序信息。", "severity": "medium",
         "ask": "自注意力本身不区分顺序，靠什么补充位置信息？"},
        {"keys": ["前馈", "残差", "layernorm", "归一化"], "title": "前馈与残差归一化",
         "detail": "未提到前馈网络与残差 + LayerNorm。", "severity": "low",
         "ask": "编码器每层除了注意力还有哪些子层？"},
    ],
    "finetune": [
        {"keys": ["lora", "低秩"], "title": "LoRA 低秩适配",
         "detail": "未讲清 LoRA 冻结原权重、用低秩矩阵学增量。", "severity": "high",
         "ask": "LoRA 是如何在不改动原权重的情况下微调的？"},
        {"keys": ["全参", "全量", "参数高效", "peft", "adapter"], "title": "全参 vs 参数高效微调",
         "detail": "未对比全参微调与 PEFT 的开销差异。", "severity": "medium",
         "ask": "全参微调和参数高效微调的主要区别是什么？"},
        {"keys": ["指令", "sft", "监督微调"], "title": "指令微调",
         "detail": "未提到指令微调提升模型遵循指令的能力。", "severity": "medium",
         "ask": "如何让模型更好地理解并遵循指令？"},
        {"keys": ["对齐", "rlhf", "dpo", "偏好"], "title": "对齐",
         "detail": "未提到 RLHF/DPO 等对齐方法。", "severity": "low",
         "ask": "训练后如何让模型输出更符合人类偏好？"},
    ],
}

# 缺口严重度排序（接口文档 18.2）：high 最先，决定 feedback 焦点与 complete 判定
_SEVERITY_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}
# 含此类缺口即「讲解未充分」（done=False）；仅 low 或无缺口 → complete=True
_FEYNMAN_BLOCKING: tuple[str, ...] = ("high", "medium")


class LLMClient:
    """LLM 适配层。provider=mock 时确定性产出；其余 provider 为 B5 占位。"""

    def __init__(self, provider: str | None = None) -> None:
        self.provider = provider or settings.llm_provider

    # ---- provider 守卫 ----------------------------------------------------
    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"

    def _ensure_supported(self) -> None:
        if self.provider not in ("mock", "deepseek"):
            raise NotImplementedError(
                f"LLM provider '{self.provider}' 尚未实现："
                "当前支持 mock / deepseek；qwen / anthropic 为后续占位。"
            )

    # ---- 画像抽取（接口文档 4.1） -----------------------------------------
    @staticmethod
    def _keyword_skills(text: str, source: str) -> list[dict[str, Any]]:
        """确定性 6 维技能基线：命中关键词的维度小幅抬升（mock / 无材料兜底共用）。"""
        levels = list(_MOCK_BASELINE)
        lowered = (text or "").lower()
        for keyword, dim in _KEYWORD_TO_DIM.items():
            if keyword in lowered:
                levels[dim] = min(100, levels[dim] + 8)
        return [
            {"name": name, "level": level, "source": source}
            for name, level in zip(ABILITY_DIMENSIONS, levels)
        ]

    def parse_skills(self, text: str, source: str) -> list[dict[str, Any]]:
        """从材料文本抽取 6 维技能画像（接口文档 4.1 skills，mock 确定性口径）。

        以基线值为底，命中关键词的维度小幅抬升（上限 100），每项 source 取调用方
        传入的来源类型（resume|ocr|text|manual）。无文本（纯手动）时 source 应为
        manual，且仅给基线值不编造经历。真实模式请使用 extract_profile。
        """
        return self._keyword_skills(text, source)

    def extract_profile(self, text: str, source: str) -> dict[str, Any]:
        """抽取完整结构化画像（接口文档 4.1：education/major/goal/skills）。

        - mock 或**无材料文本**（manual，防幻觉约束：不得调用 LLM 编造经历）：
          确定性产出，与 B2 行为逐字等价；
        - deepseek：真实抽取 + 契约清洗（枚举白名单、level 截断 0-100、
          固定 6 维补齐、source 统一为调用方传入值）。
        """
        self._ensure_supported()
        stripped = (text or "").strip()
        if self.is_mock or not stripped:
            return {
                "education": "硕士",
                "major": "人工智能",
                "goal": "职业培训",
                "skills": self._keyword_skills(stripped, source),
            }
        return self._deepseek_extract_profile(stripped, source)

    def _deepseek_extract_profile(self, text: str, source: str) -> dict[str, Any]:
        system = (
            "你是学习者画像抽取专家。从材料文本中抽取结构化画像，仅输出 JSON："
            '{"education": "...", "major": "...", "goal": "...", '
            '"skills": [{"name": "...", "level": 0}]}。'
            f"education 取值 {list(_EDUCATION_ENUM)}；major 取值 {list(_MAJOR_ENUM)}；"
            f"goal 取值 {list(_GOAL_ENUM)}；"
            f"skills.name 必须取自固定 6 维 {ABILITY_DIMENSIONS}，level 为 0-100 整数，"
            "仅依据材料体现的能力给出，材料未体现的维度可省略；"
            "材料明确说明某维度零基础/未接触/从未学过时，该维度必须给出且 level 取 0-10"
            "（显式负证据不是「未体现」，省略会被默认值虚高）；"
            "禁止编造材料中不存在的经历。"
        )
        raw = llm_transport.chat(f"材料文本：\n{text}", system=system)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            raise LLMGenerationError("画像抽取输出无法解析为契约 JSON")

        def _pick(value: Any, enum: tuple[str, ...]) -> str:
            return value if value in enum else "其他"

        by_name: dict[str, int] = {}
        for s in data.get("skills") or []:
            if not isinstance(s, dict):
                continue
            name, level = s.get("name"), s.get("level")
            if name in ABILITY_DIMENSIONS and isinstance(level, (int, float)):
                by_name[name] = max(0, min(100, int(level)))  # 截断 0-100
        skills = [
            {"name": name, "level": by_name.get(name, baseline), "source": source}
            for name, baseline in zip(ABILITY_DIMENSIONS, _MOCK_BASELINE)
        ]
        return {
            "education": _pick(data.get("education"), _EDUCATION_ENUM),
            "major": _pick(data.get("major"), _MAJOR_ENUM),
            "goal": _pick(data.get("goal"), _GOAL_ENUM),
            "skills": skills,
        }

    def generate_narrative(
        self,
        draft: dict[str, Any],
        materials: list[dict[str, Any]],
        target_job: dict[str, Any] | None,
    ) -> list[list[dict[str, Any]]]:
        """生成两段式带来源标注的画像叙述（接口文档 4.2 paragraphs）。

        返回恰好两段，每段为 NarrativeSegment 数组：
        - 第一段：背景与优势（tone=key，sourceId 指向支撑材料）；
        - 第二段：与目标岗位差距（tone=weak，定位最弱维度）。
        调用方负责在「无材料」时不调用本方法（叙述应返回 null，防幻觉）。
        deepseek 模式：真实生成 + 契约清洗（恰好两段、sourceId 白名单、tone 校验）。
        """
        self._ensure_supported()
        if not self.is_mock:
            return self._deepseek_narrative(draft, materials, target_job)
        return self._mock_narrative(draft, materials, target_job)

    def _mock_narrative(
        self,
        draft: dict[str, Any],
        materials: list[dict[str, Any]],
        target_job: dict[str, Any] | None,
    ) -> list[list[dict[str, Any]]]:
        """B2 确定性两段叙述（mock 模式逐字等价保留）。"""
        skills: list[dict[str, Any]] = draft.get("skills") or []
        major = (draft.get("major") or {}).get("value") or "人工智能"
        # 首个材料作为关键句的来源锚点
        source_id = materials[0]["id"] if materials else None

        # 优势维度（按 level；薄弱维度在 _gap_paragraph 内定位）
        strongest = (
            max(skills, key=lambda s: s.get("level", 0))
            if skills
            else {"name": ABILITY_DIMENSIONS[0]}
        )

        para1 = [
            {"text": "该学习者具备 ", "sourceId": None},
            {"text": major, "tone": "key", "sourceId": source_id},
            {"text": " 专业背景，", "sourceId": None},
            {"text": f"{strongest['name']}能力突出", "tone": "key", "sourceId": source_id},
            {"text": "。"},
        ]

        para2 = self._gap_paragraph(draft, target_job)
        return [para1, para2]

    @staticmethod
    def _gap_paragraph(
        draft: dict[str, Any], target_job: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """确定性「差距段」（mock 第二段；真实模式段数不足时的兜底段）。"""
        skills: list[dict[str, Any]] = draft.get("skills") or []
        weakest = (
            min(skills, key=lambda s: s.get("level", 0))
            if skills
            else {"name": ABILITY_DIMENSIONS[-1]}
        )
        job_name = (target_job or {}).get("name")
        lead = f"与目标岗位「{job_name}」相比，" if job_name else "与目标岗位要求相比，"
        return [
            {"text": lead, "sourceId": None},
            {"text": f"{weakest['name']}能力偏弱", "tone": "weak"},
            {"text": "，建议作为后续学习路径的优先强化方向。"},
        ]

    def _deepseek_narrative(
        self,
        draft: dict[str, Any],
        materials: list[dict[str, Any]],
        target_job: dict[str, Any] | None,
    ) -> list[list[dict[str, Any]]]:
        """真实两段叙述 + 契约清洗（接口文档 4.2）。

        sourceId 标注规则与 4.2 契约一致：只能取材料列表中的 id（白名单），
        模型给出列表外 id 一律置 null（防幻觉引用）；tone 仅保留 key|weak。
        """
        material_ids = {m["id"] for m in materials}
        system = (
            "你是学习画像叙述专家。基于给定结构化画像草稿与材料清单，生成恰好两段叙述，"
            '仅输出 JSON：{"paragraphs": [[{"text": "...", "tone": "key", '
            '"sourceId": "m1"}], [{"text": "..."}]]}。'
            "规则：第一段讲学习者背景与优势，关键事实片段 tone=key 并把 sourceId 标注为"
            "支撑该事实的材料 id；第二段讲与目标岗位的差距，薄弱点片段 tone=weak；"
            "sourceId 只能取材料清单中的 id，无材料支撑的片段 sourceId 置 null；"
            "tone 只能取 key 或 weak，普通叙述片段省略 tone；"
            "禁止编造材料中不存在的经历。"
        )
        payload = {
            "draft": draft,
            "materials": materials,
            "targetJob": target_job,
        }
        raw = llm_transport.chat(
            json.dumps(payload, ensure_ascii=False), system=system
        )
        data = _extract_json(raw)
        if not isinstance(data, dict) or not isinstance(data.get("paragraphs"), list):
            raise LLMGenerationError("叙述输出无法解析为契约 JSON")

        paragraphs: list[list[dict[str, Any]]] = []
        for para in data["paragraphs"][:2]:
            if not isinstance(para, list):
                continue
            segments: list[dict[str, Any]] = []
            for seg in para:
                if not isinstance(seg, dict) or not seg.get("text"):
                    continue
                cleaned: dict[str, Any] = {"text": str(seg["text"])}
                if seg.get("tone") in ("key", "weak"):
                    cleaned["tone"] = seg["tone"]
                sid = seg.get("sourceId")
                cleaned["sourceId"] = sid if sid in material_ids else None
                segments.append(cleaned)
            if segments:
                paragraphs.append(segments)
        if not paragraphs:
            raise LLMGenerationError("叙述输出不含有效段落")
        while len(paragraphs) < 2:  # 恰好两段（4.2 契约）：不足时补确定性差距段
            paragraphs.append(self._gap_paragraph(draft, target_job))
        return paragraphs

    def generate_lecture(
        self,
        kp_id: str,
        kp_name: str,
        difficulty: str,
        description: str = "",
        tier: str | None = None,
    ) -> dict[str, Any]:
        """生成自适应讲义（接口文档 8.2）。返回 markdown + sources + hallucinationRate。

        mock 口径：按难度档 + 画像能力档 tier（advanced/beginner/basic/None）确定性产出
        递进式 Markdown（概念→原理含 LaTeX 公式→例子→代码→误区→小结）。tier 由调用方
        据请求用户画像派生（services.resource），使同一知识点对不同用户产出深度不同的讲义；
        tier=None（无画像信号）→ 按难度基线。sources/hallucinationRate 为占位常量。
        真实模式讲义不走本方法——经 workflows.run_learning_workflow 生成。
        """
        if not self.is_mock:
            raise LLMGenerationError(
                "真实模式讲义应经 run_learning_workflow 生成，不应调用 generate_lecture"
            )
        return {
            "markdown": self._lecture_markdown(kp_name, difficulty, description, tier),
            "sources": [dict(s) for s in _LECTURE_SOURCES],
            "hallucinationRate": _LECTURE_HALLUCINATION_RATE,
        }

    @staticmethod
    def _lecture_markdown(
        name: str, difficulty: str, description: str, tier: str | None = None
    ) -> str:
        """生成递进式讲义 Markdown（确定性 mock / 真实回落共用）。

        结构：概念引入→核心原理(含 LaTeX 公式)→具体例子→代码示例→常见误区→小结。
        - difficulty 决定基线深度；tier（画像能力档 advanced/beginner/basic）个性化主控，
          使「同一知识点、同一难度」对能力强 / 零基础两位用户产出深度不同的讲义；
        - tier=None（直出 / 无画像信号）→ 按难度基线，保证直出与工作流产物在同 depth 逐字一致。
        合成逻辑见 app.core.lecture_content.compose_lecture（纯函数，便于扩充知识原子）。
        """
        from app.core import lecture_content

        return lecture_content.compose_lecture(name, difficulty, description, tier)

    # ---- 简答题 AI 评分（接口文档 9.3，C-fix 批2） -----------------------------
    def score_short_answer(
        self,
        question_text: str,
        reference_points: list[str],
        reference_answer: str,
        student_answer: str,
    ) -> dict[str, Any]:
        """简答题对照参考要点评分（0-100 + 简短点评）。

        - mock 或空作答：确定性评分（参考要点字符二元组覆盖度），无任何 Key 不崩；
        - deepseek：真实评分 + 契约清洗（score 截断 0-100 整数、comment 非空）；
          上游异常 → 回落确定性评分（演示兜底，不向路由抛 2001）。
        """
        self._ensure_supported()
        answer = (student_answer or "").strip()
        points = [p for p in (reference_points or []) if isinstance(p, str) and p.strip()]
        if self.is_mock or not answer:
            return self._mock_score_short_answer(answer, points)
        try:
            return self._deepseek_score_short_answer(
                question_text, points, reference_answer, answer
            )
        except LLMGenerationError as exc:
            logger.warning("简答评分真实生成失败，回落确定性评分：%s", exc)
            return self._mock_score_short_answer(answer, points)

    @staticmethod
    def _mock_score_short_answer(answer: str, points: list[str]) -> dict[str, Any]:
        """确定性简答评分：参考要点字符二元组覆盖度 → 0-100 + 覆盖/待补点评。"""
        answer = (answer or "").strip()
        if not answer:
            tail = "参考要点：" + "；".join(points) if points else ""
            return {"score": 0, "comment": ("未作答。" + tail).strip()}
        if not points:
            score = 70 if len(answer) >= 16 else 50 if len(answer) >= 6 else 30
            return {"score": score, "comment": "已作答，按作答完整度给分。"}
        per = [(_point_coverage(p, answer), p) for p in points]
        covered = [p for c, p in per if c >= 0.34]
        missing = [p for c, p in per if c < 0.34]
        avg = sum(c for c, _ in per) / len(per)
        # 覆盖各要点二元组的约一半即满分（鼓励复述关键概念，而非逐字照抄参考答案）
        score = max(0, min(100, round(min(1.0, avg / 0.5) * 100)))
        parts: list[str] = []
        if covered:
            parts.append("已覆盖：" + "、".join(covered))
        if missing:
            parts.append("可补充：" + "、".join(missing))
        return {"score": score, "comment": ("；".join(parts) + "。") if parts else "已完成评分。"}

    def _deepseek_score_short_answer(
        self,
        question_text: str,
        points: list[str],
        reference_answer: str,
        answer: str,
    ) -> dict[str, Any]:
        """真实简答评分 + 契约清洗（score 0-100 整数、comment 非空）。"""
        system = (
            "你是严谨的简答题阅卷老师。对照参考要点与参考答案给学生作答打分，"
            '仅输出 JSON：{"score": 0, "comment": "..."}。'
            "score 为 0-100 整数，按要点覆盖程度与准确性评分；comment 为一句中文点评，"
            "指出答到的要点与缺漏，不超过 60 字；禁止编造学生未写的内容。"
        )
        payload = {
            "question": question_text,
            "referencePoints": points,
            "referenceAnswer": reference_answer,
            "studentAnswer": answer,
        }
        raw = llm_transport.chat(json.dumps(payload, ensure_ascii=False), system=system)
        data = _extract_json(raw)
        if not isinstance(data, dict) or "score" not in data:
            raise LLMGenerationError("简答评分输出无法解析为契约 JSON")
        try:
            score = max(0, min(100, int(data["score"])))
        except (TypeError, ValueError) as exc:
            raise LLMGenerationError("简答评分 score 非法") from exc
        comment = str(data.get("comment") or "").strip() or "已完成评分。"
        return {"score": score, "comment": comment}

    # ---- 学习过程评估叙述（接口文档 12.2，C-fix 批3） --------------------------
    def evaluate_learning(
        self, signals: dict[str, Any], metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """学习评估叙述：综述 + 学习方法建议 + 动态调整建议。

        - 动态调整（adjustment）**始终确定性派生**（保证 nextKpId 合法、不被幻觉）；
        - 综述/方法建议：mock 据信号模板 / deepseek 真实生成 + 契约清洗，上游异常回落 mock。
        无任何 Key 也能跑通（mock 兜底）。
        """
        self._ensure_supported()
        adjustment = self._eval_adjustment(signals, metrics)
        if self.is_mock:
            narrative = self._mock_eval_narrative(signals, metrics)
        else:
            try:
                narrative = self._deepseek_eval_narrative(signals, metrics)
            except LLMGenerationError as exc:
                logger.warning("学习评估真实生成失败，回落确定性叙述：%s", exc)
                narrative = self._mock_eval_narrative(signals, metrics)
        return {
            "summary": narrative["summary"],
            "suggestions": narrative["suggestions"],
            "adjustment": adjustment,
        }

    @staticmethod
    def _eval_adjustment(signals: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
        """确定性动态调整建议：下一步知识点（薄弱点优先）+ 难度建议 + 行动。"""
        dims = {d["key"]: d["score"] for d in metrics.get("dimensions", [])}
        weak = metrics.get("weakPoints") or []
        attempts = signals.get("attemptCount", 0)
        trend = metrics.get("trend", "stable")
        if weak:
            nxt = weak[0]
            next_id, next_name = nxt.get("kpId"), nxt.get("name")
            action = f"下一步优先攻克「{next_name}」：先看讲义 + 图解，再做阶段测试。"
        else:
            next_id = next_name = None
            action = "核心知识点已全部通过，可转入复习巩固或挑战更高难度内容。"
        qp = dims.get("quiz_performance", 0)
        mp = dims.get("mastery_progress", 0)
        if trend == "declining" or (attempts and qp < 60):
            difficulty_advice = "建议将讲义难度下调到「入门」，先夯实基础概念。"
        elif mp >= 80 and qp >= 80:
            difficulty_advice = "建议将讲义难度上调到「高级」，深入数学形式化与工程细节。"
        else:
            difficulty_advice = "建议维持「初级」难度，稳步推进、边学边测。"
        return {
            "nextKpId": next_id,
            "nextKpName": next_name,
            "difficultyAdvice": difficulty_advice,
            "action": action,
        }

    @staticmethod
    def _mock_eval_narrative(
        signals: dict[str, Any], metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """确定性评估综述 + 方法建议（mock / deepseek 兜底）。"""
        trend_label = {"improving": "稳步上升", "declining": "有所下滑", "stable": "基本平稳"}
        dims = {d["key"]: d["score"] for d in metrics.get("dimensions", [])}
        mastered = signals["masteredCount"]
        total = signals["totalCore"]
        attempts = signals["attemptCount"]
        weak = metrics.get("weakPoints") or []
        if attempts:
            summary = (
                f"你已掌握 {mastered}/{total} 个核心知识点，近 {attempts} 次测验平均最佳 "
                f"{signals['avgBestScore']} 分，分数趋势{trend_label[metrics['trend']]}，"
                f"整体处于「{metrics['level']}」阶段。"
            )
        else:
            summary = (
                f"你已掌握 {mastered}/{total} 个核心知识点，尚无测验记录，整体处于"
                f"「{metrics['level']}」阶段，建议尽快做一次阶段测试以校准学情。"
            )
        suggestions: list[str] = []
        if weak:
            names = "、".join(w["name"] for w in weak)
            suggestions.append(f"优先复习薄弱点：{names}，配合讲义/图解后重做阶段测试巩固。")
        if metrics["trend"] == "declining":
            suggestions.append("近期测验分数下滑，建议放慢节奏、回看讲义并用费曼讲解自检。")
        elif metrics["trend"] == "improving":
            suggestions.append("学习状态向好，保持当前节奏，可适当增加练习难度。")
        if dims.get("engagement", 0) < 50:
            suggestions.append("学习投入偏低，建议多用康奈尔笔记与费曼讲解加深理解。")
        if dims.get("mastery_progress", 0) >= 80:
            suggestions.append("基础掌握扎实，可尝试上调讲义难度到「高级」拓展深度。")
        if not suggestions:
            suggestions.append("继续按学习路径推进，保持测验与笔记的规律使用。")
        return {"summary": summary, "suggestions": suggestions[:4]}

    def _deepseek_eval_narrative(
        self, signals: dict[str, Any], metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """真实评估综述 + 方法建议 + 契约清洗（summary 非空、suggestions 为非空 str 列表）。"""
        system = (
            "你是学习数据分析师。基于给定的学习行为信号与多维指标，给出一句中文学习综述与"
            '2-4 条具体可执行的学习方法建议，仅输出 JSON：{"summary": "...", '
            '"suggestions": ["...", "..."]}。综述不超过 80 字；建议聚焦薄弱点复习、'
            "节奏与难度调整、笔记/费曼等方法；禁止编造未提供的数据。"
        )
        payload = {"signals": signals, "metrics": metrics}
        raw = llm_transport.chat(json.dumps(payload, ensure_ascii=False), system=system)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            raise LLMGenerationError("学习评估输出无法解析为契约 JSON")
        summary = str(data.get("summary") or "").strip()
        suggestions = [
            str(s).strip()
            for s in (data.get("suggestions") or [])
            if isinstance(s, str) and str(s).strip()
        ]
        if not summary or not suggestions:
            raise LLMGenerationError("学习评估输出缺少 summary/suggestions")
        return {"summary": summary, "suggestions": suggestions[:4]}

    # ---- 视频讲解分镜脚本（接口文档 8.3，画面/旁白随知识点动态生成） ----------
    def generate_video_script(
        self, kp_id: str, kp_name: str, difficulty: str, description: str = ""
    ) -> dict[str, Any]:
        """生成讲解视频分镜脚本（接口文档 8.3 scenes）。

        返回 {title, scenes:[{title, points:[str], narration}]}（3-5 个场景）。
        - mock：确定性、与主题相关的占位脚本——nn 用与前端原 5 场景逐字对齐的精写
          内容（不回归），其余知识点按相同结构参数化生成，内容紧扣 kpName，
          **绝不固定为神经网络**；
        - deepseek：真实生成 + 契约清洗（场景数截断 3-5、每场景要点 1-4 条、
          标题/旁白非空）；解析失败或上游异常时**回落确定性主题脚本**，
          保证视频始终可渲染（演示兜底，不向路由抛 2001）。
        """
        self._ensure_supported()
        if self.is_mock:
            return self._mock_video_script(kp_id, kp_name, difficulty, description)
        try:
            return self._deepseek_video_script(kp_name, difficulty, description)
        except LLMGenerationError as exc:
            logger.warning("视频分镜脚本真实生成失败，回落主题占位脚本：%s", exc)
            return self._mock_video_script(kp_id, kp_name, difficulty, description)

    @staticmethod
    def _video_scene(title: str, points: list[str], narration: str) -> dict[str, Any]:
        return {"title": title, "points": points, "narration": narration}

    def _mock_video_script(
        self, kp_id: str, kp_name: str, difficulty: str, description: str
    ) -> dict[str, Any]:
        """确定性主题分镜脚本（mock / deepseek 兜底共用）。"""
        if kp_id == "nn":
            return {"title": "神经网络基础", "scenes": [dict(s) for s in _VIDEO_SCRIPT_NN]}
        desc = (description or "").strip()
        desc_point = desc[:18] if desc else f"{kp_name}的核心要点"
        scenes = [
            self._video_scene(
                f"课程导入 · {kp_name}",
                [f"按「{difficulty}」难度定制", desc_point, "建立整体认知框架"],
                f"欢迎学习{kp_name}。本视频由领域知识生成智能体按「{difficulty}」难度为你定制。",
            ),
            self._video_scene(
                f"{kp_name}的核心构成",
                [f"拆解{kp_name}的关键概念", "理清各部分之间的关系", "形成整体认知框架"],
                f"我们先拆解{kp_name}的核心构成，建立整体认知框架。",
            ),
            self._video_scene(
                f"{kp_name}在实践中如何运作",
                [f"一个{difficulty}难度的典型示例", "跟随流程逐步理解", "对照输入与输出"],
                f"接着通过一个{difficulty}难度的典型示例，看看{kp_name}在实践中如何运作。",
            ),
            self._video_scene(
                "常见方法与适用场景",
                [f"对比{kp_name}的相关方法", "明确各自适用场景", "避开典型误区"],
                f"再对比{kp_name}相关的常见方法与适用场景，避免典型误区。",
            ),
            self._video_scene(
                "要点回顾",
                [f"回顾{kp_name}的核心要点", "纳入完整学习闭环", "建议完成测验巩固"],
                f"最后回顾要点，把{kp_name}纳入完整的学习闭环。建议完成测验巩固理解。",
            ),
        ]
        return {"title": kp_name, "scenes": scenes}

    def _deepseek_video_script(
        self, kp_name: str, difficulty: str, description: str
    ) -> dict[str, Any]:
        """真实分镜脚本生成 + 契约清洗（接口文档 8.3）。"""
        system = (
            "你是领域知识讲解视频的分镜脚本编剧。根据给定知识点生成用于讲解视频的"
            "结构化分镜脚本，仅输出 JSON："
            '{"title":"视频标题","scenes":[{"title":"场景标题",'
            '"points":["要点1","要点2"],"narration":"该场景旁白"}]}。'
            "要求：scenes 为 3-5 个场景，按「导入 → 核心概念 → 工作机制或示例 → "
            "方法对比或要点 → 小结」组织；每个场景 points 为 2-4 条精炼要点"
            "（每条不超过 20 字），narration 为 1-2 句口语化旁白（不超过 60 字）；"
            "所有内容必须紧扣该知识点主题，禁止跑题到其它领域；只输出 JSON，不要额外说明。"
        )
        prompt = f"知识点：{kp_name}\n难度档：{difficulty}\n知识点说明：{description or kp_name}"
        raw = llm_transport.chat(prompt, system=system)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            raise LLMGenerationError("视频分镜脚本输出无法解析为契约 JSON")
        return self._clean_video_script(data, kp_name)

    @staticmethod
    def _clean_video_script(data: dict[str, Any], kp_name: str) -> dict[str, Any]:
        """分镜脚本契约清洗：场景数 3-5、每场景要点 1-4 条、标题/旁白非空。"""
        raw_scenes = data.get("scenes")
        if not isinstance(raw_scenes, list):
            raise LLMGenerationError("视频分镜脚本缺 scenes 数组")
        scenes: list[dict[str, Any]] = []
        for s in raw_scenes:
            if not isinstance(s, dict):
                continue
            title = str(s.get("title") or "").strip()
            narration = str(s.get("narration") or "").strip()
            points = [
                str(p).strip()
                for p in (s.get("points") or [])
                if isinstance(p, (str, int, float)) and str(p).strip()
            ][:4]  # 每场景最多 4 条要点
            if not title or not narration or not points:
                continue
            scenes.append({"title": title, "points": points, "narration": narration})
        if len(scenes) < 3:
            raise LLMGenerationError(f"视频分镜有效场景不足 3 个（得到 {len(scenes)}）")
        scenes = scenes[:5]  # 截断到 5 个场景（契约 3-5）
        title = str(data.get("title") or "").strip() or kp_name
        return {"title": title, "scenes": scenes}

    # ---- Mermaid 知识图解（接口文档 8.5，与讲义/视频同口径经 LLMClient 生成） ----
    def generate_diagram(
        self, kp_id: str, kp_name: str, description: str = ""
    ) -> dict[str, Any]:
        """生成 Mermaid 知识图解（接口文档 8.5）。返回 {mermaid}。

        - mock：确定性主题流程图——已收录知识点用精写模板（nn 与前端逐字一致），
          未收录知识点按主题参数化生成，恒以 `flowchart` 开头、紧扣 kpName；
        - deepseek：真实生成 mermaid + 契约清洗（首行须 flowchart/graph）；解析失败
          或上游异常时**回落确定性主题模板**，保证图解始终可渲染（不向路由抛 2001）。
        """
        self._ensure_supported()
        # GEN 板块（重点亮点·多图示）：精写论文级模板**优先于真实生成**——
        # 该板块图解质量为验收硬指标，确定性模板保证教材级标准结构（不抽卡）；
        # 其余板块维持原行为（真实生成优先，失败回落模板），不动已验收链路。
        if kp_id.startswith("GEN-") and kp_id in _DIAGRAM_TEMPLATES:
            return {"mermaid": _DIAGRAM_TEMPLATES[kp_id]}
        if self.is_mock:
            return {"mermaid": self._mock_diagram(kp_id, kp_name, description)}
        try:
            return {"mermaid": self._deepseek_diagram(kp_name, description)}
        except LLMGenerationError as exc:
            logger.warning("知识图解真实生成失败，回落主题占位图：%s", exc)
            return {"mermaid": self._mock_diagram(kp_id, kp_name, description)}

    @staticmethod
    def _mock_diagram(kp_id: str, kp_name: str, description: str) -> str:
        """确定性主题知识图解（mock / deepseek 兜底共用）。

        已收录知识点用精写模板（图型按内容各异）；未收录知识点按 description 动态合成
        （不同知识点产出不同图、图型按内容自选），见 _generic_diagram。
        """
        tpl = _DIAGRAM_TEMPLATES.get(kp_id)
        if tpl:
            return tpl
        return _generic_diagram(kp_name, description)

    def _deepseek_diagram(self, kp_name: str, description: str) -> str:
        """真实知识图解生成 + 契约清洗（接口文档 8.5）。

        提示要求按知识点内容结构**自选最贴切的图型**（流程/管线→flowchart；
        分类/谱系→mindmap 或 graph TD；模块结构→带 subgraph 的 flowchart），避免千篇一律。
        """
        system = (
            "你是深度学习/机器学习领域的知识图解专家。根据给定知识点生成一张**论文级标准示意图**"
            "（即该知识点在教材/论文里那类规范的架构图或流程图），用 Mermaid 画。"
            "只输出 Mermaid 源码本身，不要任何解释文字、不要 ``` 围栏。要求：\n"
            "1) 图必须还原该知识点的**真实标准结构**，例如：神经网络→输入层→隐藏层→输出层 + 前向/反向；"
            "CNN→卷积→ReLU→池化→全连接→Softmax；Transformer→嵌入+位置编码→多头自注意力→前馈→输出；"
            "梯度下降/训练→前向→损失→反向→参数更新的迭代回路。务必贴合本知识点的标准结构，不要臆造。\n"
            "2) 按内容自选最贴切的图型：流程/计算管线用 `flowchart LR` 或 `flowchart TD`；"
            "分类/谱系/对比用 `mindmap` 或 `graph TD` 层次图；含多模块的结构用带 `subgraph` 的 flowchart。\n"
            "3) 第一行必须是所选图型的合法声明（如 `flowchart TD` / `mindmap` / `graph TD`）。\n"
            "4) 6-14 个节点，体现该知识点的核心机制或构成；节点文字简短（不超过 12 字）"
            "且严格限定在本知识点的学术含义内——**禁止跑题到其它领域**（如 Transformer 不得画电力变压器、"
            "CNN 不得画新闻台、微调不得画乐器调音）。\n"
            "5) 只输出 Mermaid 源码。"
        )
        prompt = f"知识点：{kp_name}\n知识点说明：{description or kp_name}"
        raw = llm_transport.chat(prompt, system=system)
        return _clean_mermaid(raw)

    # ---- 文档学习：闪卡 + 文档练习题（平行链路，复用 LLMClient mock/real 双模 + 内容安全） ----
    def generate_flashcards(
        self,
        source_title: str,
        contexts: list[str],
        *,
        count: int = 8,
    ) -> dict[str, Any]:
        """从文档内容抽「正面问题 / 背面答案」闪卡集（接口文档 20.7）。返回 {cards:[{front,back}]}。

        contexts：该文档检索命中的切片内容（知识源，防幻觉——只据文档产出，不引入外部知识）。
        - mock：确定性——按文档要点句逐条转「问/答」卡，无随机、无网络；
        - deepseek：真实生成 + 契约清洗；解析失败回落确定性 mock（闪卡始终可用）。
        """
        self._ensure_supported()
        if self.is_mock:
            return {"cards": self._mock_flashcards(source_title, contexts, count)}
        try:
            return {"cards": self._deepseek_flashcards(source_title, contexts, count)}
        except LLMGenerationError as exc:
            logger.warning("闪卡真实生成失败，回落确定性 mock：%s", exc)
            return {"cards": self._mock_flashcards(source_title, contexts, count)}

    @staticmethod
    def _mock_flashcards(
        source_title: str, contexts: list[str], count: int
    ) -> list[dict[str, str]]:
        """确定性闪卡：取文档要点句，正面设问、背面即该句原文（内容严格来自文档）。"""
        sentences = _doc_key_sentences(contexts, max_n=count)
        cards: list[dict[str, str]] = []
        for i, sent in enumerate(sentences, start=1):
            topic = sent[:14].rstrip("，,。.；;：: ") or f"要点 {i}"
            cards.append(
                {
                    "front": f"关于「{topic}」，《{source_title}》是怎么讲的？",
                    "back": sent,
                }
            )
        if not cards:  # 文档无可用文本 → 单张兜底卡（不臆造内容）
            cards.append(
                {
                    "front": f"《{source_title}》的核心内容是什么？",
                    "back": "该文档暂未解析到可用于生成闪卡的正文内容，请检查文档是否为纯文本可抽取格式。",
                }
            )
        return cards

    def _deepseek_flashcards(
        self, source_title: str, contexts: list[str], count: int
    ) -> list[dict[str, str]]:
        system = (
            "你是学习卡片设计专家。仅依据给定的文档片段，抽取要点做成正/背面记忆闪卡。"
            "严格只用文档片段中的信息，禁止编造文档之外的事实。"
            f'仅输出 JSON：{{"cards": [{{"front": "正面问题", "back": "背面答案"}}]}}，'
            f"卡片数不超过 {count} 张，front 是一个针对要点的简短问题，back 是简明答案。"
        )
        joined = "\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts) if c)[:6000]
        prompt = f"文档标题：{source_title}\n文档片段：\n{joined or source_title}"
        data = _extract_json(llm_transport.chat(prompt, system=system))
        raw_cards = data.get("cards") if isinstance(data, dict) else None
        cards: list[dict[str, str]] = []
        for c in raw_cards or []:
            if isinstance(c, dict) and str(c.get("front") or "").strip() and str(c.get("back") or "").strip():
                cards.append({"front": str(c["front"]).strip(), "back": str(c["back"]).strip()})
        if not cards:
            raise LLMGenerationError("闪卡输出无法解析为契约 JSON")
        return cards[:count]

    # ---- 文档学习：文档概览（NotebookLM 式速读，复用双模 + 内容安全 + 防幻觉） ----
    def generate_overview(self, source_title: str, contexts: list[str]) -> dict[str, Any]:
        """文档概览：这篇文档是什么、讲了什么、核心结构概况、关键点。

        返回 {summary, about, structure, keyPoints:[...]}。contexts 为该文档检索命中的
        切片（知识源，防幻觉——只据文档产出，不引入外部知识）。
        - mock：确定性——按文档要点句合成概览，无随机、无网络；
        - deepseek：真实生成 + 契约清洗；解析失败回落确定性 mock（概览始终可用）。
        """
        self._ensure_supported()
        if self.is_mock:
            return self._mock_overview(source_title, contexts)
        try:
            return self._deepseek_overview(source_title, contexts)
        except LLMGenerationError as exc:
            logger.warning("文档概览真实生成失败，回落确定性 mock：%s", exc)
            return self._mock_overview(source_title, contexts)

    @staticmethod
    def _mock_overview(source_title: str, contexts: list[str]) -> dict[str, Any]:
        """确定性文档概览：全部取材自文档要点句（严格来自文档、不臆造）。"""
        sentences = _doc_key_sentences(contexts, max_n=8)
        if not sentences:
            return {
                "summary": f"《{source_title}》暂未解析到可用于生成概览的正文内容。",
                "about": "请确认文档为可抽取文本的格式（PDF / TXT / Markdown / DOCX）后重试。",
                "structure": "—",
                "keyPoints": [],
            }
        topic = sentences[0][:24].rstrip("，,。.；;：: ")
        return {
            "summary": f"《{source_title}》是一篇围绕「{topic}」展开的资料。",
            "about": "".join(sentences[:2])[:180],
            "structure": (
                f"全文自「{sentences[0][:14]}」切入，逐步展开到「{sentences[-1][:14]}」，"
                f"共梳理约 {len(sentences)} 个要点。"
            ),
            "keyPoints": sentences[:5],
        }

    def _deepseek_overview(self, source_title: str, contexts: list[str]) -> dict[str, Any]:
        system = (
            "你是资料速读专家。仅依据给定文档片段，产出一份「文档概览」，帮助读者快速判断"
            "这篇文档是什么、讲了什么、核心内容/结构概况与关键点。"
            "严格只用文档片段中的信息，禁止编造文档之外的事实。"
            '仅输出 JSON：{"summary":"一句话这篇文档是什么","about":"讲了什么（2-3句）",'
            '"structure":"核心内容/结构概况","keyPoints":["关键点1","关键点2"]}。'
        )
        joined = "\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts) if c)[:6000]
        prompt = f"文档标题：{source_title}\n文档片段：\n{joined or source_title}"
        data = _extract_json(llm_transport.chat(prompt, system=system))
        if not isinstance(data, dict) or not str(data.get("summary") or "").strip():
            raise LLMGenerationError("文档概览输出无法解析为契约 JSON")
        kp = data.get("keyPoints")
        key_points = (
            [str(x).strip() for x in kp if str(x).strip()] if isinstance(kp, list) else []
        )
        return {
            "summary": str(data.get("summary") or "").strip(),
            "about": str(data.get("about") or "").strip(),
            "structure": str(data.get("structure") or "").strip(),
            "keyPoints": key_points[:8],
        }

    def generate_doc_quiz(
        self,
        source_title: str,
        contexts: list[str],
        *,
        count: int = 5,
    ) -> dict[str, Any]:
        """从文档内容出练习题（接口文档 20.6）。返回 {questions:[QuizQuestion 契约结构]}。

        - mock：确定性——按文档要点句出判断题（true/false，答案自洽），内容来自文档；
        - deepseek：真实生成 + audit_practice 自洽审核；不自洽/解析失败回落确定性 mock。
        """
        self._ensure_supported()
        if self.is_mock:
            return {"questions": self._mock_doc_quiz(source_title, contexts, count)}
        try:
            return {"questions": self._deepseek_doc_quiz(source_title, contexts, count)}
        except LLMGenerationError as exc:
            logger.warning("文档练习题真实生成失败，回落确定性 mock：%s", exc)
            return {"questions": self._mock_doc_quiz(source_title, contexts, count)}

    @staticmethod
    def _mock_doc_quiz(
        source_title: str, contexts: list[str], count: int
    ) -> list[dict[str, Any]]:
        """确定性判断题：取文档要点句，命题「以下说法是否符合文档」，答案恒 true（内容来自文档）。"""
        sentences = _doc_key_sentences(contexts, max_n=count)
        questions: list[dict[str, Any]] = []
        for i, sent in enumerate(sentences, start=1):
            questions.append(
                {
                    "question_id": f"docq_{i}",
                    "question_type": "boolean",
                    "question_text": f"根据《{source_title}》，以下说法是否正确：{sent}",
                    "options": [
                        {"option_id": "true", "option_text": "正确"},
                        {"option_id": "false", "option_text": "错误"},
                    ],
                    "correct_answer": "true",
                    "explanation": f"该表述取自文档原文要点：{sent}",
                }
            )
        return questions

    def _deepseek_doc_quiz(
        self, source_title: str, contexts: list[str], count: int
    ) -> list[dict[str, Any]]:
        system = (
            "你是命题专家。仅依据给定文档片段出练习题，严格只考文档中出现的知识，禁止编造。"
            f'仅输出 JSON：{{"questions": [{{"question_id": "docq_1", '
            '"question_type": "single|multiple|boolean", "question_text": "...", '
            '"options": [{"option_id": "a", "option_text": "..."}], '
            '"correct_answer": "option_id（multiple 为数组；boolean 用 true/false）", '
            '"explanation": "..."}]}。'
            f"题数不超过 {count}；correct_answer 必须取自 options 的 option_id；explanation 非空。"
        )
        joined = "\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts) if c)[:6000]
        prompt = f"文档标题：{source_title}\n文档片段：\n{joined or source_title}"
        data = _extract_json(llm_transport.chat(prompt, system=system))
        raw = data.get("questions") if isinstance(data, dict) else None
        questions: list[dict[str, Any]] = []
        for idx, q in enumerate(raw or [], start=1):
            if not isinstance(q, dict):
                continue
            options = [
                {"option_id": str(o.get("option_id")), "option_text": str(o.get("option_text") or "")}
                for o in (q.get("options") or [])
                if isinstance(o, dict) and o.get("option_id")
            ]
            cleaned = {
                "question_id": str(q.get("question_id") or f"docq_{idx}"),
                "question_type": q.get("question_type"),
                "question_text": str(q.get("question_text") or ""),
                "options": options,
                "correct_answer": q.get("correct_answer"),
                "explanation": str(q.get("explanation") or ""),
            }
            if not audit_practice(cleaned):  # 仅收自洽题（防幻觉/防错题）
                questions.append(cleaned)
        if not questions:
            raise LLMGenerationError("文档练习题输出无自洽题（审核未通过）")
        return questions[:count]

    # ---- 错题强化（接口文档 9.2，B6） --------------------------------------
    def generate_reinforcement(
        self, kp_name: str, wrong_questions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """错题 → 薄弱点定位 + recap + 一道针对性练习（接口文档 9.2）。

        wrong_questions：答错题的 QuizQuestion 契约结构（2.5）列表。
        - mock：确定性产出（nn 三题与前端 WeakPointReinforce 演示内容对齐，
          其余题走确定性变式兜底），无随机、无网络；
        - deepseek：真实生成 + critic 自洽审核（correct_answer 必须在 options 中、
          explanation 非空），不自洽时带审核意见重试一次，仍失败 → LLMGenerationError。
        """
        self._ensure_supported()
        if self.is_mock:
            return [self._mock_reinforce_card(q) for q in wrong_questions]
        return self._deepseek_reinforcement(kp_name, wrong_questions)

    @staticmethod
    def _mock_reinforce_card(question: dict[str, Any]) -> dict[str, Any]:
        """单题确定性强化卡。命中预置库用精写内容，否则确定性变式兜底。"""
        qid = question["question_id"]
        bank = _REINFORCE_BANK.get(qid)
        if bank is not None:
            card = {"questionId": qid, **bank}
            card["practice"] = {**bank["practice"], "question_id": f"{qid}-r"}
            return card
        # 兜底变式：题干前缀【强化·变式】+ 选项确定性轮转一位（option_id 随选项移动，
        # correct_answer 不变仍指向原选项，答案自洽）。
        options = list(question.get("options") or [])
        rotated = options[1:] + options[:1] if len(options) > 1 else options
        point = str(question.get("question_text") or "").rstrip("？?。.")[:24]
        return {
            "questionId": qid,
            "point": point,
            "recap": f"回顾：{question.get('explanation') or '请重读讲义对应小节。'}",
            "practice": {
                "question_id": f"{qid}-r",
                "question_type": question["question_type"],
                "question_text": f"【强化·变式】{question['question_text']}",
                "options": rotated,
                "correct_answer": question["correct_answer"],
                "explanation": question.get("explanation") or "",
            },
        }

    def _deepseek_reinforcement(
        self, kp_name: str, wrong_questions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """真实强化生成 + critic 答案自洽审核（不自洽带反馈重试一次）。"""
        system = (
            "你是错题强化教练。针对每道答错的题，定位薄弱知识点并生成强化内容，"
            '仅输出 JSON：{"items": [{"questionId": "原题id", "point": "薄弱点短语", '
            '"recap": "针对性回顾讲解", "practice": {"question_id": "原题id-r", '
            '"question_type": "single|multiple|boolean", "question_text": "...", '
            '"options": [{"option_id": "a", "option_text": "..."}], '
            '"correct_answer": "option_id（multiple 为 option_id 数组）", '
            '"explanation": "..."}}]}。'
            "practice 必须是与原题同考点但不同问法的新题；correct_answer 必须取自 "
            "options 的 option_id；explanation 必须非空；items 数量与输入错题数一致。"
        )
        payload = {"knowledgePoint": kp_name, "wrongQuestions": wrong_questions}
        prompt = json.dumps(payload, ensure_ascii=False)

        last_issues: list[str] = []
        for attempt in range(2):  # 首次 + 审核不通过重试一次
            feedback = (
                f"\n上一轮输出未通过审核，请修正以下问题后重新输出完整 JSON：{last_issues}"
                if last_issues
                else ""
            )
            raw = llm_transport.chat(prompt + feedback, system=system)
            cards, last_issues = self._clean_reinforcement(raw, wrong_questions)
            if not last_issues:
                return cards
        raise LLMGenerationError(f"强化练习审核未通过（答案不自洽）：{last_issues[:3]}")

    @staticmethod
    def _clean_reinforcement(
        raw: str, wrong_questions: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """解析 + 契约清洗 + critic 自洽审核。返回 (cards, issues)；issues 非空即不通过。"""
        data = _extract_json(raw)
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            return [], ["输出无法解析为契约 JSON（缺 items 数组）"]

        wrong_ids = [q["question_id"] for q in wrong_questions]
        cards: list[dict[str, Any]] = []
        issues: list[str] = []
        items = data["items"][: len(wrong_ids)]
        if len(items) < len(wrong_ids):
            issues.append(f"items 数量 {len(items)} 少于错题数 {len(wrong_ids)}")
        for idx, item in enumerate(items):
            if not isinstance(item, dict) or not isinstance(item.get("practice"), dict):
                issues.append(f"items[{idx}] 缺 practice 对象")
                continue
            qid = item.get("questionId")
            if qid not in wrong_ids:
                qid = wrong_ids[idx]  # questionId 漂移 → 按输入顺序回正
            practice = item["practice"]
            options = [
                {
                    "option_id": str(o.get("option_id")),
                    "option_text": str(o.get("option_text") or ""),
                }
                for o in (practice.get("options") or [])
                if isinstance(o, dict) and o.get("option_id")
            ]
            cleaned = {
                "question_id": str(practice.get("question_id") or f"{qid}-r"),
                "question_type": practice.get("question_type"),
                "question_text": str(practice.get("question_text") or ""),
                "options": options,
                "correct_answer": practice.get("correct_answer"),
                "explanation": str(practice.get("explanation") or ""),
            }
            issues.extend(
                f"items[{idx}]({qid}) {msg}" for msg in audit_practice(cleaned)
            )
            cards.append(
                {
                    "questionId": qid,
                    "point": str(item.get("point") or ""),
                    "recap": str(item.get("recap") or ""),
                    "practice": cleaned,
                }
            )
        return cards, issues

    # ---- 苏格拉底辅导（接口文档 8.7 / 15.4，B7-a） --------------------------
    def tutor_chat(
        self, *, kp_name: str, history: list[dict[str, str]], message: str
    ) -> dict[str, Any]:
        """整体回复（8.7 JSON 模式）：{reply, suggestions}。

        mock：确定性引导链（不直接给答案，问题收尾）；
        deepseek：真实生成（system 约束引导式），suggestions 可空（契约允许）。
        """
        self._ensure_supported()
        if self.is_mock:
            reply, suggestions = _mock_tutor_reply(message)
            return {"reply": reply, "suggestions": suggestions}
        reply = llm_transport.chat(
            message, system=_TUTOR_SYSTEM.format(kp_name=kp_name), history=history
        )
        return {"reply": reply, "suggestions": []}

    def tutor_chat_stream(
        self, *, kp_name: str, history: list[dict[str, str]], message: str
    ) -> Iterator[str]:
        """流式回复（15.4 SSE）：逐 delta 产出。

        mock：确定性引导链**逐字**流式（字间延迟见 settings.tutor_stream_delay_ms，
        打字机演示效果）；deepseek：经 llm_deepseek.chat_stream 真实流式透传。
        """
        self._ensure_supported()
        if not self.is_mock:
            return llm_transport.chat_stream(
                message, system=_TUTOR_SYSTEM.format(kp_name=kp_name), history=history
            )
        reply, _suggestions = _mock_tutor_reply(message)

        def _char_stream() -> Iterator[str]:
            delay = settings.tutor_stream_delay_ms / 1000
            for char in reply:
                if delay > 0:
                    time.sleep(delay)
                yield char

        return _char_stream()

    def tutor_suggestions(self, message: str) -> list[str]:
        """done 事件的快捷建议（15.4）：mock 按引导链分支；deepseek 可空。"""
        if self.is_mock:
            return _mock_tutor_reply(message)[1]
        return []

    # ---- 文档问答（NotebookLM 式「和文档对话」，严格基于文档 + 溯源，流式） ----
    def doc_chat_stream(
        self,
        *,
        source_title: str,
        contexts: list[str],
        history: list[dict[str, str]],
        message: str,
    ) -> Iterator[str]:
        """就选中文档回答用户问题（逐 delta 流式）。**严格基于文档片段、防幻觉、标出处**。

        与苏格拉底辅导不同：这里是「理解文档」的即问即答（直接作答，不刻意反问）；答案只依据
        传入的文档检索片段（contexts），文档没有的明确回答「文档中未提及」，引用处以 [n] 标注
        对应片段序号（与下方来源列表一一对应）。
        - mock：确定性——由文档要点句合成带 [n] 溯源标记的回答，**逐字**流式（无 Key 全链路可跑）；
        - deepseek：真实流式，system 约束「仅据文档片段作答 + [n] 标注」。
        """
        self._ensure_supported()
        if not self.is_mock:
            joined = "\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts) if c)[:6000]
            prompt = (
                f"文档标题：{source_title}\n文档片段（回答只能依据这些片段）：\n"
                f"{joined or '（未检索到相关片段）'}\n\n用户问题：{message}"
            )
            return llm_transport.chat_stream(
                prompt, system=_DOC_CHAT_SYSTEM.format(source_title=source_title), history=history
            )
        answer = _mock_doc_answer(source_title, contexts, message)

        def _char_stream() -> Iterator[str]:
            delay = settings.tutor_stream_delay_ms / 1000
            for char in answer:
                if delay > 0:
                    time.sleep(delay)
                yield char

        return _char_stream()

    # ---- 智能辅导·按需资源生成（接口文档 8.8，C-fix 批3-bonus） ---------------
    def suggest_remedial_resources(
        self, kp_name: str, question: str
    ) -> dict[str, Any]:
        """识别问题点 + 给出针对性资源生成清单（8.8）。

        返回 {problemPoint, suggestions:[{id,type,title,expect}]}，type ∈ REMEDIAL_TYPES。
        - mock：关键词识别问题点 + 模板清单；
        - deepseek：真实识别 + 清洗（type 白名单、title/expect 非空，不足回落模板）。
        无 Key 也能跑（mock 兜底）。
        """
        self._ensure_supported()
        if self.is_mock:
            point = _mock_identify_problem(question, kp_name)
            return {"problemPoint": point, "suggestions": _build_remedial_suggestions(point)}
        try:
            return self._deepseek_suggest_remedial(kp_name, question)
        except LLMGenerationError as exc:
            logger.warning("资源建议真实生成失败，回落模板清单：%s", exc)
            point = _mock_identify_problem(question, kp_name)
            return {"problemPoint": point, "suggestions": _build_remedial_suggestions(point)}

    def _deepseek_suggest_remedial(self, kp_name: str, question: str) -> dict[str, Any]:
        system = (
            f"你是「{kp_name}」的辅导助手。学生提出了一个困惑，请先用一句话精炼概括其"
            "「问题点」，再给出可按需生成的针对性学习资源清单。仅输出 JSON："
            '{"problemPoint": "...", "suggestions": [{"type": "diagram", '
            '"title": "...", "expect": "..."}]}。'
            f"type 只能取 {list(REMEDIAL_TYPES)}（图解/例题/短视频/补充讲义片段），"
            "每种最多 1 项；title 简短、expect 说明预计内容；禁止编造与问题点无关的资源。"
        )
        raw = llm_transport.chat(f"学生困惑：{question}", system=system)
        data = _extract_json(raw)
        point = ""
        suggestions: list[dict[str, Any]] = []
        if isinstance(data, dict):
            point = str(data.get("problemPoint") or "").strip()
            seen: set[str] = set()
            for s in data.get("suggestions") or []:
                if not isinstance(s, dict):
                    continue
                t = s.get("type")
                if t not in REMEDIAL_TYPES or t in seen:
                    continue
                title = str(s.get("title") or "").strip()
                expect = str(s.get("expect") or "").strip()
                if not title or not expect:
                    continue
                seen.add(t)
                suggestions.append({"id": f"r-{t}", "type": t, "title": title, "expect": expect})
        if not point:
            point = _mock_identify_problem(question, kp_name)
        if len(suggestions) < 2:  # 兜底：保证清单可用
            suggestions = _build_remedial_suggestions(point)
        return {"problemPoint": point, "suggestions": suggestions}

    def generate_remedial_content(
        self, kind: str, kp_name: str, problem_point: str
    ) -> dict[str, Any]:
        """按需生成例题 / 补充讲义片段（8.8；diagram/video 复用既有资源服务）。

        kind=='example' → {title, statement, solution}；
        kind=='lecture' → {title, markdown}。mock 确定性 / deepseek 真实 + 兜底。
        """
        self._ensure_supported()
        if self.is_mock:
            return self._mock_remedial_content(kind, kp_name, problem_point)
        try:
            return self._deepseek_remedial_content(kind, kp_name, problem_point)
        except LLMGenerationError as exc:
            logger.warning("按需资源真实生成失败，回落确定性内容：%s", exc)
            return self._mock_remedial_content(kind, kp_name, problem_point)

    @staticmethod
    def _mock_remedial_content(kind: str, kp_name: str, point: str) -> dict[str, Any]:
        """确定性例题 / 讲义片段（mock / deepseek 兜底）。"""
        if kind == "example":
            return {
                "title": f"例题 · {point}",
                "statement": (
                    f"【例题】围绕「{point}」：请说明它在「{kp_name}」中的作用，"
                    "并用一个具体例子说明其工作过程。"
                ),
                "solution": (
                    f"解析：\n1. 先明确「{point}」的定义与要解决的问题；\n"
                    f"2. 结合「{kp_name}」的整体流程，定位它处于哪一步、起什么作用；\n"
                    "3. 举一个最小例子，代入数据走一遍，观察输入到输出的变化；\n"
                    f"小结：抓住「{point}」的本质，即可举一反三。"
                ),
            }
        # 默认 lecture 片段
        return {
            "title": f"补充讲义 · {point}",
            "markdown": (
                f"# 补充讲义 · {point}\n\n"
                f"> 针对你在「{kp_name}」中卡住的「{point}」，这里做一段精炼补充。\n\n"
                f"## 一、它解决什么问题\n\n「{point}」是「{kp_name}」的关键一环——"
                "先理解它「要做什么」，再看「怎么做」。\n\n"
                "## 二、关键要点\n\n"
                f"- 抓住「{point}」的输入、变换与输出三段式；\n"
                "- 留意它与相邻概念的衔接关系（前一步给它什么、它给后一步什么）；\n"
                "- 用一个最小例子复现，建立可迁移的直觉。\n\n"
                f"## 三、一句话小结\n\n理解「{point}」的本质，就抓住了这一段的核心。"
            ),
        }

    def _deepseek_remedial_content(
        self, kind: str, kp_name: str, problem_point: str
    ) -> dict[str, Any]:
        """真实例题 / 讲义片段 + 契约清洗。"""
        if kind == "example":
            system = (
                f"你是「{kp_name}」的辅导老师。针对学生的问题点「{problem_point}」出一道例题"
                '并给出分步解析，仅输出 JSON：{"title": "...", "statement": "...", "solution": "..."}。'
                "statement 为题干、solution 为分步解析，紧扣问题点，简体中文。"
            )
            raw = llm_transport.chat(f"问题点：{problem_point}", system=system)
            data = _extract_json(raw)
            if not isinstance(data, dict) or not str(data.get("statement") or "").strip():
                raise LLMGenerationError("例题输出无法解析为契约 JSON")
            return {
                "title": str(data.get("title") or f"例题 · {problem_point}").strip(),
                "statement": str(data["statement"]).strip(),
                "solution": str(data.get("solution") or "").strip() or "（解析略）",
            }
        system = (
            f"你是「{kp_name}」的讲义作者。针对学生的问题点「{problem_point}」写一段精炼的补充"
            '讲义片段（Markdown），仅输出 JSON：{"title": "...", "markdown": "..."}。'
            "markdown 用二级标题分节、紧扣问题点、200-400 字，简体中文。"
        )
        raw = llm_transport.chat(f"问题点：{problem_point}", system=system)
        data = _extract_json(raw)
        if not isinstance(data, dict) or not str(data.get("markdown") or "").strip():
            raise LLMGenerationError("讲义片段输出无法解析为契约 JSON")
        return {
            "title": str(data.get("title") or f"补充讲义 · {problem_point}").strip(),
            "markdown": str(data["markdown"]).strip(),
        }

    # ---- 外部资源·联网搜索聚合（接口文档 8.6 增量，C-fix 批3-bonus） ----------
    def aggregate_resources(
        self,
        kp_name: str,
        weak_points: list[str],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """聚合 Agent 整理 + critic 评分（接口文档 8.6）。

        candidates 为联网搜索命中（或种子兜底）[{title,url,source,snippet,type,embed?,duration?}]，
        输出按相关度降序的 8.6 资源清单 [{id,type,title,source,url,relevance,credibility,reason,embed?,duration?}]。
        - mock：确定性评分（字符二元组相关度 + 来源可信度启发式 + 模板理由）；
        - deepseek：真实排序/评分/理由 + 契约清洗（**URL 必须取自候选，杜绝幻觉链接**）。
        """
        self._ensure_supported()
        cands = [
            c for c in candidates
            if isinstance(c, dict) and str(c.get("url") or "").strip() and str(c.get("title") or "").strip()
        ]
        if not cands:
            return []
        if self.is_mock:
            return self._mock_aggregate(kp_name, weak_points, cands)
        try:
            return self._deepseek_aggregate(kp_name, weak_points, cands)
        except LLMGenerationError as exc:
            logger.warning("资源聚合评分真实生成失败，回落确定性评分：%s", exc)
            return self._mock_aggregate(kp_name, weak_points, cands)

    @staticmethod
    def _agg_item(cand: dict[str, Any], idx: int, *, type_: str, rel: int, cred: int, reason: str) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": f"agg-{idx}",
            "type": type_ if type_ in _AGG_TYPES else (cand.get("type") if cand.get("type") in _AGG_TYPES else "文档"),
            "title": str(cand.get("title")),
            "source": str(cand.get("source") or "web"),
            "url": str(cand.get("url")),
            "relevance": rel,
            "credibility": cred,
            "reason": reason,
        }
        if cand.get("embed"):
            item["embed"] = cand["embed"]
        if cand.get("duration"):
            item["duration"] = cand["duration"]
        return item

    @staticmethod
    def _mock_aggregate(
        kp_name: str, weak_points: list[str], cands: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """确定性聚合评分（字符二元组相关度 + 来源可信度 + 模板理由）。"""
        target = _char_bigrams(kp_name + "".join(weak_points))
        wp = weak_points[0] if weak_points else kp_name
        scored: list[tuple[int, dict[str, Any]]] = []
        for i, c in enumerate(cands, start=1):
            text = f"{c.get('title', '')} {c.get('snippet', '')} {c.get('source', '')}"
            overlap = (len(target & _char_bigrams(text)) / len(target)) if target else 0.0
            rel = max(60, min(99, round(60 + overlap * 39)))
            cred = _credibility_of(str(c.get("source", "")), str(c.get("url", "")))
            reason = f"契合你当前「{kp_name}」的学习，对补强「{wp}」很有帮助。"
            scored.append((rel, LLMClient._agg_item(c, i, type_=str(c.get("type") or ""), rel=rel, cred=cred, reason=reason)))
        scored.sort(key=lambda e: e[0], reverse=True)
        return [it for _, it in scored][:8]

    def _deepseek_aggregate(
        self, kp_name: str, weak_points: list[str], cands: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """真实聚合排序/评分/理由 + 契约清洗（URL 白名单防幻觉）。"""
        by_url = {str(c["url"]): c for c in cands}
        listing = [
            {
                "title": c.get("title"),
                "url": c.get("url"),
                "source": c.get("source"),
                "snippet": str(c.get("snippet") or "")[:200],
                "type": c.get("type"),
            }
            for c in cands
        ]
        system = (
            "你是学习资源聚合与审核 Agent。从候选搜索结果中筛选并排序出对该学习者最有价值的优质"
            '资源，仅输出 JSON：{"items": [{"type": "视频", "title": "...", "source": "...", '
            '"url": "...", "relevance": 0, "credibility": 0, "reason": "..."}]}。'
            f"type 只能取 {list(_AGG_TYPES)}；relevance/credibility 为 0-100 整数（相关度结合"
            "知识点与薄弱点、可信度结合来源权威性）；reason 一句中文说明为何推荐（结合薄弱点）；"
            "**url 必须原样取自候选列表，禁止编造或改写链接**；按 relevance 降序，最多 8 条。"
        )
        payload = {"knowledgePoint": kp_name, "weakPoints": weak_points, "candidates": listing}
        raw = llm_transport.chat(json.dumps(payload, ensure_ascii=False), system=system)
        data = _extract_json(raw)
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise LLMGenerationError("资源聚合输出无法解析为契约 JSON")
        items: list[dict[str, Any]] = []
        for it in data["items"]:
            if not isinstance(it, dict):
                continue
            url = str(it.get("url") or "").strip()
            cand = by_url.get(url)
            if cand is None:  # 防幻觉：只接受候选列表内的真实 URL
                continue
            reason = str(it.get("reason") or "").strip() or "与当前学习高度相关。"
            merged = dict(cand)
            if it.get("title"):
                merged["title"] = it["title"]
            if it.get("source"):
                merged["source"] = it["source"]
            items.append(
                LLMClient._agg_item(
                    merged,
                    len(items) + 1,
                    type_=str(it.get("type") or ""),
                    rel=_clamp_score(it.get("relevance"), 75),
                    cred=_clamp_score(it.get("credibility"), 85),
                    reason=reason,
                )
            )
        if not items:
            raise LLMGenerationError("资源聚合输出不含有效候选")
        items.sort(key=lambda x: x["relevance"], reverse=True)
        return items[:8]

    # ---- 康奈尔线索生成（接口文档 18.1，C2） -------------------------------
    def generate_cornell_cues(
        self, kp_id: str, kp_name: str, difficulty: str, description: str = ""
    ) -> dict[str, Any]:
        """生成康奈尔笔记线索（接口文档 18.1）。

        返回 {cues:[{id,type,text}], noteOutline:[{id,cueId,heading,points}],
        summaryHint, sources}（sources 复用 8.2 讲义 RAG 引用占位 _LECTURE_SOURCES）。
        - mock：确定性主题模板（已收录知识点精写线索，未收录参数化生成），cues 5-8 条；
        - deepseek：真实生成 + 契约清洗（cues 5-8 条、type 枚举、要点截断）；解析失败
          或上游异常 → 回落确定性主题模板（线索始终可用，不向路由抛 2001）。
        """
        self._ensure_supported()
        if self.is_mock:
            return self._mock_cornell(kp_id, kp_name, difficulty, description)
        try:
            return self._deepseek_cornell(kp_id, kp_name, difficulty, description)
        except LLMGenerationError as exc:
            logger.warning("康奈尔线索真实生成失败，回落主题模板：%s", exc)
            return self._mock_cornell(kp_id, kp_name, difficulty, description)

    @staticmethod
    def _assemble_cornell(
        cue_specs: list[tuple[str, str]],
        outline_specs: list[tuple[str, list[str]]],
        summary_hint: str,
    ) -> dict[str, Any]:
        """把 (cues, outline, summaryHint) 装配为契约结构（id 编号 + cueId 关联）。"""
        cues = [
            {"id": f"c{i + 1}", "type": t, "text": text}
            for i, (t, text) in enumerate(cue_specs)
        ]
        note_outline: list[dict[str, Any]] = []
        for i, (heading, points) in enumerate(outline_specs):
            # 第 i 条要点关联第 i 条线索（若该线索为问题）；否则通用要点 cueId=null
            cue_id = cues[i]["id"] if i < len(cues) and cues[i]["type"] == "question" else None
            note_outline.append(
                {"id": f"n{i + 1}", "cueId": cue_id, "heading": heading, "points": list(points)}
            )
        return {
            "cues": cues,
            "noteOutline": note_outline,
            "summaryHint": summary_hint,
            "sources": [dict(s) for s in _LECTURE_SOURCES],
        }

    def _mock_cornell(
        self, kp_id: str, kp_name: str, difficulty: str, description: str
    ) -> dict[str, Any]:
        """确定性康奈尔线索（mock / deepseek 兜底共用）。"""
        tpl = _CORNELL_TEMPLATES.get(kp_id)
        if tpl:
            return self._assemble_cornell(tpl["cues"], tpl["outline"], tpl["summaryHint"])
        desc = (description or "").strip()
        cue_specs = [
            ("question", f"{kp_name}要解决的核心问题是什么？"),
            ("question", f"{kp_name}的关键步骤 / 组成有哪些？"),
            ("question", f"{kp_name}在实践中如何应用？"),
            ("question", f"学习{kp_name}时最容易混淆的点是什么？"),
            ("keyword", f"{kp_name}核心概念"),
        ]
        outline_specs = [
            (f"{kp_name}核心概念", [desc[:24] if desc else f"{kp_name}的定义与作用", "关键组成与原理"]),
            ("实践应用", [f"{kp_name}的典型场景", "动手示例巩固理解"]),
        ]
        summary_hint = f"用一句话概括：{kp_name}是什么、解决了什么问题？"
        return self._assemble_cornell(cue_specs, outline_specs, summary_hint)

    def _deepseek_cornell(
        self, kp_id: str, kp_name: str, difficulty: str, description: str
    ) -> dict[str, Any]:
        """真实康奈尔线索生成 + 契约清洗（接口文档 18.1）。"""
        system = (
            "你是康奈尔笔记法的教学设计助手。针对给定知识点，产出供学生做笔记的"
            "「线索区」关键问题/关键词，以及「主笔记区」要点预填骨架。仅输出 JSON："
            '{"cues":[{"type":"question|keyword","text":"..."}],'
            '"noteOutline":[{"heading":"要点标题","points":["要点1","要点2"]}],'
            '"summaryHint":"总结区引导语"}。'
            "要求：cues 为 5-8 条（多为启发性问题、少量关键词）；noteOutline 2-4 条，"
            "每条 points 2-4 个；所有内容必须紧扣该知识点主题、简体中文、不要跑题；只输出 JSON。"
        )
        prompt = f"知识点：{kp_name}\n难度档：{difficulty}\n知识点说明：{description or kp_name}"
        raw = llm_transport.chat(prompt, system=system)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            raise LLMGenerationError("康奈尔线索输出无法解析为契约 JSON")
        return self._clean_cornell(data)

    @staticmethod
    def _clean_cornell(data: dict[str, Any]) -> dict[str, Any]:
        """康奈尔线索契约清洗：cues 5-8 条、type 枚举、noteOutline 要点截断。"""
        raw_cues = data.get("cues")
        if not isinstance(raw_cues, list):
            raise LLMGenerationError("康奈尔线索缺 cues 数组")
        cues: list[dict[str, Any]] = []
        for c in raw_cues:
            if not isinstance(c, dict):
                continue
            text = str(c.get("text") or "").strip()
            if not text:
                continue
            ctype = c.get("type") if c.get("type") in ("question", "keyword") else "question"
            cues.append({"id": f"c{len(cues) + 1}", "type": ctype, "text": text})
            if len(cues) >= 8:  # 上限 8 条（契约 5-8）
                break
        if len(cues) < 5:
            raise LLMGenerationError(f"康奈尔线索有效条目不足 5 条（得到 {len(cues)}）")
        note_outline: list[dict[str, Any]] = []
        for o in data.get("noteOutline") or []:
            if not isinstance(o, dict):
                continue
            heading = str(o.get("heading") or "").strip()
            if not heading:
                continue
            points = [
                str(p).strip() for p in (o.get("points") or []) if str(p).strip()
            ][:4]
            i = len(note_outline)
            cue_id = cues[i]["id"] if i < len(cues) and cues[i]["type"] == "question" else None
            note_outline.append(
                {"id": f"n{len(note_outline) + 1}", "cueId": cue_id, "heading": heading, "points": points}
            )
        summary_hint = str(data.get("summaryHint") or "").strip()
        return {
            "cues": cues,
            "noteOutline": note_outline,
            "summaryHint": summary_hint,
            "sources": [dict(s) for s in _LECTURE_SOURCES],
        }

    # ---- 费曼讲解评估（接口文档 18.2，C2；复用苏格拉底 Agent 的引导式取向） ------
    def feynman_eval(
        self,
        *,
        kp_id: str,
        kp_name: str,
        description: str,
        history: list[dict[str, str]],
        explanation: str,
    ) -> dict[str, Any]:
        """评估学生对某知识点的「费曼讲解」（接口文档 18.2）。

        返回 {feedback, gaps, score, followups, complete}——gaps 元素为
        {kpId, title, detail, severity}（应回看资源 review[] 由服务层按 kp 注入）。
        - mock：确定性评估——按 _FEYNMAN_CONCEPTS 比对学生讲解，定位「讲漏」的关键
          概念为 gaps，覆盖率折算 score，无随机、无网络；
        - deepseek：真实评估 + 契约清洗（severity 枚举、score 截断、gaps 标题非空），
          解析失败/上游异常 → 回落确定性评估（评估始终可用，不向路由抛 2001）。
        """
        self._ensure_supported()
        if self.is_mock:
            return self._mock_feynman(kp_id, kp_name, explanation)
        try:
            return self._deepseek_feynman(kp_id, kp_name, description, history, explanation)
        except LLMGenerationError as exc:
            logger.warning("费曼讲解评估真实生成失败，回落确定性评估：%s", exc)
            return self._mock_feynman(kp_id, kp_name, explanation)

    @staticmethod
    def _mock_feynman(kp_id: str, kp_name: str, explanation: str) -> dict[str, Any]:
        """确定性费曼评估：比对应覆盖概念，定位讲漏点为 gaps。"""
        text = explanation or ""
        low = text.lower()
        concepts = _FEYNMAN_CONCEPTS.get(kp_id)
        if not concepts:
            # 未收录知识点：按讲解充实度给确定性评估（仍指向真实 kp）
            if len(text.strip()) >= 40:
                return {
                    "feedback": f"你对「{kp_name}」做了讲解，已覆盖主要思路，可继续补充细节使其更完整。",
                    "gaps": [], "score": 70, "followups": [], "complete": True,
                }
            return {
                "feedback": f"你的讲解略显简略，试着把「{kp_name}」的核心机制讲得更具体一些。",
                "gaps": [{
                    "kpId": kp_id, "title": f"{kp_name}讲解过于简略",
                    "detail": "讲解信息量不足，难以判断理解程度，建议展开核心机制。",
                    "severity": "medium",
                }],
                "followups": [f"用你自己的话说说，{kp_name}最关键的一步是什么？"],
                "complete": False,
            }
        covered: list[str] = []
        gaps: list[dict[str, Any]] = []
        for c in concepts:
            if any(k.lower() in low for k in c["keys"]):
                covered.append(c["title"])
            else:
                gaps.append({
                    "kpId": kp_id, "title": c["title"], "detail": c["detail"],
                    "severity": c["severity"], "_ask": c["ask"],
                })
        total = len(concepts)
        score = round(len(covered) / total * 100) if total else 0
        gaps.sort(key=lambda g: _SEVERITY_RANK.get(g["severity"], 9))
        ack = f"你讲清了「{'、'.join(covered)}」。" if covered else "你的讲解还比较笼统。"
        if gaps:
            top = gaps[0]
            body = f"但还有需要补充的地方：最关键的是{top['title']}——{top['detail']}"
        else:
            body = "关键点都覆盖到了，讲解相当完整！"
        followups = [g["_ask"] for g in gaps[:2]]
        complete = not any(g["severity"] in _FEYNMAN_BLOCKING for g in gaps)
        clean_gaps = [
            {"kpId": g["kpId"], "title": g["title"], "detail": g["detail"], "severity": g["severity"]}
            for g in gaps
        ]
        return {
            "feedback": ack + body, "gaps": clean_gaps, "score": score,
            "followups": followups, "complete": complete,
        }

    def _deepseek_feynman(
        self,
        kp_id: str,
        kp_name: str,
        description: str,
        history: list[dict[str, str]],
        explanation: str,
    ) -> dict[str, Any]:
        """真实费曼评估 + 契约清洗（接口文档 18.2）。"""
        system = (
            "你是费曼学习法导师。学生会用自己的话讲解一个知识点，你要：① 点评其讲解的"
            "亮点与问题；② 找出讲错或讲漏的关键知识点（gaps）；③ 给出引导学生补讲的追问，"
            "但不要直接替学生把答案讲完。仅输出 JSON："
            '{"feedback":"点评(简体中文,不超过150字)","score":0到100整数(讲解完整度),'
            '"gaps":[{"title":"缺口标题","detail":"为什么这是缺口","severity":"high|medium|low"}],'
            '"followups":["引导补讲的追问"],"complete":true或false(是否已无 high/medium 缺口)}。只输出 JSON。'
        )
        prompt = (
            f"知识点：{kp_name}\n知识点说明：{description or kp_name}\n"
            f"学生讲解：{explanation}"
        )
        raw = llm_transport.chat(prompt, system=system, history=history)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            raise LLMGenerationError("费曼评估输出无法解析为契约 JSON")
        return self._clean_feynman(data, kp_id)

    @staticmethod
    def _clean_feynman(data: dict[str, Any], kp_id: str) -> dict[str, Any]:
        """费曼评估契约清洗：gaps 标题/说明非空、severity 枚举、score 截断、complete 布尔。

        gap.kpId 一律回正为当前知识点 id（不信任模型给的 kp，防幻觉引用）。
        """
        gaps: list[dict[str, Any]] = []
        for g in data.get("gaps") or []:
            if not isinstance(g, dict):
                continue
            title = str(g.get("title") or "").strip()
            detail = str(g.get("detail") or "").strip()
            if not title or not detail:
                continue
            sev = g.get("severity") if g.get("severity") in _SEVERITY_RANK else "medium"
            gaps.append({"kpId": kp_id, "title": title, "detail": detail, "severity": sev})
        gaps.sort(key=lambda x: _SEVERITY_RANK[x["severity"]])
        feedback = str(data.get("feedback") or "").strip()
        if not feedback:
            raise LLMGenerationError("费曼评估缺 feedback")
        try:
            score = int(data.get("score"))
        except (TypeError, ValueError):
            blocking = len([g for g in gaps if g["severity"] in _FEYNMAN_BLOCKING])
            score = max(0, 100 - 25 * blocking)
        score = max(0, min(100, score))
        followups = [
            str(f).strip() for f in (data.get("followups") or []) if str(f).strip()
        ][:3]
        complete = data.get("complete")
        if not isinstance(complete, bool):
            complete = not any(g["severity"] in _FEYNMAN_BLOCKING for g in gaps)
        return {
            "feedback": feedback, "gaps": gaps, "score": score,
            "followups": followups, "complete": complete,
        }

    # ---- 对话式画像抽取（接口文档 17.1，C1-b） ------------------------------
    def extract_portrait(
        self,
        *,
        message: str,
        context: dict[str, Any] | None,
        first_turn: bool,
    ) -> list[dict[str, Any]]:
        """从单轮自然语言抽取画像维度增量（接口文档 17.1 portraitUpdates）。

        返回 PortraitDimension[]（已契约清洗：key 白名单、source 枚举、
        inferred 低 confidence、无信号不编造）。
        - mock：确定性关键词抽取（无随机、无网络）；
        - deepseek：真实抽取 + 契约清洗（防幻觉 system 约束）。
        供 DialogueDiagnosticAgent 调用；问题编排策略在 Agent 侧（确定性）。
        """
        self._ensure_supported()
        if self.is_mock:
            return _mock_extract_portrait(message, context, first_turn)
        return self._deepseek_extract_portrait(message, context)

    def _deepseek_extract_portrait(
        self, message: str, context: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """真实画像维度抽取 + 契约清洗（17.1 防幻觉约束）。"""
        system = (
            "你是对话式学习画像抽取专家。从学生的自然语言中抽取**可确定**的画像维度，"
            '仅输出 JSON：{"updates":[{"key":"...","label":"...","value":"...",'
            '"score":0,"confidence":0.0,"source":"dialogue|inferred"}]}。'
            f"key 只能取自固定维度集 {list(_PORTRAIT_KEYS)}，label 用对应中文名；"
            "value 为简短中文描述；仅 knowledge_base 等可量化维度给 score（0-100 整数），"
            "其余维度省略 score；confidence 为 0-1 小数；"
            "学生明确陈述的维度用 source=dialogue，由上下文间接推断的用 source=inferred "
            "且 confidence≤0.6；无法从文本判断的维度一律不要输出（禁止编造）。"
        )
        payload = {"studentMessage": message, "knownContext": context or {}}
        raw = llm_transport.chat(
            json.dumps(payload, ensure_ascii=False), system=system
        )
        data = _extract_json(raw)
        if not isinstance(data, dict):
            raise LLMGenerationError("画像维度抽取输出无法解析为契约 JSON")
        return _sanitize_portrait_updates(data.get("updates"))

    # ---- 学习路径规划（接口文档 6.2，真实规划 Agent 的叙述层） ----------------
    def plan_path(
        self,
        *,
        profile: dict[str, Any],
        steps: list[dict[str, Any]],
        deterministic: bool = False,
    ) -> dict[str, Any]:
        """为已排序的路径步骤生成「为什么这样排」的理由 + 整体摘要。

        排序/优先级由 agents.planner_agent 按画像+掌握度确定性计算（科学排程），
        本方法只负责把每步的排程信号（signals）转成可读理由：
        - mock：按信号确定性模板（无随机、无网络，不同画像/掌握度 → 不同理由）；
        - deepseek：真实生成 + 契约清洗（reason 按 kpId 回填，缺失回落模板），
          解析失败/上游异常 → 回落 mock，保证演示稳定（不向路由抛 2001）。
        - deterministic=True：**强制走确定性模板、零网络**（供 GET /learning-path 实时
          重算用——画像变即重算、不阻塞页面、不计费）。

        入参 steps[i]：{kpId, topic, order, status, signals:{weak,mastered,
        foundational,jobBoost}}；profile：{foundationLevel, goal, pace, jobName}。
        返回 {reasons: {kpId: reason}, summary: str}。
        """
        self._ensure_supported()
        if deterministic or self.is_mock:
            return self._mock_plan_path(profile, steps)
        try:
            return self._deepseek_plan_path(profile, steps)
        except LLMGenerationError as exc:
            logger.warning("路径规划理由真实生成失败，回落确定性模板：%s", exc)
            return self._mock_plan_path(profile, steps)

    @staticmethod
    def _mock_plan_path(
        profile: dict[str, Any], steps: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """确定性规划理由（mock / deepseek 兜底共用）。按排程信号分支产出理由。"""
        job_name = (profile.get("jobName") or "").strip()
        reasons: dict[str, str] = {}
        weak_count = 0
        mastered_count = 0

        def _ability(sig: dict[str, Any]) -> str:
            s = sig.get("abilityScore")
            return f"（微测能力分 {int(s)}）" if isinstance(s, (int, float)) and not isinstance(s, bool) else ""

        for step in steps:
            sig = step.get("signals") or {}
            topic = step.get("topic") or step.get("kpId")
            order = step.get("order")
            if sig.get("mastered"):
                mastered_count += 1
                reasons[step["kpId"]] = (
                    f"你已掌握「{topic}」（测验通过），后置到第 {order} 步用于巩固复习，可快速跳过。"
                )
            elif sig.get("proficient"):
                # 微测能力分达标但未正式通过测验 → 后置略读（靠测：用实测分判定"已会"）
                mastered_count += 1
                reasons[step["kpId"]] = (
                    f"微测显示你对「{topic}」已基本达标{_ability(sig)}，后置到第 {order} 步快速复习、可略读。"
                )
            elif sig.get("jobBoost") and sig.get("weak"):
                weak_count += 1
                lead = f"目标岗位「{job_name}」" if job_name else "你的目标岗位"
                reasons[step["kpId"]] = (
                    f"{lead}对「{topic}」要求高且你尚薄弱{_ability(sig)}，按先修顺序排在第 {order} 步并列为重点强化项。"
                )
            elif sig.get("weak") and sig.get("foundational"):
                weak_count += 1
                reasons[step["kpId"]] = (
                    f"「{topic}」是后续内容的基础且你尚未掌握{_ability(sig)}，优先安排在第 {order} 步打牢根基。"
                )
            elif sig.get("weak"):
                weak_count += 1
                reasons[step["kpId"]] = (
                    f"「{topic}」是你的薄弱点{_ability(sig)}，按先修顺序安排在第 {order} 步集中攻克。"
                )
            else:
                reasons[step["kpId"]] = (
                    f"按知识先修依赖，「{topic}」承接前序内容，安排在第 {order} 步进阶。"
                )
        level = profile.get("foundationLevel") or "中等"
        style = (profile.get("style") or "").strip()
        pace_type = (profile.get("paceType") or "").strip()
        how = ""
        if style or pace_type:
            tag = "·".join(t for t in (style, pace_type) if t)
            how = f"；并按你的学习偏好（{tag}）为每步默认推荐最适合的资源形式"
        summary = (
            f"本路径依据你的画像（基础{level}）与各知识点实测能力规划：将 {weak_count} 个薄弱/未掌握点"
            f"按先修顺序前置，{mastered_count} 个已达标点后置复习，共 {len(steps)} 步{how}，"
            "每步配套讲义/思维导图/图解/视频/题库资源。"
        )
        return {"reasons": reasons, "summary": summary}

    def _deepseek_plan_path(
        self, profile: dict[str, Any], steps: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """真实规划理由生成 + 契约清洗（reason 按 kpId 回填，缺失回落模板）。"""
        system = (
            "你是个性化学习路径规划专家。给定学习者画像与一条**已排好序**的学习路径"
            "（每步含 kpId/topic/order/status 及排程信号 signals），为每一步用一句话"
            "解释「为什么排在这个位置」，并给出整体路径摘要。仅输出 JSON："
            '{"reasons":[{"kpId":"...","reason":"..."}],"summary":"..."}。'
            "理由必须扣住该步信号：weak=薄弱点优先、mastered=已掌握后置复习、"
            "foundational=先修基础、jobBoost=目标岗位高需求前置；语言简体中文、"
            "每条不超过 50 字；不得改变给定顺序，只解释顺序；只输出 JSON。"
        )
        payload = {"profile": profile, "steps": steps}
        raw = llm_transport.chat(json.dumps(payload, ensure_ascii=False), system=system)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            raise LLMGenerationError("路径规划输出无法解析为契约 JSON")
        valid_ids = {s["kpId"] for s in steps}
        reasons: dict[str, str] = {}
        for item in data.get("reasons") or []:
            if not isinstance(item, dict):
                continue
            kid = item.get("kpId")
            reason = str(item.get("reason") or "").strip()
            if kid in valid_ids and reason:
                reasons[kid] = reason
        # 缺失步骤回落确定性模板（保证每步都有理由）
        fallback = self._mock_plan_path(profile, steps)
        for step in steps:
            reasons.setdefault(step["kpId"], fallback["reasons"][step["kpId"]])
        summary = str(data.get("summary") or "").strip() or fallback["summary"]
        return {"reasons": reasons, "summary": summary}

    # ---- 通用补全（B5-a：供 Agent 节点调用） -------------------------------
    def complete(
        self,
        prompt: str,
        *,
        agent_id: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """通用补全入口（B5-a 工作流骨架）。

        Agent 先经 services.prompts.get_template() 现读模板并渲染占位符，
        再把渲染后的 prompt 交本方法。mock provider 按 agent 类型返回
        **确定性结构化输出**（无随机、无网络）；variables 仅供 mock 产出
        与输入相关的确定性内容，真实 provider（B5-b）忽略该参数、只发 prompt。
        """
        self._ensure_supported()
        variables = variables or {}
        if not self.is_mock:
            return self._deepseek_complete(prompt, agent_id)
        if agent_id == "diagnosis":
            return self._mock_diagnosis(variables)
        if agent_id == "generation":
            return self._mock_generation(variables)
        if agent_id == "critic":
            return self._mock_critic(variables)
        raise ValueError(f"未知 agent_id：{agent_id}（固定 3 项：diagnosis/generation/critic）")

    def _deepseek_complete(self, prompt: str, agent_id: str) -> dict[str, Any]:
        """真实 Agent 补全：只发渲染后 prompt + 按 agent 类型的输出约束。"""
        if agent_id == "generation":
            text = llm_transport.chat(
                prompt,
                system="你是领域知识讲义生成专家。直接输出 Markdown 讲义正文，"
                "不要输出讲义之外的解释或前后缀。",
            )
            return {"markdown": _strip_md_fence(text)}
        if agent_id == "diagnosis":
            text = llm_transport.chat(
                prompt,
                system='请仅输出 JSON：{"weakKpIds": ["知识点id"], '
                '"summary": "一句话诊断摘要", "reasoning": "诊断依据"}',
            )
            data = _extract_json(text)
            if isinstance(data, dict) and data.get("summary"):
                weak = [str(k) for k in (data.get("weakKpIds") or []) if k]
                return {
                    "weakKpIds": weak,
                    "summary": str(data["summary"]),
                    "reasoning": str(data.get("reasoning") or ""),
                }
            # 非 JSON 输出 → 自由文本兜底，不中断工作流
            return {"weakKpIds": [], "summary": text[:100], "reasoning": text}
        if agent_id == "critic":
            raise LLMGenerationError(
                "critic 在真实模式走本地逐句接地校验（agents.critic_agent），不经 LLM 通道"
            )
        raise ValueError(f"未知 agent_id：{agent_id}（固定 3 项：diagnosis/generation/critic）")

    @staticmethod
    def _mock_diagnosis(variables: dict[str, Any]) -> dict[str, Any]:
        """诊断 Agent mock：基于**该用户真实画像 + 掌握度**定位薄弱点（因人而异）。

        - 薄弱点：目标 kp + 该用户尚未通过（status≠passed）的其它知识点；不足 3 项时
          以固定后备维度补齐，保证输出稳定；
        - 诊断依据（reasoning）引用该用户画像摘要与掌握度计数，不同用户 / 不同掌握度
          → 文案不同，不再是全局同一句模板。
        """
        target_kp = variables.get("kpId") or "attention"
        target_name = variables.get("kpName") or target_kp
        profile_summary = (variables.get("profileSummary") or "").strip()
        try:
            mastery_map = json.loads(variables.get("masteryStatus") or "{}")
            if not isinstance(mastery_map, dict):
                mastery_map = {}
        except (ValueError, TypeError):
            mastery_map = {}

        not_passed = [
            k for k, v in mastery_map.items() if v != "passed" and k != target_kp
        ]
        weak = [target_kp] + not_passed
        for fallback in ("transformer", "finetune"):
            if len(weak) >= 3:
                break
            if fallback not in weak:
                weak.append(fallback)
        weak = weak[:3]

        passed_n = sum(1 for v in mastery_map.values() if v == "passed")
        pending_n = sum(1 for v in mastery_map.values() if v != "passed")
        basis = profile_summary[:60] if profile_summary else "画像尚未采集（按通用基线）"
        reasoning = (
            f"依据该用户画像（{basis}）与掌握度（已通过 {passed_n} 项、待巩固 "
            f"{pending_n} 项）：「{target_name}」等 {len(weak)} 处为当前薄弱点。"
        )
        return {
            "weakKpIds": weak,
            "summary": f"检测到 {len(weak)} 处薄弱点，建议优先学习「{target_name}」",
            "reasoning": reasoning,
        }

    def _mock_generation(self, variables: dict[str, Any]) -> dict[str, Any]:
        """生成 Agent mock：确定性递进讲义产出（按 kpName/难度 + 画像能力档 depthTier）。

        depthTier 由工作流 generation_node 依当前用户画像派生（advanced/beginner/basic）；
        直出 /resource/lecture 不传 → tier=None 走难度基线（与 B5b/B10 契约一致）。
        """
        kp_name = variables.get("kpName") or "神经网络"
        difficulty = variables.get("difficulty") or "初级"
        tier = variables.get("depthTier") or None
        return {
            "markdown": self._lecture_markdown(
                kp_name, difficulty, variables.get("description", ""), tier
            ),
        }

    @staticmethod
    def _mock_critic(variables: dict[str, Any]) -> dict[str, Any]:
        """审核 Agent mock：默认通过；测试钩子可强制低分（验证重试/降级路径）。"""
        if _force_critic_low:
            return {
                "passed": False,
                "validationScore": 0.42,
                "hallucinationRate": 0.18,
                "issues": ["第 2 段「梯度直觉」未在检索上下文中找到接地来源（测试钩子注入）"],
            }
        return {
            "passed": True,
            "validationScore": 0.93,
            "hallucinationRate": _LECTURE_HALLUCINATION_RATE,
            "issues": [],
        }


# ---- 测试钩子：强制 critic 返回低分（B5-a 验证重试→降级路径） -----------------
_force_critic_low: bool = False


def set_force_critic_low(enabled: bool) -> None:
    """测试钩子：True 时 mock critic 恒返回低分（validationScore=0.42）。

    仅影响 mock provider；pytest 用例 finally/fixture 中必须复位 False。
    """
    global _force_critic_low
    _force_critic_low = bool(enabled)


# ---- 内容安全过滤：中心钝化点（统一包裹全部生成方法的返回，覆盖所有生成器） ------
# 所有面向学习者的 LLM 生成文本都经 LLMClient 公共方法返回，这里在一个集中点把它们
# 统一过一道内容安全过滤（讲义/对话/费曼/苏格拉底/线索/图解/视频/路径理由/画像叙述/
# 错题强化全覆盖），避免在各路由/服务分散重复。仅在输出环节加过滤，不改任何方法签名。
_GUARDED_METHODS: tuple[str, ...] = (
    "extract_profile",       # 4.1 画像抽取
    "generate_narrative",    # 4.2 画像叙述
    "generate_lecture",      # 8.2 讲义（mock 直出）
    "generate_video_script",  # 8.3 视频脚本
    "generate_diagram",      # 8.5 知识图解
    "generate_flashcards",   # 20.7 文档学习·闪卡
    "generate_doc_quiz",     # 20.6 文档学习·练习题
    "generate_overview",     # 20.8 文档学习·文档概览（NotebookLM 式速读）
    "generate_reinforcement",  # 9.2 错题强化
    "tutor_chat",            # 8.7 苏格拉底（JSON）
    "tutor_suggestions",     # 15.4 苏格拉底快捷建议
    "generate_cornell_cues",  # 18.1 康奈尔线索
    "feynman_eval",          # 18.2 费曼评估
    "extract_portrait",      # 17.1 对话画像抽取
    "plan_path",             # 6.2 学习路径理由
    "complete",              # B5-a Agent 通用补全（讲义生成 / 诊断）
)


def _install_content_guard() -> None:
    """在类定义后一次性包裹全部生成方法（含流式 tutor），实现单一中心钝化点。"""
    from app.core import content_safety

    for name in _GUARDED_METHODS:
        setattr(LLMClient, name, content_safety.guarded(getattr(LLMClient, name)))
    LLMClient.tutor_chat_stream = content_safety.guarded_stream(  # type: ignore[assignment]
        LLMClient.tutor_chat_stream
    )


_install_content_guard()


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """返回进程内 LLMClient 单例（按当前 settings.llm_provider）。"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
