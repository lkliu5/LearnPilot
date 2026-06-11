"""测试全局基线（B5-b）。

backend/.env 在真实演示环境可能配置 LLM_PROVIDER=deepseek + 真实 Key；
测试套件必须与环境无关：一律以 mock provider 为基线（确定性、零网络、零计费），
deepseek 路径用例自行构造 LLMClient("deepseek") 并 monkeypatch llm_deepseek.chat
（见 test_b5b.py 的 deepseek_llm fixture），不受本基线影响。
"""
from __future__ import annotations

import pytest

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
