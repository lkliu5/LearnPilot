"""Profile / LearningPath 请求体校验（B2-a）。

字段名严格对齐《后端接口文档》4.2 / 4.3 / 6.2（camelCase 契约字段）。
parse 接口为 multipart，用 Form/File 解析，不在此建模。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FieldValue(BaseModel):
    """带来源的单值字段（接口文档 4.1 education/major/goal）。"""

    value: str
    source: str | None = None  # resume|ocr|text|manual


class SkillItem(BaseModel):
    """技能项（接口文档 4.1 skills）。name 取自固定 6 维。"""

    name: str
    level: int = 0  # 0-100
    source: str | None = None


class Material(BaseModel):
    """材料引用（接口文档 4.1 materials）。kind: doc|image|text。"""

    id: str
    label: str
    kind: str


class DraftProfile(BaseModel):
    """4.2 请求中的结构化画像草稿（4.1 ParsedProfile 子集）。"""

    education: FieldValue | None = None
    major: FieldValue | None = None
    goal: FieldValue | None = None
    skills: list[SkillItem] = Field(default_factory=list)


class TargetJob(BaseModel):
    """目标岗位（接口文档 4.2 targetJob，可为 null）。"""

    name: str
    radar: dict[str, int] = Field(default_factory=dict)


class NarrativeRequest(BaseModel):
    """POST /profile/narrative 请求体（接口文档 4.2）。"""

    draft: DraftProfile
    materials: list[Material] = Field(default_factory=list)
    targetJob: TargetJob | None = None


class DiagnosisCompleteRequest(BaseModel):
    """POST /profile/diagnosis-complete 请求体（接口文档 4.3）。"""

    targetJobName: str
    matchPct: int  # 0-100


class GeneratePathRequest(BaseModel):
    """POST /learning-path/generate 请求体（接口文档 6.2，targetJobId 可选）。"""

    targetJobId: str | None = None


class PortraitDimensionItem(BaseModel):
    """单个画像维度（接口文档 17.2 PortraitDimension）。

    简历 / 手动路径把表单输入映射为与对话诊断同一套 canonical key 后回写。
    updatedAt 由服务端统一加盖，请求体可不带。
    """

    key: str
    label: str
    value: str = ""
    score: int | None = None  # 仅可量化维度（如知识基础）0-100
    confidence: float = 0.6
    source: str = "manual"  # dialogue|manual|inferred


class StudentPortraitWriteRequest(BaseModel):
    """PUT /profile/student-portrait 请求体（接口文档 17.4，覆盖写入权威画像）。"""

    dimensions: list[PortraitDimensionItem] = Field(default_factory=list)


class DialogueRequest(BaseModel):
    """POST /profile/dialogue 请求体（接口文档 17.1，对话式画像诊断）。

    sessionId 首轮可空（后端生成 d_ 前缀 id）；message 学生自然语言输入；
    context 可选，首轮可带已知信息（major/goal，复用 4.1 枚举），多余键忽略。
    """

    sessionId: str | None = None
    message: str = ""
    context: dict[str, Any] | None = None
