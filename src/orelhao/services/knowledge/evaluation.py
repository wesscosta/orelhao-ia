from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from .models import SearchResult
from .retriever import Retriever


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


@dataclass(frozen=True, slots=True)
class EvaluationMatch:
    chunk_id: str
    document_id: str
    source: str
    position: int
    score: float
    text: str
    metadata: dict[str, str]

    @classmethod
    def from_search_result(cls, result: SearchResult) -> EvaluationMatch:
        chunk = result.chunk
        return cls(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            source=chunk.source,
            position=chunk.position,
            score=result.score,
            text=chunk.text,
            metadata=dict(chunk.metadata),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source": self.source,
            "position": self.position,
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class EvaluationCaseResult:
    query: str
    expected_sources: tuple[str, ...]
    expected_abstention: bool
    sources: tuple[str, ...]
    scores: tuple[float, ...]
    matches: tuple[EvaluationMatch, ...]
    relevant_rank: int | None
    correct: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "expected_sources": list(self.expected_sources),
            "expected_abstention": self.expected_abstention,
            "sources": list(self.sources),
            "scores": list(self.scores),
            "matches": [match.as_dict() for match in self.matches],
            "relevant_rank": self.relevant_rank,
            "correct": self.correct,
        }


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    metrics: EvaluationMetrics
    results: tuple[EvaluationCaseResult, ...]


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
    retriever: Retriever,
    cases: list[EvaluationCase],
    *,
    limit: int = 4,
) -> EvaluationMetrics:
    return evaluate_retriever_detailed(retriever, cases, limit=limit).metrics


def evaluate_retriever_detailed(
    retriever: Retriever,
    cases: list[EvaluationCase],
    *,
    limit: int = 4,
) -> EvaluationReport:
    if not cases:
        raise ValueError("a avaliação exige pelo menos um caso")
    if limit <= 0:
        raise ValueError("limit deve ser maior que zero")

    hits_1 = hits_k = 0
    reciprocal_ranks: list[float] = []
    abstention_checks: list[float] = []
    latencies: list[float] = []
    case_results: list[EvaluationCaseResult] = []

    for case in cases:
        started = time.perf_counter()
        results = retriever.search(case.query, limit=limit)
        latencies.append((time.perf_counter() - started) * 1000.0)
        sources = [result.chunk.source for result in results]
        scores = [result.score for result in results]
        matches = tuple(EvaluationMatch.from_search_result(result) for result in results)
        if case.abstain:
            correct = not results
            abstention_checks.append(float(correct))
            case_results.append(
                EvaluationCaseResult(
                    query=case.query,
                    expected_sources=case.expected_sources,
                    expected_abstention=True,
                    sources=tuple(sources),
                    scores=tuple(scores),
                    matches=matches,
                    relevant_rank=None,
                    correct=correct,
                )
            )
            continue

        expected = set(case.expected_sources)
        hits_1 += int(bool(sources) and sources[0] in expected)
        hits_k += int(any(source in expected for source in sources))
        rank = next((index for index, source in enumerate(sources, 1) if source in expected), None)
        reciprocal_ranks.append(0.0 if rank is None else 1.0 / rank)
        case_results.append(
            EvaluationCaseResult(
                query=case.query,
                expected_sources=case.expected_sources,
                expected_abstention=False,
                sources=tuple(sources),
                scores=tuple(scores),
                matches=matches,
                relevant_rank=rank,
                correct=rank is not None,
            )
        )

    relevant_count = sum(not case.abstain for case in cases)
    return EvaluationReport(
        metrics=EvaluationMetrics(
            cases=len(cases),
            hit_at_1=hits_1 / relevant_count if relevant_count else 0.0,
            hit_at_k=hits_k / relevant_count if relevant_count else 0.0,
            mrr=mean(reciprocal_ranks) if reciprocal_ranks else 0.0,
            abstention_accuracy=mean(abstention_checks) if abstention_checks else 0.0,
            mean_latency_ms=mean(latencies),
        ),
        results=tuple(case_results),
    )
