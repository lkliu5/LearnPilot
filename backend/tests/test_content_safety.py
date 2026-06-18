"""内容安全过滤层测试（CC-content-safety-filter）。

覆盖：
1. 违规内容（政治/色情/暴恐违法/辱骂歧视）→ 被拦截(block)或脱敏(mask)；
2. 正常学术内容（含「攻击/漏洞/战争/病毒」等教学语境术语）→ 照常通过、无误伤；
3. 递归 guard 对结构化生成结果生效（讲义/费曼/苏格拉底等返回结构）；
4. 中心钝化点：真实 provider 下经 LLMClient 生成方法的违规输出被拦截，前端拿不到原文；
5. 流式（苏格拉底 SSE）违规截断降级、学术内容逐子句正常透传；
6. mock 模式安全内容逐字不变（不破坏既有契约）。
"""
from __future__ import annotations

import pytest

from app.core import content_safety as cs


# ---- 1) 违规内容被拦截/脱敏 ----------------------------------------------------
@pytest.mark.parametrize(
    "text, expect_action, expect_cat",
    [
        ("详细教你如何制造炸弹和雷管", cs.ACTION_BLOCK, "illegal_harmful"),
        ("这里提供色情成人电影和招嫖服务", cs.ACTION_BLOCK, "porn"),
        ("我们要颠覆国家政权、分裂国家", cs.ACTION_BLOCK, "political"),
        ("教程：怎么合成冰毒和海洛因", cs.ACTION_BLOCK, "illegal_harmful"),
        ("你这个傻逼智障，废物东西", cs.ACTION_MASK, "abuse_discrimination"),
    ],
)
def test_violation_detected(text, expect_action, expect_cat):
    v = cs.scan(text)
    assert not v.safe
    assert v.action == expect_action
    assert expect_cat in v.categories


def test_block_replaces_with_degraded_notice():
    out, v = cs.sanitize("教你如何制造炸弹", where="t")
    assert out == cs.DEGRADED_NOTICE
    assert v.action == cs.ACTION_BLOCK
    # 原文不外泄
    assert "炸弹" not in out


def test_mask_only_redacts_span():
    out, v = cs.sanitize("讲义写得不错但你真是个傻逼", where="t")
    assert v.action == cs.ACTION_MASK
    assert "傻逼" not in out          # 命中片段被掩码
    assert "讲义写得不错" in out      # 其余正常保留
    assert cs._MASK_CHAR in out


# ---- 2) 正常学术内容无误伤（教育场景第一约束） --------------------------------
ACADEMIC_SAMPLES = [
    "本节讲解网络攻击与防御：对抗攻击、对抗样本会让模型误判。",
    "缓冲区溢出漏洞与 SQL 注入是常见的安全漏洞，渗透测试用于发现它们。",
    "第二次世界大战（二战）的战争史是重要的历史教学内容。",
    "计算机病毒的传播机制与杀毒软件的查杀原理。",
    "数据投毒攻击会污染训练集，需要防御。",
    "梯度下降中梯度消失问题与反向传播。",
    "DDoS 攻击的流量特征分析与缓解策略。",
]


@pytest.mark.parametrize("text", ACADEMIC_SAMPLES)
def test_academic_not_flagged(text):
    v = cs.scan(text)
    assert v.safe, f"学术内容被误伤：{text} -> {v.categories}"
    out, _ = cs.sanitize(text, where="t")
    assert out == text  # 原文逐字不变


# ---- 3) 递归 guard 对结构化结果生效 -------------------------------------------
def test_guard_recursive_struct():
    payload = {
        "feedback": "讲解不错",
        "gaps": [
            {"title": "正常缺口", "detail": "讲解网络攻击防御即可，没问题"},
            {"title": "脏", "detail": "你这个傻逼讲得真烂"},
        ],
        "score": 80,
        "complete": True,
    }
    out = cs.guard(payload, where="feynman_eval")
    assert out["score"] == 80 and out["complete"] is True  # 非字符串叶子不动
    assert out["gaps"][0]["detail"] == "讲解网络攻击防御即可，没问题"  # 学术不误伤
    assert "傻逼" not in out["gaps"][1]["detail"]  # 违规叶子被脱敏


