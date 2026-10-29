from __future__ import annotations

from orelhao.services.knowledge.claim_grounding import assess_answer, split_factual_claims
from orelhao.services.knowledge.grounding_decision import GroundingPolicy
from orelhao.services.knowledge.models import Chunk, SearchResult


class FakeVerifier:
    def support_score(self, query: str, passage: str) -> float:
        return 0.9 if query in passage else 0.01


def evidence(text: str, source: str) -> SearchResult:
    return SearchResult(Chunk(source, source, text, source, 0), 0.9)


def test_every_sentence_requires_support() -> None:
    result = assess_answer(
        "O curso é gratuito. A inscrição termina amanhã.",
        [evidence("O curso é gratuito.", "curso.md")],
        FakeVerifier(),
        GroundingPolicy(),
    )
    assert len(result.claims) == 2
    assert result.claims[0].decision.allows_response
    assert result.claims[1].decision.should_abstain
    assert result.decision.should_abstain


def test_different_chunks_may_support_distinct_claims() -> None:
    result = assess_answer(
        "O curso é gratuito. As aulas são presenciais.",
        [evidence("O curso é gratuito.", "curso.md"),
         evidence("As aulas são presenciais.", "modalidade.md")],
        FakeVerifier(),
        GroundingPolicy(),
    )
    assert result.decision.allows_response
    assert [item.source for item in result.claims] == ["curso.md", "modalidade.md"]


def test_empty_or_excessive_answer_fails_closed() -> None:
    for text in ("", " ".join(f"Fato {i}." for i in range(9))):
        result = assess_answer(text, [evidence(text, "corpus.md")], FakeVerifier(), GroundingPolicy())
        assert result.decision.should_abstain
    assert split_factual_claims("Primeiro. Segundo; Terceiro.") == (
        "Primeiro.", "Segundo;", "Terceiro."
    )


def test_no_evidence_fails_closed() -> None:
    result = assess_answer("O curso é gratuito.", [], FakeVerifier(), GroundingPolicy())
    assert result.decision.should_abstain
