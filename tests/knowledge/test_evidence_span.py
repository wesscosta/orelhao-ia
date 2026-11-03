from __future__ import annotations

from orelhao.services.knowledge.claim_grounding import assess_answer
from orelhao.services.knowledge.evidence_selector import select_evidence_span
from orelhao.services.knowledge.evidence_span import EvidenceSpan, extract_evidence_spans
from orelhao.services.knowledge.grounding_decision import GroundingPolicy
from orelhao.services.knowledge.models import Chunk, SearchResult


def chunk(text: str, **meta: str) -> Chunk:
    return Chunk("unit:1", "unit", text, "unidade.md", 1, meta)


def test_unicode_offsets_exact_and_metadata_provenance() -> None:
    text = "# Ouvidoria\nO prazo é de 15 dias úteis.\nA taxa é de R$ 30,50."
    item = chunk(
        text, source_url="https://instituicao.example/ouvidoria",
        entity_id="servico:ouvidoria", fact_key="deadline",
    )
    parts = extract_evidence_spans(item)
    assert [x.text for x in parts] == [
        "# Ouvidoria", "O prazo é de 15 dias úteis.", "A taxa é de R$ 30,50."
    ]
    assert all(x.matches_chunk(item) for x in parts)
    assert all(x.text == text[x.start:x.end] for x in parts)
    assert parts[1].source_url == "https://instituicao.example/ouvidoria"
    assert parts[1].entity_id == "servico:ouvidoria"
    assert parts[1].attribute == "deadline"
    assert parts[1].start == text.index("O prazo")


def test_long_paragraph_splits_only_at_existing_word_bounds() -> None:
    item = chunk("Documentação " * 30)
    spans = extract_evidence_spans(item, max_span_chars=64)
    assert len(spans) >= 2
    assert all(s.matches_chunk(item) for s in spans)
    assert all(len(s.text) <= 64 for s in spans)
    assert all(s.text.startswith("Documentação") for s in spans)


def test_not_split_decimal_and_explicit_limit_guard() -> None:
    item = chunk("O valor é R$ 30,50. O outro é 40.5 unidades.")
    spans = extract_evidence_spans(item)
    assert len(spans) == 2
    assert "40.5" in spans[1].text
    assert len(extract_evidence_spans(item, max_spans=1)) == 1


def test_selector_prefers_most_relevant_phrase_not_heading() -> None:
    item = chunk(
        "O Senac oferece cursos.\nO prazo da Ouvidoria é de 15 dias úteis."
        "\nO telefone é 3000-0000."
    )
    choice = select_evidence_span("O prazo da Ouvidoria é de 15 dias úteis", item)
    assert choice is not None
    assert "15 dias úteis" in choice.span.text
    assert choice.span.matches_chunk(item)
    assert "ouvidoria" in choice.matched_terms
    assert 0 < choice.lexical_coverage <= 1
    assert choice.as_dict()["support_verified"] is False


def test_selector_rejects_absent_fact_without_fabricating_span() -> None:
    item = chunk("Biblioteca de livros impressos.")
    assert select_evidence_span("O acesso começa às 16h.", item) is None


def test_span_can_validate_own_offset_but_not_other_chunk() -> None:
    item = chunk("A instituição oferece cursos.")
    other = chunk("A instituição não oferece cursos.")
    span = EvidenceSpan.from_chunk(item, 0, len(item.text))
    assert span.matches_chunk(item)
    assert not span.matches_chunk(other)


def test_grounding_score_is_unchanged_by_span_metadata() -> None:
    class Verifier:
        def support_score(self, claim: str, passage: str) -> float:
            return 0.83 if "15 dias úteis" in passage else 0.03

    item = chunk("A Ouvidoria atua na instituição.\nPrazo: 15 dias úteis.")
    assessment = assess_answer(
        "Prazo: 15 dias úteis.",
        [SearchResult(item, 0.9)], Verifier(), GroundingPolicy()
    )
    assert assessment.decision.allows_response
    assert assessment.decision.score == 0.83
    selection = assessment.claims[0].span_selection
    assert selection is not None
    assert selection.span.matches_chunk(item)
    assert "15 dias úteis" in selection.span.text


def test_invalid_offset_rejected() -> None:
    item = chunk("Olá.")
    for start, end in [(-1, 2), (0, 100), (2, 2)]:
        try:
            EvidenceSpan.from_chunk(item, start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("offset inválido aceito")
