from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from .vector_retriever import PersistentVectorRetriever


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    query: str
    expected_sources: tuple[str, ...] = ()
    abstain: bool = False


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    cases: int
    hit_at_1: float
    hit_at_k: float
    mrr: float
    abstention_accuracy: float
    mean_latency_ms: float

    def as_dict(self) -> dict[str, int | float]:
        return {
            "cases": self.cases,
            "hit_at_1": self.hit_at_1,
            "hit_at_k": self.hit_at_k,
            "mrr": self.mrr,
            "abstention_accuracy": self.abstention_accuracy,
            "mean_latency_ms": self.mean_latency_ms,
        }


def load_evaluation_cases(path: Path) -> list[EvaluationCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("dataset de avaliação deve ser uma lista JSON")
    cases: list[EvaluationCase] = []
    for item in payload:
        if not isinstance(item, dict) or not str(item.get("query", "")).strip():
            raise ValueError("cada caso deve conter query não vazia")
        expected = item.get("expected_sources", [])
        if not isinstance(expected, list) or not all(isinstance(value, str) for value in expected):
            raise ValueError("expected_sources deve ser uma lista de strings")
        abstain = bool(item.get("abstain", False))
        if abstain and expected:
            raise ValueError("caso de abstenção não deve declarar expected_sources")
        if not abstain and not expected:
            raise ValueError("caso relevante deve declarar expected_sources")
        cases.append(EvaluationCase(str(item["query"]), tuple(expected), abstain))
    if not cases:
        raise ValueError("dataset de avaliação está vazio")
    return cases


def evaluate_retriever(
    retriever: PersistentVectorRetriever,
    cases: list[EvaluationCase],
    *,
    limit: int = 4,
) -> EvaluationMetrics:
    hits_1 = hits_k = 0
    reciprocal_ranks: list[float] = []
    abstention_checks: list[float] = []
    latencies: list[float] = []

    for case in cases:
        started = time.perf_counter()
        results = retriever.search(case.query, limit=limit)
        latencies.append((time.perf_counter() - started) * 1000.0)
        sources = [result.chunk.source for result in results]
        if case.abstain:
            abstention_checks.append(float(not results))
            continue

        expected = set(case.expected_sources)
        hits_1 += int(bool(sources) and sources[0] in expected)
        hits_k += int(any(source in expected for source in sources))
        rank = next((index for index, source in enumerate(sources, 1) if source in expected), None)
        reciprocal_ranks.append(0.0 if rank is None else 1.0 / rank)

    relevant_count = sum(not case.abstain for case in cases)
    return EvaluationMetrics(
        cases=len(cases),
        hit_at_1=hits_1 / relevant_count if relevant_count else 0.0,
        hit_at_k=hits_k / relevant_count if relevant_count else 0.0,
        mrr=mean(reciprocal_ranks) if reciprocal_ranks else 0.0,
        abstention_accuracy=mean(abstention_checks) if abstention_checks else 0.0,
        mean_latency_ms=mean(latencies),
    )
