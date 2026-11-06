"""Telas do FAQ supervisionado e do diagnóstico de áudio (somente administrador local)."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from .ui import Tone, alert, badge, e, empty_state, icon, panel, render_page, stat

FAQ_STATES: dict[str, tuple[str, Tone]] = {
    "unreviewed": ("Sem revisão", "warn"),
    "draft": ("Rascunho salvo", "info"),
    "published": ("Publicada", "ok"),
}


def when(value: object) -> str:
    """ISO 8601 em UTC para leitura humana; valores inválidos aparecem como estão."""
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value or "—")
    return moment.strftime("%d/%m/%Y %H:%M UTC")


def faq_link(item: Mapping[str, Any], **extra: str) -> str:
    query = urlencode({"topic": item["topic"], "label": item["label"], **extra})
    return f"/audit/faq?{query}#revisao"


def _faq_table(groups: Sequence[Mapping[str, Any]], saved: Mapping[tuple[str, str], Mapping[str, Any]],
               selected: tuple[str, str] | None) -> str:
    if not groups:
        return empty_state(
            "Nenhuma pendência no período",
            "Pendências surgem quando uma pergunta reconhecida pelo STT termina em abstenção. "
            "Para registrá-las, a auditoria local precisa estar habilitada; ela não guarda "
            "transcrições.",
        )
    rows = []
    for item in groups:
        key = (item["label"], item["topic"])
        row = saved.get(key, {})
        state = str(row.get("status") or item.get("status") or "unreviewed")
        label, tone = FAQ_STATES.get(state, (state, "neutral"))
        published = (f"<br><small class='muted'>Publicado: {e(row.get('published_path', ''))}</small>"
                     if state == "published" else "")
        current = ' aria-current="true"' if key == selected else ""
        action = "Ver publicação" if state == "published" else (
            "Continuar revisão" if state == "draft" else "Revisar")
        rows.append(
            f"<tr{current}><th scope='row' class='wrap' style='font-weight:400'>{e(item['label'])}"
            f"<br><small class='muted'>{e(item['topic'])}</small></th>"
            f"<td class='num'>{int(item['count'])}</td>"
            f"<td>{badge(label, tone)}{published}</td>"
            f"<td>{e(when(item.get('last_seen')))}</td>"
            f"<td><a class='btn btn-small' href='{e(faq_link(item))}' "
            f"aria-label='{e(action)}: {e(item['label'])}'>{e(action)}</a></td></tr>"
        )
    return (
        "<div class='table-wrap' tabindex='0' role='region' aria-labelledby='pendencias-titulo'>"
        "<table><thead><tr><th scope='col'>Pergunta agrupada e assunto</th>"
        "<th scope='col' class='num'>Frequência</th><th scope='col'>Revisão</th>"
        "<th scope='col'>Última ocorrência</th><th scope='col'><span class='visually-hidden'>Ação</span></th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _review_panel(item: Mapping[str, Any] | None, row: Mapping[str, Any],
                  values: Mapping[str, str], error: str | None, notice: str | None) -> str:
    if item is None:
        return panel("Revisão", empty_state(
            "Selecione uma pendência",
            "Escolha Revisar em uma linha da tabela para escrever a pergunta, a resposta "
            "aprovada e a fonte institucional.",
        ), id="revisao", cls="review-panel")
    state = str(row.get("status") or item.get("status") or "unreviewed")
    label, tone = FAQ_STATES.get(state, (state, "neutral"))
    context = (
        "<div class='review-source'>"
        f"<p class='small muted'>Pergunta agrupada pela auditoria</p><p><strong>{e(item['label'])}</strong></p>"
        f"<p class='small muted' style='margin-top:var(--sp-2)'>Assunto {e(item['topic'])}; "
        f"{int(item['count'])} ocorrência(s) sem resposta; última em {e(when(item.get('last_seen')))}.</p></div>"
    )
    feedback = ""
    if notice:
        feedback += alert(notice, "ok", role="status")
    if error:
        feedback += alert(error, "bad", title="Não foi possível concluir.")
    if state == "published":
        return panel("Revisão", feedback + context + alert(
            f"Publicado: {row.get('published_path', '')}. FAQ publicado não pode ser editado "
            "por esta tela; para corrigir, edite a fonte em Conhecimento e reindexe.",
            "ok", role="status") + "<p><a href='/'>Abrir fontes e índice</a></p>",
            id="revisao", aside=badge(label, tone), cls="review-panel")
    has_draft = row.get("id") is not None and state == "draft"
    steps = (
        "<ol class='steps small'>"
        f"<li{' aria-current=\"step\"' if not has_draft else ''}>Escreva a pergunta e a resposta factual com fonte HTTPS.</li>"
        "<li>Salve como rascunho. Nada é publicado nesta etapa.</li>"
        f"<li{' aria-current=\"step\"' if has_draft else ''}>Confira e publique; o índice é reconstruído e validado.</li></ol>"
    )
    invalid = ' aria-invalid="true"' if error else ""
    form = f"""
