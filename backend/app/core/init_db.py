"""数据库初始化与种子（B1）。

可重复执行（幂等）：
- create_all 本身幂等；
- 种子按主键存在性判断，已存在则跳过，绝不重复插入或覆盖。

种子内容（B1 验收要求）：
- 2 个账号：admin/admin123（role=admin）、learner_001/123456（role=learner）；
- 6 个核心知识点（接口文档 2.1）；
- 6 课学习路径 sequence 1-6（接口文档 2.3）；
- 两个用户的初始 Journey（hasDiagnosed=False / hasGeneratedPath=False）。

运行方式：
- 应用启动时由 main.py lifespan 调用；
- 亦可独立执行：`python -m app.core.init_db`。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.entities import (  # noqa: F401  确保所有表在 create_all 前注册
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


def init_db() -> None:
    """建表 + 幂等种子。"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed_users(db)
        _seed_knowledge_points(db)
        _seed_lessons(db)
        _seed_quiz_questions(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("[init_db] 数据库初始化与种子完成（幂等）。")
