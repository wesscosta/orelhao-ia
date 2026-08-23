from pathlib import Path

from orelhao.services.knowledge.loader import load_documents


def test_loader_reads_md_and_txt_and_ignores_other_files(tmp_path: Path) -> None:
    (tmp_path / "faq.md").write_text("# FAQ\nAtendimento às oito.", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("Suporte local.", encoding="utf-8")
    (tmp_path / "image.bin").write_bytes(b"x")
    docs = load_documents(tmp_path)
    assert [doc.source for doc in docs] == ["faq.md", "notes.txt"]
    assert all(len(doc.metadata["sha256"]) == 64 for doc in docs)
