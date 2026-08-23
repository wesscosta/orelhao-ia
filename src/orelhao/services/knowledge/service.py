from __future__ import annotations

from collections.abc import Iterable

from .chunking import chunk_documents
from .context import ContextBuilder
from .models import Document, KnowledgeContext
from .repository import InMemoryKnowledgeRepository, KnowledgeRepository
from .retriever import LexicalRetriever, Retriever


class KnowledgeService:
    """Facade do subsistema de conhecimento.

    O core conversa apenas com este contrato. Chunker, repository e retriever
    podem ser substituídos posteriormente por embeddings/vector store locais.
    """

    def __init__(
        self,
        repository: KnowledgeRepository | None = None,
        retriever: Retriever | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self.repository = repository or InMemoryKnowledgeRepository()
        self.retriever = retriever or LexicalRetriever(self.repository)
        self.context_builder = context_builder or ContextBuilder()

    def ingest(
        self,
        documents: Iterable[Document],
        *,
        chunk_size: int = 700,
        overlap: int = 120,
    ) -> int:
        chunks = chunk_documents(documents, chunk_size=chunk_size, overlap=overlap)
        self.repository.replace(chunks)
        return len(chunks)

    def retrieve(self, query: str, *, limit: int = 4) -> KnowledgeContext:
        results = self.retriever.search(query, limit=limit)
        return self.context_builder.build(query, results)
