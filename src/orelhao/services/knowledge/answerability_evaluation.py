"""Avaliação offline da decisão pré-geração, separada de retrieval e do NLI."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import median
from time import perf_counter

from .answerability import EvidenceAdjudicator
from .models import Chunk, SearchResult


@dataclass(frozen=True, slots=True)
class AnswerabilityCase:
    case_id: str
    query: str
    category: str
    answerable: bool
    evidence: tuple[SearchResult, ...]
    as_of: date


def load_answerability_cases(path: Path) -> list[AnswerabilityCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("dataset deve ser uma lista não vazia")
    cases: list[AnswerabilityCase] = []
    ids: set[str] = set()
    for row in data:
        if not isinstance(row, dict):
            raise TypeError("caso deve ser objeto")
        cid, query, cat = row.get("id"), row.get("query"), row.get("category")
        expected, evidence, as_of = row.get("answerable"), row.get("evidence"), row.get("as_of")
        if (
            not isinstance(cid, str) or not cid.strip()
            or not isinstance(query, str) or not query.strip()
            or not isinstance(cat, str) or not cat.strip()
            or not isinstance(expected, bool) or not isinstance(evidence, list)
            or not isinstance(as_of, str)
        ):
            raise ValueError("id, query, category, answerable, evidence e as_of obrigatórios")
        if cid in ids:
            raise ValueError("id duplicado")
        ids.add(cid)
        source_results: list[SearchResult] = []
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                raise TypeError("evidência deve ser objeto")
            source, content, metadata = item.get("source"), item.get("text"), item.get("metadata", {})
            if not isinstance(source, str) or not source.strip() or not isinstance(content, str) or not content.strip() or not isinstance(metadata, dict):
                raise ValueError("evidência inválida")
            chunk = Chunk(f"{cid}:{index}", cid, content, source, index, metadata)
            source_results.append(SearchResult(chunk, 0.9))
        cases.append(AnswerabilityCase(cid, query, cat, expected, tuple(source_results), date.fromisoformat(as_of)))
    return cases


def evaluate_answerability(
    cases: list[AnswerabilityCase],
    *, adjudicator: EvidenceAdjudicator | None = None,
) -> dict[str, object]:
    if not cases:
        raise ValueError("dataset vazio")
    judge = adjudicator or EvidenceAdjudicator()
    results: list[dict[str, object]] = []
    tp = tn = fp = fn = 0
    latencies: list[float] = []
    for case in cases:
        started = perf_counter()
        assessment = judge.assess(case.query, list(case.evidence), as_of=case.as_of)
        elapsed = (perf_counter() - started) * 1000
        latencies.append(elapsed)
        allow = assessment.decision.answerable
        if allow and case.answerable:
            tp += 1
        elif allow and not case.answerable:
            fp += 1
        elif not allow and not case.answerable:
            tn += 1
        else:
            fn += 1
        results.append({
            "id": case.case_id,
            "category": case.category,
            "expected_answerable": case.answerable,
            "predicted_answerable": allow,
            "reason": assessment.decision.reason.value if assessment.decision.reason else None,
            "correct": allow == case.answerable,
            "latency_ms": elapsed,
        })
    p95_index = max(0, (len(latencies) * 95 + 99) // 100 - 1)
    return {
        "summary": {
            "cases": len(cases),
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else 0,
            "recall": tp / (tp + fn) if tp + fn else 0,
            "specificity": tn / (tn + fp) if tn + fp else 0,
            "balanced_accuracy": (
                (tp / (tp + fn) if tp + fn else 0)
                + (tn / (tn + fp) if tn + fp else 0)
            ) / 2,
            "false_allow_rate": fp / (fp + tn) if fp + tn else 0,
            "false_block_rate": fn / (fn + tp) if fn + tp else 0,
            "latency_p50_ms": median(latencies),
            "latency_p95_ms": sorted(latencies)[p95_index],
        },
        "categories": {
            category: {
                "cases": sum(x["category"] == category for x in results),
                "errors": sum(x["category"] == category and not x["correct"] for x in results),
            }
            for category in sorted({case.category for case in cases})
        },
        "results": results,
    }
