"""FAQ supervisionado e áudio diagnóstico restritos ao administrador local."""
from __future__ import annotations

import html
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from orelhao.hardware import audio_diagnostics, faq
from orelhao.services.knowledge.paths import default_knowledge_paths

from .audit_routes import _admin_only

router = APIRouter(prefix="/audit")
Auth = Annotated[None, Depends(_admin_only)]
NO_CACHE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def _origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="Origem da solicitação não autorizada")


def _h(value: object) -> str:
    return html.escape(str(value), quote=True)


@router.get("/faq", response_class=HTMLResponse)
async def faq_dashboard(_auth: Auth) -> HTMLResponse:
    from .app import _layout

    groups = await run_in_threadpool(faq.candidates)
    existing = await run_in_threadpool(faq.reviews)
    saved = {(r["label"], r["topic"]): r for r in existing}
    sections: list[str] = []
    for item in groups[:50]:
        row = saved.get((item["label"], item["topic"]), {})
        state = row.get("status", "unreviewed")
        if state == "published":
            sections.append(
                f"<section class='card'><h3>{_h(item['label'])}</h3>"
                f"<p>Categoria: {_h(item['topic'])} · Ocorrências sem resposta: {item['count']}</p>"
                f"<p class='ok'>Publicado: {_h(row.get('published_path', ''))}</p></section>"
            )
            continue
        question = _h(row.get("question", ""))
        answer = _h(row.get("answer", ""))
        source = _h(row.get("source", ""))
        sections.append(
            f"<section class='card'><h3>{_h(item['label'])}</h3>"
            f"<p>Categoria: {_h(item['topic'])} · Sem resposta: {item['count']}"
            f" · Estado: {_h(state)}</p>"
            "<p class='muted'>O agrupamento é aproximado. Confira o tema e escreva "
            "uma pergunta específica; não presuma que todas as falas sejam idênticas.</p>"
            "<form method='post' action='/audit/faq/review'>"
            f"<input type='hidden' name='label' value='{_h(item['label'])}'>"
            f"<input type='hidden' name='topic' value='{_h(item['topic'])}'>"
            "<label>Pergunta revisada pelo gestor</label>"
            f"<input name='question' required maxlength='240' value='{question}'>"
            "<label>Resposta aprovada (deve ser factual)</label>"
            f"<textarea name='answer' required maxlength='1600' style='min-height:90px'>{answer}</textarea>"
            "<label>URL HTTPS da fonte institucional vigente</label>"
            f"<input name='source' type='url' required maxlength='700' value='{source}'>"
            "<button type='submit'>Salvar revisão, sem publicar</button></form>"
        )
        if row.get("id") is not None:
            sections.append(
                f"<form method='post' action='/audit/faq/publish/{row['id']}'>"
                "<label><input type='checkbox' name='confirmed' value='1' required "
                "style='width:auto'> Conferi fonte, atualidade e exatidão; autorizo publicar.</label>"
                "<button type='submit'>Publicar na base e reindexar</button></form>"
            )
        sections.append("</section>")
    body = (
        "<section class='card'><h2>FAQ supervisionado</h2>"
        "<p>As pendências são derivadas exclusivamente de perguntas reconhecidas pelo STT "
        "que terminaram em abstenção RAG. Falhas de microfone não viram FAQ.</p>"
        "<p>A ferramenta não gera respostas automaticamente. A publicação exige revisão "
        "humana, fonte HTTPS e reconstrução validada do índice. A base continua offline.</p>"
        "</section>"
        + ("".join(sections) if sections else
           "<section class='card'><p>Sem pendências de conhecimento no período. "
           "Para registrar, habilite a auditoria local (sem armazenar transcrições).</p></section>")
    )
    return HTMLResponse(_layout("FAQ supervisionado", body), headers=NO_CACHE)


