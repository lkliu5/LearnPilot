"""测验服务（B2-b；B6 追加 9.2 错题强化）。

覆盖接口文档 9.1 / 9.2：
- get_questions：GET /quiz/{kpId} → { questions: QuizQuestion[] }（种子题，含
  correct_answer/explanation，契约 2.5 要求一并返回）。
- submit：POST /quiz/{kpId}/submit → 判分；score≥60 → passed，并联动掌握度
  置 passed（7.3），返回 wrong[] 与 masteryUpdated。
- reinforce：POST /reinforce → 错题 → 薄弱点定位 → recap + 针对性练习
  （LLMClient 双模式：mock 确定性 / deepseek 真实生成；critic 审核练习题
  答案自洽后才返回，mock 产物同样过审保证口径统一）。

判分口径与前端 QuizRenderer 一致：single/boolean 直接比较，multiple 需集合相等
（顺序无关）。score = 答对数 / 总题数 × 100（四舍五入），passed = score ≥ 60。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.llm import LLMGenerationError, audit_practice, get_llm
from app.models.entities import KnowledgePoint, QuizQuestion
from app.schemas.resource import QuizAnswerItem
from app.services import mastery as mastery_service

PASS_SCORE = 60


class UnknownKnowledgePoint(Exception):
    """知识点不存在（→ code 1004 / 404）。"""


def _question_to_dict(q: QuizQuestion) -> dict[str, Any]:
    """转 QuizQuestion 契约结构（接口文档 2.5）。"""
    return {
        "question_id": q.question_id,
        "question_type": q.question_type,
        "question_text": q.question_text,
        "options": q.options,
        "correct_answer": q.correct_answer,
        "explanation": q.explanation,
    }


def _list_questions(db: Session, kp_id: str) -> list[QuizQuestion]:
    return (
        db.query(QuizQuestion)
        .filter(QuizQuestion.kp_id == kp_id)
        .order_by(QuizQuestion.question_id)
        .all()
    )


def get_questions(db: Session, kp_id: str) -> dict[str, Any]:
    """获取测验题（接口文档 9.1）。知识点不存在 → 抛 UnknownKnowledgePoint。"""
    if db.get(KnowledgePoint, kp_id) is None:
        raise UnknownKnowledgePoint(kp_id)
    questions = _list_questions(db, kp_id)
    return {"questions": [_question_to_dict(q) for q in questions]}


def _is_correct(question: QuizQuestion, answer: Any) -> bool:
    """判定单题是否答对。multiple 需集合相等（顺序无关）。"""
    correct = question.correct_answer
    if isinstance(correct, list):
        if not isinstance(answer, list):
            return False
        return sorted(answer) == sorted(correct)
    return answer == correct


def submit(
    db: Session, user_id: str, kp_id: str, answers: list[QuizAnswerItem]
) -> dict[str, Any]:
    """提交作答并判分（接口文档 9.1）。≥60 联动掌握度置 passed。"""
    if db.get(KnowledgePoint, kp_id) is None:
        raise UnknownKnowledgePoint(kp_id)

    questions = _list_questions(db, kp_id)
    total = len(questions)
    answer_map = {a.question_id: a.answer for a in answers}

    wrong: list[dict[str, Any]] = []
    correct_count = 0
    for q in questions:
        if _is_correct(q, answer_map.get(q.question_id)):
            correct_count += 1
        else:
            wrong.append(_question_to_dict(q))

    score = round(correct_count / total * 100) if total else 0
    passed = score >= PASS_SCORE

    mastery_updated: dict[str, Any] | None = None
    if passed:
        status = mastery_service.mark_pass(db, user_id, kp_id)
        mastery_updated = {"id": kp_id, "status": status}

    return {
        "score": score,
        "passed": passed,
        "correctCount": correct_count,
        "total": total,
        "wrong": wrong,
        "masteryUpdated": mastery_updated,
    }


def reinforce(
    db: Session, user_id: str, kp_id: str, wrong_question_ids: list[str]
) -> list[dict[str, Any]]:
    """错题强化生成（接口文档 9.2）。

    错题 id 经种子题库回查题面（未知 id 跳过）→ LLMClient.generate_reinforcement
    定位薄弱点并产出 recap + practice → critic 审核（audit_practice）兜底校验
    答案自洽（deepseek 分支内部已审核重试，此处为最终防线；mock 产物零成本同审）。
    """
    kp = db.get(KnowledgePoint, kp_id)
    if kp is None:
        raise UnknownKnowledgePoint(kp_id)

    questions = {q.question_id: q for q in _list_questions(db, kp_id)}
    wrong = [
        _question_to_dict(questions[qid])
        for qid in wrong_question_ids
        if qid in questions
    ]
    if not wrong:
        return []

    cards = get_llm().generate_reinforcement(kp.name, wrong)
    for card in cards:
        issues = audit_practice(card["practice"])
        if issues:
            raise LLMGenerationError(f"强化练习审核未通过：{issues}")
    return cards
