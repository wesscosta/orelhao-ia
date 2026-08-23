from __future__ import annotations

from typing import Protocol

from .models import Chunk


class KnowledgeRepository(Protocol):
    def replace(self, chunks: list[Chunk]) -> None: ...

    def all_chunks(self) -> tuple[Chunk, ...]: ...


class InMemoryKnowledgeRepository:
    """Repositório determinístico usado em testes e na fundação da v0.4."""

    def __init__(self, chunks: list[Chunk] | None = None) -> None:
        self._chunks: tuple[Chunk, ...] = tuple(chunks or ())

    def replace(self, chunks: list[Chunk]) -> None:
        self._chunks = tuple(chunks)

    def all_chunks(self) -> tuple[Chunk, ...]:
        return self._chunks
