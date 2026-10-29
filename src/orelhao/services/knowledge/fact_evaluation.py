"""Auditoria retrospectiva do Fact Validator no corpus versionado.

Usa apenas o chunk original referenciado por cada claim; não recalcula NLI
nem consulta o gabarito, logo não classifica acurácia de respostas.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from .fact_validation import validate_claim_facts
from .index import load_chunks
from .models import SearchResult


def audit_fact_validation(
    model_results: dict[str, list[dict[str, Any]]], *,
    index_dir: Path, as_of: date,
) -> dict[str, object]:
    chunks = {item.id: item for item in load_chunks(index_dir)}
    counts: Counter[str] = Counter()
    results: list[dict[str, object]] = []
    missing_ids: list[str] = []
    for model, rows in model_results.items():
        for row in rows:
            for claim in row.get("claim_assessments", []):
                claim_text, chunk_id = claim.get("claim"), claim.get("chunk_id")
                if not isinstance(claim_text, str) or not isinstance(chunk_id, str):
                    continue
                chunk = chunks.get(chunk_id)
                if chunk is None:
                    missing_ids.append(f"{model}/{row['id']}/{chunk_id}")
                    continue
                validation = validate_claim_facts(
                    claim_text, [SearchResult(chunk, 1.0)], as_of=as_of,
                    requires_current_state=False,
                )
                counts[validation.status.value] += 1
                results.append({
                    "model": model, "id": row["id"], "claim": claim_text,
                    "nli_status": row.get("grounding_status"),
                    "chunk_id": chunk_id,
                    "validation": validation.as_dict(),
                    "revised_by_human": False,
                })
    return {
        "status": "diagnostic-only-not-human-adjudicated",
        "checked_claims": len(results),
        "missing_chunks": missing_ids,
        "categories": dict(sorted(counts.items())),
        "results": results,
        "note": (
            "Chunk escolhido pelo NLI, não necessariamente fonte factual correta; "
            "um match numérico não comprova a afirmação completa."
        ),
    }


def save_audit(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
