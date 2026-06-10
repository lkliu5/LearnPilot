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


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """返回进程内 LLMClient 单例（按当前 settings.llm_provider）。"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
