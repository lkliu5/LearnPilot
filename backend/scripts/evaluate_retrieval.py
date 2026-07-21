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
from app.rag.evaluation import measure_latency_phases, validate_evaluation_dataset
from app.rag.embeddings import (
    Embedder,
    EmbeddingProfile,
    EmbeddingUnavailableError,
    set_embedder_for_evaluation,
)
from app.rag.pipeline import TrustedRetrievalPipeline
from app.rag.retriever import HybridRetriever, LegacyHybridRetriever, get_retriever
from app.rag.vector_store import _ChromaStore
from app.core.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="运行可信检索离线基线评测")
    parser.add_argument(
        "--dataset",
        default=str(_BACKEND_ROOT / "evaluation" / "retrieval_cases.json"),
    )
    parser.add_argument("--output", help="可选JSON报告路径；缺省输出stdout")
    parser.add_argument("--collection", help="离线评测专用Collection；不切换生产默认")
    parser.add_argument("--embedding-mode", choices=["configured", "hash", "real"], default="configured")
    parser.add_argument("--require-real", action="store_true")
    parser.add_argument("--steady-rounds", type=int, default=5)
    parser.add_argument(
        "--compare-legacy",
        action="store_true",
        help="使用TASK-003-C1旧Hybrid算法作为before基线",
    )
    parser.add_argument(
        "--compare-d1",
        action="store_true",
        help="关闭Score Calibration，使用TASK-003-D1排序作为before基线",
    )
    args = parser.parse_args()

    cases = load_evaluation_cases(args.dataset)
    require_real = (
        args.require_real
        or args.embedding_mode == "real"
        or settings.embedding_evaluation_require_real
    )
    if args.embedding_mode == "hash":
        profile = EmbeddingProfile("hash", "deterministic-hash-v1", settings.embedding_dimension)
        embedder = Embedder(profile=profile, allow_fallback=True)
    else:
        profile = EmbeddingProfile("sentence-transformers", settings.embedding_model_name, settings.embedding_dimension)
        embedder = Embedder(profile=profile, allow_fallback=not require_real)
    set_embedder_for_evaluation(embedder)
    try:
        embedding_status = embedder.require_real() if require_real else embedder.status(load=True)
    except EmbeddingUnavailableError as exc:
        blocked = {"status": "blocked", "requestedMode": "real_embedding", "reason": str(exc)}
        rendered = json.dumps(blocked, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            print(rendered)
        raise SystemExit(2)

    if args.collection:
        store = _ChromaStore(settings.chroma_dir, collection=args.collection, profile=profile)
        if args.compare_legacy and args.compare_d1:
            parser.error("--compare-legacy和--compare-d1不能同时使用")
        if args.compare_legacy:
            old = LegacyHybridRetriever(store_getter=lambda: store)
            old_system_name = "hybrid_retriever"
        else:
            old_retriever = HybridRetriever(
                store_getter=lambda: store,
                enable_score_calibration=not args.compare_d1,
            )
            old = (
                TrustedRetrievalPipeline(retriever=old_retriever)
                if args.compare_d1
                else old_retriever
            )
            old_system_name = "d1_baseline" if args.compare_d1 else "hybrid_retriever"
        new_retriever = HybridRetriever(store_getter=lambda: store)
        available = store.get_all()
        validate_evaluation_dataset(
            cases,
            available_document_ids={item["metadata"].get("document_id") for item in available},
            available_chunk_ids={item["id"] for item in available},
        )
    else:
        old = get_retriever()
        new_retriever = old
    pipeline = TrustedRetrievalPipeline(retriever=new_retriever)
    report = RetrievalEvaluator(
        old,
        pipeline,
        old_system_name=old_system_name if args.collection else "hybrid_retriever",
        new_system_name="d2a_calibrated" if args.compare_d1 else "trusted_pipeline",
    ).evaluate(cases)
    sample_request = cases[0]
    latency = measure_latency_phases(
        lambda: (
            old.execute({"query": sample_request.query, "user_id": "offline-evaluation", "top_k": 5})
            if isinstance(old, TrustedRetrievalPipeline)
            else old.search(sample_request.query, top_k=5)
        ),
        lambda: pipeline.execute({"query": sample_request.query, "user_id": "offline-evaluation", "top_k": 5}),
        steady_rounds=args.steady_rounds,
    )
    payload = report.model_dump(mode="json")
    payload["embeddingRuntime"] = embedding_status
    payload["latencyPhases"] = latency
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
