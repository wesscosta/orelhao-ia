"""Rotas de monitoramento e visão geral permanecem restritas ao acesso local."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orelhao.admin.app import create_admin_app
from orelhao.services.knowledge.paths import KnowledgePaths

# Todo o Admin é local: monitoramento, visão geral, fontes, bancada e auditoria.
LOCAL_ONLY = ["/overview", "/monitor", "/monitor/state", "/monitor/events",
              "/system", "/system/state", "/", "/edit/x.md", "/workbench",
              "/workbench/stt-status", "/audit/summary"]
LOCAL_ONLY_POSTS = ["/save", "/delete", "/create", "/reindex", "/workbench/run"]

pytestmark = pytest.mark.real_access
AUTH = ("admin", "long-local-password-for-tests")


@pytest.fixture
def paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KnowledgePaths:
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path / "monitor"))
    monkeypatch.setenv("ORELHAO_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("ORELHAO_AUDIT_PASSWORD", AUTH[1])
    sources = tmp_path / "sources"
    sources.mkdir()
    return KnowledgePaths(sources=sources, index=tmp_path / "index")


def _local(paths: KnowledgePaths) -> TestClient:
    return TestClient(create_admin_app(paths=paths), client=("127.0.0.1", 50000),
                      base_url="http://127.0.0.1:8765")


def _remote(paths: KnowledgePaths) -> TestClient:
    # Simula o Admin iniciado com --host 0.0.0.0 e acessado de outra máquina.
    return TestClient(create_admin_app(paths=paths), client=("192.168.0.50", 50000))


@pytest.mark.parametrize("route", LOCAL_ONLY)
def test_remote_client_is_rejected(paths: KnowledgePaths, route: str) -> None:
    response = _remote(paths).get(route, headers={"Host": "127.0.0.1:8765"})
    assert response.status_code == 403


@pytest.mark.parametrize("route", LOCAL_ONLY_POSTS)
def test_remote_writes_are_rejected(paths: KnowledgePaths, route: str) -> None:
    client = TestClient(create_admin_app(paths=paths), client=("127.0.0.1", 50000),
                        base_url="http://rebind.attacker.example")
    assert client.post(route, data={"relative_path": "x.md", "content": "x"}).status_code == 403
    assert _remote(paths).post(route, headers={"Host": "127.0.0.1:8765"}).status_code == 403


def test_default_testclient_is_not_local(paths: KnowledgePaths) -> None:
    # Sem a exceção dos testes, "testclient"/"testserver" não contam como loopback.
    assert TestClient(create_admin_app(paths=paths)).get("/monitor/state").status_code == 403


def test_openapi_schema_is_not_published(paths: KnowledgePaths) -> None:
    assert _local(paths).get("/openapi.json").status_code == 404


@pytest.mark.parametrize("route", LOCAL_ONLY)
def test_dns_rebinding_host_is_rejected(paths: KnowledgePaths, route: str) -> None:
    client = TestClient(create_admin_app(paths=paths), client=("127.0.0.1", 50000))
    response = client.get(route, headers={"Host": "rebind.attacker.example"})
    assert response.status_code == 403


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "localhost"])
def test_loopback_with_local_host_is_allowed(paths: KnowledgePaths, host: str) -> None:
    client = TestClient(create_admin_app(paths=paths), client=("127.0.0.1", 50000))
    response = client.get("/monitor/state", headers={"Host": host})
    assert response.status_code == 200
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_ipv6_loopback_is_allowed(paths: KnowledgePaths) -> None:
    client = TestClient(create_admin_app(paths=paths), client=("::1", 50000))
    assert client.get("/system/state", headers={"Host": "[::1]:8765"}).status_code == 200


def test_rejection_page_is_html_for_browsers(paths: KnowledgePaths) -> None:
    response = _remote(paths).get("/overview", headers={"Accept": "text/html"})
    assert response.status_code == 403
    assert "text/html" in response.headers["content-type"]
    assert "somente local" in response.text


def test_audit_also_rejects_rebinding_even_with_password(paths: KnowledgePaths) -> None:
    client = TestClient(create_admin_app(paths=paths), client=("127.0.0.1", 50000))
    response = client.get("/audit/summary", auth=AUTH,
                          headers={"Host": "rebind.attacker.example"})
    assert response.status_code == 403


def test_background_fetch_does_not_trigger_basic_auth_dialog(paths: KnowledgePaths) -> None:
    client = _local(paths)
    plain = client.get("/audit/summary")
    assert plain.status_code == 401
    assert "www-authenticate" in plain.headers
    fetch = client.get("/audit/summary", headers={"X-Requested-With": "fetch"})
    assert fetch.status_code == 401
    assert "www-authenticate" not in fetch.headers
