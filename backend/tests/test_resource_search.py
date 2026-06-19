"""外部资源·联网搜索聚合 契约测试（接口文档 8.6 增量，C-fix 批3-bonus）。

- POST /resource/external/aggregate：聚合 Agent 整理 + critic 评分，返回带相关度/可信度清单。
- 无搜索能力（默认 search_provider=none）→ online=false + 种子兜底候选，**保证可跑**。
- 需登录；知识点不存在 → 1004；既有 GET /resource/external/{kpId} 回归未变。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

AGG_KEYS = {"kpId", "kpName", "provider", "online", "items"}
ITEM_KEYS = {"id", "type", "title", "source", "url", "relevance", "credibility", "reason"}
RES_TYPES = {"视频", "论文", "文档", "课程"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def headers(client) -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"username": "learner_001", "password": "123456"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['data']['token']}"}


def _data(res) -> dict:
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["code"] == 0, body
    return body["data"]


def test_aggregate_requires_login(client):
    assert client.post("/api/v1/resource/external/aggregate", json={"kpId": "nn"}).status_code == 401


def test_aggregate_unknown_kp(client, headers):
    res = client.post("/api/v1/resource/external/aggregate", headers=headers, json={"kpId": "zzz"})
    assert res.status_code == 404 and res.json()["code"] == 1004


def test_aggregate_offline_seed_fallback(client, headers):
    """默认无搜索能力 → online=false + 种子兜底候选，聚合评分后返回合规清单。"""
    data = _data(client.post("/api/v1/resource/external/aggregate", headers=headers, json={"kpId": "nn"}))
    assert set(data) == AGG_KEYS
    assert data["kpId"] == "nn"
    assert data["provider"] == "none"  # 未配置搜索 API
    assert data["online"] is False
    items = data["items"]
    assert isinstance(items, list) and items
    rels = []
    for it in items:
        assert ITEM_KEYS <= set(it)  # 允许附加 embed/duration
        assert it["type"] in RES_TYPES
        assert 0 <= it["relevance"] <= 100 and 0 <= it["credibility"] <= 100
        assert it["url"].startswith("http")
        assert it["reason"]
        rels.append(it["relevance"])
    assert rels == sorted(rels, reverse=True)  # 按相关度降序


def test_aggregate_custom_weakpoints(client, headers):
    """显式薄弱点参与聚合（因人而异），仍返回合规清单。"""
    data = _data(client.post(
        "/api/v1/resource/external/aggregate",
        headers=headers,
        json={"kpId": "nn", "weakPoints": ["反向传播", "梯度下降"]},
    ))
    assert data["items"] and all(it["url"].startswith("http") for it in data["items"])


def test_existing_external_endpoint_unchanged(client, headers):
    """既有 GET /resource/external/{kpId}（静态种子）回归未变。"""
    data = _data(client.get("/api/v1/resource/external/nn", headers=headers))
    assert isinstance(data, list) and data
    assert {"id", "type", "title", "source", "url", "relevance", "credibility", "reason"} <= set(data[0])
