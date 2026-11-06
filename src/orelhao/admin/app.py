from __future__ import annotations

import asyncio
import json
import os
import subprocess
import threading
from pathlib import Path
from time import perf_counter
from typing import Annotated
from urllib.parse import quote

from orelhao.config import AppConfig, load_config
from orelhao.hardware.live_monitor import snapshot as monitor_snapshot
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.resample import resample_pcm16, trim_silence_pcm16
from orelhao.runtime_paths import resolve_project_path
from orelhao.services.knowledge.index import build_index
from orelhao.services.knowledge.loader import load_documents
from orelhao.services.knowledge.observation import (
    LocalLLMAnswerGenerator,
    ObservationWorkbench,
    build_default_observation_workbench,
)
from orelhao.services.knowledge.paths import KnowledgePaths, default_knowledge_paths
from orelhao.services.llm.service import LLMService, LocalOpenAICompatibleLLMService
from orelhao.services.stt.service import FasterWhisperSTTService, STTService
from orelhao.services.tts.service import TTSService
from orelhao.services.tts.voice_catalog import (
    WorkbenchPiperVoices,
    validate_voice_id,
)

try:
    from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
    from fastapi.exceptions import HTTPException as _FastAPIHTTPException
    from fastapi.responses import (
        HTMLResponse,
        JSONResponse,
        RedirectResponse,
        Response,
        StreamingResponse,
    )
    from fastapi.staticfiles import StaticFiles
    from starlette.concurrency import run_in_threadpool
    from starlette.exceptions import HTTPException as StarletteHTTPException
except ImportError:  # pacote base continua utilizável sem o extra [admin]
    FastAPI = File = Form = HTTPException = Request = UploadFile = None
    HTMLResponse = JSONResponse = RedirectResponse = Response = StreamingResponse = None
    run_in_threadpool = None
    StaticFiles = StarletteHTTPException = _FastAPIHTTPException = None

from . import knowledge_view, workbench_view
from .live_view import monitor_page
from .overview_view import overview_page
from .source_manager import (
    MAX_SOURCE_BYTES,
    atomic_write_source,
    create_markdown_source,
    delete_source,
    list_sources,
    normalize_uploaded_text,
    read_source,
)
from .system_metrics import SystemMetricsCollector
from .system_view import system_page
from .ui import STATIC_DIR, alert, render_page


def _require_web() -> None:
    if FastAPI is None:
        raise RuntimeError(
            "Interface web não instalada. Execute: pip install -e '.[admin]'"
        )


_render_evidence_span = workbench_view.render_evidence_span


def _layout(title: str, body: str) -> str:
    """Compatibilidade: páginas antigas passam a usar o shell novo."""
    return render_page(title, body)


def _error_page(status_code: int, detail: str) -> str:
    titles = {401: "Autenticação necessária", 403: "Acesso negado", 404: "Página não encontrada",
              413: "Arquivo muito grande", 503: "Serviço indisponível"}
    title = titles.get(status_code, "Não foi possível concluir")
    body = (alert(f"{detail}", "bad", title=f"Erro {status_code}.")
            + "<div class='btn-row'><a class='btn btn-primary' href='javascript:history.back()'>"
              "Voltar e corrigir</a><a class='btn' href='/overview'>Ir para a visão geral</a></div>"
            + "<p class='note section-gap'>Ao voltar, o navegador normalmente mantém o que "
              "foi digitado no formulário.</p>")
    return render_page(title, body)


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


