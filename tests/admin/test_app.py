from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient

from orelhao.admin.app import create_admin_app
from orelhao.services.knowledge.paths import KnowledgePaths


def test_admin_upload_edit_and_reindex(tmp_path: Path):
    paths = KnowledgePaths(sources=tmp_path / "sources", index=tmp_path / "index")
    client = TestClient(create_admin_app(paths))

    response = client.post(
        "/upload",
        files={"file": ("faq.txt", b"Atendimento de segunda a sexta.", "text/plain")},
        data={"title": "FAQ", "tags": "atendimento"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (paths.sources / "faq.md").exists()

    response = client.post("/reindex")
    assert response.status_code == 200
    assert (paths.index / "manifest.json").exists()


def test_admin_marks_index_stale_after_edit(tmp_path: Path):
    paths = KnowledgePaths(sources=tmp_path / "sources", index=tmp_path / "index")
    client = TestClient(create_admin_app(paths))
    client.post(
        "/upload",
        files={"file": ("faq.txt", b"Atendimento de segunda a sexta.", "text/plain")},
        data={"title": "FAQ", "tags": "atendimento"},
    )
    client.post("/reindex")
    response = client.get("/")
    assert "ATUALIZADO" in response.text
    assert "indexado" in response.text
    client.post(
        "/save",
        data={"relative_path": "faq.md", "content": "# FAQ\n\nConteúdo alterado.\n"},
    )
    response = client.get("/")
    assert "DESATUALIZADO" in response.text
    assert "alterado" in response.text


def test_admin_create_and_delete_source(tmp_path: Path):
    paths = KnowledgePaths(sources=tmp_path / "sources", index=tmp_path / "index")
    client = TestClient(create_admin_app(paths))
    response = client.post(
        "/create",
        data={"filename": "manual", "title": "Manual", "tags": "teste"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (paths.sources / "manual.md").exists()
    response = client.post(
        "/delete", data={"relative_path": "manual.md"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert not (paths.sources / "manual.md").exists()


def test_admin_ignores_control_and_evaluation_sources_for_freshness(tmp_path: Path):
    paths = KnowledgePaths(sources=tmp_path / "sources", index=tmp_path / "index")
    paths.sources.mkdir(parents=True)
    (paths.sources / "00-README.md").write_text("# Regras do corpus\n", encoding="utf-8")
    evaluation = paths.sources / "faq" / "faq-rag.md"
    evaluation.parent.mkdir(parents=True)
    evaluation.write_text(
        "---\ncategory: evaluation\n---\n# Perguntas de avaliação\n",
        encoding="utf-8",
    )
    (paths.sources / "atendimento.md").write_text(
        "# Atendimento\n\nAtendimento de segunda a sexta.\n",
        encoding="utf-8",
    )

    client = TestClient(create_admin_app(paths))
    response = client.post("/reindex")
    assert response.status_code == 200

    response = client.get("/")
    assert "ATUALIZADO" in response.text
    assert response.text.count("ignorado") == 2
    assert "indexado" in response.text
