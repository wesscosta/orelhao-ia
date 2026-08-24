from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from orelhao.services.knowledge.index import build_index
from orelhao.services.knowledge.loader import load_documents
from orelhao.services.knowledge.paths import KnowledgePaths, default_knowledge_paths

try:
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.responses import HTMLResponse, RedirectResponse
except ImportError:  # pacote base continua utilizável sem o extra [admin]
    FastAPI = File = Form = HTTPException = UploadFile = None
    HTMLResponse = RedirectResponse = None

from .source_manager import (
    MAX_SOURCE_BYTES,
    atomic_write_source,
    create_markdown_source,
    delete_source,
    list_sources,
    normalize_uploaded_text,
    read_source,
)


def _require_web() -> None:
    if FastAPI is None:
        raise RuntimeError(
            "Interface web não instalada. Execute: pip install -e '.[admin]'"
        )


def _layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — Orelhão IA</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 1080px; margin: 2rem auto; padding: 0 1rem; color: #1f2937; }}
header {{ display:flex; justify-content:space-between; align-items:center; gap:1rem; }}
nav a {{ margin-left:1rem; }}
.card {{ border:1px solid #d1d5db; border-radius:10px; padding:1rem; margin:1rem 0; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:1rem; }}
input, textarea {{ width:100%; box-sizing:border-box; padding:.65rem; margin:.3rem 0 .8rem; }}
textarea {{ min-height:420px; font-family:ui-monospace,monospace; }}
button {{ padding:.65rem 1rem; cursor:pointer; }}
.muted {{ color:#6b7280; }}
.ok {{ color:#047857; }}
.warn {{ color:#b45309; }}
code {{ background:#f3f4f6; padding:.15rem .35rem; border-radius:4px; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ text-align:left; padding:.6rem; border-bottom:1px solid #e5e7eb; }}
</style>
</head>
<body>
<header><h1>Orelhão IA — Knowledge Admin</h1><nav><a href="/">Base</a></nav></header>
{body}
</body>
</html>"""


def _manifest(index_dir: Path) -> dict[str, object]:
    path = index_dir / "manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _indexed_sources(manifest: dict[str, object]) -> dict[str, str]:
    sources = manifest.get("sources", {})
    if not isinstance(sources, dict):
        return {}
    return {str(key): str(value) for key, value in sources.items()}


def _current_indexable_sources(sources_dir: Path) -> dict[str, str]:
    """Return exactly the source set represented by the knowledge index."""
    return {
        document.source: str(document.metadata.get("sha256", ""))
        for document in load_documents(sources_dir)
    }


def _source_status(
    relative_path: str,
    sha256: str,
    indexed: dict[str, str],
    current_indexable: dict[str, str],
) -> str:
    if relative_path not in current_indexable:
        return "ignorado"
    indexed_hash = indexed.get(relative_path)
    if indexed_hash is None:
        return "novo"
    if indexed_hash != sha256:
        return "alterado"
    return "indexado"


def _index_is_stale(current_indexable: dict[str, str], manifest: dict[str, object]) -> bool:
    return current_indexable != _indexed_sources(manifest)


def create_admin_app(paths: KnowledgePaths | None = None):
    _require_web()
    resolved = paths or default_knowledge_paths()
    app = FastAPI(title="Orelhão IA Knowledge Admin", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def home():
        files = list_sources(resolved.sources)
        manifest = _manifest(resolved.index)
        indexed = _indexed_sources(manifest)
        current_indexable = _current_indexable_sources(resolved.sources)
        rows = "".join(
            f"<tr><td><a href='/edit/{quote(item.relative_path)}'>{html.escape(item.relative_path)}</a></td>"
            f"<td>{item.size_bytes:,} B</td>"
            f"<td>{html.escape(_source_status(item.relative_path, item.sha256, indexed, current_indexable))}</td></tr>"
            for item in files
        ) or "<tr><td colspan='3' class='muted'>Nenhuma fonte cadastrada.</td></tr>"
        stale = _index_is_stale(current_indexable, manifest)
        status = (
            f"{manifest.get('documents', 0)} documentos / {manifest.get('chunks', 0)} chunks"
            if manifest
            else "Índice ainda não gerado"
        )
        freshness = "DESATUALIZADO" if stale else "ATUALIZADO"
        freshness_class = "warn" if stale else "ok"
        body = f"""
<div class="grid">
<section class="card">
<h2>Status</h2>
<p><strong>Fontes:</strong> {len(files)}</p>
<p><strong>Índice:</strong> {html.escape(status)}</p>
<p><strong>Estado:</strong> <span class="{freshness_class}">{freshness}</span></p>
<p class="muted">A interface altera apenas <code>knowledge/sources/</code>.</p>
<form method="post" action="/reindex"><button type="submit">Reindexar base</button></form>
</section>
<section class="card">
<h2>Criar documento</h2>
<form method="post" action="/create">
<label>Nome do arquivo</label><input name="filename" placeholder="faq.md">
<label>Título</label><input name="title" placeholder="FAQ geral" required>
<label>Tags opcionais, separadas por vírgula</label><input name="tags" placeholder="faq, atendimento">
<button type="submit">Criar Markdown</button>
</form>
<hr>
<h2>Enviar arquivo</h2>
<form method="post" action="/upload" enctype="multipart/form-data">
<label>Arquivo Markdown ou TXT</label><input type="file" name="file" accept=".md,.txt" required>
<label>Título opcional</label><input name="title" placeholder="Título do documento">
<label>Tags opcionais, separadas por vírgula</label><input name="tags" placeholder="faq, atendimento">
<button type="submit">Enviar e salvar</button>
</form>
<p class="muted">TXT é normalizado para Markdown. Limite: {MAX_SOURCE_BYTES // 1024 // 1024} MiB.</p>
</section>
</div>
<section class="card"><h2>Fontes</h2><table><thead><tr><th>Arquivo</th><th>Tamanho</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table></section>
"""
        return HTMLResponse(_layout("Base de conhecimento", body))

    @app.post("/create")
    async def create(
        filename: str = Form(""),
        title: str = Form(...),
        tags: str = Form(""),
    ):
        try:
            path = create_markdown_source(
                resolved.sources,
                filename=filename,
                title=title,
                tags=tags,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        relative = path.relative_to(resolved.sources).as_posix()
        return RedirectResponse(url=f"/edit/{quote(relative)}", status_code=303)

    @app.post("/upload")
    async def upload(
        file: Annotated[UploadFile, File()],
        title: Annotated[str, Form()] = "",
        tags: Annotated[str, Form()] = "",
    ):
        raw = await file.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            raise HTTPException(status_code=413, detail="Arquivo excede 2 MiB")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Arquivo deve estar em UTF-8") from exc
        try:
            name, normalized = normalize_uploaded_text(
                original_name=file.filename or "documento.md",
                raw_text=text,
                title=title,
                tags=tags,
            )
            atomic_write_source(resolved.sources, name, normalized)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(url=f"/edit/{quote(name)}", status_code=303)

    @app.get("/edit/{relative_path:path}", response_class=HTMLResponse)
    async def edit(relative_path: str):
        try:
            content = read_source(resolved.sources, relative_path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="Fonte não encontrada") from exc
        body = f"""
<section class="card">
<h2>{html.escape(relative_path)}</h2>
<form method="post" action="/save">
<input type="hidden" name="relative_path" value="{html.escape(relative_path, quote=True)}">
<textarea name="content" required>{html.escape(content)}</textarea>
<button type="submit">Salvar</button>
</form>
<p class="muted">Salvar não reindexa automaticamente. Isso permite revisar várias fontes antes de reconstruir o índice.</p>
<form method="get" action="/delete/{quote(relative_path)}">
<button type="submit">Excluir documento</button>
</form>
</section>
"""
        return HTMLResponse(_layout("Editar fonte", body))

    @app.post("/save")
    async def save(relative_path: str = Form(...), content: str = Form(...)):
        try:
            atomic_write_source(resolved.sources, relative_path, content.rstrip() + "\n")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(url=f"/edit/{quote(relative_path)}", status_code=303)

    @app.get("/delete/{relative_path:path}", response_class=HTMLResponse)
    async def confirm_delete(relative_path: str):
        try:
            read_source(resolved.sources, relative_path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="Fonte não encontrada") from exc
        body = f"""
<section class="card">
<h2 class="warn">Confirmar exclusão</h2>
<p>Deseja realmente excluir <strong>{html.escape(relative_path)}</strong>?</p>
<p class="muted">O índice ficará desatualizado até a próxima reindexação.</p>
<form method="post" action="/delete">
<input type="hidden" name="relative_path" value="{html.escape(relative_path, quote=True)}">
<button type="submit">Confirmar exclusão</button>
</form>
<p><a href="/edit/{quote(relative_path)}">Cancelar</a></p>
</section>
"""
        return HTMLResponse(_layout("Excluir fonte", body))

    @app.post("/delete")
    async def remove(relative_path: str = Form(...)):
        try:
            delete_source(resolved.sources, relative_path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="Fonte não encontrada") from exc
        return RedirectResponse(url="/", status_code=303)

    @app.post("/reindex", response_class=HTMLResponse)
    async def reindex():
        stats = build_index(resolved.sources, resolved.index)
        body = f"""
<section class="card">
<h2 class="ok">Índice atualizado</h2>
<p>Documentos: <strong>{stats['documents']}</strong></p>
<p>Chunks: <strong>{stats['chunks']}</strong></p>
<p><a href="/">Voltar para a base</a></p>
</section>
"""
        return HTMLResponse(_layout("Índice atualizado", body))

    return app
