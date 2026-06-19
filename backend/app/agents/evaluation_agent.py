"""学习过程评估 Agent（接口文档 12.2，C-fix 批3）。

赛题「学习评估 Agent」：基于真实学习行为数据产出**多维学习评估 + 动态调整建议**。
编排三步（数据 → 指标 → 叙述），与既有 Agent（诊断/生成/审核/规划/费曼）并列：

1. `learning_eval.gather_signals`：复用既有 Mastery/Journey/QuizAttempt/Steps/Notes 汇总
   真实学习行为信号（因人而异，新用户归 0/中性）；
2. `learning_eval.compute_metrics`：据信号派生确定性多维指标（掌握进度/测验表现/学习效率/
   学习投入）+ 综合分 + 趋势 + 薄弱点；
3. `LLMClient.evaluate_learning`：在指标之上叠加学习综述 + 方法建议（mock 确定性 / deepseek
   真实），并给确定性动态调整建议（下一步学什么 / 难度调整）。

输出供 12.2 `GET /dashboard/evaluation` 直出，前端「学习评估」面板渲染。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.llm import get_llm
from app.services import learning_eval


def evaluate(db: Session, user_id: str) -> dict[str, Any]:
    """产出该用户的多维学习评估（接口文档 12.2）。"""
    signals = learning_eval.gather_signals(db, user_id)
    metrics = learning_eval.compute_metrics(signals)
    llm = get_llm()
    narrative = llm.evaluate_learning(signals, metrics)

    return {
        "overallScore": metrics["overallScore"],
        "level": metrics["level"],
        "trend": metrics["trend"],
        "dimensions": metrics["dimensions"],
        "weakPoints": metrics["weakPoints"],
        "summary": narrative["summary"],
        "suggestions": narrative["suggestions"],
        "adjustment": narrative["adjustment"],
        "generatedBy": "mock" if llm.is_mock else llm.provider,
        # 透明化原始行为信号（轻量子集，供前端可选展示/调试，不喧宾夺主）
        "signals": {
            "masteredCount": signals["masteredCount"],
            "totalCore": signals["totalCore"],
            "attemptCount": signals["attemptCount"],
            "avgBestScore": signals["avgBestScore"],
            "stepsDone": signals["stepsDone"],
            "notesFilled": signals["notesFilled"],
            "retries": signals["retries"],
        },
    }
