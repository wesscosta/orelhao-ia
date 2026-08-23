"""Camada de conhecimento independente de domínio."""

from .models import Chunk, Document, KnowledgeContext, SearchResult
from .repository import InMemoryKnowledgeRepository, KnowledgeRepository
from .retriever import LexicalRetriever, Retriever
from .service import KnowledgeService

__all__ = [
    "Chunk",
    "Document",
    "KnowledgeContext",
    "SearchResult",
    "KnowledgeRepository",
    "InMemoryKnowledgeRepository",
    "Retriever",
    "LexicalRetriever",
    "KnowledgeService",
]
