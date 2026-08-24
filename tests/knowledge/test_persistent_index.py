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


def test_hybrid_retriever_rejects_unrelated_domain(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    index = tmp_path / "index"
    sources.mkdir()

    (sources / "psg.md").write_text(
        """
# Vagas e editais PSG

O programa mantém uma área de consulta de vagas, editais,
inscrições e comunicados para cursos gratuitos.
""".strip(),
        encoding="utf-8",
    )

    build_index(sources, index)

    results = PersistentVectorRetriever(index).search(
        "qual é a temperatura de Marte?"
    )

    assert results == []


def test_hybrid_retriever_prefers_action_document(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    index = tmp_path / "index"
    (sources / "psg").mkdir(parents=True)

    (sources / "psg" / "programa.md").write_text(
        """
---
title: Programa de Gratuidade
category: psg
---
# Programa de Gratuidade

O programa oferece educação profissional gratuita.
""".strip(),
        encoding="utf-8",
    )

    (sources / "psg" / "como-se-inscrever.md").write_text(
        """
---
title: Como se inscrever no PSG
category: psg
---
# Como se inscrever no PSG

O interessado deve acompanhar as vagas e preencher
a ficha de inscrição com suas informações pessoais.
""".strip(),
        encoding="utf-8",
    )

    build_index(sources, index)

    results = PersistentVectorRetriever(index).search(
        "como faço para me inscrever no programa de gratuidade?"
    )

    assert results
    assert results[0].chunk.source == "psg/como-se-inscrever.md"


def test_hybrid_retriever_prefers_address_evidence(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    index = tmp_path / "index"

    (sources / "institucional").mkdir(parents=True)
    (sources / "atendimento").mkdir(parents=True)

    (sources / "institucional" / "sobre.md").write_text(
        """
# Sobre a instituição

A instituição oferece educação profissional
e mantém diversas unidades no estado.
""".strip(),
        encoding="utf-8",
    )

    (sources / "atendimento" / "canais.md").write_text(
        """
---
title: Endereço e canais institucionais
category: atendimento
---
# Administração Regional

Endereço: Avenida Campos Sales, 1111,
Centro, Teresina, Piauí.
""".strip(),
        encoding="utf-8",
    )

    build_index(sources, index)

    results = PersistentVectorRetriever(index).search(
        "qual o endereço da instituição no Piauí?"
    )

    assert results
    assert results[0].chunk.source == "atendimento/canais.md"
