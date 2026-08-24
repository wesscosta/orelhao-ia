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
