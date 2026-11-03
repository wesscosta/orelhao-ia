"""Executa auditoria de spans nos 40 casos arquivados, sem novas LLMs.

Exige NLI ONNX local e índice correspondente ao corpus histórico.
Nenhuma pontuação é usada para autorizar resposta.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from orelhao.services.knowledge.index import load_chunks
from orelhao.services.knowledge.span_evaluation import (
    compare_nli_spans,
    diagnose_expected_source_misses,
    dump_audit,
    load_audit_inputs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Grounding V3: auditoria de trechos literais")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--tucano", type=Path, required=True)
    parser.add_argument("--qwen", type=Path, required=True)
    parser.add_argument("--nli-model", type=Path, required=True)
    parser.add_argument("--index", type=Path, default=Path("knowledge/index"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases, results = load_audit_inputs(args.dataset, args.tucano, args.qwen)
    indexed = load_chunks(args.index)
    misses = diagnose_expected_source_misses(cases, results, indexed_chunks=indexed)
    comparison = compare_nli_spans(
        results, model_path=args.nli_model, index_dir=args.index
    )
    report = {
        "meta": {
            "created_at_utc": datetime.now(UTC).isoformat(),
            "dataset": str(args.dataset),
            "dataset_status": "model-curated-development-regression",
            "no_model_or_threshold_changes": True,
        },
        "retrieval_misses": misses,
        "span_nli": comparison,
    }
    dump_audit(args.output, report)
    print("Spans pareados:", comparison["paired_nli_observations"])
    print("Sem match lexical:", comparison["no_lexical_span"])
    print("NLI maior/menor com span:", comparison["span_score_higher"], comparison["span_score_lower"])
    print("Misses de fonte esperada:", misses["count"], "indexadas:", misses["expected_source_indexed"])
    print("Relatório:", args.output)


if __name__ == "__main__":
    main()
