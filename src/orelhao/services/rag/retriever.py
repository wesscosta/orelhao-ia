from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class RetrievedContext:
    text: str
    source: str


class Retriever(Protocol):
    def search(self, query: str) -> list[RetrievedContext]: ...


class MockRetriever:
    def search(self, query: str) -> list[RetrievedContext]:
        return [
            RetrievedContext(
                text=f"Contexto institucional simulado para: {query}",
                source="base-senac-mock",
            )
        ]
