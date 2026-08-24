from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .chunking import chunk_documents
from .loader import load_documents
from .models import Chunk
from .vectorizer import hashing_vector

INDEX_VERSION = 1
VECTOR_DIMENSIONS = 384


def _chunk_to_dict(chunk: Chunk) -> dict[str, object]:
    payload = asdict(chunk)
    payload["metadata"] = dict(chunk.metadata)
    return payload


def build_index(sources: Path, index_dir: Path, *, chunk_size: int = 700, overlap: int = 120) -> dict[str, int]:
    documents = load_documents(sources)
    chunks = chunk_documents(documents, chunk_size=chunk_size, overlap=overlap)
    index_dir.mkdir(parents=True, exist_ok=True)

    vectors = np.vstack([hashing_vector(chunk.text, dimensions=VECTOR_DIMENSIONS) for chunk in chunks]) if chunks else np.empty((0, VECTOR_DIMENSIONS), dtype=np.float32)
    np.save(index_dir / "vectors.npy", vectors, allow_pickle=False)

    with (index_dir / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(_chunk_to_dict(chunk), ensure_ascii=False) + "\n")

    manifest = {
        "version": INDEX_VERSION,
        "vectorizer": "hashing-word-char-v1",
        "dimensions": VECTOR_DIMENSIONS,
        "documents": len(documents),
        "chunks": len(chunks),
        "sources": {document.source: document.metadata.get("sha256", "") for document in documents},
    }
    (index_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"documents": len(documents), "chunks": len(chunks)}


def load_chunks(index_dir: Path) -> list[Chunk]:
    path = index_dir / "chunks.jsonl"
    if not path.exists():
        raise RuntimeError("Índice inexistente. Execute: orelhao knowledge index")
    chunks: list[Chunk] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        chunks.append(Chunk(**payload))
    return chunks


def load_vectors(index_dir: Path) -> np.ndarray:
    path = index_dir / "vectors.npy"
    if not path.exists():
        raise RuntimeError("Índice inexistente. Execute: orelhao knowledge index")
    vectors: np.ndarray = np.load(path, allow_pickle=False)
    return vectors