<form method="post" action="/audit/faq/review" data-busy="Salvando…">
  <input type="hidden" name="label" value="{e(item['label'])}">
  <input type="hidden" name="topic" value="{e(item['topic'])}">
  <div class="field"><label for="faq-question">Pergunta revisada</label>
    <input id="faq-question" name="question" required minlength="10" maxlength="240"
      value="{e(values.get('question', ''))}" aria-describedby="faq-question-hint"{invalid}>
    <span class="field-hint" id="faq-question-hint">Uma linha, 10 a 240 caracteres. O agrupamento é
    aproximado: escreva uma pergunta específica.</span></div>
  <div class="field"><label for="faq-answer">Resposta aprovada</label>
    <textarea id="faq-answer" name="answer" required minlength="10" maxlength="1600" rows="6"
      aria-describedby="faq-answer-hint"{invalid}>{e(values.get('answer', ''))}</textarea>
    <span class="field-hint" id="faq-answer-hint">Somente fatos confirmados na fonte; até 1.600 caracteres.</span></div>
  <div class="field"><label for="faq-source">Fonte institucional vigente</label>
    <input id="faq-source" name="source" type="url" required maxlength="700" inputmode="url"
      spellcheck="false" placeholder="https://" value="{e(values.get('source', ''))}"
      aria-describedby="faq-source-hint"{invalid}>
    <span class="field-hint" id="faq-source-hint">Endereço HTTPS completo da página oficial consultada.</span></div>
  <button class="btn btn-primary" type="submit">Salvar rascunho</button>
</form>"""
    publish = ""
    if has_draft:
        publish = f"""
<hr class="divider">
<form method="post" action="/audit/faq/publish/{int(row['id'])}" data-busy="Publicando e reindexando…">
  <h3 style="margin-bottom:var(--sp-2)">Publicar na base</h3>
  <p class="small muted">Publica a versão salva em {e(when(row.get('updated_at')))}. Alterações
  não salvas acima não são publicadas. Se a reindexação falhar, o índice anterior e o rascunho
  são preservados.</p>
  <label class="check"><input type="checkbox" name="confirmed" value="1" required>
    <span>Conferi fonte, atualidade e exatidão; autorizo publicar.</span></label>
  <div class="btn-row"><button class="btn btn-primary" type="submit">Publicar na base e reindexar</button></div>
