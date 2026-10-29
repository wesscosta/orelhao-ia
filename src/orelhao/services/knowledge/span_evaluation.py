"""Compara NLI de chunks inteiros e passagens literais no corpus local.

Somente diagnóstico: não usa spans para permitir respostas. O dataset
histórico fornece rótulos provisórios, não gabaritos humanos independentes.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any

from .evidence import OnnxNliEvidenceVerifier
from .evidence_selector import select_evidence_span
from .index import load_chunks
from .live_pipeline_evaluation import LiveCase
from .models import Chunk


def compare_nli_spans(
    model_results: dict[str, list[dict[str, Any]]], *, model_path: Path,
    index_dir: Path,
) -> dict[str, object]:
    """Compara o mesmo NLI contra premissa longa e curta (sem mudar a policy).

    Scores históricos são usados como baseline. A NLI do chunk é reavaliada
    para distinguir drift de diferenças causadas pelo tamanho da premissa.
    """
    verifier = OnnxNliEvidenceVerifier(model_path)
    chunks = {chunk.id: chunk for chunk in load_chunks(index_dir)}
    observations: list[dict[str, object]] = []
    deltas: list[float] = []
    no_span: list[str] = []
    missing: list[str] = []
    for model, results in model_results.items():
        for row in results:
            for claim in row.get("claim_assessments", []):
                cid = claim.get("chunk_id")
                text = claim.get("claim")
                if not isinstance(cid, str) or not isinstance(text, str):
                    continue
                chunk = chunks.get(cid)
                if chunk is None:
                    missing.append(f"{model}/{row['id']}/{cid}")
                    continue
                choice = select_evidence_span(text, chunk)
                if choice is None:
                    no_span.append(f"{model}/{row['id']}/{cid}")
                    continue
                chunk_nli = verifier.classify(text, chunk.text)
                span_nli = verifier.classify(text, choice.span.text)
                delta = span_nli.entailment - chunk_nli.entailment
                deltas.append(delta)
                item = {
                    "model": model,
                    "id": row["id"],
                    "source": chunk.source,
                    "claim": text,
                    "chunk_id": cid,
                    "span": choice.as_dict(),
                    "nli_chunk": chunk_nli.as_dict(),
                    "nli_span": span_nli.as_dict(),
                    "delta_entailment": delta,
                    "original_chunk_score": claim.get("score"),
                    "unchanged_policy": True,
                    "human_validation_required": True,
                }
                if not choice.span.matches_chunk(chunk):
                    raise RuntimeError("span não corresponde à fonte indexada")
                observations.append(item)
    return {
        "status": "diagnostic-only-no-promotion",
        "paired_nli_observations": len(observations),
        "no_lexical_span": len(no_span),
        "missing_historical_chunk": len(missing),
        "span_score_higher": sum(delta > 0.01 for delta in deltas),
        "span_score_lower": sum(delta < -0.01 for delta in deltas),
        "span_score_within_0_01": sum(abs(delta) <= 0.01 for delta in deltas),
        "median_delta_entailment": median(deltas) if deltas else None,
        "items_without_span": no_span,
        "items_without_chunk": missing,
        "cases": observations,
        "note": (
            "Higher span entailment is not proof of factual support. "
            "Select spans without NLI scoring, then compare independently."
        ),
    }


def diagnose_expected_source_misses(
    cases: list[LiveCase],
    model_results: dict[str, list[dict[str, Any]]],
    *, indexed_chunks: list[Chunk],
) -> dict[str, object]:
    """Conta fontes não recuperadas, distinguindo ausente vs indexada.

    A 'source' esperada vem dos rótulos assistidos por IA; só é utilizada
    no relatório de avaliação, jamais na decisão de resposta.
    """
    sources = {chunk.source for chunk in indexed_chunks}
    mapping = {case.case_id: case for case in cases}
    entries: list[dict[str, object]] = []
    for model, results in model_results.items():
        for result in results:
            case = mapping.get(str(result.get("id")))
            if case is None or case.source is None:
                continue
            retrieved = result.get("evidence_sources", [])
            if not isinstance(retrieved, list):
                raise TypeError("lista de evidências esperada")
            if case.source not in retrieved:
                entries.append({
                    "model": model,
                    "id": case.case_id,
                    "query": case.query,
                    "expected_source": case.source,
                    "source_indexed": case.source in sources,
                    "retrieval_miss": True,
                    "human_review_required": True,
                })
    return {
        "count": len(entries),
        "expected_source_indexed": sum(
            bool(entry["source_indexed"]) for entry in entries
        ),
        "cases": entries,
        "note": "Ground-truth source used only for retrospective diagnostics.",
    }


def load_audit_inputs(
    dataset: Path, tucano: Path, qwen: Path
) -> tuple[list[LiveCase], dict[str, list[dict[str, Any]]]]:
    from .grounding_diagnostics import audit_archived_results, read_archived_model_results
    from .live_pipeline_evaluation import load_live_cases

    _, cases = load_live_cases(dataset)
    results = {
        "tucano2": read_archived_model_results(tucano),
        "qwen35": read_archived_model_results(qwen),
    }
    audit_archived_results(cases, results)  # recusa IDs ausentes/duplicados
    return cases, results


def dump_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
