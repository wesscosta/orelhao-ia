from __future__ import annotations

from dataclasses import dataclass

import pytest

from orelhao.services.knowledge.evidence import EvidenceFilteredRetriever
from orelhao.services.knowledge.models import Chunk, SearchResult


def _result(chunk_id: str, text: str) -> SearchResult:
    return SearchResult(
        chunk=Chunk(chunk_id, chunk_id, text, f"{chunk_id}.md", 0),
        score=0.8,
    )


@dataclass
class StaticRetriever:
    results: list[SearchResult]

    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]:
        return self.results[:limit]


@dataclass
class StaticVerifier:
    scores: dict[str, float]

    def support_score(self, query: str, passage: str) -> float:
        del query
        return self.scores[passage]


def test_evidence_filter_preserves_order_and_removes_unsupported_chunks() -> None:
    supported = _result("supported", "resposta presente")
    unsupported = _result("unsupported", "assunto relacionado")
    retriever = EvidenceFilteredRetriever(
        StaticRetriever([unsupported, supported]),
        StaticVerifier({"resposta presente": 0.9, "assunto relacionado": 0.2}),
        min_support=0.5,
    )

    results = retriever.search("pergunta")
    assert [result.chunk.id for result in results] == [supported.chunk.id]
    assert results[0].score == supported.score
    assert results[0].chunk.metadata["evidence_support"] == "0.900000"


def test_evidence_filter_abstains_when_no_chunk_is_supported() -> None:
    candidate = _result("candidate", "sem resposta")
    retriever = EvidenceFilteredRetriever(
        StaticRetriever([candidate]),
        StaticVerifier({"sem resposta": 0.4}),
        min_support=0.5,
    )

    assert retriever.search("pergunta") == []


@pytest.mark.parametrize("min_support", [-0.1, 1.1])
def test_evidence_filter_rejects_invalid_threshold(min_support: float) -> None:
    with pytest.raises(ValueError, match="min_support"):
        EvidenceFilteredRetriever(StaticRetriever([]), StaticVerifier({}), min_support=min_support)
