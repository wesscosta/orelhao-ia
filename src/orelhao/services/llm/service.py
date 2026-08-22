from typing import Protocol

from orelhao.services.rag.retriever import RetrievedContext


class LLMService(Protocol):
    def generate(self, query: str, context: list[RetrievedContext]) -> str: ...


class MockLLMService:
    def generate(self, query: str, context: list[RetrievedContext]) -> str:
        source = context[0].source if context else "sem fonte"
        return f"Resposta simulada para '{query}'. A resposta foi baseada na fonte {source}."