@router.post("/faq/review")
async def faq_save(
    request: Request, _auth: Auth,
    label: str = Form(...), topic: str = Form(...), question: str = Form(...),
    answer: str = Form(...), source: str = Form(...),
) -> RedirectResponse:
    _origin(request)
    try:
        await run_in_threadpool(
            faq.save_review, label=label, topic=topic, question=question,
            answer=answer, source=source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RedirectResponse("/audit/faq", status_code=303, headers=NO_CACHE)


@router.post("/faq/publish/{review_id}")
async def faq_publish(
    request: Request, review_id: int, _auth: Auth, confirmed: str = Form(...),
) -> RedirectResponse:
    _origin(request)
    if confirmed != "1":
        raise HTTPException(status_code=422, detail="Confirmação obrigatória")
    try:
        await run_in_threadpool(faq.publish_review, review_id, default_knowledge_paths())
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RedirectResponse("/audit/faq", status_code=303, headers=NO_CACHE)


@router.get("/audio", response_class=HTMLResponse)
async def audio_dashboard(_auth: Auth) -> HTMLResponse:
    from .app import _layout

    active = audio_diagnostics.enabled()
    armed = await run_in_threadpool(audio_diagnostics.arm_status)
    samples = await run_in_threadpool(audio_diagnostics.list_samples)
    lines = []
    for item in samples:
        lines.append(
            f"<tr><td>{_h(item['captured_at'])}</td><td>{item['turn']}</td>"
            f"<td>{_h(item['stt_status'])}</td>"
            f"<td>{item['duration_seconds']} s</td>"
            f"<td>{_h(item['peak_rms'])}</td>"
            f"<td><audio controls preload='none' src='/audit/audio/sample/{item['id']}'></audio></td></tr>"
        )
    body = (
        "<section class='card'><h2>Diagnóstico de microfone</h2>"
        "<p>Desligado por padrão. Cada autorização cobre a próxima sessão e permite "
        "até duas amostras WAV. Sem retenção de transcrição ou geração de resposta.</p>"
        f"<p><strong>Coleta:</strong> {'habilitada' if active else 'desabilitada no servidor'}"
        f" · <strong>Próxima sessão:</strong> {'armada' if armed else 'não armada'}</p>"
        "<form method='post' action='/audit/audio/arm'>"
        "<label><input name='confirmed' type='checkbox' value='1' required style='width:auto'> "
        "Declaro que o visitante foi informado e autorizou a gravação para diagnóstico.</label>"
        f"<button type='submit' {'disabled' if not active else ''}>Ativar somente próxima sessão (5 min)</button>"
        "</form><form method='post' action='/audit/audio/disarm'>"
        "<button type='submit'>Cancelar ativação pendente</button></form>"
        "<p class='muted'>Somente o administrador local tem acesso. "
        "Armazenamento privado; retenção padrão de 7 dias, máximo de 14.</p></section>"
        "<section class='card'><h3>Amostras disponíveis</h3>"
        "<table><thead><tr><th>Data UTC</th><th>Turno</th><th>STT</th>"
        "<th>Duração</th><th>Pico RMS</th><th>Ouvir</th></tr></thead><tbody>"
        + ("".join(lines) if lines else "<tr><td colspan='6'>Nenhuma amostra.</td></tr>")
        + "</tbody></table></section>"
    )
    return HTMLResponse(_layout("Diagnóstico de áudio", body), headers=NO_CACHE)


@router.post("/audio/arm")
async def audio_arm(
    request: Request, _auth: Auth, confirmed: str = Form(...),
) -> RedirectResponse:
    _origin(request)
    try:
        await run_in_threadpool(
            audio_diagnostics.arm_next_session, visitor_informed=(confirmed == "1"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RedirectResponse("/audit/audio", status_code=303, headers=NO_CACHE)


@router.post("/audio/disarm")
async def audio_disarm(request: Request, _auth: Auth) -> RedirectResponse:
    _origin(request)
    await run_in_threadpool(audio_diagnostics.disarm)
    return RedirectResponse("/audit/audio", status_code=303, headers=NO_CACHE)


@router.get("/audio/sample/{sample_id}")
async def audio_download(sample_id: str, _auth: Auth) -> FileResponse:
    path = await run_in_threadpool(audio_diagnostics.sample_path, sample_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Amostra não encontrada")
    return FileResponse(
        path, media_type="audio/wav", headers=NO_CACHE, filename=path.name,
    )
