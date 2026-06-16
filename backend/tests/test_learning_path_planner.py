"""真实学习路径规划 Agent 测试（接口文档 6.2，赛题功能 3）。

验证「真实化」核心断言（区别于此前 mock 写死的固定 6 课）：
1. **画像/掌握度差异 → 路径差异**：两个差异明显的学生生成的路径在顺序/覆盖上不同；
2. **薄弱点优先、已掌握后置**：未掌握点前置，passed 知识点排到路径末段（completed）；
3. **资源精准推送且可点开**：每步 resources 指向该 kpId 真实存在的资源端点；
4. **步骤带明确顺序 + 理由**：sequence 1..N 连续，每步 reason 非空且扣住排程信号；
5. **mock 无密钥可跑通**：全程 mock provider（conftest 基线），确定性、零网络。

为不污染共享种子用户（u_10000/u_10001 被其它用例断言），本测试创建一次性用户
并在 finally 清理；只读资源端点（GET）用于「可点开」证明，不写共享用户态。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents.planner_agent import plan_path
from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.entities import (
    Journey,
    Mastery,
    StudentPortrait,
    User,
)
from app.services import mastery as mastery_service
from app.services import student_portrait as portrait_service

API = "/api/v1"
_LESSON_CORE = {"sequence", "topic", "difficulty", "status", "progress", "description"}
_KP_IDS = {"ml", "nn", "dl", "cnn", "transformer", "finetune"}

# 两个差异明显的画像 / 掌握度场景
_USER_ZERO = "u_test_plan_zero"   # 零基础 + 目标「大模型应用」+ 全未掌握
_USER_PRIOR = "u_test_plan_prior"  # 有先验（基础扎实）+ ml/nn 已掌握 + 无目标岗位


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # 触发 lifespan 建表+种子
        yield c


@pytest.fixture(scope="module")
def two_profiles():
    """构造两个差异明显的学生（画像 + 掌握度 + 目标岗位），用后清理。"""
    db = SessionLocal()
    try:
        for uid in (_USER_ZERO, _USER_PRIOR):
            if db.get(User, uid) is None:
                db.add(User(id=uid, username=uid, display_name=uid, password_hash="x"))
        db.commit()

        # 零基础学生：knowledge_base 薄弱(score=22) + 目标大模型应用工程师
        portrait_service.apply_updates(
            db,
            _USER_ZERO,
            [
                {"key": "knowledge_base", "label": "知识基础", "value": "薄弱",
                 "score": 22, "confidence": 0.8, "source": "dialogue"},
                {"key": "learning_goal", "label": "学习目标", "value": "转大模型应用方向",
                 "confidence": 0.9, "source": "dialogue"},
            ],
        )
        jz = db.get(Journey, _USER_ZERO) or Journey(user_id=_USER_ZERO)
        jz.target_job_name = "大模型应用工程师"
        jz.has_diagnosed = True
        db.add(jz)
        # 全部未掌握（不写 Mastery 行 = 未开始）

        # 有先验学生：knowledge_base 扎实(score=88) + ml/nn 已通过、dl 学习中
        portrait_service.apply_updates(
            db,
            _USER_PRIOR,
            [
                {"key": "knowledge_base", "label": "知识基础", "value": "扎实",
                 "score": 88, "confidence": 0.8, "source": "dialogue"},
                {"key": "prior_experience", "label": "先验经验", "value": "有工程实践",
                 "confidence": 0.8, "source": "dialogue"},
            ],
        )
        jp = db.get(Journey, _USER_PRIOR) or Journey(user_id=_USER_PRIOR)
        jp.has_diagnosed = True
        db.add(jp)
        mastery_service.set_status(db, _USER_PRIOR, "ml", mastery_service.STATUS_PASSED)
        mastery_service.set_status(db, _USER_PRIOR, "nn", mastery_service.STATUS_PASSED)
        mastery_service.set_status(db, _USER_PRIOR, "dl", mastery_service.STATUS_LEARNING)
        db.commit()
        yield db
    finally:
        # 清理一次性用户的所有派生行，避免污染共享会话库
        for uid in (_USER_ZERO, _USER_PRIOR):
            db.query(Mastery).filter(Mastery.user_id == uid).delete()
            row = db.get(StudentPortrait, uid)
            if row is not None:
                db.delete(row)
            jr = db.get(Journey, uid)
            if jr is not None:
                db.delete(jr)
            u = db.get(User, uid)
            if u is not None:
                db.delete(u)
        db.commit()
        db.close()


def _topics(plan: dict) -> list[str]:
    return [s["topic"] for s in plan["lessons"]]


def test_plan_shape_and_ordering(two_profiles):
    """每步契约六字段 + additive(kpId/reason/resources)；sequence 连续；理由非空。"""
    db = two_profiles
    plan = plan_path(db, user_id=_USER_ZERO, target_job_id="llm-app")
    lessons = plan["lessons"]
    assert len(lessons) == 6
    assert [l["sequence"] for l in lessons] == [1, 2, 3, 4, 5, 6]
    for l in lessons:
        assert _LESSON_CORE <= set(l)               # 契约六字段齐全（向后兼容）
        assert l["status"] in {"completed", "in_progress", "pending"}
        assert 0 <= l["progress"] <= 100
        # additive：每步有 kpId / 非空 reason / 非空 resources（验证项 3、4）
        assert l["kpId"] in _KP_IDS
        assert isinstance(l["reason"], str) and l["reason"].strip()
        assert l["resources"] and all(r["kpId"] == l["kpId"] for r in l["resources"])


def test_two_profiles_yield_different_paths(two_profiles):
    """验证项 1：差异明显的画像/掌握度 → 顺序/覆盖不同（区别于写死固定路径）。"""
    db = two_profiles
    plan_zero = plan_path(db, user_id=_USER_ZERO, target_job_id="llm-app")
    plan_prior = plan_path(db, user_id=_USER_PRIOR)
    assert _topics(plan_zero) != _topics(plan_prior), "不同学生应生成不同顺序的路径"

    # 零基础：基础课先行（ml/nn 在前两步），难度被下调（首步入门级）
    zt = _topics(plan_zero)
    assert zt.index("机器学习基础") < zt.index("Transformer架构")
    assert plan_zero["lessons"][0]["difficulty"] in {"入门", "初级"}

    # 有先验：扎实基础 → 难度被上调（同一基础课难度更高），体现画像联动
    assert plan_prior["lessons"][0]["difficulty"] in {"初级", "中级", "高级", "精通"}


def test_weak_first_mastered_deferred(two_profiles):
    """验证项 2：薄弱点优先、已掌握后置，与 Mastery 真实联动。"""
    db = two_profiles
    plan = plan_path(db, user_id=_USER_PRIOR)
    lessons = plan["lessons"]
    seq_by_topic = {l["topic"]: l["sequence"] for l in lessons}

    # ml/nn 已通过 → status=completed 且排到所有未掌握(pending)步骤之后（后置复习）
    mastered_seqs = [l["sequence"] for l in lessons if l["status"] == "completed"]
    pending_seqs = [l["sequence"] for l in lessons if l["status"] == "pending"]
    assert {"机器学习基础", "神经网络基础"} <= {
        l["topic"] for l in lessons if l["status"] == "completed"
    }
    assert min(mastered_seqs) > max(pending_seqs), "已掌握点应排在未掌握点之后"
    # 薄弱点（未掌握）应抢占第 1 步，而非已掌握的 ml
    assert seq_by_topic["机器学习基础"] > 1

    # 理由层（经 LLMClient mock）扣住信号：已掌握点理由含「已掌握」，薄弱点含「薄弱/基础」
    ml_reason = next(l["reason"] for l in lessons if l["topic"] == "机器学习基础")
    assert "已掌握" in ml_reason
    weak_reason = " ".join(l["reason"] for l in lessons if l["status"] != "completed")
    assert ("薄弱" in weak_reason) or ("基础" in weak_reason)


def test_target_job_influences_path(two_profiles):
    """目标岗位真实参与规划：同一学生换目标岗位 → 重点强化项（理由）随岗位需求变化。

    先修依赖是硬约束（线性课程不因岗位破坏先修），故岗位需求体现为「重点强化项」
    标注：llm-app 对 Transformer/微调需求高(92/88)→ 标重点；data-analyst 需求低
    (15/10)→ 不标。两者的重点强化集合应不同（区别于与岗位无关的写死路径）。
    """
    db = two_profiles
    plan_llm = plan_path(db, user_id=_USER_ZERO, target_job_id="llm-app")
    plan_da = plan_path(db, user_id=_USER_ZERO, target_job_id="data-analyst")

    def emphasized(plan: dict) -> set[str]:
        return {l["topic"] for l in plan["lessons"] if "重点强化项" in l["reason"]}

    emp_llm, emp_da = emphasized(plan_llm), emphasized(plan_da)
    assert emp_llm != emp_da, "切换目标岗位应改变重点强化的知识点集合"
    # llm-app 应把 Transformer/微调列为重点（岗位需求 ≥80），data-analyst 不应
    assert {"Transformer架构", "大模型微调技术"} & emp_llm
    assert not ({"Transformer架构", "大模型微调技术"} & emp_da)


def test_resources_openable(client, two_profiles):
    """验证项 3：每步推送的资源指向真实存在、可点开的生成内容（只读端点证明）。"""
    db = two_profiles
    res = client.post(f"{API}/auth/login",
                      json={"username": "learner_001", "password": "123456"})
    headers = {"Authorization": f"Bearer {res.json()['data']['token']}"}

    plan = plan_path(db, user_id=_USER_ZERO, target_job_id="llm-app")
    for step in plan["lessons"]:
        kp = step["kpId"]
        # 题库（9.1）：真实存在 ≥1 题
        quiz = client.get(f"{API}/quiz/{kp}", headers=headers)
        assert quiz.status_code == 200 and quiz.json()["data"]["questions"]
        # 外部精选（8.6）：真实种子 ≥1 条（data 为资源数组）
        ext = client.get(f"{API}/resource/external/{kp}", headers=headers)
        assert ext.status_code == 200 and ext.json()["data"]
        # 思维导图（8.4）：真实 Markdown
        mind = client.get(f"{API}/resource/mindmap/{kp}", headers=headers)
        assert mind.status_code == 200 and mind.json()["data"]["markdown"]
