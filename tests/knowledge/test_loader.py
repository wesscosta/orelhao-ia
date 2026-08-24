from pathlib import Path

from orelhao.services.knowledge.loader import load_documents


def test_load_documents_recursively(tmp_path: Path) -> None:
    nested = tmp_path / "psg"
    nested.mkdir()

    (nested / "programa.md").write_text(
        "# Programa\nConteúdo do programa.",
        encoding="utf-8",
    )

    documents = load_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0].source == "psg/programa.md"


def test_markdown_frontmatter_becomes_metadata(tmp_path: Path) -> None:
    path = tmp_path / "documento.md"
    path.write_text(
        """---
title: "Documento de teste"
category: institucional
authority: primary
temporal: false
retrieved_at: "2026-08-24"
source_url: "https://example.com/documento"
---
# Documento

Conteúdo relevante.
""",
        encoding="utf-8",
    )

    documents = load_documents(tmp_path)

    assert len(documents) == 1

    document = documents[0]

    assert document.title == "Documento de teste"
    assert document.text == "# Documento\n\nConteúdo relevante."
    assert not document.text.startswith("---")

    assert document.metadata["category"] == "institucional"
    assert document.metadata["authority"] == "primary"
    assert document.metadata["temporal"] is False
    assert document.metadata["retrieved_at"] == "2026-08-24"
    assert document.metadata["source_url"] == "https://example.com/documento"
    assert document.metadata["format"] == "md"
    assert "sha256" in document.metadata


def test_control_readme_is_not_indexed(tmp_path: Path) -> None:
    (tmp_path / "00-README.md").write_text(
        """---
title: "Corpus"
---
# Regras do corpus
""",
        encoding="utf-8",
    )

    assert load_documents(tmp_path) == []


def test_evaluation_document_is_not_indexed(tmp_path: Path) -> None:
    faq = tmp_path / "faq"
    faq.mkdir()

    (faq / "faq-rag.md").write_text(
        """---
title: "FAQ de avaliação"
category: evaluation
authority: derived-from-primary-sources
---
# Perguntas de avaliação

Qual é o endereço?
""",
        encoding="utf-8",
    )

    assert load_documents(tmp_path) == []


def test_regular_text_file_is_still_supported(tmp_path: Path) -> None:
    (tmp_path / "atendimento.txt").write_text(
        "Atendimento de segunda a sexta.",
        encoding="utf-8",
    )

    documents = load_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0].text == "Atendimento de segunda a sexta."
    assert documents[0].metadata["format"] == "txt"


def test_invalid_frontmatter_does_not_drop_document(tmp_path: Path) -> None:
    (tmp_path / "invalido.md").write_text(
        """---
title: [yaml inválido
---
# Conteúdo

Documento ainda deve ser carregado.
""",
        encoding="utf-8",
    )

    documents = load_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0].text.startswith("---")
