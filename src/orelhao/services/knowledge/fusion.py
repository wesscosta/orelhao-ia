from __future__ import annotations

from collections.abc import Sequence

from .models import Chunk, SearchResult
from .retriever import Retriever

RRF_RANK_CONSTANT = 60


class ReciprocalRankFusionRetriever:
    """Combina rankings sem comparar diretamente seus scores.

    Cada retriever mantém seu próprio mecanismo de seleção e abstenção. A
    fusão atua somente sobre as posições das listas já filtradas.
    """

    def __init__(
        self,
        retrievers: Sequence[Retriever],
        *,
        rank_constant: int = RRF_RANK_CONSTANT,
    ) -> None:
        if len(retrievers) < 2:
            raise ValueError("a fusão exige pelo menos dois retrievers")
        if rank_constant <= 0:
            raise ValueError("rank_constant deve ser maior que zero")
        self._retrievers = tuple(retrievers)
        self.rank_constant = rank_constant

    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]:
        if limit <= 0 or not query.strip():
            return []

        scores: dict[str, float] = {}
        chunks: dict[str, Chunk] = {}
        for retriever in self._retrievers:
            for rank, result in enumerate(retriever.search(query, limit=limit), start=1):
                chunks.setdefault(result.chunk.id, result.chunk)
                scores[result.chunk.id] = scores.get(result.chunk.id, 0.0) + 1.0 / (
                    self.rank_constant + rank
                )

        maximum_score = len(self._retrievers) / (self.rank_constant + 1)
        ranked = sorted(
            scores,
            key=lambda chunk_id: (
                -scores[chunk_id],
                chunks[chunk_id].source,
                chunks[chunk_id].position,
            ),
        )
        return [
            SearchResult(
                chunk=chunks[chunk_id],
                score=min(1.0, scores[chunk_id] / maximum_score),
            )
            for chunk_id in ranked[:limit]
        ]
