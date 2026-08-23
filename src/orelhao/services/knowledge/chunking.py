from __future__ import annotations

from collections.abc import Iterable

from .models import Chunk, Document


def chunk_document(document: Document, *, chunk_size: int = 700, overlap: int = 120) -> list[Chunk]:
    """Divide texto por caracteres preservando overlap simples e determinístico.

    Nesta alpha o chunker é deliberadamente simples. Ele estabelece o contrato e
    permite medir recuperação antes de introduzir tokenizadores/modelos externos.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser positivo")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap deve ser >= 0 e menor que chunk_size")

    normalized = " ".join(document.text.split())
    step = chunk_size - overlap
    chunks: list[Chunk] = []
    for position, start in enumerate(range(0, len(normalized), step)):
        text = normalized[start : start + chunk_size].strip()
        if not text:
            continue
        chunks.append(
            Chunk(
                id=f"{document.id}:{position}",
                document_id=document.id,
                text=text,
                source=document.source,
                position=position,
                metadata=document.metadata,
            )
        )
        if start + chunk_size >= len(normalized):
            break
    return chunks


def chunk_documents(
    documents: Iterable[Document], *, chunk_size: int = 700, overlap: int = 120
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        chunks.extend(chunk_document(document, chunk_size=chunk_size, overlap=overlap))
    return chunks
