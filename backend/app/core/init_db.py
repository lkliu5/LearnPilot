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


def init_db() -> None:
    """建表 + 幂等种子。"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed_users(db)
        _seed_knowledge_points(db)
        _seed_lessons(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("[init_db] 数据库初始化与种子完成（幂等）。")