</form>"""
    return panel("Revisão", feedback + context + steps + form + publish, id="revisao",
                 aside=badge(label, tone), cls="review-panel")


def faq_page(
    groups: Sequence[Mapping[str, Any]],
    existing: Sequence[Mapping[str, Any]],
    *,
    selected: tuple[str, str] | None = None,
    values: Mapping[str, str] | None = None,
    error: str | None = None,
    notice: str | None = None,
) -> str:
    saved = {(r["label"], r["topic"]): r for r in existing}
    shown = list(groups[:50])
    item = next((g for g in shown if (g["label"], g["topic"]) == selected), None)
    if item is None and selected and (error or values is not None or selected in saved):
        # Pendência fora da janela exibida: mantém o painel para não perder o contexto.
        item = {"label": selected[0], "topic": selected[1], "count": 0, "last_seen": None}
    row = saved.get(selected, {}) if selected else {}
    form_values = values if values is not None else {
        k: str(row.get(k, "")) for k in ("question", "answer", "source")
    }
    states = [str(saved.get((g["label"], g["topic"]), {}).get("status") or g.get("status")
                  or "unreviewed") for g in shown]
    stats = (
        "<div class='stats'>"
        + stat("Sem revisão", str(states.count("unreviewed")), tone="warn" if "unreviewed" in states else "neutral")
        + stat("Rascunhos aguardando publicação", str(states.count("draft")))
        + stat("Publicadas", str(states.count("published")))
        + "</div>"
    )
    intro = alert(
        "Pendências vêm somente de perguntas reconhecidas pelo STT que terminaram em abstenção "
        "do RAG; falhas de microfone não viram FAQ. Nenhuma resposta é gerada automaticamente: "
        "a publicação exige revisão humana, fonte HTTPS e reindexação validada.",
        "info", title="Como funciona.")
    body = (
        intro + stats
        + "<div class='grid-split grid-wide-first section-gap'>"
        + panel("Pendências dos últimos 30 dias", _faq_table(shown, saved, selected), id="pendencias")
        + _review_panel(item, row, form_values, error, notice)
        + "</div>"
    )
    return render_page(
        "FAQ supervisionado", body, active="faq", section="Conhecimento",
        lede="Transforme perguntas que o Lumi não soube responder em respostas revisadas, "
             "com fonte oficial, publicadas por decisão explícita.",
    )


def _signal(item: Mapping[str, Any]) -> str:
    def value(name: str) -> float | None:
        raw = item.get(name)
        return float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None

    peak, noise, threshold = value("peak_rms"), value("noise_floor"), value("threshold")
    present = [v for v in (peak, noise, threshold) if v is not None]
    if not present or max(present) <= 0:
        return "<span class='muted'>Sem medição</span>"
    scale = max(present) * 1.25

    def pct(v: float) -> str:
        return f"{max(0.0, min(100.0, v / scale * 100)):.1f}%"

    fmt = {k: (f"{v:.4f}" if v is not None else "—")
           for k, v in (("peak", peak), ("noise", noise), ("threshold", threshold))}
    verdict = ""
    if peak is not None and threshold is not None:
        verdict = "; pico acima do limiar" if peak >= threshold else "; pico abaixo do limiar"
    label = (f"Pico RMS {fmt['peak']}, piso de ruído {fmt['noise']}, "
             f"limiar {fmt['threshold']}{verdict}")
    marks = ""
    if noise is not None:
        marks += f"<span class='signal-mark signal-noise' style='left:{pct(noise)}'></span>"
    if threshold is not None:
        marks += f"<span class='signal-mark signal-threshold' style='left:{pct(threshold)}'></span>"
    width = pct(peak) if peak is not None else "0"
    return (f"<div class='signal' role='img' aria-label='{e(label)}'>"
            f"<span class='signal-peak' style='width:{width}'></span>{marks}</div>"
            f"<small class='muted'>pico {fmt['peak']}; ruído {fmt['noise']}; limiar {fmt['threshold']}</small>")


def audio_page(
    *, active: bool, armed: bool, samples: Sequence[Mapping[str, Any]], retention_days: int,
    error: str | None = None, notice: str | None = None,
) -> str:
    feedback = (alert(notice, "ok", role="status") if notice else "") + (
        alert(error, "bad", title="Não foi possível concluir.") if error else "")
    status = f"""
<ul class="status-list" aria-label="Estado da coleta diagnóstica">
  <li class="status-item"><h2>{icon("i-mic")}Coleta no servidor</h2>
    {badge("Habilitada", "info") if active else badge("Desabilitada", "neutral")}
    <p>{"Pode ser autorizada para a próxima sessão." if active else
        "Desligada por padrão. Habilitação exige ORELHAO_AUDIO_DIAGNOSTICS_ENABLED=1 no serviço."}</p></li>
  <li class="status-item"><h2>{icon("i-phone")}Próxima sessão</h2>
    {badge("Autorizada", "live") if armed else badge("Não autorizada", "neutral")}
    <p>{"A próxima ligação grava até duas amostras. A autorização expira em 5 minutos." if armed else
        "Nenhuma ligação será gravada."}</p></li>
  <li class="status-item"><h2>{icon("i-server")}Amostras retidas</h2>
    <strong style="font-size:var(--fs-xl)">{len(samples)}</strong>
    <p>Retenção de {retention_days} dia(s); excluídas automaticamente depois disso.</p></li>
