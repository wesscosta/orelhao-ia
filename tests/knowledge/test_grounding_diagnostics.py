"""Auditoria v3: contratos de labels e classificação de falhas por estágio."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orelhao.services.knowledge.evidence import (
    NLI_LABELS,
    NliProbabilities,
    _check_nli_labels,
)
from orelhao.services.knowledge.grounding_diagnostics import (
    audit_archived_results,
    classify_archived_case,
    read_archived_model_results,
)
from orelhao.services.knowledge.live_pipeline_evaluation import (
    LiveCase,
    load_live_cases,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "knowledge/evaluation/grounding-real-senac-pi-v1.json"
RESULT_DIR = ROOT / "knowledge/evaluation/results"


def test_labels_match_exact_pinned_checkpoint() -> None:
    assert NLI_LABELS == ("entailment", "neutral", "contradiction")


def test_label_config_validates_order_and_refuses_drift(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    for labels in (
        {"0": "entailment", "1": "neutral", "2": "contradiction"},
        {"0": "contradiction", "1": "neutral", "2": "entailment"},
    ):
        path.write_text(json.dumps({"id2label": labels}), encoding="utf-8")
        if labels["0"] == "entailment":
            _check_nli_labels(tmp_path)
        else:
            with pytest.raises(RuntimeError, match="labels do NLI"):
                _check_nli_labels(tmp_path)


def test_nli_probabilities_are_normalized_and_serializable() -> None:
    probs = NliProbabilities(.25, .70, .05)
    assert probs.as_dict() == {
        "entailment": .25, "neutral": .70, "contradiction": .05,
    }
    for values in ((1.0, 0.1, 0.0), (float("nan"), 0, 1), (-.1, .5, .6)):
        with pytest.raises(ValueError, match="probabilidades NLI"):
            NliProbabilities(*values)


def test_missing_evidence_is_identified_before_nli() -> None:
    case = LiveCase("P1", "Qual é a missão?", False, "mission", ("trabalho",), "mission.md")
    row = {
        "id": "P1", "evidence_sources": ["unrelated.md"],
        "predicted_abstain": True, "answer": "Não sei.",
        "presented_answer": "Não encontrei evidências suficientes.",
        "grounding_status": "uncertain",
    }
    diagnostic = classify_archived_case(case, row)
    assert diagnostic.stage == "retrieval"
    assert diagnostic.suspected_cause == "expected_source_missing"
    assert diagnostic.requires_human_review


def test_nli_false_support_diagnostic_is_not_automatic_verdict() -> None:
    case = LiveCase("P1", "Missão?", False, "mission", ("educar",), "mission.md")
    result = {
        "id": "P1", "evidence_sources": ["mission.md"],
        "predicted_abstain": False, "text_anchor_pass": False,
        "grounding_status": "supported", "answer": "Outra coisa.",
        "presented_answer": "Outra coisa.",
    }
    diagnostic = classify_archived_case(case, result)
    assert diagnostic.stage == "post_generation"
    assert diagnostic.suspected_cause == "potential_false_support_or_answer_mismatch"


def test_archived_benchmarks_are_preserved_and_auditable() -> None:
    _, cases = load_live_cases(DATASET)
    results = {
        "tucano": read_archived_model_results(
            RESULT_DIR / "grounding-tucano2-2026-10-29.json"
        ),
        "qwen": read_archived_model_results(
            RESULT_DIR / "grounding-qwen35-2026-10-29.json"
        ),
    }
    report = audit_archived_results(cases, results)
    assert report["dataset_cases"] == 40
    assert report["models"]["tucano"]["total"] == 40
    assert report["models"]["qwen"]["total"] == 40
    assert report["models"]["tucano"]["stages"]["retrieval"] == 2
    assert report["status"].startswith("development-diagnostics-only")


def test_cannot_silently_drop_unfavorable_cases() -> None:
    cases = [LiveCase("a", "pergunta", True, "negative")]
    with pytest.raises(ValueError, match="incompleto"):
        audit_archived_results(cases, {"model": []})
