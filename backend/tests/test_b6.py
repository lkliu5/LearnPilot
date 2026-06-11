"""B6 契约测试：P1 特色 6 接口（JobMarket / KnowledgeGraph / Reinforce / External / Dashboard）。

验收口径（执行方案 B6 + 接口文档 5/8.6/9.2/10/12 章）：
- JobMarket：预置 4 岗位（种子自 frontend/public/data/job-market/*.json）；
  数据源不可用（job_market_offline 模拟）→ code 2002 + data.offline=true（HTTP 200 非 500）；
- KnowledgeGraph：12 节点 / 14 边；category 按 mastery 实时推导
  （passed→0 / learning|pending-check→1 / 未开始高 value→2 / value<20 盲区→3），
  含推导边界用例；
- Reinforce：mock 确定性输出（两次调用逐字一致）；deepseek 路径（monkeypatch
  llm_deepseek.chat，无 Key 可跑）生成练习题须 critic 审核自洽——
  correct_answer 在 options 中且 explanation 非空，不自洽重试一次仍失败 → 2001；
- External：6 KP 精选种子，relevance 降序，字段对齐 8.6；
- Dashboard：与明细接口严格一致（radar=4.4、targetSummary=7.4、
  强弱项/评分与 10.1 图谱节点同口径），mastery 置 passed → 图谱该节点 category=0
  且 overall_score / strong_topics 联动（一致性断言）。

测试自带 mastery 状态清理（dev 库不残留），全程 mock provider（conftest 基线）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.entities import Mastery, User
from app.services.knowledge_graph import derive_node


@pytest.fixture(scope="module")
def client():
    # with 触发 lifespan：建表 + 幂等种子（含 B6 JobSnapshot / ExternalResource）
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(client):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['data']['token']}"}


@pytest.fixture(scope="module")
def learner_headers(client) -> dict[str, str]:
    return _login(client, "learner_001", "123456")


@pytest.fixture()
def clean_mastery(db):
    """测试前后清空 learner_001 的掌握度行（保存原状并复原，不污染 dev 库）。"""
    user = db.query(User).filter(User.username == "learner_001").one()
    original = [
        (m.kp_id, m.status)
        for m in db.query(Mastery).filter(Mastery.user_id == user.id).all()
    ]

    def _reset() -> None:
        db.query(Mastery).filter(Mastery.user_id == user.id).delete()
        db.commit()

    _reset()
    yield user
    _reset()
    for kp_id, status in original:
        db.add(Mastery(user_id=user.id, kp_id=kp_id, status=status))
    db.commit()


# ---- JobMarket（接口文档 5.1/5.2/15.5） ----------------------------------------

def test_job_hot_list_contract_order(client, learner_headers):
    res = client.get("/api/v1/job-market/hot", headers=learner_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    assert [j["id"] for j in body["data"]] == [
        "llm-app", "algo-engineer", "ml-engineer", "data-analyst"
    ]
    assert body["data"][0]["name"] == "大模型应用工程师"


def test_job_snapshot_contract_fields(client, learner_headers):
    res = client.get("/api/v1/job-market/llm-app", headers=learner_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    data = body["data"]
    # 2.4 JobMarket 契约字段（前端 JSON 原样导入）
    for key in (
        "id", "name", "salaryRange", "salaryMedian", "heat", "heatPct",
        "openings", "source", "fetchedAt", "skills", "radar",
    ):
        assert key in data, f"缺字段 {key}"
    assert data["id"] == "llm-app" and data["heatPct"] == 95
    assert {s["name"] for s in data["skills"]} >= {"Prompt 工程", "Python"}
    # 雷达 6 维固定键名（2.4 备注）
    assert set(data["radar"]) == {
        "机器学习基础", "神经网络", "深度学习", "注意力机制", "Transformer", "大模型微调"
    }
    assert "offline" not in data  # 正常路径不带降级标记


def test_job_snapshot_degrades_to_2002_not_500(client, learner_headers, monkeypatch):
    """模拟岗位数据源故障 → 2002 + offline:true + 最近快照（而非 500）。"""
    monkeypatch.setattr(settings, "job_market_offline", True)
    res = client.get("/api/v1/job-market/llm-app", headers=learner_headers)
    assert res.status_code == 200  # 1.3：2002 → HTTP 200
    body = res.json()
    assert body["code"] == 2002
    assert body["data"]["offline"] is True
    assert body["data"]["id"] == "llm-app"  # 最近快照仍完整返回
    assert body["data"]["fetchedAt"]  # 前端 timeAgo 渲染快照年龄


def test_job_snapshot_unknown_id_404(client, learner_headers):
    res = client.get("/api/v1/job-market/nope", headers=learner_headers)
    assert res.status_code == 404
    assert res.json()["code"] == 1004


# ---- KnowledgeGraph（接口文档 10.1） -------------------------------------------

def test_graph_structure_12_nodes_14_links(client, learner_headers):
    res = client.get("/api/v1/knowledge-graph", headers=learner_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["nodes"]) == 12
    assert len(data["links"]) == 14
    assert [c["name"] for c in data["categories"]] == [
        "已掌握", "学习中", "待学习", "知识盲区"
    ]
    node = data["nodes"][0]
    assert set(node) == {"id", "name", "category", "value"}
    assert {"source": "ml", "target": "nn"} in data["links"]


def test_graph_category_derived_from_mastery(client, learner_headers, clean_mastery):
    """mastery 联动：passed→0/100；learning→1/min(值,60)；未开始按种子值推导。"""
    # 未开始基线：nn 高种子值 → 待学习(2)；transformer 种子 15 → 盲区(3)
    nodes = {
        n["id"]: n
        for n in client.get("/api/v1/knowledge-graph", headers=learner_headers)
        .json()["data"]["nodes"]
    }
    assert (nodes["nn"]["category"], nodes["nn"]["value"]) == (2, 85)
    assert (nodes["transformer"]["category"], nodes["transformer"]["value"]) == (3, 15)

    # nn 置 passed → category 0 / value 100
    assert (
        client.post("/api/v1/mastery/nn/pass", headers=learner_headers).status_code
        == 200
    )
    # dl 置 pending-check → category 1 / value min(65, 60)=60
    assert (
        client.post("/api/v1/mastery/dl/check", headers=learner_headers).status_code
        == 200
    )
    nodes = {
        n["id"]: n
        for n in client.get("/api/v1/knowledge-graph", headers=learner_headers)
        .json()["data"]["nodes"]
    }
    assert (nodes["nn"]["category"], nodes["nn"]["value"]) == (0, 100)
    assert (nodes["dl"]["category"], nodes["dl"]["value"]) == (1, 60)


def test_derive_node_boundaries():
    """category 推导边界：盲区阈值 20、学习中 60 封顶、passed 恒 100。"""
    assert derive_node("passed", 12) == (0, 100)
    assert derive_node("learning", 85) == (1, 60)   # 高种子值封顶 60
    assert derive_node("pending-check", 35) == (1, 35)
    assert derive_node(None, 20) == (2, 20)          # 阈值上：待学习
    assert derive_node(None, 19) == (3, 19)          # 阈值下：盲区
    assert derive_node(None, 92) == (2, 92)


# ---- Reinforce（接口文档 9.2） --------------------------------------------------

def test_reinforce_mock_deterministic(client, learner_headers):
    """mock 确定性：两次调用逐字一致；卡片结构与预置库对齐。"""
    payload = {"kpId": "nn", "wrongQuestionIds": ["nn_q1", "nn_q3"]}
    first = client.post("/api/v1/reinforce", json=payload, headers=learner_headers)
    second = client.post("/api/v1/reinforce", json=payload, headers=learner_headers)
    assert first.status_code == 200
    assert first.json()["data"] == second.json()["data"]  # 确定性

    cards = first.json()["data"]
    assert [c["questionId"] for c in cards] == ["nn_q1", "nn_q3"]
    assert cards[0]["point"] == "神经元运算顺序"
    assert cards[0]["practice"]["question_id"] == "nn_q1-r"
    for card in cards:
        practice = card["practice"]
        option_ids = [o["option_id"] for o in practice["options"]]
        correct = practice["correct_answer"]
        assert (
            all(c in option_ids for c in correct)
            if isinstance(correct, list)
            else correct in option_ids
        )
        assert practice["explanation"].strip()
        assert card["recap"].strip()


def test_reinforce_generic_fallback_self_consistent(client, learner_headers):
    """预置库外的题走确定性变式兜底：选项轮转后答案仍自洽。"""
    res = client.post(
        "/api/v1/reinforce",
        json={"kpId": "ml", "wrongQuestionIds": ["ml_q1"]},
        headers=learner_headers,
    )
    assert res.status_code == 200
    card = res.json()["data"][0]
    assert card["questionId"] == "ml_q1"
    assert card["practice"]["question_text"].startswith("【强化·变式】")
    option_ids = [o["option_id"] for o in card["practice"]["options"]]
    assert card["practice"]["correct_answer"] in option_ids


def test_reinforce_unknown_kp_404_and_unknown_qid_filtered(client, learner_headers):
    res = client.post(
        "/api/v1/reinforce",
        json={"kpId": "nope", "wrongQuestionIds": ["x"]},
        headers=learner_headers,
    )
    assert res.status_code == 404 and res.json()["code"] == 1004

    res = client.post(
        "/api/v1/reinforce",
        json={"kpId": "nn", "wrongQuestionIds": ["not_a_question"]},
        headers=learner_headers,
    )
    assert res.status_code == 200 and res.json()["data"] == []


@pytest.fixture()
def deepseek_llm(monkeypatch):
    """进程内 LLM 单例切到 deepseek provider（测试后自动还原）。"""
    from app.core import llm as llm_mod

    fake = llm_mod.LLMClient("deepseek")
    monkeypatch.setattr(llm_mod, "_client", fake)
    return fake


_VALID_REINFORCE_JSON = """
{"items": [{"questionId": "nn_q1", "point": "神经元计算流程",
  "recap": "先加权求和、加偏置，最后过激活函数。",
  "practice": {"question_id": "nn_q1-r", "question_type": "single",
    "question_text": "偏置 b 在神经元中的作用是？",
    "options": [{"option_id": "a", "option_text": "平移激活输入"},
                {"option_id": "b", "option_text": "归一化输出"}],
    "correct_answer": "a", "explanation": "偏置对加权和做平移，再交给激活函数。"}}]}