</ul>"""
    arm = f"""
<form method="post" action="/audit/audio/arm" data-busy="Autorizando…">
  <label class="check"><input name="confirmed" type="checkbox" value="1" required{"" if active else " disabled"}>
    <span>Declaro que o visitante foi informado e autorizou a gravação para diagnóstico.</span></label>
  <div class="btn-row">
    <button class="btn btn-primary" type="submit"{"" if active else " disabled"}>Autorizar somente a próxima sessão (5 min)</button>
  </div>
</form>
<form method="post" action="/audit/audio/disarm" class="btn-row">
  <button class="btn" type="submit"{"" if armed else " disabled"}>Cancelar autorização pendente</button>
</form>
<p class="note section-gap">Cada autorização cobre uma ligação e no máximo duas amostras WAV.
Sem transcrição armazenada nem geração de resposta. Arquivos privados, acessíveis somente ao
administrador local.</p>"""
    rows = "".join(
        f"<tr><td>{e(when(item.get('captured_at')))}</td>"
        f"<td class='num'>{int(item['turn'])}</td>"
        f"<td>{e(item.get('stt_status') or '—')}</td>"
        f"<td>{e(item.get('capture_status') or '—')}</td>"
        f"<td class='num'>{float(item['duration_seconds']):.1f} s</td>"
        f"<td style='min-width:12rem'>{_signal(item)}</td>"
        f"<td><audio controls preload='none' src='/audit/audio/sample/{e(item['id'])}' "
        f"aria-label='Amostra do turno {int(item['turn'])}'></audio></td></tr>"
        for item in samples
    )
    table = (
        "<div class='table-wrap' tabindex='0' role='region' aria-labelledby='amostras-titulo'>"
        "<table><thead><tr><th scope='col'>Capturada em</th><th scope='col' class='num'>Turno</th>"
        "<th scope='col'>STT</th><th scope='col'>Parada do VAD</th><th scope='col' class='num'>Duração</th>"
        "<th scope='col'>Sinal</th><th scope='col'>Ouvir</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
        "<ul class='signal-legend'><li><span class='swatch swatch-peak'></span>Pico RMS</li>"
        "<li><span class='swatch swatch-noise'></span>Piso de ruído</li>"
        "<li><span class='swatch swatch-threshold'></span>Limiar do VAD</li></ul>"
        if samples else empty_state(
            "Nenhuma amostra",
            "Autorize a próxima sessão, faça a ligação de teste e volte a esta página.",
        )
    )
    indicators = """
<p id="audio-summary-status" class="small muted" role="status">Carregando indicadores…</p>
<div class="stats" id="audio-stats"></div>
<h3 class="panel-sub">Falhas de reconhecimento por motivo</h3>
<div id="audio-stt-failures"></div>
<p class="note section-gap">Origem: auditoria agregada (sem áudio). Capturas sem fala costumam
indicar silêncio, ruído ou ganho baixo, não necessariamente erro do Whisper.</p>"""
    body = (
        feedback + status
        + "<div class='grid-split section-gap'>"
        + panel("Indicadores dos últimos 7 dias", indicators, id="indicadores")
        + panel("Gravação diagnóstica", arm, id="gravacao")
        + "</div>"
        + panel("Amostras autorizadas", table, id="amostras", cls="section-gap")
    )
    return render_page(
        "Diagnóstico de microfone", body, active="audio", section="Diagnóstico",
        scripts=("audio.js",),
        lede="Investigue falhas de captura e reconhecimento. A gravação fica desligada por "
             "padrão e só ocorre com autorização por sessão.",
    )
