"""运行 TASK-003-D3-A Mock Rerank 离线实验。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings
from app.rag.embeddings import Embedder, EmbeddingProfile, set_embedder_for_evaluation
from app.rag.evaluation import load_evaluation_cases
from app.rag.rerank_evaluation import FixedCandidateCase, candidate_from_dict, evaluate_fixed_candidates
from app.rag.reranker import MockReranker
from app.rag.retriever import HybridRetriever
from app.rag.vector_store import _ChromaStore


def main() -> None:
    parser = argparse.ArgumentParser(description="固定 Hybrid Top20 的离线 Rerank 实验")
    parser.add_argument("--dataset", default=str(_BACKEND_ROOT / "evaluation" / "retrieval_cases.json"))
    parser.add_argument("--collection", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    profile = EmbeddingProfile("hash", "deterministic-hash-v1", settings.embedding_dimension)
    set_embedder_for_evaluation(Embedder(profile=profile, allow_fallback=True))
    store = _ChromaStore(settings.chroma_dir, collection=args.collection, profile=profile)
    retriever = HybridRetriever(store_getter=lambda: store)
    fixed_cases = []
    for case in load_evaluation_cases(args.dataset):
        filters = {"knowledge_scope": case.knowledge_scope} if case.knowledge_scope else None
        rows = retriever.search(case.query, top_k=20, filters=filters)
        fixed_cases.append(FixedCandidateCase(case, tuple(candidate_from_dict(row) for row in rows)))

    report = evaluate_fixed_candidates(fixed_cases, MockReranker())
    report["embeddingProfile"] = profile.profile_id
    report["collection"] = args.collection
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
