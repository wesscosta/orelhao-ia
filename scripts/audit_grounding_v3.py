"""Audita os casos históricos e (opcionalmente) reavalia NLI em cada chunk.

Não executa LLM nem altera thresholds. Saída: /tmp para evitar versionar
uma nova avaliação baseada nos mesmos casos de desenvolvimento.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orelhao.services.knowledge.evidence import OnnxNliEvidenceVerifier
from orelhao.services.knowledge.grounding_diagnostics import (
    audit_archived_results,
    read_archived_model_results,
)
from orelhao.services.knowledge.index import load_chunks
from orelhao.services.knowledge.live_pipeline_evaluation import load_live_cases


def recheck_nli(
    model_results: dict[str, list[dict[str, Any]]],
    *,
    model_path: Path,
    index_dir: Path,
) -> dict[str, object]:
    verifier = OnnxNliEvidenceVerifier(model_path)
    chunks = {chunk.id: chunk for chunk in load_chunks(index_dir)}
    checked = missing = mismatched = 0
    rows: list[dict[str, object]] = []
    for name, results in model_results.items():
        for row in results:
            claims = row.get("claim_assessments", [])
            if not isinstance(claims, list):
                continue
            for claim in claims:
                if not isinstance(claim, dict):
                    continue
                cid = claim.get("chunk_id")
                claim_text = claim.get("claim")
                if not isinstance(cid, str) or not isinstance(claim_text, str):
                    continue
                chunk = chunks.get(cid)
                if chunk is None:
                    missing += 1
                    continue
                probs = verifier.classify(claim_text, chunk.text)
                stored = float(claim.get("score", 0.0))
                difference = abs(probs.entailment - stored)
                if difference > 0.01:
                    mismatched += 1
                checked += 1
                rows.append({
                    "model": name,
                    "case_id": row["id"],
                    "chunk_id": cid,
                    "claim": claim_text,
                    "source": chunk.source,
                    "original_entailment": stored,
                    "rechecked": probs.as_dict(),
                    "entailment_delta": difference,
                    "same_evidence_score": difference <= 0.01,
                })
    return {
        "model_manifest": json.loads(
            (model_path / "manifest-fp32.json").read_text(encoding="utf-8")
        ),
        "indexed_chunks": len(chunks),
        "rechecked_claims": checked,
        "missing_historical_chunks": missing,
        "score_mismatches_over_0_01": mismatched,
        "claim_scores": rows,
        "reproduction_note": (
            "An archived claim may reference an old chunk; absent IDs are reported, "
            "not silently mapped to a different passage."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--tucano", type=Path, required=True)
    parser.add_argument("--qwen", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--nli-model", type=Path, help="habilita NLI ONNX em CPU")
    parser.add_argument("--index", type=Path, default=Path("knowledge/index"))
    args = parser.parse_args()
    _, cases = load_live_cases(args.dataset)
    results = {
        "tucano2": read_archived_model_results(args.tucano),
        "qwen35": read_archived_model_results(args.qwen),
    }
    payload = audit_archived_results(cases, results)
    payload["meta"] = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "dataset": str(args.dataset),
        "nli_enabled": args.nli_model is not None,
        "source": "archived-results; no new LLM generation",
    }
    if args.nli_model:
        payload["nli_recheck"] = recheck_nli(
            results, model_path=args.nli_model, index_dir=args.index
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for name, value in payload["models"].items():
        print(name, value["stages"], value["suspected_causes"])
    if "nli_recheck" in payload:
        checks = payload["nli_recheck"]
        print(
            "NLI audit:", checks["rechecked_claims"], "rechecked;",
            checks["missing_historical_chunks"], "missing chunks;",
            checks["score_mismatches_over_0_01"], "score mismatches",
        )
    print("saved", args.output)


if __name__ == "__main__":
    main()