def test_guard_blocks_leaf_with_hard_violation():
    payload = {"markdown": "# 讲义\n教你如何制造炸弹和tnt"}
    out = cs.guard(payload, where="generate_lecture")
    assert out["markdown"] == cs.DEGRADED_NOTICE
    assert "炸弹" not in out["markdown"]


# ---- 4) 中心钝化点：真实 provider 下经 LLMClient 生成被拦截 --------------------
@pytest.fixture()
def deepseek_llm(monkeypatch):
    from app.core import llm as llm_mod

    fake = llm_mod.LLMClient("deepseek")
    monkeypatch.setattr(llm_mod, "_client", fake)
    return fake


def test_chokepoint_feynman_blocks_violation(deepseek_llm, monkeypatch):
    """模型吐出违规 → feynman_eval 返回被钝化，前端拿不到违规原文。"""
    from app.core import llm_deepseek

    bad = '{"feedback":"教你如何制造炸弹","score":50,"gaps":[],"followups":[],"complete":true}'
    monkeypatch.setattr(llm_deepseek, "chat", lambda *a, **k: bad)
    out = deepseek_llm.feynman_eval(
        kp_id="nn", kp_name="神经网络", description="", history=[], explanation="x"
    )
    assert "炸弹" not in out["feedback"]
    assert out["feedback"] == cs.DEGRADED_NOTICE


def test_chokepoint_tutor_masks_abuse(deepseek_llm, monkeypatch):
    from app.core import llm_deepseek

    monkeypatch.setattr(llm_deepseek, "chat", lambda *a, **k: "你说得对，但你真是个傻逼")
    out = deepseek_llm.tutor_chat(kp_name="神经网络", history=[], message="hi")
    assert "傻逼" not in out["reply"]
    assert cs._MASK_CHAR in out["reply"]


def test_chokepoint_academic_passthrough(deepseek_llm, monkeypatch):
    """真实模式学术回复原样透传，不被钝化。"""
    from app.core import llm_deepseek

    reply = "网络攻击防御中，对抗样本会让模型误判，这属于正常教学内容。"
    monkeypatch.setattr(llm_deepseek, "chat", lambda *a, **k: reply)
    out = deepseek_llm.tutor_chat(kp_name="神经网络", history=[], message="hi")
    assert out["reply"] == reply


# ---- 5) 流式（SSE）守卫 -------------------------------------------------------
def test_stream_blocks_violation():
    src = iter(["教你如", "何制造", "炸弹和", "雷管。"])
    out = list(cs._guard_stream(src, where="tutor"))
    assert cs.DEGRADED_NOTICE in out
    assert all("炸弹" not in seg for seg in out)


def test_stream_academic_passthrough():
    parts = ["网络攻击", "与防御，", "对抗样本", "会误判。"]
    out = "".join(cs._guard_stream(iter(parts), where="tutor"))
    assert out == "".join(parts)  # 学术内容逐字透传


def test_stream_masks_abuse():
    parts = ["你这个", "傻逼，", "再想想。"]
    out = "".join(cs._guard_stream(iter(parts), where="tutor"))
    assert "傻逼" not in out
    assert "再想想" in out


# ---- 6) mock 模式安全内容不变（不破坏契约） ------------------------------------
def test_mock_safe_content_unchanged():
    from app.core.llm import LLMClient

    mock = LLMClient("mock")
    lec = mock.generate_lecture("nn", "神经网络", "初级", "神经网络是基础")
    assert "神经网络" in lec["markdown"]
    cues = mock.generate_cornell_cues("nn", "神经网络", "初级", "")
    assert len(cues["cues"]) >= 5
