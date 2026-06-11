"""测试全局基线（B5-b）。

backend/.env 在真实演示环境可能配置 LLM_PROVIDER=deepseek + 真实 Key；
测试套件必须与环境无关：一律以 mock provider 为基线（确定性、零网络、零计费），
deepseek 路径用例自行构造 LLMClient("deepseek") 并 monkeypatch llm_deepseek.chat
（见 test_b5b.py 的 deepseek_llm fixture），不受本基线影响。
"""
from __future__ import annotations

import pytest

# Windows 已知问题（B8）：torch DLL 在非主线程首次加载会 access violation 崩溃进程。
# TestClient 的请求处理都在 portal 线程进行，kb/RAG 模块的惰性导入会在该线程触发
# torch 导入 → 在 pytest 主线程先行导入 embeddings（连带 sentence_transformers/torch），
# 之后任何线程再 import 仅命中 sys.modules 缓存，不再加载 DLL。
from app.rag import embeddings as _warmup_embeddings  # noqa: F401  isort: skip

from app.core import llm as llm_mod
from app.core.config import settings


@pytest.fixture(scope="session", autouse=True)
def _force_mock_provider():
    """整个测试会话强制 mock provider，并重置 LLM 单例。"""
    original = settings.llm_provider
    settings.llm_provider = "mock"
    llm_mod._client = None
    yield
    settings.llm_provider = original
    llm_mod._client = None
