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
import re
from typing import Any

from app.core import llm_deepseek
from app.core.config import settings
from app.core.llm_deepseek import LLMGenerationError  # 路由层从本模块导入（re-export）

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

# 关键词 → 维度索引，用于在 mock 中「读到」材料文本时小幅抬升对应维度，
# 体现解析的可解释性；未命中则用基线值（不编造、不随机）。
# 接口文档 4.1 枚举（真实抽取的契约清洗白名单；非法值回落「其他」）
_EDUCATION_ENUM = ("本科", "硕士", "博士", "其他")
_MAJOR_ENUM = ("计算机科学", "电子信息", "人工智能", "软件工程", "数据科学", "其他")
_GOAL_ENUM = ("职业培训", "技能认证", "学术研究", "兴趣学习", "其他")

# 容错 JSON 提取：取首个 { 到末个 } 的最大块（模型常在 JSON 外包裹说明文字）
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.S)


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
