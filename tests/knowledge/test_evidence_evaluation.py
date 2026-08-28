from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from orelhao.services.knowledge.evidence_decision import AbstentionReason
from orelhao.services.knowledge.evidence_evaluation import (
    EvidenceEvaluationCase,
    evaluate_evidence_verifier,
    load_evidence_evaluation_cases,
)
from orelhao.services.knowledge.index import build_index


@dataclass
class StaticVerifier:
    scores: dict[tuple[str, str], float]

    def support_score(self, query: str, passage: str) -> float:
        return self.scores[(query, passage)]


def _index(tmp_path: Path) -> Path:
    sources = tmp_path / "sources"
    index = tmp_path / "index"
    sources.mkdir()
    (sources / "base.md").write_text(
        "---\ntitle: Base\n---\n\nA resposta correta é azul.",
        encoding="utf-8",
    )
    build_index(sources, index)
    return index


def test_load_evidence_cases_requires_both_classes(tmp_path: Path) -> None:
    dataset = tmp_path / "evidence.json"
    dataset.write_text(
        json.dumps([{"query": "Pergunta", "chunk_id": "base.md:0", "answerable": True}]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duas classes"):
        load_evidence_evaluation_cases(dataset)


def test_load_evidence_cases_preserves_category_and_abstention_reason(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "evidence.json"
    dataset.write_text(
        json.dumps(
            [
                {
                    "query": "Pergunta positiva",
                    "chunk_id": "base.md:0",
                    "answerable": True,
                    "category": "paraphrase",
                },
                {
                    "query": "Pergunta temporal",
                    "chunk_id": "base.md:0",
                    "answerable": False,
                    "category": "temporal",
                    "abstention_reason": "temporal_evidence_unavailable",
                },
            ]
        ),
        encoding="utf-8",
    )

    positive, negative = load_evidence_evaluation_cases(dataset)

    assert positive.category == "paraphrase"
    assert negative.category == "temporal"
    assert negative.abstention_reason is AbstentionReason.TEMPORAL_EVIDENCE_UNAVAILABLE


def test_evidence_evaluation_measures_classifier_and_auc(tmp_path: Path) -> None:
    index = _index(tmp_path)
    passage = "A resposta correta é azul."
    cases = [
        EvidenceEvaluationCase("Qual é a resposta?", "base.md:0", True),
        EvidenceEvaluationCase("Qual é o telefone?", "base.md:0", False),
    ]
    verifier = StaticVerifier(
        {
            ("Qual é a resposta?", passage): 0.9,
            ("Qual é o telefone?", passage): 0.1,
        }
    )

    report = evaluate_evidence_verifier(verifier, cases, index, threshold=0.5)

    assert report.metrics.accuracy == 1.0
    assert report.metrics.balanced_accuracy == 1.0
    assert report.metrics.precision == 1.0
    assert report.metrics.recall == 1.0
    assert report.metrics.specificity == 1.0
    assert report.metrics.f1 == 1.0
    assert report.metrics.roc_auc == 1.0
    assert report.category_metrics["uncategorized"].cases == 2
    assert len(report.results) == 2


def test_category_metric_uses_the_metric_defined_for_its_class(tmp_path: Path) -> None:
    index = _index(tmp_path)
    passage = "A resposta correta é azul."
    cases = [
        EvidenceEvaluationCase("Afirmação suportada", "base.md:0", True, "supported"),
        EvidenceEvaluationCase("Afirmação ausente", "base.md:0", False, "unsupported"),
    ]
    verifier = StaticVerifier(
        {
            ("Afirmação suportada", passage): 0.9,
            ("Afirmação ausente", passage): 0.1,
        }
    )

    report = evaluate_evidence_verifier(verifier, cases, index, threshold=0.5)

    assert report.category_metrics["supported"].applicable_metric() == ("recall", 1.0)
    assert report.category_metrics["unsupported"].applicable_metric() == (
        "specificity",
        1.0,
    )


def test_grounding_holdout_is_balanced_and_has_no_calibration_claims() -> None:
    calibration = load_evidence_evaluation_cases(
        Path("knowledge/evaluation/grounding-v1.json")
    )
    holdout = load_evidence_evaluation_cases(
        Path("knowledge/evaluation/grounding-v2-holdout.json")
    )

    assert len(holdout) == 40
    assert sum(case.answerable for case in holdout) == 20
    assert {case.query for case in calibration}.isdisjoint(case.query for case in holdout)
    assert {
        case.category for case in holdout if not case.answerable
    } == {
        "unsupported_contradiction",
        "unsupported_entity",
        "unsupported_specific",
        "unsupported_temporal",
    }


def test_evidence_evaluation_rejects_missing_chunk(tmp_path: Path) -> None:
    index = _index(tmp_path)
    cases = [EvidenceEvaluationCase("Pergunta", "ausente.md:0", True)]

    with pytest.raises(ValueError, match="chunks ausentes"):
        evaluate_evidence_verifier(StaticVerifier({}), cases, index)


@pytest.mark.parametrize("threshold", [-0.1, 1.1])
def test_evidence_evaluation_rejects_invalid_threshold(
    tmp_path: Path,
    threshold: float,
) -> None:
    index = _index(tmp_path)
    cases = [EvidenceEvaluationCase("Pergunta", "base.md:0", True)]

    with pytest.raises(ValueError, match="threshold"):
        evaluate_evidence_verifier(StaticVerifier({}), cases, index, threshold=threshold)
