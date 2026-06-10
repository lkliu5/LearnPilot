"""Resource / Quiz 请求体校验（B2-b）。

字段名严格对齐《后端接口文档》8.2（讲义）/ 9.1（测验提交）的 camelCase / snake_case
契约字段：讲义请求用 camelCase（kpId/difficulty），测验题字段沿用 snake_case
（question_id 等，与 2.5 QuizQuestion 一致）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LectureRequest(BaseModel):
    """POST /resource/lecture 请求体（接口文档 8.2）。"""

    kpId: str
    difficulty: str  # 入门|初级|高级（资源页难度档，与路径难度档不同）


class QuizAnswerItem(BaseModel):
    """单题作答（接口文档 9.1）。answer：single/boolean 为 str，multiple 为 str[]。"""

    question_id: str
    answer: str | list[str]


class QuizSubmitRequest(BaseModel):
    """POST /quiz/{kpId}/submit 请求体（接口文档 9.1）。"""

    answers: list[QuizAnswerItem] = Field(default_factory=list)
