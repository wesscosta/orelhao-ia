from datetime import date

from orelhao.services.knowledge.answerability import EvidenceAdjudicator
from orelhao.services.knowledge.evidence_decision import AbstentionReason
from orelhao.services.knowledge.models import Chunk, SearchResult

TODAY = date(2026, 10, 29)


def item(text: str, **metadata: object) -> SearchResult:
    return SearchResult(
        Chunk(
            id=str(metadata.get("id", "demo:0")),
            document_id="demo",
            text=text,
            source="demo.md",
            position=0,
            metadata=metadata,
        ),
        0.9,
    )


def test_empty_evidence_abstains() -> None:
    decision = EvidenceAdjudicator().assess("Qual é a missão?", [], as_of=TODAY)
    assert decision.decision.reason is AbstentionReason.NO_RELEVANT_EVIDENCE


def test_related_historical_offer_cannot_prove_current_availability() -> None:
    evidence = [item("O curso Excel teve vagas anunciadas em outubro.", retrieved_at="2026-10-29", temporal=True)]
    decision = EvidenceAdjudicator().assess(
        "Ainda há vagas disponíveis hoje para Excel?", evidence, as_of=TODAY
    )
    assert decision.decision.reason is AbstentionReason.TEMPORAL_EVIDENCE_UNAVAILABLE


def test_a_historical_question_does_not_require_live_state() -> None:
    result = EvidenceAdjudicator().assess(
        "Quais editais apareciam no portal em outubro de 2026?",
        [item("O edital 006/2026 apareceu na consulta de outubro.")],
        as_of=TODAY,
    )
    assert result.decision.answerable


def test_current_state_requires_explicit_same_day_verification() -> None:
    evidence = [item("Vaga ativa hoje.", current_state_confirmed=True, authority="primary", source_url="https://example.org/fonte",
                     verified_at="2026-10-29", valid_until="2026-10-29")]
    result = EvidenceAdjudicator().assess("Há vagas abertas hoje?", evidence, as_of=TODAY)
    assert result.decision.answerable
    assert len(result.admissible_chunk_ids) == 1


def test_expired_state_fails_closed() -> None:
    evidence = [item("Vaga ativa em agosto.", current_state_confirmed=True,
                     verified_at="2026-08-24", valid_until="2026-08-25")]
    result = EvidenceAdjudicator().assess("Há vagas hoje?", evidence, as_of=TODAY)
    assert result.decision.reason is AbstentionReason.TEMPORAL_EVIDENCE_UNAVAILABLE


def test_structured_entity_mismatch() -> None:
    evidence = [item("O curso B custa R$ 90.", entity_id="curso:curso b")]
    result = EvidenceAdjudicator().assess("Qual o valor do curso de Curso A?", evidence, as_of=TODAY)
    assert result.decision.reason is AbstentionReason.ENTITY_MISMATCH


def test_conflicting_facts_are_not_resolved_by_retrieval_rank() -> None:
    a = item("A carga horária é de 40 horas.", id="x", entity_id="curso:excel",
             fact_key="duration", fact_value="40", authority="primary")
    b = item("A carga horária é de 60 horas.", id="y", entity_id="curso:excel",
             fact_key="duration", fact_value="60", authority="primary")
    result = EvidenceAdjudicator().assess("Qual a carga horária do curso de Excel?", [a, b], as_of=TODAY)
    assert result.decision.reason is AbstentionReason.CONFLICTING_EVIDENCE
    assert set(result.conflicting_chunk_ids) == {"x", "y"}


def test_different_entities_do_not_conflict() -> None:
    a = item("Curso Excel A: 40 horas.", id="x", entity_id="curso:excel a",
             fact_key="duration", fact_value="40", authority="primary")
    b = item("Curso Excel B: 60 horas.", id="y", entity_id="curso:excel b",
             fact_key="duration", fact_value="60", authority="primary")
    result = EvidenceAdjudicator().assess("Quais são as durações?", [a, b], as_of=TODAY)
    assert result.decision.answerable


def test_unstructured_positive_is_not_claimed_verified() -> None:
    result = EvidenceAdjudicator().assess("O que é o PSG?", [item("PSG é programa de gratuidade.")], as_of=TODAY)
    assert result.decision.answerable
    assert result.verified_specific_answer is False
