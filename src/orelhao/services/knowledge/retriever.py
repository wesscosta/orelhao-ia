from __future__ import annotations

import re
from typing import Protocol

from .models import SearchResult
from .repository import KnowledgeRepository

_TOKEN_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(text) if len(token) > 1}


class Retriever(Protocol):
    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]: ...


class LexicalRetriever:
    """Retriever local sem dependências externas para validar o contrato RAG.

    O score usa cobertura lexical da consulta. Não é a solução final de busca
    semântica; é uma baseline mensurável para a alpha.1.
    """

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]:
        if limit <= 0:
            return []
        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        scored: list[SearchResult] = []
        for chunk in self.repository.all_chunks():
            chunk_tokens = _tokens(chunk.text)
            overlap = query_tokens & chunk_tokens
            if not overlap:
                continue
            score = len(overlap) / len(query_tokens)
            scored.append(SearchResult(chunk=chunk, score=min(1.0, score)))

        scored.sort(key=lambda item: (-item.score, item.chunk.source, item.chunk.position))
        return scored[:limit]
