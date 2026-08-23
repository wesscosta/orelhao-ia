from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class RetrievedContext:
    text: str
    source: str


class Retriever(Protocol):
    def search(self, query: str) -> list[RetrievedContext]: ...


class MockRetriever:
    """Compatibilidade temporária do pipeline mock até o orquestrador v0.4."""

    def search(self, query: str) -> list[RetrievedContext]:
        return [
            RetrievedContext(
                text=f"Contexto controlado simulado para: {query}",
                source="knowledge-base-mock",
            )
        ]
