from __future__ import annotations

from dataclasses import dataclass

import pytest

from orelhao.services.knowledge.fusion import ReciprocalRankFusionRetriever
from orelhao.services.knowledge.models import Chunk, SearchResult


def _chunk(chunk_id: str, source: str, position: int = 0) -> Chunk:
    return Chunk(
        id=chunk_id,
        document_id=source,
        text=f"Conteúdo de {source}",
        source=source,
        position=position,
    )


@dataclass
class StaticRetriever:
    results: list[SearchResult]

    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]:
        return self.results[:limit] if query.strip() and limit > 0 else []


def _result(chunk: Chunk, score: float = 1.0) -> SearchResult:
    return SearchResult(chunk=chunk, score=score)


def test_rrf_promotes_chunk_supported_by_both_retrievers() -> None:
    common = _chunk("common", "comum.md")
    lexical = StaticRetriever([_result(_chunk("lexical", "lexical.md")), _result(common)])
    semantic = StaticRetriever([_result(common), _result(_chunk("semantic", "semantic.md"))])

    results = ReciprocalRankFusionRetriever([lexical, semantic]).search("consulta")

    assert results[0].chunk.id == "common"
    assert results[0].score <= 1.0


def test_rrf_keeps_complementary_candidates() -> None:
    lexical = StaticRetriever([_result(_chunk("lexical", "lexical.md"))])
    semantic = StaticRetriever([_result(_chunk("semantic", "semantic.md"))])

    results = ReciprocalRankFusionRetriever([lexical, semantic]).search("consulta")

    assert {result.chunk.id for result in results} == {"lexical", "semantic"}


def test_rrf_preserves_abstention_when_all_retrievers_abstain() -> None:
    fusion = ReciprocalRankFusionRetriever([StaticRetriever([]), StaticRetriever([])])
    assert fusion.search("consulta") == []


def test_rrf_returns_empty_for_invalid_query_or_limit() -> None:
    candidate = StaticRetriever([_result(_chunk("candidate", "candidate.md"))])
    fusion = ReciprocalRankFusionRetriever([candidate, candidate])
    assert fusion.search("") == []
    assert fusion.search("consulta", limit=0) == []


@pytest.mark.parametrize("rank_constant", [0, -1])
def test_rrf_rejects_invalid_rank_constant(rank_constant: int) -> None:
    with pytest.raises(ValueError, match="rank_constant"):
        ReciprocalRankFusionRetriever(
            [StaticRetriever([]), StaticRetriever([])],
            rank_constant=rank_constant,
        )


def test_rrf_requires_at_least_two_retrievers() -> None:
    with pytest.raises(ValueError, match="dois retrievers"):
        ReciprocalRankFusionRetriever([StaticRetriever([])])
