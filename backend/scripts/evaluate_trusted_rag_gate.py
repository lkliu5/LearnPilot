"""Run TASK-004-E1 Trusted RAG Gate against frozen offline evidence."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.rag.trusted_rag_gate import (
    FaultInjectionResults,
    RerankMetrics,
    ShadowMetrics,
    TrustedRAGGate,
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="TASK-004-E1 offline canary Gate")
    parser.add_argument(
        "--shadow-metrics",
        help="Optional aggregated real Shadow metrics JSON; omitted means unavailable.",
    )
    parser.add_argument(
        "--fault-results",
        default=str(_BACKEND_ROOT / "evaluation" / "trusted_rag_fault_results.json"),
    )
    parser.add_argument(
        "--rerank-results",
        default=str(_BACKEND_ROOT / "evaluation" / "rerank_blind_results.json"),
    )
    parser.add_argument(
        "--output",
        default=str(_BACKEND_ROOT / "evaluation" / "trusted_rag_gate_decision.json"),
    )
    args = parser.parse_args()

    shadow: ShadowMetrics | None = None
    if args.shadow_metrics:
        shadow = ShadowMetrics.model_validate(_read_json(Path(args.shadow_metrics)))
    else:
        # Rerank evidence is known, while production Shadow quality/performance is absent.
        shadow = ShadowMetrics(rerank=RerankMetrics.from_blind_evaluation(
            _read_json(Path(args.rerank_results))
        ))

    faults = FaultInjectionResults.from_report(_read_json(Path(args.fault_results)))
    decision = TrustedRAGGate().evaluate(shadow, faults)
    payload = {
        "schemaVersion": "trusted-rag-canary-gate-v1",
        "evaluationType": "offline_canary_admission_gate",
        "generatedAt": datetime.now(UTC).isoformat(),
        "productionMutation": False,
        "inputs": {
            "shadowMetrics": args.shadow_metrics,
            "faultResults": str(Path(args.fault_results)),
            "rerankResults": str(Path(args.rerank_results)),
        },
        **decision.model_dump(mode="json"),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
