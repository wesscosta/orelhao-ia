"""Gate de expansão documental para Saúde e TI do Senac Piauí (03/11/2026).

Não é teste independente da qualidade da geração ou da voz.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from orelhao.services.knowledge.answerability import EvidenceAdjudicator
from orelhao.services.knowledge.evaluation import (
    evaluate_retriever,
    load_evaluation_cases,
)
from orelhao.services.knowledge.index import build_index, load_chunks
from orelhao.services.knowledge.loader import load_documents
from orelhao.services.knowledge.vector_retriever import PersistentVectorRetriever

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "knowledge" / "sources"
EVALUATION = ROOT / "knowledge" / "evaluation"
EXPANDED_FILES = (
    "cursos/saude-capacitacoes-2026.md",
    "cursos/saude-tecnicos-2026.md",
    "cursos/tecnico-enfermagem-catalogo-2026.md",
    "cursos/tecnicos-ti-2026.md",
)


def _build(tmp_path: Path) -> Path:
    path = tmp_path / "index"
    build_index(SOURCES, path)
    return path


def test_fontes_verificadas_nao_afirmam_atualidade(tmp_path: Path) -> None:
    documents = {d.source: d for d in load_documents(SOURCES)}
    for source in EXPANDED_FILES:
        doc = documents[source]
        assert doc.metadata["authority"] == "primary"
        assert doc.metadata["temporal"] is True
        assert doc.metadata["retrieved_at"] == "2026-11-03"
        assert str(doc.metadata["source_url"]).startswith("https://www.pi.senac.br/")
        assert doc.metadata.get("current_state_confirmed") is not True

    assert documents["cursos/tecnico-enfermagem-catalogo-2026.md"].metadata[
        "entity_id"
    ] == "curso:tecnico em enfermagem"
    assert (ROOT / "docs" / "catalogo-por-unidade-2026.md").is_file()
    assert "unidades/catalogo-por-unidade-2026.md" not in documents


def test_expansao_preserva_benchmark_legado(tmp_path: Path) -> None:
    retriever = PersistentVectorRetriever(_build(tmp_path))
    legacy = evaluate_retriever(
        retriever, load_evaluation_cases(EVALUATION / "retrieval-v1.json"),
    )
    assert legacy.cases == 40
    assert legacy.hit_at_1 >= 0.600 - 1e-9
    assert legacy.hit_at_k >= 0.8333333333 - 1e-9
    assert legacy.mrr >= 0.6972222222 - 1e-9
    assert legacy.abstention_accuracy >= 0.600 - 1e-9


def test_documentos_novos_cobrem_perguntas_fundamentadas(tmp_path: Path) -> None:
    retriever = PersistentVectorRetriever(_build(tmp_path))
    cases = load_evaluation_cases(
        EVALUATION / "expansion-health-ti-20261103.json",
    )
    result = evaluate_retriever(retriever, cases)
    assert result.cases == 17
    assert result.hit_at_1 == 1.0
    assert result.hit_at_k == 1.0


def test_vagas_hoje_permanecem_bloqueadas_no_precheck(tmp_path: Path) -> None:
    index = _build(tmp_path)
    retriever = PersistentVectorRetriever(index)
    known_entities = [
        str(c.metadata["entity_id"])
        for c in load_chunks(index)
        if c.metadata.get("entity_id")
    ]
    adjudicator = EvidenceAdjudicator(known_entities=known_entities)
    for question in (
        "Tem vagas abertas hoje para Técnico em Enfermagem no Senac?",
        "Qual é o preço atual do curso de Técnico em Enfermagem?",
    ):
        evidence = retriever.search(question, limit=8)
        assert evidence, "A fonte histórica pode ser recuperada"
        check = adjudicator.assess(
            question, evidence, as_of=date(2026, 11, 3),
        )
        assert check.constraints.requires_current_state
        assert not check.decision.answerable
        assert check.decision.reason.value == "temporal_evidence_unavailable"
