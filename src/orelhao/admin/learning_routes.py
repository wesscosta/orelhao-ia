"""FAQ supervisionado e áudio diagnóstico restritos ao administrador local."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from orelhao.hardware import audio_diagnostics, faq
from orelhao.services.knowledge.paths import default_knowledge_paths

from .audit_routes import _admin_only
from .learning_view import audio_page, faq_link, faq_page

router = APIRouter(prefix="/audit")
Auth = Annotated[None, Depends(_admin_only)]
NO_CACHE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def _origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="Origem da solicitação não autorizada")


def _html(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(content, status_code=status_code, headers=NO_CACHE)


async def _faq_view(
    *, selected: tuple[str, str] | None = None, values: dict[str, str] | None = None,
    error: str | None = None, notice: str | None = None, status_code: int = 200,
) -> HTMLResponse:
    groups = await run_in_threadpool(faq.candidates)
    existing = await run_in_threadpool(faq.reviews)
    return _html(faq_page(groups, existing, selected=selected, values=values,
                          error=error, notice=notice), status_code)


@router.get("/faq", response_class=HTMLResponse)
async def faq_dashboard(
    _auth: Auth, topic: str | None = None, label: str | None = None,
    salvo: str | None = None, publicado: str | None = None,
) -> HTMLResponse:
    selected = (label, topic) if label and topic else None
    notice = None
    if salvo:
        notice = "Rascunho salvo. Nada foi publicado; confira e publique quando estiver pronto."
    elif publicado:
        notice = "FAQ publicado e índice reconstruído. O Lumi já consulta a nova resposta."
    return await _faq_view(selected=selected, notice=notice)


@router.post("/faq/review", response_model=None)
async def faq_save(
    request: Request, _auth: Auth,
    label: str = Form(...), topic: str = Form(...), question: str = Form(...),
    answer: str = Form(...), source: str = Form(...),
) -> RedirectResponse | HTMLResponse:
    _origin(request)
    try:
        await run_in_threadpool(
            faq.save_review, label=label, topic=topic, question=question,
            answer=answer, source=source,
        )
    except ValueError as exc:
        # Reapresenta o formulário com o texto digitado para correção sem perda.
        return await _faq_view(
            selected=(label, topic), error=f"{exc}. Revise os campos e salve novamente.",
            values={"question": question, "answer": answer, "source": source},
            status_code=422,
        )
    target = faq_link({"label": label, "topic": topic}, salvo="1")
    return RedirectResponse(target, status_code=303, headers=NO_CACHE)


@router.post("/faq/publish/{review_id}", response_model=None)
async def faq_publish(
    request: Request, review_id: int, _auth: Auth, confirmed: str = Form(...),
) -> RedirectResponse | HTMLResponse:
    _origin(request)
    if confirmed != "1":
        raise HTTPException(status_code=422, detail="Confirmação obrigatória")
    existing = await run_in_threadpool(faq.reviews)
    row = next((r for r in existing if r.get("id") == review_id), None)
    selected = (row["label"], row["topic"]) if row else None
    try:
        await run_in_threadpool(faq.publish_review, review_id, default_knowledge_paths())
    except (ValueError, OSError, RuntimeError) as exc:
        # publish_review preserva o índice anterior e o rascunho quando falha.
        return await _faq_view(
            selected=selected, status_code=422,
            error=f"Publicação cancelada: {exc}. O rascunho e o índice anterior foram "
                  "preservados; corrija a causa e tente novamente.",
        )
    if row is None:
        return RedirectResponse("/audit/faq", status_code=303, headers=NO_CACHE)
    return RedirectResponse(faq_link(row, publicado="1"), status_code=303, headers=NO_CACHE)


async def _audio_view(
    *, error: str | None = None, notice: str | None = None, status_code: int = 200,
) -> HTMLResponse:
    armed = await run_in_threadpool(audio_diagnostics.arm_status)
    samples = await run_in_threadpool(audio_diagnostics.list_samples)
    return _html(audio_page(
        active=audio_diagnostics.enabled(), armed=armed, samples=samples,
        retention_days=audio_diagnostics._retention_days(), error=error, notice=notice,
    ), status_code)


@router.get("/audio", response_class=HTMLResponse)
async def audio_dashboard(
    _auth: Auth, autorizado: str | None = None, cancelado: str | None = None,
) -> HTMLResponse:
    notice = None
    if autorizado:
        notice = "Próxima sessão autorizada por 5 minutos. Faça a ligação de teste agora."
    elif cancelado:
        notice = "Autorização pendente cancelada. Nenhuma ligação será gravada."
    return await _audio_view(notice=notice)


@router.post("/audio/arm", response_model=None)
async def audio_arm(
    request: Request, _auth: Auth, confirmed: str = Form(...),
) -> RedirectResponse | HTMLResponse:
    _origin(request)
    try:
        await run_in_threadpool(
            audio_diagnostics.arm_next_session, visitor_informed=(confirmed == "1"),
        )
    except ValueError as exc:
        return await _audio_view(error=str(exc), status_code=422)
    return RedirectResponse("/audit/audio?autorizado=1", status_code=303, headers=NO_CACHE)


@router.post("/audio/disarm")
async def audio_disarm(request: Request, _auth: Auth) -> RedirectResponse:
    _origin(request)
    await run_in_threadpool(audio_diagnostics.disarm)
    return RedirectResponse("/audit/audio?cancelado=1", status_code=303, headers=NO_CACHE)


@router.get("/audio/sample/{sample_id}")
async def audio_download(sample_id: str, _auth: Auth) -> FileResponse:
    path = await run_in_threadpool(audio_diagnostics.sample_path, sample_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Amostra não encontrada")
    return FileResponse(
        path, media_type="audio/wav", headers=NO_CACHE, filename=path.name,
    )
