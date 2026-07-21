"""运行TASK-003-C1离线检索基线，不接入生产API。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.rag.evaluation import RetrievalEvaluator, load_evaluation_cases
from app.rag.pipeline import TrustedRetrievalPipeline
from app.rag.retriever import get_retriever


def main() -> None:
    parser = argparse.ArgumentParser(description="运行可信检索离线基线评测")
    parser.add_argument(
        "--dataset",
        default=str(_BACKEND_ROOT / "evaluation" / "retrieval_cases.json"),
    )
    parser.add_argument("--output", help="可选JSON报告路径；缺省输出stdout")
    args = parser.parse_args()

    cases = load_evaluation_cases(args.dataset)
    old = get_retriever()
    report = RetrievalEvaluator(
        old,
        TrustedRetrievalPipeline(retriever=old),
    ).evaluate(cases)
    rendered = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
