"""Integridade temporal e recuperação do catálogo atualizado em novembro de 2026."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from orelhao.services.knowledge.answerability import EvidenceAdjudicator
from orelhao.services.knowledge.evaluation import (
    evaluate_retriever,
    load_evaluation_cases,
)
from orelhao.services.knowledge.index import build_index, load_chunks
from orelhao.services.knowledge.loader import load_documents
from orelhao.services.knowledge.vector_retriever import PersistentVectorRetriever

ROOT = Path("knowledge/sources")
NEW = {
    "cursos/introducao-ia-consulta-2026-11-03.md",
    "cursos/power-bi-consulta-2026-11-03.md",
    "cursos/sala-vacina-consulta-2026-11-03.md",
}


@pytest.fixture(scope="module")
def candidate_index(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp("catalogo-novembro-index")
    build_index(ROOT, dest)
    return dest


def test_fontes_novas_sao_primarias_dated_sem_confirmacao_de_vaga() -> None:
    docs = {d.source: d for d in load_documents(ROOT)}
    assert NEW.issubset(docs)
    for name in NEW:
        metadata = docs[name].metadata
        assert metadata["authority"] == "primary"
        assert metadata["temporal"] is True
        assert metadata["retrieved_at"] == "2026-11-03"
        assert str(metadata["source_url"]).startswith("https://")
        assert metadata.get("current_state_confirmed") is not True
        assert "não" in docs[name].text.lower()


def test_novos_documentos_nao_atestam_vaga_atual(
    candidate_index: Path,
) -> None:
    retriever = PersistentVectorRetriever(candidate_index)
    adjudicator = EvidenceAdjudicator(known_entities=(
        str(c.metadata["entity_id"])
        for c in load_chunks(candidate_index)
        if c.metadata.get("entity_id")
    ))
    for question in (
        "Tem vagas abertas hoje para Introdução à IA?",
        "Qual é o preço atual do curso de Power BI?",
        "Há inscrições abertas em Procedimentos Técnicos em Sala de Vacina atualmente?",
    ):
        results = retriever.search(question, limit=8)
        assessment = adjudicator.assess(
            question, results, as_of=date(2026, 11, 3)
        )
        assert assessment.constraints.requires_current_state
        assert not assessment.decision.answerable


def test_catalogo_novo_recupera_fontes_corretas(candidate_index: Path) -> None:
    cases = load_evaluation_cases(
        Path("knowledge/evaluation/catalogo-novembro-2026.json")
    )
    assert len(cases) == 11
    metrics = evaluate_retriever(
        PersistentVectorRetriever(candidate_index), cases
    )
    assert metrics.hit_at_1 >= 0.9
    assert metrics.hit_at_k >= 0.9


def test_fontes_diferenciam_curso_e_unidade_de_vaga() -> None:
    docs = {d.source: d for d in load_documents(ROOT)}
    checks = {
        "cursos/introducao-ia-consulta-2026-11-03.md": (
            "Severino Ramos Brasil", "Floriano", "40 horas",
        ),
        "cursos/power-bi-consulta-2026-11-03.md": (
            "Severino Ramos Brasil", "40 horas", "16 de novembro",
        ),
        "cursos/sala-vacina-consulta-2026-11-03.md": (
            "Teresina", "Picos", "40 horas",
        ),
    }
    for source, terms in checks.items():
        for term in terms:
            assert term in docs[source].text