def create_admin_app(
    paths: KnowledgePaths | None = None,
    *,
    workbench: ObservationWorkbench | None = None,
    stt: STTService | None = None,
    tts: TTSService | None = None,
    llm: LLMService | None = None,
    tts_voices: dict[str, TTSService] | None = None,
):
    _require_web()
    resolved = paths or default_knowledge_paths()
    app = FastAPI(title="Orelhão IA Knowledge Admin", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(StarletteHTTPException)
    async def html_errors(request: Request, exc: StarletteHTTPException) -> Response:
        # Navegação do navegador (Accept: text/html) recebe página legível; fetch e
        # clientes de API continuam recebendo JSON com "detail".
        headers = getattr(exc, "headers", None)
        if "text/html" in request.headers.get("accept", ""):
            return HTMLResponse(_error_page(exc.status_code, str(exc.detail)),
                                status_code=exc.status_code, headers=headers)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                            headers=headers)
    active_workbench = workbench
    active_stt = stt
    active_llm = llm
    voice_catalog: WorkbenchPiperVoices | None = None
    stt_preparation_lock = threading.Lock()
    system_collector = SystemMetricsCollector()
    app.state.stt_preparation = {"status": "idle", "elapsed_ms": None, "error": None}

    def app_config() -> AppConfig:
        path = os.getenv("ORELHAO_CONFIG", "config/development.yaml")
        return load_config(resolve_project_path(path))

    def get_workbench() -> ObservationWorkbench:
        nonlocal active_workbench
        if active_workbench is None:
            active_workbench = build_default_observation_workbench(
                resolved.index,
                answer_generator=LocalLLMAnswerGenerator(get_llm()),
            )
        return active_workbench

    def get_llm() -> LLMService:
        nonlocal active_llm
        if active_llm is None:
            active_llm = LocalOpenAICompatibleLLMService(app_config().llm)
        return active_llm

    def get_stt() -> STTService:
        nonlocal active_stt
        if active_stt is None:
            active_stt = FasterWhisperSTTService(app_config().stt)
        return active_stt

    def get_tts(voice: str = "cadu") -> TTSService:
        nonlocal voice_catalog
        validate_voice_id(voice)
        if voice_catalog is None:
            voice_catalog = WorkbenchPiperVoices(
                app_config().tts,
                injected={"cadu": tts, **(tts_voices or {})} if tts is not None
                else tts_voices,
            )
        return voice_catalog.get(voice)

    def prepare_stt() -> None:
        with stt_preparation_lock:
            if app.state.stt_preparation["status"] != "idle":
                return
            app.state.stt_preparation = {
                "status": "loading",
                "elapsed_ms": None,
                "error": None,
            }

        def load() -> None:
            started = perf_counter()
            try:
                service = get_stt()
                preparer = getattr(service, "prepare", None)
                if callable(preparer):
                    preparer()
            except RuntimeError as exc:
                app.state.stt_preparation = {
                    "status": "error",
                    "elapsed_ms": (perf_counter() - started) * 1000.0,
                    "error": str(exc),
                }
                return
            app.state.stt_preparation = {
                "status": "ready",
                "elapsed_ms": (perf_counter() - started) * 1000.0,
                "error": None,
            }

        threading.Thread(target=load, name="orelhao-stt-prepare", daemon=True).start()

    @app.get("/system", response_class=HTMLResponse)
    async def system_home():
        return HTMLResponse(
            system_page(),
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/system/state", response_class=JSONResponse)
    async def system_state():
        # systemctl e /proc são leitura local; não bloquear o event loop ASGI.
        data = await run_in_threadpool(system_collector.snapshot)
        return JSONResponse(
            data, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/monitor", response_class=HTMLResponse)
    async def monitor_home():
        return HTMLResponse(monitor_page(), headers={"Cache-Control": "no-store"})

    @app.get("/monitor/state", response_class=JSONResponse)
    async def monitor_state():
        return JSONResponse(monitor_snapshot(), headers={"Cache-Control": "no-store"})

    @app.get("/monitor/events")
    async def monitor_events(request: Request):
        async def stream():
            last_payload = None
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 15.0
            # Encerrar fluxos periodicamente evita bloquear reinícios do Uvicorn.
            while loop.time() < deadline and not await request.is_disconnected():
                payload = json.dumps(monitor_snapshot(), ensure_ascii=False,
                                     separators=(",", ":"))
                if payload != last_payload:
                    yield f"data: {payload}\n\n"
                    last_payload = payload
                await asyncio.sleep(0.5)
            yield "retry: 500\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store",
                                          "X-Accel-Buffering": "no",
                                          "X-Content-Type-Options": "nosniff"})

    def knowledge_state() -> tuple[list, dict[str, str], dict[str, object], bool]:
        files = list_sources(resolved.sources)
        manifest = _manifest(resolved.index)
        indexed = _indexed_sources(manifest)
        current_indexable = _current_indexable_sources(resolved.sources)
        statuses = {
            item.relative_path: _source_status(
                item.relative_path, item.sha256, indexed, current_indexable)
            for item in files
        }
        return files, statuses, manifest, _index_is_stale(current_indexable, manifest)

    @app.get("/overview", response_class=HTMLResponse)
    async def overview():
        files, _statuses, manifest, stale = await run_in_threadpool(knowledge_state)
        return HTMLResponse(
            overview_page(index_ready=bool(manifest), index_stale=stale, sources=len(files)),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/", response_class=HTMLResponse)
    async def home():
        files, statuses, manifest, stale = knowledge_state()
        return HTMLResponse(knowledge_view.sources_page(files, statuses, manifest, stale=stale))

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
    async def edit(relative_path: str, saved: bool = False):
        try:
            content = read_source(resolved.sources, relative_path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="Fonte não encontrada") from exc
        return HTMLResponse(knowledge_view.edit_page(relative_path, content, saved=saved))

    @app.post("/save")
    async def save(relative_path: str = Form(...), content: str = Form(...)):
        try:
            atomic_write_source(resolved.sources, relative_path, content.rstrip() + "\n")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(url=f"/edit/{quote(relative_path)}?saved=1", status_code=303)

    @app.get("/delete/{relative_path:path}", response_class=HTMLResponse)
    async def confirm_delete(relative_path: str):
        try:
            read_source(resolved.sources, relative_path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="Fonte não encontrada") from exc
        return HTMLResponse(knowledge_view.confirm_delete_page(relative_path))

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
        return HTMLResponse(knowledge_view.reindex_page(stats))

    @app.get("/workbench", response_class=HTMLResponse)
    async def workbench_home():
        prepare_stt()
        return HTMLResponse(workbench_view.home_page())

    @app.get("/workbench/stt-status", response_class=JSONResponse)
    async def stt_status():
        return JSONResponse(app.state.stt_preparation)

    @app.get("/workbench/llm-status", response_class=JSONResponse)
    async def llm_status():
        if active_workbench is not None and active_llm is None:
            return JSONResponse(
                {"available": True, "detail": "gerador injetado para teste"}
            )
        service = get_llm()
        checker = getattr(service, "health", None)
        if not callable(checker):
            return JSONResponse({"available": True, "detail": "serviço injetado"})
        health = checker()
        return JSONResponse(
            {"available": health.available, "detail": health.detail}
        )

    @app.post("/workbench/run", response_class=HTMLResponse)
    async def run_workbench(
        question: str = Form(...), mode: str = Form("observe"),
        voice: str = Form("cadu"),
    ):
        try:
            validate_voice_id(voice)
            observation = get_workbench().observe(question, mode=mode)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return HTMLResponse(workbench_view.result_page(observation, voice))

    @app.post("/workbench/rate", response_class=HTMLResponse)
    async def rate_workbench(
        observation_id: str = Form(...),
        rating: str = Form(...),
        grounding_status: str = Form(...),
    ):
        try:
            diagnostic = get_workbench().log.append_rating(
                observation_id,
                rating,
                grounding_status=grounding_status,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        diagnostic_text = {
            "possible_false_positive": "Possível falso positivo do grounding",
            "possible_false_negative": "Possível falso negativo do grounding",
            "aligned": "Avaliação humana alinhada à decisão do grounding",
        }.get(diagnostic, "Avaliação registrada")
        return HTMLResponse(workbench_view.rating_page(diagnostic_text))

    @app.post("/workbench/transcribe", response_class=JSONResponse)
    async def transcribe_workbench(file: Annotated[UploadFile, File()]):
        raw = await file.read(20 * 1024 * 1024 + 1)
        if len(raw) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Áudio excede 20 MiB")
        try:
            started = perf_counter()
            audio = PCM16Audio.from_wav_bytes(raw)
            if audio.channels != 1:
                raise ValueError("Áudio deve ser mono")
            if audio.duration_seconds > 15.0:
                raise ValueError("Gravação deve ter no máximo 15 segundos")
            audio = resample_pcm16(audio, 16_000)
            audio = trim_silence_pcm16(audio)
            if audio.duration_seconds < 0.25:
                raise ValueError("Nenhuma fala foi detectada")
            transcription = get_stt().transcribe(audio)
            if not transcription.text.strip():
                raise ValueError("O STT não reconheceu fala na gravação")
        except (RuntimeError, ValueError, EOFError) as exc:
            raise HTTPException(
                status_code=422,
                detail="Envie WAV PCM16 mono 16 kHz",
            ) from exc
        return JSONResponse(
            {
                "text": transcription.text,
                "elapsed_ms": transcription.elapsed_seconds * 1000.0,
                "total_ms": (perf_counter() - started) * 1000.0,
                "audio_seconds": transcription.audio_seconds,
            }
        )

    @app.get("/workbench/tts-status", response_class=JSONResponse)
    async def tts_status(voice: str = "cadu"):
        try:
            service = get_tts(voice)
            check = getattr(service, "validate", None)
            if callable(check):
                check()
            return JSONResponse({
                "available": True, "voice": voice,
                "detail": f"Piper {voice.capitalize()} pronto para síntese",
            })
        except (RuntimeError, ValueError) as exc:
            return JSONResponse({"available": False, "voice": voice, "detail": str(exc)})

    @app.get("/workbench/voice-preview", response_class=Response)
    async def preview_voice(voice: str = "cadu"):
        # Texto fixo: esta rota nunca sintetiza texto livre do cliente.
        try:
            service = get_tts(voice)
            audio = await run_in_threadpool(
                service.synthesize,
                "Olá! Eu sou o Lumi, assistente virtual do Senac Piauí.",
            )
        except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(
            content=audio.to_wav_bytes(),
            media_type="audio/wav",
            headers={
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "X-Orelhao-Voice": voice,
            },
        )

    @app.get("/workbench/speech/{observation_id}", response_class=Response)
    async def synthesize_workbench(observation_id: str, voice: str = "cadu"):
        try:
            service = get_tts(voice)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        answer = get_workbench().log.presented_answer_for(observation_id)
        if answer is None:
            raise HTTPException(status_code=404, detail="Observação não encontrada")
        try:
            audio = await run_in_threadpool(service.synthesize, answer)
        except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(status_code=422, detail=f"Falha de síntese de voz: {exc}") from exc
        return Response(
            content=audio.to_wav_bytes(),
            media_type="audio/wav",
            headers={
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "X-Orelhao-Voice": voice,
            },
        )

    from .audit_routes import router as audit_router
    from .learning_routes import router as learning_router
    app.include_router(audit_router)
    app.include_router(learning_router)
    return app
