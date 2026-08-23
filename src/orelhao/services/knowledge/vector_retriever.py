from __future__ import annotations

from pathlib import Path

import numpy as np

from .index import VECTOR_DIMENSIONS, load_chunks, load_vectors
from .models import SearchResult
from .vectorizer import hashing_vector


class PersistentVectorRetriever:
    """Busca vetorial local persistente sem modelo externo.

    A alpha.2 usa hashing de palavras + trigramas como baseline rápida e offline.
    Embeddings semânticos de modelo entram em etapa posterior sem alterar o contrato Retriever.
    """

    def __init__(self, index_dir: Path, *, min_score: float = 0.40) -> None:
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score deve estar entre 0 e 1")
        self.index_dir = index_dir
        self.min_score = min_score
        self._chunks = load_chunks(index_dir)
        self._vectors = load_vectors(index_dir)
        if len(self._chunks) != len(self._vectors):
            raise RuntimeError("Índice inconsistente: quantidade de chunks e vetores diverge")

    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]:
        if limit <= 0 or not query.strip() or not self._chunks:
            return []
        query_vector = hashing_vector(query, dimensions=VECTOR_DIMENSIONS)
        if not np.any(query_vector):
            return []
        scores = self._vectors @ query_vector
        order = np.argsort(scores)[::-1]
        results: list[SearchResult] = []
        for raw_index in order:
            score = float(scores[int(raw_index)])
            if score < self.min_score:
                break
            results.append(SearchResult(chunk=self._chunks[int(raw_index)], score=max(0.0, min(1.0, score))))
            if len(results) >= limit:
                break
        return results
