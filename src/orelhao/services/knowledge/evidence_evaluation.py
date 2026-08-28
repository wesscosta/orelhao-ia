from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from .evidence import EvidenceVerifier
from .evidence_decision import AbstentionReason
from .index import load_chunks

EVIDENCE_THRESHOLD_POLICIES = {
    "initial": 0.5,
    "conservative": 0.69740408,
    "balanced": 0.00016509,
    "nli-balanced": 0.1250362694,
    "nli-conservative": 0.7557643056,
}


@dataclass(frozen=True, slots=True)
class EvidenceEvaluationCase:
    query: str
    chunk_id: str
    answerable: bool
    category: str = "uncategorized"
    abstention_reason: AbstentionReason | None = None


@dataclass(frozen=True, slots=True)
class EvidenceEvaluationResult:
    query: str
    chunk_id: str
    expected_answerable: bool
    category: str
    expected_abstention_reason: AbstentionReason | None
    support: float
    predicted_answerable: bool
    correct: bool
    latency_ms: float

    def as_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "chunk_id": self.chunk_id,
            "expected_answerable": self.expected_answerable,
            "category": self.category,
            "expected_abstention_reason": self.expected_abstention_reason,
            "support": self.support,
            "predicted_answerable": self.predicted_answerable,
            "correct": self.correct,
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True, slots=True)
class EvidenceEvaluationMetrics:
    cases: int
    answerable_cases: int
    unanswerable_cases: int
    accuracy: float
    balanced_accuracy: float
    precision: float
    recall: float
    specificity: float
    f1: float
    roc_auc: float
    mean_latency_ms: float

    def as_dict(self) -> dict[str, int | float]:
        return {
            "cases": self.cases,
            "answerable_cases": self.answerable_cases,
            "unanswerable_cases": self.unanswerable_cases,
            "accuracy": self.accuracy,
            "balanced_accuracy": self.balanced_accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "specificity": self.specificity,
            "f1": self.f1,
            "roc_auc": self.roc_auc,
            "mean_latency_ms": self.mean_latency_ms,
        }

    def applicable_metric(self) -> tuple[str, float]:
        if self.answerable_cases and not self.unanswerable_cases:
            return "recall", self.recall
        if self.unanswerable_cases and not self.answerable_cases:
            return "specificity", self.specificity
        return "balanced_accuracy", self.balanced_accuracy


@dataclass(frozen=True, slots=True)
class EvidenceEvaluationReport:
    metrics: EvidenceEvaluationMetrics
    category_metrics: dict[str, EvidenceEvaluationMetrics]
    results: tuple[EvidenceEvaluationResult, ...]


def load_evidence_evaluation_cases(path: Path) -> list[EvidenceEvaluationCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("dataset de evidência deve ser uma lista JSON")

    cases: list[EvidenceEvaluationCase] = []
    identities: set[tuple[str, str]] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise TypeError("cada caso de evidência deve ser um objeto")
        query = item.get("query")
        chunk_id = item.get("chunk_id")
        answerable = item.get("answerable")
        category = item.get("category", "uncategorized")
        raw_reason = item.get("abstention_reason")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("cada caso deve conter query não vazia")
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise ValueError("cada caso deve conter chunk_id não vazio")
        if not isinstance(answerable, bool):
            raise TypeError("answerable deve ser booleano")
        if not isinstance(category, str) or not category.strip():
            raise ValueError("category deve ser uma string não vazia")
        try:
            reason = None if raw_reason is None else AbstentionReason(raw_reason)
        except (TypeError, ValueError) as exc:
            raise ValueError("abstention_reason inválido") from exc
        if answerable and reason is not None:
            raise ValueError("caso respondível não deve declarar abstention_reason")
        identity = (query, chunk_id)
        if identity in identities:
            raise ValueError("dataset de evidência contém caso duplicado")
        identities.add(identity)
        cases.append(EvidenceEvaluationCase(query, chunk_id, answerable, category, reason))

    if not cases:
        raise ValueError("dataset de evidência está vazio")
    if len({case.answerable for case in cases}) != 2:
        raise ValueError("dataset de evidência deve conter as duas classes")
    return cases


def evaluate_evidence_verifier(
    verifier: EvidenceVerifier,
    cases: list[EvidenceEvaluationCase],
    index_dir: Path,
    *,
    threshold: float = 0.5,
) -> EvidenceEvaluationReport:
    if not cases:
        raise ValueError("a avaliação exige pelo menos um caso")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold deve estar entre 0 e 1")

    chunks = {chunk.id: chunk for chunk in load_chunks(index_dir)}
    missing = sorted({case.chunk_id for case in cases} - chunks.keys())
    if missing:
        raise ValueError("chunks ausentes no índice: " + ", ".join(missing))

    results: list[EvidenceEvaluationResult] = []
    for case in cases:
        started = time.perf_counter()
        support = verifier.support_score(case.query, chunks[case.chunk_id].text)
        latency_ms = (time.perf_counter() - started) * 1000.0
        predicted = support >= threshold
        results.append(
            EvidenceEvaluationResult(
                query=case.query,
                chunk_id=case.chunk_id,
                expected_answerable=case.answerable,
                category=case.category,
                expected_abstention_reason=case.abstention_reason,
                support=support,
                predicted_answerable=predicted,
                correct=predicted is case.answerable,
                latency_ms=latency_ms,
            )
        )

    metrics = _calculate_metrics(results)
    categories = sorted({result.category for result in results})
    category_metrics = {
        category: _calculate_metrics(
            [result for result in results if result.category == category]
        )
        for category in categories
    }
    return EvidenceEvaluationReport(metrics, category_metrics, tuple(results))


def _calculate_metrics(
    results: list[EvidenceEvaluationResult],
) -> EvidenceEvaluationMetrics:
    true_positive = sum(r.expected_answerable and r.predicted_answerable for r in results)
    false_positive = sum(not r.expected_answerable and r.predicted_answerable for r in results)
    true_negative = sum(not r.expected_answerable and not r.predicted_answerable for r in results)
    false_negative = sum(r.expected_answerable and not r.predicted_answerable for r in results)
    positives = true_positive + false_negative
    negatives = true_negative + false_positive
    precision = _divide(true_positive, true_positive + false_positive)
    recall = _divide(true_positive, positives)
    specificity = _divide(true_negative, negatives)

    return EvidenceEvaluationMetrics(
        cases=len(results),
        answerable_cases=positives,
        unanswerable_cases=negatives,
        accuracy=_divide(true_positive + true_negative, len(results)),
        balanced_accuracy=(recall + specificity) / 2.0,
        precision=precision,
        recall=recall,
        specificity=specificity,
        f1=_divide(2.0 * precision * recall, precision + recall),
        roc_auc=_roc_auc(results),
        mean_latency_ms=mean(result.latency_ms for result in results),
    )


def _roc_auc(results: list[EvidenceEvaluationResult]) -> float:
    positives = [result.support for result in results if result.expected_answerable]
    negatives = [result.support for result in results if not result.expected_answerable]
    if not positives or not negatives:
        return 0.0
    favorable = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative:
                favorable += 1.0
            elif positive == negative:
                favorable += 0.5
    return favorable / (len(positives) * len(negatives))


def _divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0
