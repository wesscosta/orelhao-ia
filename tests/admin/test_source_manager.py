from pathlib import Path

import pytest

from orelhao.admin.source_manager import (
    atomic_write_source,
    list_sources,
    normalize_source_name,
    normalize_uploaded_text,
    resolve_source,
)


def test_txt_is_normalized_to_markdown():
    name, content = normalize_uploaded_text(
        original_name="FAQ Geral.txt",
        raw_text="Horário de atendimento: 8h às 18h.",
        title="FAQ Geral",
        tags="faq, atendimento",
    )
    assert name == "FAQ-Geral.md"
    assert 'title: "FAQ Geral"' in content
    assert "# FAQ Geral" in content
    assert "Horário de atendimento" in content


def test_markdown_frontmatter_is_not_duplicated():
    original = "---\ntitle: X\n---\n# X\nTexto"
    _, content = normalize_uploaded_text(
        original_name="x.md", raw_text=original, title="Outro", tags="tag"
    )
    assert content.count("---") == 2


def test_source_path_cannot_escape_root(tmp_path: Path):
    with pytest.raises(ValueError):
        resolve_source(tmp_path, "../fora.md")


def test_atomic_write_and_list(tmp_path: Path):
    atomic_write_source(tmp_path, "faq.md", "# FAQ\n\nTexto\n")
    assert (tmp_path / "faq.md").read_text() == "# FAQ\n\nTexto\n"
    items = list_sources(tmp_path)
    assert [item.relative_path for item in items] == ["faq.md"]


def test_rejects_unsupported_suffix():
    with pytest.raises(ValueError):
        normalize_source_name("manual.pdf")
