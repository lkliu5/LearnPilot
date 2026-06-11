"""LLM 调用适配层（B2-a）。

CLAUDE.md 工程纪律：所有生成类接口必须经本层调用，provider 可配
`mock / deepseek / qwen / anthropic`。本阶段只落地 **mock** provider——按接口
契约返回结构化假数据，无任何 API Key 即可跑通全链路；真实 provider（deepseek /
qwen / anthropic）仅留接口占位，抛 NotImplementedError，B5 阶段接入真实生成与 RAG。

设计：
- 语义化方法（parse_skills / generate_narrative）而非裸 `complete()`，因为各生成
  接口需返回与接口文档逐字对齐的结构化数据；mock 在此确定性产出，B5 改为
  「RAG 检索 → 生成 Agent → 审核 Agent」时保持方法签名不变，仅替换实现。
- `get_llm()` 返回进程内单例，按 settings.llm_provider 选择实现。

字段口径依据《后端接口文档》4.1（ParsedProfile.skills）、4.2（Narrative）、
2.4（雷达 6 维固定键名）。
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings

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
    def _ensure_supported(self) -> None:
        if self.provider != "mock":
            raise NotImplementedError(
                f"LLM provider '{self.provider}' 尚未实现："
                "deepseek / qwen / anthropic 真实生成将在 B5 阶段接入；"
                "当前请将 settings.llm_provider 配置为 'mock'。"
            )

    # ---- 生成类方法（mock 实现） -----------------------------------------
    def parse_skills(self, text: str, source: str) -> list[dict[str, Any]]:
        """从材料文本抽取 6 维技能画像（接口文档 4.1 skills）。

        mock 口径：以基线值为底，命中关键词的维度小幅抬升（上限 100），
        每项 source 取调用方传入的来源类型（resume|ocr|text|manual）。
        无文本（纯手动）时 source 应为 manual，且仅给基线值不编造经历。
        """
        self._ensure_supported()
        levels = list(_MOCK_BASELINE)
        lowered = (text or "").lower()
        for keyword, dim in _KEYWORD_TO_DIM.items():
            if keyword in lowered:
                levels[dim] = min(100, levels[dim] + 8)
        return [
            {"name": name, "level": level, "source": source}
            for name, level in zip(ABILITY_DIMENSIONS, levels)
        ]

    def generate_narrative(
        self,
        draft: dict[str, Any],
        materials: list[dict[str, Any]],
        target_job: dict[str, Any] | None,
    ) -> list[list[dict[str, Any]]]:
        """生成两段式带来源标注的画像叙述（接口文档 4.2 paragraphs）。

        返回恰好两段，每段为 NarrativeSegment 数组：
        - 第一段：背景与优势（tone=key，sourceId 指向首个材料）；
        - 第二段：与目标岗位差距（tone=weak，定位最弱维度）。
        调用方负责在「无材料」时不调用本方法（叙述应返回 null，防幻觉）。
        """
        self._ensure_supported()
        skills: list[dict[str, Any]] = draft.get("skills") or []
        major = (draft.get("major") or {}).get("value") or "人工智能"
        # 首个材料作为关键句的来源锚点
        source_id = materials[0]["id"] if materials else None

        # 优势 / 薄弱维度（按 level）
        if skills:
            strongest = max(skills, key=lambda s: s.get("level", 0))
            weakest = min(skills, key=lambda s: s.get("level", 0))
        else:
            strongest = {"name": ABILITY_DIMENSIONS[0]}
            weakest = {"name": ABILITY_DIMENSIONS[-1]}

        para1 = [
            {"text": "该学习者具备 ", "sourceId": None},
            {"text": major, "tone": "key", "sourceId": source_id},
            {"text": " 专业背景，", "sourceId": None},
            {"text": f"{strongest['name']}能力突出", "tone": "key", "sourceId": source_id},
            {"text": "。"},
        ]

        job_name = (target_job or {}).get("name")
        lead = f"与目标岗位「{job_name}」相比，" if job_name else "与目标岗位要求相比，"
        para2 = [
            {"text": lead, "sourceId": None},
            {"text": f"{weakest['name']}能力偏弱", "tone": "weak"},
            {"text": "，建议作为后续学习路径的优先强化方向。"},
        ]
        return [para1, para2]

    def generate_lecture(
        self, kp_id: str, kp_name: str, difficulty: str, description: str = ""
    ) -> dict[str, Any]:
        """生成自适应讲义（接口文档 8.2）。返回 markdown + sources + hallucinationRate。

        mock 口径：按难度档（入门/初级/高级）确定性产出三种讲述风格的 Markdown
        （初级/高级含 ```python 代码块```），sources/hallucinationRate 为占位常量。
        B5 替换为「RAG 检索 → 生成 Agent → 审核 Agent」，方法签名不变，sources 由
        真实命中切片回填、hallucinationRate 按 15.3 逐句接地口径计算。
        """
        self._ensure_supported()
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
        与输入相关的确定性内容，真实 provider（B5-b）将忽略该参数、只发 prompt。
        """
        self._ensure_supported()
        variables = variables or {}
        if agent_id == "diagnosis":
            return self._mock_diagnosis(variables)
        if agent_id == "generation":
            return self._mock_generation(variables)
        if agent_id == "critic":
            return self._mock_critic(variables)
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
