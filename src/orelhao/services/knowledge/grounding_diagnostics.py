"""Diagnóstico reprodutível do gate factual: separa estágio de falha e suporte NLI.

Estas categorias indicam *hipóteses* com rótulos assistidos por IA, não
adjudicação humana. Não são usadas para liberar uma resposta em produção.
"""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .live_pipeline_evaluation import LiveCase


@dataclass(frozen=True, slots=True)
class GroundingDiagnostic:
    case_id: str
    stage: str
    suspected_cause: str
    expected_source_found: bool
    requires_human_review: bool = True

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "id": self.case_id,
            "stage": self.stage,
            "suspected_cause": self.suspected_cause,
            "expected_source_found": self.expected_source_found,
            "requires_human_review": self.requires_human_review,
        }


def classify_archived_case(
    case: LiveCase,
    result: Mapping[str, Any],
) -> GroundingDiagnostic:
    """Classifica sinais observáveis sem alterar a política nem os rótulos."""
    sources = result.get("evidence_sources", ())
    if not isinstance(sources, list):
        raise TypeError("evidence_sources precisa ser lista")
    source_hit = case.source is None or case.source in sources
    reason = result.get("answerability_reason")
    grounding = result.get("grounding_status")
    blocked = bool(result.get("predicted_abstain"))
    raw = str(result.get("answer", "")).strip()
    presented = str(result.get("presented_answer", "")).strip()

    if not case.expected_abstain and not source_hit:
        stage, cause = "retrieval", "expected_source_missing"
    elif reason is not None and blocked:
        stage, cause = "pre_generation", str(reason)
    elif not case.expected_abstain and blocked and raw == presented:
        stage, cause = "generation", "model_refused_or_incomplete"
    elif blocked and grounding in ("uncertain", "unsupported"):
        stage, cause = "post_generation", f"nli_{grounding}"
    elif case.expected_abstain and not blocked:
        stage, cause = "post_generation", "potential_unsafe_allow"
    elif not case.expected_abstain and not blocked and result.get("text_anchor_pass") is False:
        stage, cause = "post_generation", "potential_false_support_or_answer_mismatch"
    elif case.expected_abstain:
        stage, cause = "abstention", "expected_refusal_provisional"
    else:
        stage, cause = "passed_checks", "lexical_anchors_only"
    return GroundingDiagnostic(case.case_id, stage, cause, source_hit)


def audit_archived_results(
    dataset: list[LiveCase],
    model_results: Mapping[str, list[dict[str, Any]]],
) -> dict[str, object]:
    """Exige mesmo conjunto por modelo e reporta por causa, sem tuning."""
    expected_ids = {c.case_id for c in dataset}
    if not expected_ids or len(expected_ids) != len(dataset):
        raise ValueError("IDs de casos ausentes/duplicados")
    by_id = {case.case_id: case for case in dataset}
    audit: dict[str, object] = {}
    for name, results in model_results.items():
        result_ids = [str(item.get("id", "")) for item in results]
        if len(result_ids) != len(expected_ids) or set(result_ids) != expected_ids:
            raise ValueError(f"conjunto de casos incompleto/duplicado: {name}")
        evaluations = [
            classify_archived_case(by_id[str(row["id"])], row)
            for row in results
        ]
        causes = Counter(ev.suspected_cause for ev in evaluations)
        stages = Counter(ev.stage for ev in evaluations)
        audit[name] = {
            "total": len(evaluations),
            "stages": dict(sorted(stages.items())),
            "suspected_causes": dict(sorted(causes.items())),
            "cases": [item.as_dict() for item in evaluations],
        }
    return {
        "status": "development-diagnostics-only-not-human-adjudicated",
        "dataset_cases": len(dataset),
        "models": audit,
    }


def read_archived_model_results(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results")
    if not isinstance(results, list):
        raise TypeError("arquivo de avaliação não tem results")
    if not all(isinstance(row, dict) for row in results):
        raise ValueError("resultado de caso inválido")
    return results
