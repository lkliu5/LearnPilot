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

from app.core import llm_deepseek
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

# 讲义资源页难度档（接口文档 8.2 备注：入门|初级|高级，与路径难度档不同）
LECTURE_DIFFICULTIES: list[str] = ["入门", "初级", "高级"]

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
_PORTRAIT_SOURCES: tuple[str, ...] = ("dialogue", "manual", "inferred")
# inferred（推断）维度 confidence 上限（17.1：inferred 须给较低 confidence）
_INFERRED_CONFIDENCE_CAP: float = 0.6

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
        cleaned: dict[str, Any] = {
            "key": key,
            "label": _PORTRAIT_LABELS[key],
            "value": value,
            "confidence": round(confidence, 2),
            "source": source,
        }
        score = item.get("score")
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            cleaned["score"] = max(0, min(100, int(score)))
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


_QUESTION_TYPES = ("single", "multiple", "boolean")


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
        raw = llm_deepseek.chat(f"材料文本：\n{text}", system=system)
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
        raw = llm_deepseek.chat(
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
        self, kp_id: str, kp_name: str, difficulty: str, description: str = ""
    ) -> dict[str, Any]:
        """生成自适应讲义（接口文档 8.2）。返回 markdown + sources + hallucinationRate。

        mock 口径：按难度档（入门/初级/高级）确定性产出三种讲述风格的 Markdown
        （初级/高级含 ```python 代码块```），sources/hallucinationRate 为占位常量。
        真实模式讲义不走本方法——经 workflows.run_learning_workflow
        「RAG 检索 → 生成 Agent → 审核 Agent」生成（services.resource 分支）。
        """
        if not self.is_mock:
            raise LLMGenerationError(
                "真实模式讲义应经 run_learning_workflow 生成，不应调用 generate_lecture"
            )
        return {
            "markdown": self._lecture_markdown(kp_name, difficulty, description),
            "sources": [dict(s) for s in _LECTURE_SOURCES],
            "hallucinationRate": _LECTURE_HALLUCINATION_RATE,
        }

    @staticmethod
    def _lecture_markdown(name: str, difficulty: str, description: str) -> str:
        """按难度档生成讲义 Markdown（确定性 mock）。"""
        desc = description or f"{name}是本知识点的核心内容。"
        code_block = (
            "```python\n"
            "import numpy as np\n\n"
            "def forward(x, w, b):\n"
            "    z = np.dot(x, w) + b      # 加权求和 + 偏置\n"
            "    return np.maximum(0, z)   # ReLU 激活\n\n"
            "print(forward(np.array([0.5, 0.8]), np.array([0.4, 0.7]), 0.1))\n"
            "```"
        )
        if difficulty == "入门":
            return (
                f"# {name}（入门版）\n\n"
                f"> 本讲义由**领域知识生成 Agent**按「入门」难度生成——用最直白的比喻，少公式。\n\n"
                f"## 一、先建立直觉\n\n{desc}\n\n"
                f"不必纠结公式：先把握「{name}」要解决什么问题、大致怎么做。\n\n"
                f"## 二、一句话理解\n\n"
                f"**{name}**的核心，是用一套可学习的规则，把输入逐步变换为更有用的表示。\n\n"
                f"> 小结：先有直觉，下一步看「初级版」了解具体计算与代码。"
            )
        if difficulty == "高级":
            return (
                f"# {name}（高级版）\n\n"
                f"> 本讲义由**领域知识生成 Agent**按「高级」难度生成——侧重数学形式化与工程细节。\n\n"
                f"## 一、问题形式化\n\n{desc}\n\n"
                f"将{name}抽象为参数化映射 \\(f_\\theta\\)，以损失 \\(L\\) 为目标，"
                f"经梯度 \\(\\partial L/\\partial \\theta\\) 迭代优化。\n\n"
                f"## 二、关键实现\n\n{code_block}\n\n"
                f"## 三、工程权衡\n\n"
                f"- 数值稳定性：注意归一化与初始化对收敛的影响。\n"
                f"- 计算/显存：在精度与吞吐间按部署约束取舍。\n\n"
                f"> 小结：掌握形式化与实现细节后，可结合「测验」检验理解深度。"
            )
        # 默认「初级」
        return (
            f"# {name}（初级版）\n\n"
            f"> 本讲义由**领域知识生成 Agent**适配为「初级」难度，并经**内容审核 Agent** RAG 交叉校验（幻觉率 <5%）。\n\n"
            f"## 一、核心概念\n\n{desc}\n\n"
            f"## 二、动手理解\n\n{code_block}\n\n"
            f"## 三、要点回顾\n\n"
            f"- 抓住「{name}」的输入、变换与输出三段式。\n"
            f"- 通过代码与示例建立可复现的认知。\n\n"
            f"> 小结：完成本节后建议进入「测验」巩固，或切到「高级版」深入。"
        )


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
        raw = llm_deepseek.chat(prompt, system=system)
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
            raw = llm_deepseek.chat(prompt + feedback, system=system)
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
        reply = llm_deepseek.chat(
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
            return llm_deepseek.chat_stream(
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
        raw = llm_deepseek.chat(
            json.dumps(payload, ensure_ascii=False), system=system
        )
        data = _extract_json(raw)
        if not isinstance(data, dict):
            raise LLMGenerationError("画像维度抽取输出无法解析为契约 JSON")
        return _sanitize_portrait_updates(data.get("updates"))

    # ---- 学习路径规划（接口文档 6.2，真实规划 Agent 的叙述层） ----------------
    def plan_path(
        self, *, profile: dict[str, Any], steps: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """为已排序的路径步骤生成「为什么这样排」的理由 + 整体摘要。

        排序/优先级由 agents.planner_agent 按画像+掌握度确定性计算（科学排程），
        本方法只负责把每步的排程信号（signals）转成可读理由：
        - mock：按信号确定性模板（无随机、无网络，不同画像/掌握度 → 不同理由）；
        - deepseek：真实生成 + 契约清洗（reason 按 kpId 回填，缺失回落模板），
          解析失败/上游异常 → 回落 mock，保证演示稳定（不向路由抛 2001）。

        入参 steps[i]：{kpId, topic, order, status, signals:{weak,mastered,
        foundational,jobBoost}}；profile：{foundationLevel, goal, pace, jobName}。
        返回 {reasons: {kpId: reason}, summary: str}。
        """
        self._ensure_supported()
        if self.is_mock:
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
        for step in steps:
            sig = step.get("signals") or {}
            topic = step.get("topic") or step.get("kpId")
            order = step.get("order")
            if sig.get("mastered"):
                mastered_count += 1
                reasons[step["kpId"]] = (
                    f"你已掌握「{topic}」（测验通过），后置到第 {order} 步用于巩固复习，可快速跳过。"
                )
            elif sig.get("jobBoost") and sig.get("weak"):
                weak_count += 1
                lead = f"目标岗位「{job_name}」" if job_name else "你的目标岗位"
                reasons[step["kpId"]] = (
                    f"{lead}对「{topic}」要求高且你尚薄弱，按先修顺序排在第 {order} 步并列为重点强化项。"
                )
            elif sig.get("weak") and sig.get("foundational"):
                weak_count += 1
                reasons[step["kpId"]] = (
                    f"「{topic}」是后续内容的基础且你尚未掌握，优先安排在第 {order} 步打牢根基。"
                )
            elif sig.get("weak"):
                weak_count += 1
                reasons[step["kpId"]] = (
                    f"「{topic}」是你的薄弱点，按先修顺序安排在第 {order} 步集中攻克。"
                )
            else:
                reasons[step["kpId"]] = (
                    f"按知识先修依赖，「{topic}」承接前序内容，安排在第 {order} 步进阶。"
                )
        level = profile.get("foundationLevel") or "中等"
        summary = (
            f"本路径依据你的画像（基础{level}）与知识掌握度规划：将 {weak_count} 个薄弱/未掌握点"
            f"按先修顺序前置，{mastered_count} 个已掌握点后置复习，共 {len(steps)} 步，"
            "每步配套讲义/思维导图/视频/题库资源。"
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
        raw = llm_deepseek.chat(json.dumps(payload, ensure_ascii=False), system=system)
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
            text = llm_deepseek.chat(
                prompt,
                system="你是领域知识讲义生成专家。直接输出 Markdown 讲义正文，"
                "不要输出讲义之外的解释或前后缀。",
            )
            return {"markdown": _strip_md_fence(text)}
        if agent_id == "diagnosis":
            text = llm_deepseek.chat(
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
        """诊断 Agent mock：定位薄弱知识点（确定性：取基线最低两维对应 kp）。"""
        target_kp = variables.get("kpId") or "attention"
        target_name = variables.get("kpName") or target_kp
        weak = [target_kp] + [k for k in ("transformer", "finetune") if k != target_kp]
        return {
            "weakKpIds": weak[:3],
            "summary": f"检测到 {len(weak[:3])} 处知识盲区，建议优先学习「{target_name}」",
            "reasoning": "依据画像基线与掌握度：注意力机制/Transformer/大模型微调维度偏弱。",
        }

    def _mock_generation(self, variables: dict[str, Any]) -> dict[str, Any]:
        """生成 Agent mock：复用 B2 的确定性讲义产出（按 kpName/难度）。"""
        kp_name = variables.get("kpName") or "神经网络"
        difficulty = variables.get("difficulty") or "初级"
        return {
            "markdown": self._lecture_markdown(
                kp_name, difficulty, variables.get("description", "")
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


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """返回进程内 LLMClient 单例（按当前 settings.llm_provider）。"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