"""

# correct_answer 指向不存在的选项 → critic 审核必须拦下
_BROKEN_REINFORCE_JSON = _VALID_REINFORCE_JSON.replace(
    '"correct_answer": "a"', '"correct_answer": "c"'
)


def test_reinforce_deepseek_real_path_audited(
    client, learner_headers, deepseek_llm, monkeypatch
):
    """真实模式（monkeypatch chat）：生成结果过 critic 审核后原样返回。"""
    from app.core import llm_deepseek

    monkeypatch.setattr(llm_deepseek, "chat", lambda *a, **k: _VALID_REINFORCE_JSON)
    res = client.post(
        "/api/v1/reinforce",
        json={"kpId": "nn", "wrongQuestionIds": ["nn_q1"]},
        headers=learner_headers,
    )
    assert res.status_code == 200, res.text
    card = res.json()["data"][0]
    assert card["questionId"] == "nn_q1"
    option_ids = [o["option_id"] for o in card["practice"]["options"]]
    assert card["practice"]["correct_answer"] in option_ids  # 验收标准 3
    assert card["practice"]["explanation"].strip()


def test_reinforce_deepseek_retry_then_2001(
    client, learner_headers, deepseek_llm, monkeypatch
):
    """答案不自洽 → 带审核反馈重试一次；仍不自洽 → 2001 / HTTP 500。"""
    from app.core import llm_deepseek

    calls: list[str] = []

    def _always_broken(prompt: str, **kwargs):
        calls.append(prompt)
        return _BROKEN_REINFORCE_JSON

    monkeypatch.setattr(llm_deepseek, "chat", _always_broken)
    res = client.post(
        "/api/v1/reinforce",
        json={"kpId": "nn", "wrongQuestionIds": ["nn_q1"]},
        headers=learner_headers,
    )
    assert res.status_code == 500
    assert res.json()["code"] == 2001
    assert len(calls) == 2  # 首次 + 重试一次
    assert "审核" in calls[1]  # 重试 prompt 带审核反馈


def test_reinforce_deepseek_retry_recovers(
    client, learner_headers, deepseek_llm, monkeypatch
):
    """首轮不自洽、重试修正 → 正常返回（重试链路真实生效）。"""
    from app.core import llm_deepseek

    outputs = iter([_BROKEN_REINFORCE_JSON, _VALID_REINFORCE_JSON])
    monkeypatch.setattr(llm_deepseek, "chat", lambda *a, **k: next(outputs))
    res = client.post(
        "/api/v1/reinforce",
        json={"kpId": "nn", "wrongQuestionIds": ["nn_q1"]},
        headers=learner_headers,
    )
    assert res.status_code == 200
    assert res.json()["data"][0]["practice"]["correct_answer"] == "a"


# ---- External（接口文档 8.6） ---------------------------------------------------

def test_external_resources_seeded_and_sorted(client, learner_headers):
    res = client.get("/api/v1/resource/external/nn", headers=learner_headers)
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 4  # nn 种子 4 条（与前端演示对齐）
    relevances = [i["relevance"] for i in items]
    assert relevances == sorted(relevances, reverse=True)  # 相关度降序
    top = items[0]
    for key in ("id", "type", "title", "source", "url", "relevance", "credibility", "reason"):
        assert key in top
    assert top["type"] == "视频" and top["embed"].startswith("https://")
    # 全部 6 核心 KP 均有 3-4 条种子
    for kp in ("ml", "dl", "cnn", "transformer", "finetune"):
        rows = client.get(
            f"/api/v1/resource/external/{kp}", headers=learner_headers
        ).json()["data"]
        assert 3 <= len(rows) <= 4, kp
        assert all(r["type"] in ("视频", "论文", "文档", "课程") for r in rows)


def test_external_unknown_kp_404(client, learner_headers):
    res = client.get("/api/v1/resource/external/nope", headers=learner_headers)
    assert res.status_code == 404 and res.json()["code"] == 1004


# ---- Dashboard（接口文档 12.1）：明细接口一致性 ---------------------------------

def test_dashboard_consistent_with_details_and_mastery(
    client, learner_headers, clean_mastery
):
    """验收标准 1：mastery 置 passed → graph 节点 category=0 且 dashboard
    overall_score / strong_topics 联动，radar/targetSummary 与明细接口逐字一致。"""
    before = client.get(
        "/api/v1/dashboard/overview", headers=learner_headers
    ).json()["data"]
    for key in (
        "overall_level", "overall_score", "knowledge_graph_coverage",
        "learned_resources", "strong_topics", "weak_topics", "radar",
        "comparison", "targetSummary",
    ):
        assert key in before, f"缺字段 {key}"
    # 与 4.4 雷达明细严格一致
    portrait = client.get(
        "/api/v1/profile/ability-portrait", headers=learner_headers
    ).json()["data"]
    assert before["radar"] == portrait
    # targetSummary 与 7.4 Journey 严格一致
    journey = client.get("/api/v1/journey", headers=learner_headers).json()["data"]
    assert before["targetSummary"] == {
        "hasDiagnosed": journey["hasDiagnosed"],
        "targetJobName": journey["targetJobName"],
        "matchPct": journey["matchPct"],
    }
    # 基线：nn 未通过 → 不在满分强项里
    assert all(t["mastery"] < 100 for t in before["strong_topics"])

    # nn 置 passed → 三方联动
    client.post("/api/v1/mastery/nn/pass", headers=learner_headers)
    after = client.get(
        "/api/v1/dashboard/overview", headers=learner_headers
    ).json()["data"]
    graph_nodes = {
        n["id"]: n
        for n in client.get("/api/v1/knowledge-graph", headers=learner_headers)
        .json()["data"]["nodes"]
    }
    assert graph_nodes["nn"]["category"] == 0  # 图谱联动
    assert after["overall_score"] > before["overall_score"]  # 评分联动
    assert {"name": "神经网络基础", "mastery": 100} in after["strong_topics"]  # 强项联动
    # 强弱项口径与图谱节点推导值一致
    assert after["strong_topics"][0]["mastery"] == max(
        n["value"] for n in graph_nodes.values()
    )
    assert after["knowledge_graph_coverage"] > before["knowledge_graph_coverage"]
