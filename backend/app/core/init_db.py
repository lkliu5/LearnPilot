"""数据库初始化与种子（B1）。

可重复执行（幂等）：
- create_all 本身幂等；
- 种子按主键存在性判断，已存在则跳过，绝不重复插入或覆盖。

种子内容（B1 验收要求）：
- 2 个账号：admin/admin123（role=admin）、learner_001/123456（role=learner）；
- 6 个核心知识点（接口文档 2.1）；
- 6 课学习路径 sequence 1-6（接口文档 2.3）；
- 两个用户的初始 Journey（hasDiagnosed=False / hasGeneratedPath=False）。

B6 追加种子：
- JobSnapshot：从 frontend/public/data/job-market/*.json 导入 4 岗位（接口文档 2.4/15.5）；
- ExternalResource：6 核心知识点 × 3-4 条精选外部资源（接口文档 8.6）。

运行方式：
- 应用启动时由 main.py lifespan 调用；
- 亦可独立执行：`python -m app.core.init_db`。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.entities import (  # noqa: F401  确保所有表在 create_all 前注册
    ExternalResource,
    JobSnapshot,
    Journey,
    KnowledgePoint,
    Lesson,
    QuizQuestion,
    User,
)

# 6 核心知识点（接口文档 2.1）：(id, name, lessonSeq, graphNodeId, description)
_KNOWLEDGE_POINTS = [
    ("ml", "机器学习基础", 1, "ml", "监督/无监督学习、特征与损失、过拟合与正则。"),
    ("nn", "神经网络基础", 2, "nn", "神经元模型、前向传播、激活函数与反向传播。"),
    ("dl", "深度学习原理", 3, "dl", "反向传播、梯度下降与优化器、正则与归一化。"),
    ("cnn", "CNN架构", 4, "cnn", "卷积、池化、感受野与经典卷积网络。"),
    ("transformer", "Transformer架构", 5, "transformer", "自注意力、多头注意力与位置编码。"),
    ("finetune", "大模型微调技术", 6, "finetune", "全参/LoRA/指令微调与对齐。"),
]

# 6 课学习路径（接口文档 2.3）：(sequence, topic, difficulty, status, progress, description)
_LESSONS = [
    (1, "机器学习基础", "入门", "completed", 100, "监督学习、损失函数与过拟合的直觉建立。"),
    (2, "神经网络基础", "初级", "completed", 100, "神经元、前向传播与激活函数。"),
    (3, "深度学习原理", "中级", "in_progress", 65, "反向传播、梯度下降与优化器。"),
    (4, "CNN架构", "中级", "pending", 0, "卷积、池化与经典卷积网络结构。"),
    (5, "Transformer架构", "高级", "pending", 0, "自注意力机制与多头注意力。"),
    (6, "大模型微调技术", "精通", "pending", 0, "LoRA 与指令微调实战。"),
]

# 种子测验题（接口文档 2.5 / 9.1，B2-b）：每个核心知识点 3 题（single/multiple/boolean）。
# nn 三题与前端 LearningResource.tsx 的 quizQuestions 逐字对齐；其余 KP 为领域题。
# 结构：kp_id -> [(question_id, type, text, options[(id,text)], correct_answer, explanation)]
_QUIZ_QUESTIONS: dict[str, list] = {
    "nn": [
        ("nn_q1", "single", "一个神经元的运算顺序是？",
         [("a", "激活函数 → 加权求和 → 加偏置"), ("b", "加权求和 → 加偏置 → 激活函数"),
          ("c", "加偏置 → 激活函数 → 加权求和")], "b",
         "神经元先对输入加权求和，再加上偏置，最后通过激活函数得到输出。"),
        ("nn_q2", "multiple", "以下哪些是常见的激活函数？（多选）",
         [("a", "ReLU"), ("b", "Sigmoid"), ("c", "Gradient"), ("d", "Tanh")], ["a", "b", "d"],
         "ReLU、Sigmoid、Tanh 都是常见激活函数；Gradient（梯度）是反向传播中的概念，不是激活函数。"),
        ("nn_q3", "boolean", "ReLU 激活函数有助于缓解梯度消失问题。",
         [("true", "正确"), ("false", "错误")], "true",
         "ReLU 在正区间梯度恒为 1，相比 Sigmoid 能有效缓解深层网络的梯度消失问题。"),
    ],
    "ml": [
        ("ml_q1", "single", "过拟合（overfitting）最典型的表现是？",
         [("a", "训练集表现好、测试集表现差"), ("b", "训练集与测试集都很差"),
          ("c", "训练集差、测试集好")], "a",
         "过拟合指模型记住了训练集噪声，泛化能力下降，表现为训练好、测试差。"),
        ("ml_q2", "multiple", "下列哪些属于监督学习任务？（多选）",
         [("a", "分类"), ("b", "回归"), ("c", "聚类"), ("d", "降维")], ["a", "b"],
         "分类与回归有标注目标，属监督学习；聚类与降维通常是无监督学习。"),
        ("ml_q3", "boolean", "正则化（如 L2）有助于缓解过拟合。",
         [("true", "正确"), ("false", "错误")], "true",
         "正则化通过惩罚过大参数限制模型复杂度，从而缓解过拟合。"),
    ],
    "dl": [
        ("dl_q1", "single", "反向传播（Backpropagation）的核心作用是？",
         [("a", "计算损失函数对参数的梯度"), ("b", "随机初始化网络权重"),
          ("c", "对输入数据做归一化")], "a",
         "反向传播利用链式法则计算损失对各层参数的梯度，供梯度下降更新权重。"),
        ("dl_q2", "multiple", "下列哪些是常见的优化器？（多选）",
         [("a", "SGD"), ("b", "Adam"), ("c", "RMSprop"), ("d", "ReLU")], ["a", "b", "c"],
         "SGD、Adam、RMSprop 都是优化器；ReLU 是激活函数。"),
        ("dl_q3", "boolean", "批归一化（BatchNorm）可加速训练并缓解梯度问题。",
         [("true", "正确"), ("false", "错误")], "true",
         "BatchNorm 稳定每层输入分布，常能加速收敛并缓解梯度消失/爆炸。"),
    ],
    "cnn": [
        ("cnn_q1", "single", "卷积层（Convolution）的主要作用是？",
         [("a", "提取局部空间特征"), ("b", "对全连接层降维"),
          ("c", "生成位置编码")], "a",
         "卷积核在空间上滑动以提取局部特征（如边缘、纹理），并共享权重。"),
        ("cnn_q2", "multiple", "下列哪些是 CNN 的常见组件？（多选）",
         [("a", "卷积层"), ("b", "池化层"), ("c", "全连接层"), ("d", "自注意力层")], ["a", "b", "c"],
         "卷积、池化、全连接是经典 CNN 组件；自注意力是 Transformer 的核心。"),
        ("cnn_q3", "boolean", "池化层（Pooling）可以降低特征图的空间尺寸。",
         [("true", "正确"), ("false", "错误")], "true",
         "池化通过下采样减小特征图尺寸，降低计算量并增强平移不变性。"),
    ],
    "transformer": [
        ("transformer_q1", "single", "自注意力（Self-Attention）机制的主要作用是？",
         [("a", "建模序列中元素之间的依赖关系"), ("b", "对图像做卷积"),
          ("c", "压缩模型参数量")], "a",
         "自注意力让每个位置都能关注序列中其他位置，捕捉长距离依赖。"),
        ("transformer_q2", "multiple", "Transformer 包含下列哪些关键组件？（多选）",
         [("a", "多头注意力"), ("b", "位置编码"), ("c", "前馈网络"), ("d", "卷积核")], ["a", "b", "c"],
         "多头注意力、位置编码、前馈网络是 Transformer 的核心；卷积核不属于其结构。"),
        ("transformer_q3", "boolean", "位置编码（Positional Encoding）用于为模型注入序列顺序信息。",
         [("true", "正确"), ("false", "错误")], "true",
         "自注意力本身对顺序不敏感，需位置编码补充序列位置信息。"),
    ],
    "finetune": [
        ("finetune_q1", "single", "LoRA 微调的核心思想是？",
         [("a", "用低秩矩阵近似参数更新并冻结原权重"), ("b", "重新训练全部参数"),
          ("c", "丢弃预训练权重从零训练")], "a",
         "LoRA 在冻结原权重的同时，用低秩矩阵学习增量更新，大幅降低可训练参数量。"),
        ("finetune_q2", "multiple", "下列哪些属于参数高效微调（PEFT）方法？（多选）",
         [("a", "LoRA"), ("b", "Adapter"), ("c", "Prompt Tuning"), ("d", "全参数微调")], ["a", "b", "c"],
         "LoRA、Adapter、Prompt Tuning 仅更新少量参数；全参数微调更新全部权重，非 PEFT。"),
        ("finetune_q3", "boolean", "指令微调（Instruction Tuning）可提升模型遵循指令的能力。",
         [("true", "正确"), ("false", "错误")], "true",
         "指令微调用「指令-响应」样本训练，使模型更好地理解并遵循自然语言指令。"),
    ],
}

# 热门岗位固定顺序（接口文档 5.1 契约示例序，与前端 HOT_JOBS 一致）
_HOT_JOB_ORDER = ["llm-app", "algo-engineer", "ml-engineer", "data-analyst"]

# 精选外部资源种子（接口文档 8.6）：kp_id -> [(序号, type, title, source, url,
# embed, duration, relevance, credibility, reason)]。nn 四条与前端
# ResourceAggregator.tsx 演示数据对齐；其余 KP 为同口径人工精选。
# 生产路径：聚合 Agent 接搜索 API 检索 + critic 评分后定期刷新本表（见 entities.ExternalResource 注释）。
_EXTERNAL_RESOURCES: dict[str, list[tuple]] = {
    "ml": [
        (1, "视频", "李宏毅《机器学习》系列课程", "B站 · 李宏毅", "https://www.bilibili.com/video/BV1Wv411h7kN", "https://player.bilibili.com/player.html?bvid=BV1Wv411h7kN", "系列", 96, 94, "中文领域最权威的机器学习入门课，从回归到深度学习循序渐进。"),
        (2, "课程", "Machine Learning Specialization（Andrew Ng）", "Coursera · DeepLearning.AI", "https://www.coursera.org/specializations/machine-learning-introduction", None, "系列", 94, 97, "吴恩达经典课程重制版，监督学习与正则化讲解清晰，配套练习完善。"),
        (3, "课程", "Google 机器学习速成课程", "developers.google.com", "https://developers.google.com/machine-learning/crash-course", None, "15 小时", 90, 93, "短平快的工程视角入门，交互式可视化帮助建立损失与过拟合直觉。"),
        (4, "文档", "scikit-learn 用户指南", "scikit-learn.org", "https://scikit-learn.org/stable/user_guide.html", None, "实操", 88, 95, "官方文档配可运行示例，把监督/无监督算法落到代码实践。"),
    ],
    "nn": [
        (1, "视频", "3Blue1Brown：神经网络是什么？", "YouTube · 3Blue1Brown", "https://www.youtube.com/watch?v=aircAruvnKk", "https://www.youtube.com/embed/aircAruvnKk", "19:13", 98, 97, "可视化讲解神经元与权重，直观契合你当前「神经网络基础」知识点。"),
        (2, "课程", "CS231n：卷积神经网络（Stanford）", "Stanford 公开课", "https://cs231n.github.io/", None, "系列", 92, 96, "权威课程，从神经网络基础平滑过渡到 CNN，匹配你的下一步学习路径。"),
        (3, "论文", "Attention Is All You Need", "arXiv:1706.03762", "https://arxiv.org/abs/1706.03762", None, "15 页", 78, 99, "Transformer 奠基论文，作为你「待提升领域」的进阶拓展读物。"),
        (4, "文档", "PyTorch 官方教程 · 构建神经网络", "pytorch.org", "https://pytorch.org/tutorials/beginner/basics/buildmodel_tutorial.html", None, "实操", 90, 95, "官方动手教程，把讲义中的前向传播落到 nn.Module 代码实践。"),
    ],
    "dl": [
        (1, "视频", "3Blue1Brown：梯度下降是如何学习的", "YouTube · 3Blue1Brown", "https://www.youtube.com/watch?v=IHZwWFHWa-w", "https://www.youtube.com/embed/IHZwWFHWa-w", "21:01", 95, 96, "用可视化把梯度下降与损失曲面讲透，是反向传播的最佳直觉铺垫。"),
        (2, "文档", "《深度学习》（花书）在线版", "deeplearningbook.org", "https://www.deeplearningbook.org/", None, "教材", 92, 98, "Goodfellow 等人的领域奠基教材，优化与正则化章节与本知识点强相关。"),
        (3, "课程", "Deep Learning Specialization（吴恩达）", "Coursera · DeepLearning.AI", "https://www.coursera.org/specializations/deep-learning", None, "系列", 93, 96, "系统覆盖反向传播、优化器与调参实践，作业可逐步实现训练循环。"),
        (4, "文档", "PyTorch 官方教程 · 优化模型参数", "pytorch.org", "https://pytorch.org/tutorials/beginner/basics/optimization_tutorial.html", None, "实操", 88, 95, "把损失函数、优化器与训练循环落到可运行代码，巩固梯度下降理解。"),
    ],
    "cnn": [
        (1, "课程", "CS231n 笔记 · 卷积网络", "Stanford · cs231n.github.io", "https://cs231n.github.io/convolutional-networks/", None, "长文", 96, 96, "卷积/池化/感受野的权威讲义，配大量图示，是 CNN 架构的标准参考。"),
        (2, "文档", "CNN Explainer 交互可视化", "Georgia Tech · poloclub", "https://poloclub.github.io/cnn-explainer/", None, "交互", 93, 90, "在浏览器里逐层拖动观察卷积运算，把抽象的特征图变得可见。"),
        (3, "论文", "Deep Residual Learning（ResNet）", "arXiv:1512.03385", "https://arxiv.org/abs/1512.03385", None, "12 页", 86, 98, "经典卷积网络的里程碑，理解残差连接如何让网络更深。"),
    ],
    "transformer": [
        (1, "论文", "Attention Is All You Need", "arXiv:1706.03762", "https://arxiv.org/abs/1706.03762", None, "15 页", 97, 99, "Transformer 奠基论文，自注意力与多头注意力的第一手定义。"),
        (2, "文档", "The Illustrated Transformer", "jalammar.github.io", "https://jalammar.github.io/illustrated-transformer/", None, "图解", 96, 92, "最广为引用的图解教程，把 Q/K/V 与多头注意力拆到每一步矩阵运算。"),
        (3, "视频", "李宏毅：Transformer 详解", "YouTube · Hung-yi Lee", "https://www.youtube.com/watch?v=ugWDIIOHtPA", "https://www.youtube.com/embed/ugWDIIOHtPA", None, 94, 95, "中文系统讲解自注意力机制与位置编码，配课件推导细致。"),
        (4, "文档", "The Annotated Transformer", "Harvard NLP", "https://nlp.seas.harvard.edu/annotated-transformer/", None, "实操", 90, 94, "逐行代码复现原论文，读完即可亲手实现一个 Transformer。"),
    ],
    "finetune": [
        (1, "论文", "LoRA: Low-Rank Adaptation of LLMs", "arXiv:2106.09685", "https://arxiv.org/abs/2106.09685", None, "13 页", 96, 98, "低秩适配微调的奠基论文，理解「冻结原权重 + 低秩增量」核心思想。"),
        (2, "文档", "Hugging Face PEFT 官方文档", "huggingface.co", "https://huggingface.co/docs/peft", None, "实操", 94, 95, "参数高效微调的事实标准库，LoRA/Adapter/Prompt Tuning 即插即用。"),
        (3, "课程", "Hugging Face LLM Course · 微调章节", "huggingface.co/learn", "https://huggingface.co/learn/llm-course/chapter3/1", None, "系列", 91, 94, "手把手带你完成一次完整的预训练模型微调流程。"),
        (4, "论文", "QLoRA: Efficient Finetuning of Quantized LLMs", "arXiv:2305.14314", "https://arxiv.org/abs/2305.14314", None, "23 页", 88, 97, "量化 + LoRA 的进阶组合，单卡微调大模型的代表性工作。"),
    ],
}

# 种子账号：(id, username, displayName, password, role)
_USERS = [
    ("u_10000", "admin", "管理员", "admin123", "admin"),
    ("u_10001", "learner_001", "learner_001", "123456", "learner"),
]


def _seed_users(db: Session) -> None:
    for uid, username, display, pwd, role in _USERS:
        if db.get(User, uid) is not None:
            continue
        db.add(
            User(
                id=uid,
                username=username,
                display_name=display,
                password_hash=hash_password(pwd),
                role=role,
            )
        )
        # 每个用户初始旅程：未诊断、未生成路径
        db.add(Journey(user_id=uid, has_diagnosed=False, has_generated_path=False))


def _seed_knowledge_points(db: Session) -> None:
    for kp_id, name, seq, node, desc in _KNOWLEDGE_POINTS:
        if db.get(KnowledgePoint, kp_id) is not None:
            continue
        db.add(
            KnowledgePoint(
                id=kp_id, name=name, lesson_seq=seq, graph_node_id=node, description=desc
            )
        )


def _seed_lessons(db: Session) -> None:
    for seq, topic, diff, status, progress, desc in _LESSONS:
        if db.get(Lesson, seq) is not None:
            continue
        db.add(
            Lesson(
                sequence=seq,
                topic=topic,
                difficulty=diff,
                status=status,
                progress=progress,
                description=desc,
            )
        )


def _seed_quiz_questions(db: Session) -> None:
    for kp_id, questions in _QUIZ_QUESTIONS.items():
        for qid, qtype, text, options, correct, explanation in questions:
            if db.get(QuizQuestion, qid) is not None:
                continue
            db.add(
                QuizQuestion(
                    question_id=qid,
                    kp_id=kp_id,
                    question_type=qtype,
                    question_text=text,
                    options=[{"option_id": oid, "option_text": otext} for oid, otext in options],
                    correct_answer=correct,
                    explanation=explanation,
                )
            )


def _seed_job_snapshots(db: Session) -> None:
    """从 frontend/public/data/job-market/*.json 导入岗位快照（接口文档 2.4/15.5）。

    目录缺失/单文件损坏不致命（跳过，可重复执行补齐）；fetched_at 取 payload
    的 fetchedAt（响应中 fetchedAt 仍以 payload 为准，前端 timeAgo 渲染）。
    """
    source_dir = Path(settings.job_market_dir)
    for path in sorted(source_dir.glob("*.json")) if source_dir.is_dir() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        job_id = payload.get("id")
        if not job_id or db.get(JobSnapshot, job_id) is not None:
            continue
        try:
            fetched_at = datetime.fromisoformat(payload.get("fetchedAt", ""))
        except ValueError:
            fetched_at = None
        order = (
            _HOT_JOB_ORDER.index(job_id) + 1 if job_id in _HOT_JOB_ORDER else 99
        )
        db.add(
            JobSnapshot(
                id=job_id,
                name=payload.get("name", job_id),
                payload=payload,
                sort_order=order,
                **({"fetched_at": fetched_at} if fetched_at else {}),
            )
        )


def _seed_external_resources(db: Session) -> None:
    for kp_id, rows in _EXTERNAL_RESOURCES.items():
        for seq, rtype, title, source, url, embed, duration, rel, cred, reason in rows:
            res_id = f"{kp_id}-r{seq}"
            if db.get(ExternalResource, res_id) is not None:
                continue
            db.add(
                ExternalResource(
                    id=res_id,
                    kp_id=kp_id,
                    type=rtype,
                    title=title,
                    source=source,
                    url=url,
                    embed=embed,
                    duration=duration,
                    relevance=rel,
                    credibility=cred,
                    reason=reason,
                )
            )


def _migrate_b6() -> None:
    """B6 轻量迁移：既有开发库 job_snapshots 缺 sort_order 列时补齐。

    create_all 只建新表不加列；SQLite 支持 ADD COLUMN，幂等（先查 PRAGMA）。
    """
    inspector = inspect(engine)
    if "job_snapshots" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("job_snapshots")}
    if "sort_order" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE job_snapshots ADD COLUMN sort_order INTEGER DEFAULT 0")
            )


def _migrate_b9() -> None:
    """B9 轻量迁移：既有开发库 users 表缺 is_active / last_active_at 列时补齐。

    create_all 只建新表不加列；SQLite 支持 ADD COLUMN，幂等（先查 PRAGMA）。
    既有行 is_active 默认 1（启用），last_active_at 为 NULL（从未登录）。
    """
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "is_active" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
        if "last_active_at" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN last_active_at DATETIME"))


def init_db() -> None:
    """建表 + 幂等种子。"""
    _migrate_b6()
    _migrate_b9()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed_users(db)
        _seed_knowledge_points(db)
        _seed_lessons(db)
        _seed_quiz_questions(db)
        _seed_job_snapshots(db)
        _seed_external_resources(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("[init_db] 数据库初始化与种子完成（幂等）。")
