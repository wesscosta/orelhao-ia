"""Configuração dos testes do Admin."""
from __future__ import annotations

import pytest

from orelhao.admin import access


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "real_access: usa a regra de acesso local sem a exceção do TestClient",
    )


@pytest.fixture(autouse=True)
def _testclient_counts_as_local(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # O TestClient do Starlette usa cliente "testclient" e Host "testserver".
    # A exceção vive só nos testes; o código de produção aceita apenas loopback.
    if request.node.get_closest_marker("real_access"):
        return
    monkeypatch.setattr(access, "LOOPBACK_CLIENTS", access.LOOPBACK_CLIENTS | {"testclient"})
    monkeypatch.setattr(access, "LOOPBACK_HOSTS", access.LOOPBACK_HOSTS | {"testserver"})
