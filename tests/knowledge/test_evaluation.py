import argparse
import json
from pathlib import Path

import pytest

from orelhao.services.knowledge.cli import add_knowledge_parser
from orelhao.services.knowledge.evaluation import (
    EvaluationCase,
    evaluate_retriever,
    evaluate_retriever_detailed,
    load_evaluation_cases,
)
from orelhao.services.knowledge.index import build_index
from orelhao.services.knowledge.vector_retriever import PersistentVectorRetriever


def _retriever(tmp_path: Path) -> PersistentVectorRetriever:
    sources, index = tmp_path / "sources", tmp_path / "index"
    sources.mkdir()
    (sources / "local.md").write_text(
        "# Endereço\nEndereço da unidade: Rua Central, 10.",
        encoding="utf-8",
    )
    (sources / "matricula.md").write_text(
        "# Matrícula\nA matrícula deve ser realizada presencialmente.",
        encoding="utf-8",
    )
    build_index(sources, index)
    return PersistentVectorRetriever(index, min_score=0.40)


def test_load_evaluation_cases(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(
        '[{"query":"onde fica?","expected_sources":["local.md"]},'
        '{"query":"Marte?","abstain":true}]',
        encoding="utf-8",
    )
    cases = load_evaluation_cases(path)
    assert len(cases) == 2
    assert cases[0].expected_sources == ("local.md",)
    assert cases[1].abstain


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        [{"query": ""}],
        [{"query": "onde fica?"}],
        [{"query": "onde fica?", "expected_sources": "local.md"}],
        [{"query": "Marte?", "expected_sources": ["local.md"], "abstain": True}],
    ],
)
def test_load_evaluation_cases_rejects_invalid_dataset(
    tmp_path: Path,
    payload: object,
) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises((TypeError, ValueError)):
        load_evaluation_cases(path)


def test_evaluate_retriever_reports_ranking_and_abstention(tmp_path: Path) -> None:
    retriever = _retriever(tmp_path)
    metrics = evaluate_retriever(
        retriever,
        [
            EvaluationCase("qual o endereço da unidade?", ("local.md",)),
            EvaluationCase("qual é a temperatura de Marte?", abstain=True),
        ],
    )
    assert metrics.cases == 2
    assert metrics.hit_at_1 == 1.0
    assert metrics.hit_at_k == 1.0
    assert metrics.mrr == 1.0
    assert metrics.abstention_accuracy == 1.0
    assert metrics.mean_latency_ms >= 0.0


def test_evaluate_retriever_accepts_multiple_expected_sources(tmp_path: Path) -> None:
    retriever = _retriever(tmp_path)
    metrics = evaluate_retriever(
        retriever,
        [EvaluationCase("qual o endereço da unidade?", ("alternativa.md", "local.md"))],
    )
    assert metrics.hit_at_1 == 1.0
    assert metrics.mrr == 1.0


def test_detailed_evaluation_exposes_sources_scores_and_outcome(tmp_path: Path) -> None:
    report = evaluate_retriever_detailed(
        _retriever(tmp_path),
        [
            EvaluationCase("qual o endereço da unidade?", ("local.md",)),
            EvaluationCase("qual é a temperatura de Marte?", abstain=True),
        ],
    )

    relevant, abstention = report.results
    assert relevant.sources[0] == "local.md"
    assert relevant.scores[0] >= 0.0
    assert relevant.matches[0].source == "local.md"
    assert relevant.matches[0].position == 0
    assert "Rua Central" in relevant.matches[0].text
    assert relevant.as_dict()["matches"] == [relevant.matches[0].as_dict()]
    assert relevant.relevant_rank == 1
    assert relevant.correct
    assert abstention.sources == ()
    assert abstention.matches == ()
    assert abstention.expected_abstention
    assert abstention.correct


@pytest.mark.parametrize("limit", [0, -1])
def test_evaluate_retriever_rejects_invalid_limit(tmp_path: Path, limit: int) -> None:
    with pytest.raises(ValueError, match="limit"):
        evaluate_retriever(_retriever(tmp_path), [EvaluationCase("Marte?", abstain=True)], limit=limit)


def test_evaluate_retriever_rejects_empty_cases(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="pelo menos um caso"):
        evaluate_retriever(_retriever(tmp_path), [])


def test_evaluate_command_uses_versioned_dataset_by_default() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_knowledge_parser(subparsers)
    args = parser.parse_args(["knowledge", "evaluate"])
    assert args.dataset.name == "retrieval-v1.json"
    assert args.retriever == "baseline"
    assert args.min_score is None


def test_evaluate_command_accepts_semantic_retriever() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_knowledge_parser(subparsers)
    args = parser.parse_args(["knowledge", "evaluate", "--retriever", "semantic"])
    assert args.retriever == "semantic"


def test_evaluate_command_accepts_fusion_retriever() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_knowledge_parser(subparsers)
    args = parser.parse_args(["knowledge", "evaluate", "--retriever", "fusion"])
    assert args.retriever == "fusion"


def test_evaluate_command_accepts_diagnostics() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_knowledge_parser(subparsers)
    args = parser.parse_args(["knowledge", "evaluate", "--diagnostics", "--json"])
    assert args.diagnostics
    assert args.as_json
