"""Camada de conhecimento independente de domínio."""

from .models import Chunk, Document, KnowledgeContext, SearchResult
from .repository import InMemoryKnowledgeRepository, KnowledgeRepository
from .retriever import LexicalRetriever, Retriever
from .service import KnowledgeService
from .vector_retriever import PersistentVectorRetriever

__all__ = [
    "Chunk",
    "Document",
    "InMemoryKnowledgeRepository",
    "KnowledgeContext",
    "KnowledgeRepository",
    "KnowledgeService",
    "LexicalRetriever",
    "PersistentVectorRetriever",
    "Retriever",
    "SearchResult",
]
