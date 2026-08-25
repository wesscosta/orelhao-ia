from pathlib import Path

from orelhao.services.knowledge.evaluation import (
    EvaluationCase,
    evaluate_retriever,
    load_evaluation_cases,
)
from orelhao.services.knowledge.index import build_index
from orelhao.services.knowledge.vector_retriever import PersistentVectorRetriever


def test_load_evaluation_cases(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text('[{"query":"onde fica?","expected_sources":["local.md"]},{"query":"Marte?","abstain":true}]')
    cases = load_evaluation_cases(path)
    assert len(cases) == 2
    assert cases[1].abstain


def test_evaluate_retriever_reports_quality(tmp_path: Path) -> None:
    sources, index = tmp_path / "sources", tmp_path / "index"
    sources.mkdir()
    (sources / "local.md").write_text("# Endereço\nEndereço da unidade: Rua Central, 10.", encoding="utf-8")
    build_index(sources, index)
    retriever = PersistentVectorRetriever(index, min_score=0.40)
    metrics = evaluate_retriever(retriever, [EvaluationCase("qual o endereço da unidade?", ("local.md",))])
    assert metrics.hit_at_1 == 1.0
    assert metrics.hit_at_k == 1.0
    assert metrics.mrr == 1.0
    assert metrics.mean_latency_ms >= 0.0
