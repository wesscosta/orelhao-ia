from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from orelhao.services.knowledge.index import build_index
from orelhao.services.knowledge.semantic import (
    SEMANTIC_MANIFEST_FILENAME,
    SemanticRetriever,
    build_semantic_index,
)


class FakeSemanticVectorizer:
    model_id = "teste/semantico"
    model_revision = "revision-1"
    dimensions = 3

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_passages(self, texts: Sequence[str]) -> np.ndarray:
        return self._embed(texts)

    def _embed(self, texts: Sequence[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            lowered = text.casefold()
            if "matrícula" in lowered or "matricula" in lowered:
                vectors.append([1.0, 0.0, 0.0])
            elif "endereço" in lowered or "endereco" in lowered:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return np.asarray(vectors, dtype=np.float32)


def _baseline_index(tmp_path: Path) -> Path:
    sources = tmp_path / "sources"
    index = tmp_path / "index"
    sources.mkdir()
    (sources / "matricula.md").write_text(
        "# Matrícula\nA matrícula pode ser feita presencialmente.",
        encoding="utf-8",
    )
    (sources / "local.md").write_text(
        "# Endereço\nO endereço da unidade é Rua Central, 10.",
        encoding="utf-8",
    )
    build_index(sources, index)
    return index


def test_build_and_search_semantic_index(tmp_path: Path) -> None:
    index = _baseline_index(tmp_path)
    vectorizer = FakeSemanticVectorizer()

    manifest = build_semantic_index(index, vectorizer, batch_size=1)
    retriever = SemanticRetriever(index, vectorizer)
    results = retriever.search("Como faço a matrícula?", limit=1)

    assert manifest["chunks"] == 2
    assert manifest["model_revision"] == "revision-1"
    assert (index / SEMANTIC_MANIFEST_FILENAME).exists()
    assert results[0].chunk.source == "matricula.md"
    assert results[0].score == 1.0


def test_semantic_index_rejects_invalid_batch_size(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="batch_size"):
        build_semantic_index(_baseline_index(tmp_path), FakeSemanticVectorizer(), batch_size=0)


def test_semantic_retriever_detects_changed_chunks(tmp_path: Path) -> None:
    index = _baseline_index(tmp_path)
    vectorizer = FakeSemanticVectorizer()
    build_semantic_index(index, vectorizer)
    with (index / "chunks.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("\n")

    with pytest.raises(RuntimeError, match="desatualizado"):
        SemanticRetriever(index, vectorizer)


def test_semantic_retriever_rejects_different_model(tmp_path: Path) -> None:
    index = _baseline_index(tmp_path)
    vectorizer = FakeSemanticVectorizer()
    build_semantic_index(index, vectorizer)

    class OtherVectorizer(FakeSemanticVectorizer):
        model_revision = "revision-2"

    with pytest.raises(RuntimeError, match="outro modelo"):
        SemanticRetriever(index, OtherVectorizer())
