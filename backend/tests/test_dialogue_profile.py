"""C1-b 契约测试：对话式学习画像诊断（接口文档 17.1 / 17.2 / 17.3）。

验收口径：
- POST /profile/dialogue（JSON）：多轮对话 portraitUpdates 逐轮累积，
  GET /profile/student-portrait 维度随对话增多/更新；响应结构严格按 17.1；
- SSE 模式（Accept: text/event-stream）：delta 逐句 → event: portrait 维度增量
  → event: done，事件序列与字段对齐 17.1，delta 拼接 == reply；
- mock 与 deepseek 双模式响应结构契约一致（deepseek 真实抽取 + 契约清洗：
  未知 key 丢弃、inferred 低 confidence、防幻觉）；
- 防幻觉：source ∈ dialogue|manual|inferred；首轮 context 显式填写 → manual；
- 回归：4.4 /profile/ability-portrait 与既有接口逐字未变（并存、不替换）；
- 会话上下文内存 TTL（sessionId d_ 前缀，过期重建）。
"""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core import llm as llm_mod
from app.core import llm_deepseek
from app.core.config import settings
from app.agents import dialogue_agent
from app.main import app
from app.services import profile_dialogue as dialogue_service

# 17.1 JSON 模式 data 键集合（严格）
DIALOGUE_KEYS = {
    "sessionId",
    "reply",
    "portraitUpdates",
    "suggestions",
    "diagnosisComplete",
}
PORTRAIT_KEYS = {"dimensions", "version", "updatedAt"}
DIM_KEYS_REQUIRED = {"key", "label", "value", "confidence", "source"}
SOURCES = {"dialogue", "manual", "inferred"}
VALID_DIM_KEYS = {
    "knowledge_base",
    "prior_experience",
    "learning_goal",
    "cognitive_style",
    "learning_pace",
    "error_preference",
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _fresh_headers(client: TestClient) -> dict[str, str]:
    """注册一个全新学习者（空画像），返回鉴权头，保证测试间隔离。"""
    username = f"dlg_{uuid.uuid4().hex[:10]}"
    res = client.post(
        "/api/v1/auth/register", json={"username": username, "password": "123456"}
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['data']['token']}"}


@pytest.fixture(autouse=True)
def _no_stream_delay():
    """SSE 测试零延迟（复用 tutor_stream_delay_ms）。"""
    original = settings.tutor_stream_delay_ms
    settings.tutor_stream_delay_ms = 0
    yield
    settings.tutor_stream_delay_ms = original


def _dialogue(client, headers, message, session_id=None, context=None) -> dict:
    body: dict = {"message": message}
    if session_id is not None:
        body["sessionId"] = session_id
    if context is not None:
        body["context"] = context
    res = client.post("/api/v1/profile/dialogue", headers=headers, json=body)
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["code"] == 0
    return payload["data"]


def _get_portrait(client, headers) -> dict:
    res = client.get("/api/v1/profile/student-portrait", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["data"]


def _assert_dim_contract(dim: dict) -> None:
    assert DIM_KEYS_REQUIRED <= set(dim.keys())
    assert set(dim.keys()) <= DIM_KEYS_REQUIRED | {"score", "updatedAt"}
    assert dim["key"] in VALID_DIM_KEYS
    assert isinstance(dim["value"], str) and dim["value"]
    assert dim["source"] in SOURCES
    assert 0.0 <= dim["confidence"] <= 1.0
    if dim["source"] == "inferred":
        assert dim["confidence"] <= 0.6  # 17.1 防幻觉：推断须低 confidence
    if "score" in dim:
        assert 0 <= dim["score"] <= 100


# ---- 17.1 JSON：单轮结构 + 17.3 空画像 ----------------------------------------

def test_empty_portrait_before_dialogue(client):
    """未开始诊断 → 空画像占位（dimensions:[]），不视为错误（17.3）。"""
    headers = _fresh_headers(client)
    data = _get_portrait(client, headers)
    assert set(data.keys()) == PORTRAIT_KEYS
    assert data["dimensions"] == []
    assert data["version"] == "v1"
    assert data["updatedAt"]


def test_dialogue_json_contract_and_session_id(client):
    headers = _fresh_headers(client)
    data = _dialogue(client, headers, "我是计算机本科，做过Python爬虫，想转大模型应用")
    assert set(data.keys()) == DIALOGUE_KEYS
    assert data["sessionId"].startswith("d_")  # 首轮后端生成 d_ 前缀 id
    assert data["reply"]
    assert isinstance(data["suggestions"], list)
    assert isinstance(data["diagnosisComplete"], bool)
    assert data["portraitUpdates"], "首轮应抽取到画像维度增量"
    for dim in data["portraitUpdates"]:
        _assert_dim_contract(dim)
    # 抽取应包含先验经验（爬虫）与学习目标（转大模型）
    keys = {d["key"] for d in data["portraitUpdates"]}
    assert "prior_experience" in keys and "learning_goal" in keys


# ---- 17.1 多轮累积 + 17.3 随对话增多/更新 + diagnosisComplete -------------------

def test_multi_turn_accumulation_and_completion(client):
    headers = _fresh_headers(client)
    # 6 维逐轮采集；diagnosisComplete 须到第 6 维（含 inferred 的 error_preference）
    # 到位才翻 True，与赛题「≥6 维」及前端「满 6 维」门控一致。
    turns = [
        ("我是计算机专业本科毕业", "knowledge_base"),
        ("平时做过一些Python项目", "prior_experience"),
        ("想转行进入大模型应用方向", "learning_goal"),
        ("我比较喜欢动手实践、做中学", "cognitive_style"),
        ("时间比较紧，想尽快突破", "learning_pace"),
        ("学的时候概念总是容易混淆", "error_preference"),
    ]
    session_id = None
    seen_keys: set[str] = set()
    completions: list[bool] = []
    for message, expect_key in turns:
        data = _dialogue(client, headers, message, session_id=session_id)
        session_id = data["sessionId"]  # 复用同一会话
        assert data["portraitUpdates"], f"轮「{message}」应有抽取"
        # 本轮目标维度被采集
        assert expect_key in {d["key"] for d in data["portraitUpdates"]}
        # GET 画像随对话单调累积（维度集只增不减）
        portrait = _get_portrait(client, headers)
        keys_now = {d["key"] for d in portrait["dimensions"]}
        assert seen_keys <= keys_now, "画像维度不应回退（随学随新只增/更新）"
        assert expect_key in keys_now
        seen_keys = keys_now
        completions.append(data["diagnosisComplete"])
    # 采集到 ≥6 维 → 诊断收敛完成
    assert seen_keys >= {
        "knowledge_base",
        "prior_experience",
        "learning_goal",
        "cognitive_style",
        "learning_pace",
        "error_preference",
    }
    # 第 6 维到位前（前 5 轮）均未完成；第 6 维到位才翻 True（阈值 ≥6）
    assert completions[:5] == [False] * 5
    assert completions[5] is True
    # 末轮画像每维契约自洽
    for dim in _get_portrait(client, headers)["dimensions"]:
        _assert_dim_contract(dim)


def test_completes_only_at_six_dims_even_when_focus_exhausted():
    """阈值回归：仅采集 5 维时不收尾——即便缺口维度已问过（focus 耗尽），也须继续
    追问该缺口维度，绝不「满 5 维即完成」（与赛题 ≥6 维、前端「满 6 维」门控一致）。"""
    known = [
        "knowledge_base", "prior_experience", "learning_goal",
        "cognitive_style", "learning_pace",
    ]  # 已采集 5 维，缺 error_preference
    asked = [
        "prior_experience", "learning_goal", "cognitive_style",
        "learning_pace", "error_preference",  # error_preference 已问过但未采集
    ]
    res = dialogue_agent.respond(
        context=None,
        history=[{"role": "user", "content": "x"}],
        message="嗯嗯，了解",  # 无新维度信号（mock 抽取为空）
        known_keys=known,
        asked_keys=asked,
        first_turn=False,
    )
    assert res["diagnosisComplete"] is False  # 仅 5 维 → 未达 ≥6，不收尾
    assert res["focus"] == "error_preference"  # 回头重问未采集维度，驱动收敛到 6
    assert res["suggestions"]  # 仍为追问态（非收尾，给出快捷建议）

    # 补齐第 6 维（error_preference）→ 立即收尾
    done = dialogue_agent.respond(
        context=None,
        history=[{"role": "user", "content": "x"}],
        message="概念总是容易混淆",  # mock 抽取 error_preference
        known_keys=known,
        asked_keys=asked,
        first_turn=False,
    )
    assert "error_preference" in {u["key"] for u in done["updates"]}
    assert done["diagnosisComplete"] is True  # 第 6 维到位 → 完成
    assert done["focus"] is None


def test_reask_uses_different_wording_not_verbatim():
    """issue#2：模糊回答致同一维度需再次追问时，必须换措辞，严禁原样重发同一句问题。

    场景：已采集 5 维、缺 error_preference；该维度首问与重问应推进同一 focus，
    但回复文案不同（首问主问法 → 重问替代问法），且仍为追问态、不提前收尾。
    """
    known = [
        "knowledge_base", "prior_experience", "learning_goal",
        "cognitive_style", "learning_pace",
    ]
    # 首问 error_preference：asked 尚不含该维度（ask_count=0）→ 主问法
    first = dialogue_agent.respond(
        context=None, history=[{"role": "user", "content": "x"}],
        message="嗯嗯",  # mock 抽取为空（模糊回答）
        known_keys=known,
        asked_keys=["prior_experience", "learning_goal", "cognitive_style", "learning_pace"],
        first_turn=False,
    )
    assert first["focus"] == "error_preference"
    # 重问 error_preference：asked 已含该维度一次（ask_count=1）→ 替代问法
    second = dialogue_agent.respond(
        context=None, history=[{"role": "user", "content": "x"}],
        message="嗯嗯",
        known_keys=known,
        asked_keys=[
            "prior_experience", "learning_goal", "cognitive_style",
            "learning_pace", "error_preference",
        ],
        first_turn=False,
    )
    assert second["focus"] == "error_preference"
    assert second["diagnosisComplete"] is False  # 仅 5 维，仍追问收敛
    assert second["suggestions"]
    # 关键断言：重问与首问问法不同（不原样重发同一句）
    assert second["reply"] != first["reply"]

    # 再连问一次（ask_count=2）→ 仍与上一次不同，连续重问也不复读
    third = dialogue_agent.respond(
        context=None, history=[{"role": "user", "content": "x"}],
        message="嗯嗯",
        known_keys=known,
        asked_keys=[
            "prior_experience", "learning_goal", "cognitive_style",
            "learning_pace", "error_preference", "error_preference",
        ],
        first_turn=False,
    )
    assert third["focus"] == "error_preference"
    assert third["reply"] != second["reply"]


def test_new_session_runs_dialogue_even_with_completed_portrait(client):
    """回归：已有完整持久化画像的返回用户，开新会话仍正常多轮对话，不每轮即收尾。

    诊断收敛进度按「本会话已抽取维度」判定，与历史持久化画像解耦；否则库内画像已
    ≥ 阈值的用户一开口即被判完成，助手永远只回固定收尾语。
    """
    headers = _fresh_headers(client)
    # 会话 A：先把画像采集到收敛完成（≥6 维）
    turns = [
        "我是计算机专业本科毕业",
        "平时做过一些Python项目",
        "想转行进入大模型应用方向",
        "我比较喜欢动手实践、做中学",
        "时间比较紧，想尽快突破",
        "学的时候概念总是容易混淆",
    ]
    sid = None
    last = None
    for m in turns:
        last = _dialogue(client, headers, m, session_id=sid)
        sid = last["sessionId"]
    assert last["diagnosisComplete"] is True  # 会话 A 已收敛
    portrait_keys = {d["key"] for d in _get_portrait(client, headers)["dimensions"]}
    assert len(portrait_keys) >= 6  # 库内画像已完整

    # 会话 B（全新 sessionId）：一句简单问候不应被直接判完成，应继续追问
    fresh = _dialogue(client, headers, "你好")  # 无 sessionId → 新会话
    assert fresh["sessionId"] != sid
    assert fresh["diagnosisComplete"] is False, "新会话首轮不应因历史画像即被判完成"
    assert fresh["reply"] and "接下来就可以进入个性化学习路径" not in fresh["reply"]
    assert isinstance(fresh["suggestions"], list) and fresh["suggestions"]


def test_first_turn_context_is_manual_source(client):
    """首轮 context（表单显式填写）→ source=manual（17.1 防幻觉口径）。"""
    headers = _fresh_headers(client)
    data = _dialogue(
        client,
        headers,
        "你好",
        context={"major": "计算机科学", "goal": "职业培训"},
    )
    by_key = {d["key"]: d for d in data["portraitUpdates"]}
    assert "learning_goal" in by_key and by_key["learning_goal"]["source"] == "manual"
    assert "knowledge_base" in by_key and by_key["knowledge_base"]["source"] == "manual"


def test_portrait_updates_in_place_not_duplicated(client):
    """同维度二次抽取 → 字段级覆盖更新，不产生重复行（随学随新）。"""
    headers = _fresh_headers(client)
    d1 = _dialogue(client, headers, "我基本零基础，没怎么学过")
    sid = d1["sessionId"]
    kb1 = next(d for d in _get_portrait(client, headers)["dimensions"] if d["key"] == "knowledge_base")
    assert kb1["value"] == "薄弱" and kb1["score"] == 30
    # 二轮更新知识基础为「扎实」
    _dialogue(client, headers, "其实我后来系统学得很扎实了", session_id=sid)
    dims = _get_portrait(client, headers)["dimensions"]
    kbs = [d for d in dims if d["key"] == "knowledge_base"]
    assert len(kbs) == 1, "同 key 维度不应重复，应原地更新"
    assert kbs[0]["value"] == "扎实" and kbs[0]["score"] == 85


# ---- 17.1 SSE 流式 -------------------------------------------------------------

def _parse_sse(text: str) -> tuple[list[dict], dict[str, dict]]:
    deltas: list[dict] = []
    named: dict[str, dict] = {}
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = None
        data_line = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data_line = line[len("data: ") :]
        assert data_line is not None, f"SSE 块缺 data 行：{block!r}"
        payload = json.loads(data_line)
        if event is None:
            deltas.append(payload)
        else:
            named[event] = payload
    return deltas, named


def test_dialogue_sse_event_sequence(client):
    headers = _fresh_headers(client)
    res = client.post(
        "/api/v1/profile/dialogue",
        headers={**headers, "Accept": "text/event-stream"},
        json={"message": "我是计算机本科，做过Python爬虫，想转大模型应用"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    deltas, named = _parse_sse(res.text)
    # delta 逐句下发，键仅 delta
    assert deltas and all(set(d.keys()) == {"delta"} for d in deltas)
    reply = "".join(d["delta"] for d in deltas)
    assert reply  # 非空
    # event: portrait 携带本轮维度增量
    assert "portrait" in named
    assert isinstance(named["portrait"]["updates"], list) and named["portrait"]["updates"]
    for dim in named["portrait"]["updates"]:
        _assert_dim_contract(dim)
    # event: done 收尾，字段对齐 17.1
    done = named["done"]
    assert set(done.keys()) == {"sessionId", "suggestions", "diagnosisComplete"}
    assert done["sessionId"].startswith("d_")
    assert isinstance(done["suggestions"], list)
    assert isinstance(done["diagnosisComplete"], bool)
    # 流式与持久化同链路：画像已写入
    portrait = _get_portrait(client, headers)
    assert portrait["dimensions"]


# ---- mock / deepseek 双模式结构一致 + deepseek 真实抽取契约清洗 ------------------

def test_dialogue_deepseek_mode_structure_and_sanitize(client, monkeypatch):
    """deepseek 真实抽取：结构与 mock 一致；未知 key 丢弃、inferred 低 confidence。"""
    headers = _fresh_headers(client)
    # 故意混入非法 key、超界 confidence、inferred 高 confidence（应被清洗）
    fake = {
        "updates": [
            {"key": "prior_experience", "label": "先验经验", "value": "有NLP项目经验",
             "confidence": 0.85, "source": "dialogue"},
            {"key": "error_preference", "label": "易错点偏好", "value": "概念混淆",
             "confidence": 0.95, "source": "inferred"},  # inferred → 应被压到 ≤0.6
            {"key": "not_a_real_dim", "label": "x", "value": "y",
             "confidence": 0.9, "source": "dialogue"},  # 非白名单 → 丢弃
        ]
    }

    def fake_chat(prompt, system=None, history=None):
        assert "禁止编造" in system  # 防幻觉 system 约束
        return json.dumps(fake, ensure_ascii=False)

    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_deepseek, "chat", fake_chat)
    llm_mod._client = None
    try:
        data = _dialogue(client, headers, "我做过NLP相关项目")
        assert set(data.keys()) == DIALOGUE_KEYS
        by_key = {d["key"]: d for d in data["portraitUpdates"]}
        assert "not_a_real_dim" not in by_key  # 非白名单 key 被丢弃
        assert by_key["prior_experience"]["source"] == "dialogue"
        assert by_key["error_preference"]["confidence"] <= 0.6  # inferred 被压低
        for dim in data["portraitUpdates"]:
            _assert_dim_contract(dim)
    finally:
        monkeypatch.setattr(settings, "llm_provider", "mock")
        llm_mod._client = None


def test_dialogue_deepseek_generation_error_maps_2001(client, monkeypatch):
    headers = _fresh_headers(client)

    def boom(prompt, system=None, history=None):
        raise llm_deepseek.LLMGenerationError("DEEPSEEK_API_KEY 未配置")

    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_deepseek, "chat", boom)
    llm_mod._client = None
    try:
        res = client.post(
            "/api/v1/profile/dialogue", headers=headers, json={"message": "你好"}
        )
        assert res.status_code == 500 and res.json()["code"] == 2001
    finally:
        monkeypatch.setattr(settings, "llm_provider", "mock")
        llm_mod._client = None


# ---- 鉴权 + 会话 TTL -----------------------------------------------------------

def test_dialogue_requires_auth(client):
    res = client.post("/api/v1/profile/dialogue", json={"message": "你好"})
    assert res.status_code == 401 and res.json()["code"] == 1002
    res2 = client.get("/api/v1/profile/student-portrait")
    assert res2.status_code == 401 and res2.json()["code"] == 1002


def test_session_ttl_expiry_resets_context(client):
    headers = _fresh_headers(client)
    d1 = _dialogue(client, headers, "我是本科毕业")
    sid = d1["sessionId"]
    assert len(dialogue_service._sessions[sid]["history"]) == 2
    # 人为过期 → 同 sessionId 再聊，上下文清零重建（TTL 语义同 8.7）
    dialogue_service._sessions[sid]["expiresAt"] = 0.0
    _dialogue(client, headers, "做过Python项目", session_id=sid)
    assert len(dialogue_service._sessions[sid]["history"]) == 2  # 仅本轮，旧上下文已失效


# ---- 回归：4.4 ability-portrait 并存、逐字未变 --------------------------------

def test_ability_portrait_unchanged_and_independent(client):
    """新增异质画像不影响 4.4 固定 6 知识点雷达（并存、互不替换）。"""
    headers = _fresh_headers(client)
    # 先跑对话写入异质画像
    _dialogue(client, headers, "我是计算机本科，做过Python爬虫，想转大模型应用")
    # 4.4 仍返回固定 6 维 + 基线值（未受 student-portrait 影响）
    res = client.get("/api/v1/profile/ability-portrait", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data == {
        "dimensions": ["机器学习基础", "神经网络", "深度学习", "注意力机制", "Transformer", "大模型微调"],
        "values": [85, 72, 68, 45, 30, 20],
    }
