"""生成模型注册表（模型管理：界面切换 LLM 模型 + 接入魔搭 ModelScope）。

- 注册表：一组可选生成模型，每个含 显示名 / provider / base_url / model_id——
  默认 DeepSeek 官方模型 + 魔搭若干在线模型（settings.modelscope_models 可配）；
  ``settings.llm_provider == "mock"`` 时注册表仅含内置 mock（无 Key 全链路可跑，纪律不变）。
- 「当前模型」为进程内运行态（轻量栈，无需持久化）；**默认 = 既有 DeepSeek**，
  不切换则行为与本功能上线前逐字一致（向后兼容）。
- 切换仅影响 app/core/llm_transport.py 后续分发到哪个上游通道，
  不改任何既有生成接口签名 / 字段。

provider 语义：
  deepseek   → 既有 app.core.llm_deepseek 通道（默认）；
  modelscope → app.core.llm_modelscope（OpenAI 兼容，base_url 指向魔搭 API-Inference）；
  mock       → LLMClient 确定性假数据（llm_provider=mock 时的唯一条目，仅展示用）。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class ModelSpec:
    """注册表中的一个可选生成模型。"""

    id: str  # 注册表内唯一 id（deepseek 用模型名、魔搭用 org/model_id）
    label: str  # 界面显示名
    provider: str  # deepseek | modelscope | mock
    base_url: str
    model_id: str  # 上游 API 的 model 参数


# 当前模型 id（进程内运行态；None = 未显式切换 → 取注册表首项即默认 DeepSeek/mock）
_current_id: str | None = None


def _registry() -> list[ModelSpec]:
    """按当前 settings 构建注册表（每次现算：测试/热配均即时生效，构建成本可忽略）。"""
    if settings.llm_provider == "mock":
        return [
            ModelSpec(
                id="mock",
                label="内置模拟（离线 Mock）",
                provider="mock",
                base_url="",
                model_id="mock",
            )
        ]
    specs = [
        ModelSpec(
            id=settings.deepseek_model,
            label="DeepSeek（官方 · 默认）",
            provider="deepseek",
            base_url=settings.deepseek_base_url,
            model_id=settings.deepseek_model,
        )
    ]
    for mid in (m.strip() for m in settings.modelscope_models.split(",")):
        if not mid:
            continue
        specs.append(
            ModelSpec(
                id=mid,
                label=f"{mid.split('/')[-1]}（魔搭）",
                provider="modelscope",
                base_url=settings.modelscope_base_url,
                model_id=mid,
            )
        )
    return specs


def _available(spec: ModelSpec) -> bool:
    """该模型当前是否具备直连能力（未配 Key 仍可选，调用时自动回落，见 llm_transport）。"""
    if spec.provider == "deepseek":
        return bool(settings.deepseek_api_key)
    if spec.provider == "modelscope":
        return bool(settings.modelscope_api_key)
    return True  # mock 恒可用


def current() -> ModelSpec:
    """当前生成模型；未切换 / 切换目标已不在注册表（配置变更）→ 注册表首项（默认）。"""
    specs = _registry()
    if _current_id is not None:
        for s in specs:
            if s.id == _current_id:
                return s
    return specs[0]


def set_current(model_id: str) -> ModelSpec:
    """切换当前生成模型（后续生成即走该模型）。未知 id → KeyError（路由映射 1001）。"""
    global _current_id
    for s in _registry():
        if s.id == model_id:
            _current_id = s.id
            return s
    raise KeyError(model_id)


def reset() -> None:
    """回到默认模型（测试隔离用）。"""
    global _current_id
    _current_id = None


def snapshot() -> dict:
    """接口 21.1/21.2 响应体：{models: [...], current}。"""
    cur = current()
    return {
        "models": [
            {
                "id": s.id,
                "label": s.label,
                "provider": s.provider,
                "available": _available(s),
                "isCurrent": s.id == cur.id,
            }
            for s in _registry()
        ],
        "current": cur.id,
    }
