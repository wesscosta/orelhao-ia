"""Rotas protegidas de auditoria e download dos backups existentes."""
from __future__ import annotations

import os
import re
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.concurrency import run_in_threadpool

from orelhao.hardware.audit import export_csv, summary

from .audit_view import audit_page as render_audit_page

router = APIRouter(prefix="/audit")
basic = HTTPBasic(auto_error=False)
BACKUP_NAME = re.compile(
    r"(?:orelhao-ia-(?:codigo-config|completo-modelos)-\d{8}-\d{6}\.tar\.zst"
    r"(?:\.sha256)?|MANIFESTO-\d{8}-\d{6}\.txt)"
)
NO_CACHE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def _admin_only(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic)],
) -> None:
    # HTTPS na frente pode alterar o endereco visto pelo app. Sem proxy de confianca,
    # a rota e restrita a conexao local (acessivel por tunel SSH).
    address = request.client.host if request.client else ""
    if address not in ("127.0.0.1", "::1", "testclient"):
        raise HTTPException(status_code=403, detail="Auditoria somente via acesso local")
    expected = os.environ.get("ORELHAO_AUDIT_PASSWORD", "")
    if len(expected) < 16:
        raise HTTPException(status_code=503, detail="Senha de auditoria nao configurada")
    if credentials is None or not (secrets.compare_digest(credentials.username, "admin")
                                  and secrets.compare_digest(credentials.password, expected)):
        raise HTTPException(
            status_code=401, detail="Autenticacao necessaria",
            headers={"WWW-Authenticate": 'Basic realm="Auditoria Orelhao IA"'},
        )


Auth = Annotated[None, Depends(_admin_only)]


@router.get("", response_class=HTMLResponse)
async def audit_page(_auth: Auth) -> HTMLResponse:
    return HTMLResponse(render_audit_page(), headers=NO_CACHE)


@router.get("/summary")
async def audit_summary(
    _auth: Auth, days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> JSONResponse:
    result = await run_in_threadpool(summary, days=days)
    return JSONResponse(result, headers=NO_CACHE)


@router.get("/events.csv")
async def audit_csv(
    _auth: Auth, days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> Response:
    content = await run_in_threadpool(export_csv, days=days)
    return Response(
        content="\ufeff" + content, media_type="text/csv; charset=utf-8",
        headers={**NO_CACHE, "Content-Disposition": 'attachment; filename="auditoria.csv"'},
    )


def backup_directory() -> Path:
    return Path(os.getenv("ORELHAO_BACKUP_DIR", str(Path.home() / "backups/orelhao-ia")))


def _backups() -> list[dict[str, object]]:
    root = backup_directory()
    if not root.is_dir():
        return []
    found: list[dict[str, object]] = []
    for path in root.iterdir():
        if not BACKUP_NAME.fullmatch(path.name) or path.is_symlink() or not path.is_file():
            continue
        found.append({"name": path.name, "bytes": path.stat().st_size})
    return sorted(found, key=lambda item: str(item["name"]), reverse=True)[:60]


@router.get("/backups")
async def audit_backups(_auth: Auth) -> JSONResponse:
    return JSONResponse({"files": await run_in_threadpool(_backups)}, headers=NO_CACHE)


@router.get("/backups/{filename}")
async def audit_download(_auth: Auth, filename: str) -> FileResponse:
    if not BACKUP_NAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="Backup nao encontrado")
    directory = backup_directory()
    file = directory / filename
    if file.is_symlink() or not file.is_file() or file.parent.resolve() != directory.resolve():
        raise HTTPException(status_code=404, detail="Backup nao encontrado")
    return FileResponse(
        file, filename=filename, media_type="application/octet-stream", headers=NO_CACHE,
    )
