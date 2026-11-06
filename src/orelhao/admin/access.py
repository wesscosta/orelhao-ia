"""Restrição de acesso local compartilhada pelas rotas administrativas.

O Admin não tem login de produção: o acesso é restrito à própria máquina
(``127.0.0.1:8765``), alcançada remotamente apenas por túnel SSH. Esta
dependência mantém essa garantia mesmo que o processo seja iniciado com
``--host 0.0.0.0`` por engano, e bloqueia *DNS rebinding* (um site externo
resolvendo para 127.0.0.1 e lendo, pelo navegador do operador, as transcrições
ao vivo ou o estado da máquina).
"""
from __future__ import annotations

from fastapi import HTTPException, Request

LOOPBACK_CLIENTS = frozenset({"127.0.0.1", "::1"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
# O TestClient do Starlette usa cliente "testclient" e Host "testserver".
TEST_CLIENT = "testclient"
TEST_HOST = "testserver"


def _host_name(request: Request) -> str:
    raw = request.headers.get("host", "")
    if raw.startswith("["):  # IPv6 literal: "[::1]:8765"
        return raw[1:].split("]", 1)[0].lower()
    return raw.rsplit(":", 1)[0].lower() if raw.count(":") == 1 else raw.lower()


def is_local_request(request: Request) -> bool:
    client = request.client.host if request.client else ""
    host = _host_name(request)
    if client == TEST_CLIENT:
        return host in LOOPBACK_HOSTS or host == TEST_HOST
    return client in LOOPBACK_CLIENTS and host in LOOPBACK_HOSTS


def local_only(request: Request) -> None:
    """Dependência FastAPI: 403 para qualquer acesso que não seja local."""
    if not is_local_request(request):
        raise HTTPException(status_code=403, detail="Acesso administrativo somente local")
