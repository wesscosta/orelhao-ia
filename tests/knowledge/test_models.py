import pytest

from orelhao.services.knowledge.models import Document, SearchResult
from orelhao.services.knowledge.chunking import chunk_document


def test_document_requires_identity_text_and_source() -> None:
    with pytest.raises(ValueError):
        Document(id="", text="conteúdo", source="fonte")
    with pytest.raises(ValueError):
        Document(id="a", text=" ", source="fonte")
    with pytest.raises(ValueError):
        Document(id="a", text="conteúdo", source=" ")


def test_chunk_document_preserves_source_and_positions() -> None:
    doc = Document(id="doc", text="abcdefghij" * 20, source="base/doc.md")
    chunks = chunk_document(doc, chunk_size=60, overlap=10)
    assert len(chunks) > 1
    assert chunks[0].id == "doc:0"
    assert chunks[1].position == 1
    assert all(chunk.source == "base/doc.md" for chunk in chunks)


def test_search_result_rejects_invalid_score() -> None:
    chunk = chunk_document(Document(id="d", text="texto", source="s"), chunk_size=20, overlap=0)[0]
    with pytest.raises(ValueError):
        SearchResult(chunk=chunk, score=1.1)
