"""ORM 模型（B1）。

字段命名严格对齐《后端接口文档》第 2 章数据字典与第 14 章管理端模型：
- 对外 JSON 用 camelCase（如 lessonSeq / graphNodeId / questionType），
  列名在此用 snake_case，schema 层做映射，避免 Python 关键字/风格冲突。
- 本阶段（B1）只负责建表与种子，业务读写在 B2+ 落地。

覆盖 10 张表：User / KnowledgePoint / Lesson / Mastery / Journey /
ResourceCache / QuizQuestion / KnowledgeDocument / PromptTemplate / JobSnapshot。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """用户（含 role 双角色）。对应登录响应 user 对象（接口文档 3.1 / 15.1）。"""

    __tablename__ = "users"

    # 对外 user.userId；用字符串 ID（如 u_10001）便于契约对齐
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="learner")  # learner | admin
    # B9：账号启停（禁用 → 登录受阻，接口文档 16.0/16.4）；最近活跃 = 最近登录时间（16.2）
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class KnowledgePoint(Base):
    """知识点（接口文档 2.1）。固定 6 核心知识点。"""

    __tablename__ = "knowledge_points"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # 如 nn
    name: Mapped[str] = mapped_column(String(64))
    lesson_seq: Mapped[int] = mapped_column(Integer)  # 对外 lessonSeq
    graph_node_id: Mapped[str] = mapped_column(String(32))  # 对外 graphNodeId
    description: Mapped[str] = mapped_column(Text, default="")  # 供 8.1 知识点元信息


class Lesson(Base):
    """学习路径课程（接口文档 2.3）。B1 种子 6 课 sequence 1-6。"""

    __tablename__ = "lessons"

    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)  # 1-6
    topic: Mapped[str] = mapped_column(String(128))
    difficulty: Mapped[str] = mapped_column(String(16))  # 入门|初级|中级|高级|精通
    status: Mapped[str] = mapped_column(String(16))  # completed|in_progress|pending
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    description: Mapped[str] = mapped_column(Text, default="")


class Mastery(Base):
    """掌握度（接口文档 2.2 / 7.1，Record<kpId,KPStatus> 行存）。"""

    __tablename__ = "mastery"
    __table_args__ = (UniqueConstraint("user_id", "kp_id", name="uq_mastery_user_kp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    kp_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16))  # learning|pending-check|passed
    # C2 能力口径统一：能力分(0-100)单一来源——诊断微测写低置信基线、真实 quiz 写高置信，
    # 同一行覆盖更新；4.4 能力雷达读此分。三列均可空（向后兼容旧行，未测=None）。
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100，None=未测
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1
    score_source: Mapped[str | None] = mapped_column(String(16), nullable=True)  # diagnostic|quiz


class Journey(Base):
    """学习旅程（接口文档 7.4）。currentStep 由 B2 按规则推导，不入库。"""

    __tablename__ = "journeys"

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id"), primary_key=True
    )
    has_diagnosed: Mapped[bool] = mapped_column(Boolean, default=False)
    has_generated_path: Mapped[bool] = mapped_column(Boolean, default=False)
    target_job_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    match_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 真实规划 Agent（接口文档 6.2）产出的该用户个性化路径快照：Lesson[] + 每步
    # reason/resources（additive 字段，见接口文档 6.3 增量）。NULL = 尚未生成 → GET
    # 回落全局种子路径（向后兼容）。首次生成后落库，GET 命中缓存（同一画像不重复规划）。
    path_plan: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # C2：缓存路径对应的画像/掌握度指纹（planner.portrait_fingerprint）。GET 时若当前
    # 指纹与此不符 → 画像已变 → 实时重算个性化路径（不缓存写死）。NULL = 未缓存。
    path_fingerprint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # C2：整体规划叙述（"为你这样规划的理由"），随 path_plan 一并缓存，GET 回 summary.narrative。
    path_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResourceCache(Base):
    """资源生成缓存（接口文档 8.2 讲义产物等）。B2+ 写入。"""

    __tablename__ = "resource_cache"
    __table_args__ = (
        UniqueConstraint("kp_id", "difficulty", "kind", name="uq_res_kp_diff_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kp_id: Mapped[str] = mapped_column(String(32), index=True)
    difficulty: Mapped[str] = mapped_column(String(16), default="")
    kind: Mapped[str] = mapped_column(String(32), default="lecture")  # lecture|video|...
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # 完整响应体
    hallucination_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class QuizQuestion(Base):
    """测验题（接口文档 2.5）。B2 种子题库。"""

    __tablename__ = "quiz_questions"

    question_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kp_id: Mapped[str] = mapped_column(String(32), index=True)
    question_type: Mapped[str] = mapped_column(String(16))  # single|multiple|boolean
    question_text: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON, default=list)  # [{option_id,option_text}]
    correct_answer: Mapped[object] = mapped_column(JSON)  # string 或 string[]
    explanation: Mapped[str] = mapped_column(Text, default="")


class KnowledgeDocument(Base):
    """知识库文档（接口文档 14.1）。B3 灌库回填 chunks/status。"""

    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # doc_001
    title: Mapped[str] = mapped_column(String(256))
    filename: Mapped[str] = mapped_column(String(256))
    size: Mapped[int] = mapped_column(Integer, default=0)  # 字节
    category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tags: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|indexing|indexed|failed
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PromptTemplate(Base):
    """Agent Prompt 模板（接口文档 14.5，热更新）。agentId 固定 3 项。"""

    __tablename__ = "prompt_templates"

    agent_id: Mapped[str] = mapped_column(String(32), primary_key=True)  # diagnosis|generation|critic
    name: Mapped[str] = mapped_column(String(64))
    template: Mapped[str] = mapped_column(Text)
    variables: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class WorkflowTrace(Base):
    """工作流执行轨迹（B5-a）。结构满足接口文档 11.2 agents/messages 渲染，B7 直接消费。

    - agents / messages：11.2 响应 data 的同名数组（驱动 AgentStatusCard / 消息日志）；
    - node_log：每节点 {agent,name,startedAt,endedAt,durationMs,retryIndex,outputSummary,promptExcerpt}；
    - rag_context_used：本次生成实际使用的检索切片（B5-a 为确定性 mock，B5-b 接真实检索）。
    """

    __tablename__ = "workflow_traces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # wf_xxx
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    kp_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16))  # success|degraded|failed
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hallucination_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    agents: Mapped[list] = mapped_column(JSON, default=list)  # 11.2 agents[]
    messages: Mapped[list] = mapped_column(JSON, default=list)  # 11.2 messages[]
    node_log: Mapped[list] = mapped_column(JSON, default=list)
    rag_context_used: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StudentPortrait(Base):
    """异质学生动态画像（接口文档 17.2 / 17.3，C1-b）。

    每用户一行，dimensions 存 PortraitDimension[]（contract camelCase 形态：
    key/label/value/score?/confidence/source/updatedAt）。由对话式诊断（17.1）
    增量构建、随学习/测验更新（随学随新）；与 ability-portrait（4.4 固定 6 知识点
    雷达）并存、互不替换。空画像 dimensions=[]（17.3「尚未开始诊断」占位）。
    """

    __tablename__ = "student_portraits"

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id"), primary_key=True
    )
    dimensions: Mapped[list] = mapped_column(JSON, default=list)  # PortraitDimension[]
    version: Mapped[str] = mapped_column(String(16), default="v1")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class JobSnapshot(Base):
    """岗位市场快照（接口文档 2.4 / 15.5）。payload 存完整 JobMarket 结构。

    B6：种子从 frontend/public/data/job-market/*.json 导入（demo 阶段后端托管
    预置快照即数据源）；生产路径为离线采集管线定期刷新本表（写 README，不在 demo 实现）。
    """

    __tablename__ = "job_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # llm-app
    name: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # 热榜顺序（5.1 契约示例序）
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ExternalResource(Base):
    """外部精选资源（接口文档 8.6，B6 种子精选库）。

    demo 阶段为人工精选种子（每核心知识点 3-4 条，relevance/credibility 为
    审核 Agent 评分口径的预置值）；生产路径：聚合 Agent 调 YouTube Data API /
    B 站 / arXiv / 慕课等搜索 API 检索候选 → critic Agent 按相关性 + 来源可信度
    评分过滤 → 写回本表（接口签名不变，写 README，不在 demo 实现）。
    """

    __tablename__ = "external_resources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # nn-r1
    kp_id: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(8))  # 视频|论文|文档|课程
    title: Mapped[str] = mapped_column(String(256))
    source: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(512))
    embed: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 可嵌入播放地址
    duration: Mapped[str | None] = mapped_column(String(32), nullable=True)
    relevance: Mapped[int] = mapped_column(Integer, default=0)  # 相关度 0-100
    credibility: Mapped[int] = mapped_column(Integer, default=0)  # 可信度 0-100
    reason: Mapped[str] = mapped_column(Text, default="")


class LearningStepProgress(Base):
    """学习步骤进度（接口文档 18.3，C2）。单用户单知识点下各过程步骤完成标记。

    步骤集固定 6 项：video|lecture|diagram|note|feynman|practice（视频/讲义/图解/
    笔记/费曼/实操）。与 Mastery（2.2 三态）**解耦**——Mastery 粒度不足以表达 6 步
    过程；「已掌握」仍由阶段测试（9.1）驱动 Mastery（7.3），本表只记过程完成标记。
    **无外键耦合**（user_id 仅作隔离键，不建外键），不改 Journey/Mastery 表（契约 18.6）。
    """

    __tablename__ = "learning_step_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "kp_id", "step", name="uq_step_user_kp_step"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    kp_id: Mapped[str] = mapped_column(String(32), index=True)
    step: Mapped[str] = mapped_column(String(16))  # video|lecture|diagram|note|feynman|practice
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class LearningNote(Base):
    """康奈尔笔记（接口文档 18.4/18.5，C2）。单用户单知识点一份三栏笔记。

    cue_notes（线索区作答 [{cueId,text}]）、main_notes（主笔记区 Markdown）、
    summary（总结区）。轻量持久化（随学随新、跨设备不丢，契约 18.6 建议），
    **无外键耦合**，不改 Journey/Mastery 表。
    """

    __tablename__ = "learning_notes"
    __table_args__ = (UniqueConstraint("user_id", "kp_id", name="uq_note_user_kp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    kp_id: Mapped[str] = mapped_column(String(32), index=True)
    cue_notes: Mapped[list] = mapped_column(JSON, default=list)  # [{cueId,text}]
    main_notes: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class QuizAttempt(Base):
    """测验作答历史埋点（C-fix 批3：学习过程评估行为数据层）。

    每次 9.1 提交落一行（轻量埋点），供「学习评估 Agent」聚合做题表现/趋势/效率。
    与既有判分链路解耦——只记录结果快照，不改 quiz/Mastery 判分逻辑；**无外键耦合**
    （user_id/kp_id 仅作隔离/分组键），不改既有表结构。
    """

    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    kp_id: Mapped[str] = mapped_column(String(32), index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)  # 综合得分 0-100
    correct_count: Mapped[int] = mapped_column(Integer, default=0)  # 客观答对数
    total: Mapped[int] = mapped_column(Integer, default=0)  # 总题数
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
