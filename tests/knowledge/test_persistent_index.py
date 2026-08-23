from pathlib import Path

from orelhao.services.knowledge.index import build_index
from orelhao.services.knowledge.vector_retriever import PersistentVectorRetriever


def test_index_is_rebuildable_and_retrieves_source(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    index = tmp_path / "index"
    sources.mkdir()
    (sources / "atendimento.md").write_text(
        "# Atendimento\nO horário de atendimento é de segunda a sexta, das oito às dezoito horas.",
        encoding="utf-8",
    )
    stats = build_index(sources, index, chunk_size=300, overlap=30)
    assert stats == {"documents": 1, "chunks": 1}
    assert (index / "manifest.json").exists()
    assert (index / "vectors.npy").exists()

    results = PersistentVectorRetriever(index, min_score=0.10).search(
        "qual é o horário de atendimento?", limit=3
    )
    assert results
    assert results[0].chunk.source == "atendimento.md"


def test_retriever_abstains_when_score_is_below_threshold(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    index = tmp_path / "index"
    sources.mkdir()
    (sources / "faq.md").write_text("Matrículas exigem documento de identificação.", encoding="utf-8")
    build_index(sources, index)
    results = PersistentVectorRetriever(index, min_score=0.95).search("temperatura de marte")
    assert results == []
