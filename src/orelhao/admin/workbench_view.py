"""Telas da bancada de testes (RAG, LLM, grounding e voz)."""
from __future__ import annotations

from typing import Any

from orelhao.services.knowledge.evidence_selector import SpanSelection
from orelhao.services.tts.voice_catalog import voice_options

from .ui import alert, badge, e, panel, render_page

SECTION = "Conhecimento"
SCRIPTS = ("workbench.js",)


def render_evidence_span(selection: SpanSelection | None) -> str:
    """Exibe um candidato textual literal, nunca como prova de suporte."""
    if selection is None:
        return "<span class='muted'>Sem correspondência lexical</span>"
    span = selection.span
    label = f"[{span.start}:{span.end}]"
    return (
        f"<small class='muted'>caracteres {e(label)}; "
        f"cobertura lexical {selection.lexical_coverage:.0%}</small>"
        f"<blockquote>{e(span.text)}</blockquote>"
    )


def _voice_select(selected: str = "cadu") -> str:
    return "".join(
        f'<option value="{opt.id}"'
        f'{" selected" if opt.id == selected else ""}>{e(opt.label)}</option>'
        for opt in voice_options()
    )


def home_page() -> str:
    services = f"""
<ul class="status-list" aria-label="Serviços usados pela bancada">
  <li class="status-item"><h2>LLM local</h2>{badge("Verificando", "neutral", attrs=' id="llm-badge"')}
    <p id="llm-status" role="status">Verificando LLM local…</p></li>
  <li class="status-item"><h2>Reconhecimento de fala</h2>{badge("Verificando", "neutral", attrs=' id="stt-badge"')}
    <p id="voice-status" role="status">O microfone envia WAV PCM16 para o STT local.</p></li>
  <li class="status-item"><h2>Voz (TTS)</h2>{badge("Verificando", "neutral", attrs=' id="tts-badge"')}
    <p id="tts-status" role="status">Verificando voz local…</p></li>
</ul>"""
    form = """
<form method="post" action="/workbench/run" data-busy="Executando…">
  <div class="field"><label for="question">Pergunta</label>
    <textarea id="question" name="question" required rows="3"
      aria-describedby="question-hint"></textarea>
    <span class="field-hint" id="question-hint">Digite ou grave a pergunta como um visitante faria.</span></div>
  <div class="btn-row" style="margin-top:0;margin-bottom:var(--sp-4)">
    <button class="btn" type="button" id="record" disabled aria-pressed="false">Preparando STT…</button>
  </div>
  <div class="grid">
    <div class="field"><label for="mode">Política da bancada</label>
      <select id="mode" name="mode">
        <option value="observe">Observação: exibir a saída mesmo se não for suportada</option>
        <option value="enforce">Seguro: bloquear respostas sem suporte</option>
      </select></div>
    <div class="field"><label for="voice">Voz para ouvir a resposta</label>
      <select name="voice" id="voice">
        <option value="cadu">Piper Cadu (original)</option>
        <option value="faber">Piper Faber (experimental)</option>
      </select>
      <span class="field-hint">Trocar a voz não altera a resposta nem o Grounding V3.</span></div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" type="submit" id="run" disabled>Executar teste</button>
    <button class="btn" type="button" id="preview-voice">Ouvir apresentação do Lumi</button>
  </div>
</form>"""
    body = services + panel("Nova consulta", form, id="consulta", cls="section-gap")
    return render_page(
        "Bancada de testes", body, active="workbench", section=SECTION, scripts=SCRIPTS,
        lede="Compare a resposta gerada com a decisão factual antes de publicar mudanças "
             "na base. O modo seguro bloqueia respostas com afirmações sem suporte.",
    )


def result_page(observation: Any, voice: str) -> str:
    decision = observation.grounding
    v3 = observation.grounding_v3
    allowed = v3.allows_response if v3 else decision.allows_response
    local_clock = observation.answer_origin == "local_clock"
    nli_info = (
        "NLI não executado (fonte: relógio local)" if local_clock
        else (f"NLI anterior: {e(v3.nli_status.value)} ({v3.nli_score:.4f})" if v3 else "Sem NLI")
    )
    v3_html = (
        "<p><strong>Grounding V3 (decisão final):</strong> "
        f"{badge(v3.disposition.value.upper(), 'ok' if v3.allows_response else 'warn')} "
        f"Motivo: <code>{e(v3.reason.value)}</code>; {nli_info}; "
        f"fatos verificados: {len(v3.supporting_chunk_ids)} chunks.</p>"
        if v3 else "<p>Decisão V3 indisponível.</p>"
    )
    precheck = observation.answerability
    if local_clock:
        clock = observation.local_clock or {}
        precheck_html = (
            "<p><strong>Resposta operacional:</strong> data/hora do relógio "
            "local. RAG, LLM, NLI e pré-gate não foram executados. "
            f"Fuso: {e(clock.get('timezone', '—'))}; "
            f"instante: {e(clock.get('timestamp', '—'))}.</p>"
        )
    elif precheck is None:
        precheck_html = "<p>Gate de answerability não habilitado nesta bancada.</p>"
    else:
        answerable = precheck.decision.answerable
        pre_status = "SEM IMPEDIMENTO DETECTADO" if answerable else "ABSTENÇÃO"
        pre_reason = precheck.decision.reason.value if precheck.decision.reason else "—"
        precheck_html = (
            f"<p><strong>Answerability pré-geração:</strong> {e(pre_status)} "
            f"<code>{e(pre_reason)}</code></p>"
            f"<p class='small muted'>Fontes admitidas: {len(precheck.admissible_chunk_ids)}"
            f"; conflitos: {len(precheck.conflicting_chunk_ids)}"
            f"; verificação específica: {str(precheck.verified_specific_answer).lower()}"
            f"; geração ignorada: {str(observation.generation_skipped).lower()}"
            f"; entidade incorreta na resposta: "
            f"{str(observation.answer_entity_mismatch).lower()}</p>"
        )
    evidence = "".join(
        f"<article class='panel'><div class='panel-head'><h3>{e(item.source)}</h3>"
        f"{badge(f'retrieval {item.score:.4f}', 'neutral')}</div>"
        f"<pre class='evidence'>{e(item.text)}</pre></article>"
        for item in observation.evidence
    ) or "<p class='muted'>Nenhum chunk recuperado.</p>"
    claim_rows = "".join(
        f"<tr><td class='wrap'>{e(item.claim)}</td>"
        f"<td>{e(item.decision.status.value.upper())}</td>"
        f"<td class='num'>{item.decision.score:.4f}</td>"
        f"<td>{e(item.source or '—')}</td>"
        f"<td>{e(item.chunk_id or '—')}</td>"
        f"<td class='wrap'>{render_evidence_span(item.span_selection)}</td></tr>"
        for item in observation.claims
    )
    fact_rows = "".join(
        f"<tr><td class='wrap'>{e(item.fact.literal)}</td>"
        f"<td>{e(item.fact.kind.value)}</td>"
        f"<td>{e(item.status.value)}</td>"
        f"<td>{e(item.source or '—')} "
        f"<small>{'[' + str(item.source_start) + ':' + str(item.source_end) + ']' if item.source_start is not None else ''}</small></td>"
        f"<td class='wrap'>{e(item.explanation)}</td></tr>"
        for assessment in observation.fact_validations
        for item in assessment.checks
    )
    if observation.mode == "enforce":
        policy = alert("Modo seguro: saída bloqueada quando grounding não permite resposta.",
                       "info", role="status")
    else:
        policy = alert("Modo observação: saída mostrada para diagnóstico, mesmo se não suportada.",
                       "warn", role="status")
    nli_badge = (badge("NLI não executado", "neutral") if local_clock
                 else badge(f"NLI {decision.score:.6f}", "neutral"))
    lat = observation.latency
    speech_url = f"/workbench/speech/{e(observation.observation_id)}"
    summary = f"""
{policy}
<p><strong>Pergunta:</strong> {e(observation.question)}</p>
<h3 class="panel-sub">Resposta apresentada</h3>
<p class="answer">{e(observation.presented_answer)}</p>
<div class="grid" style="margin-top:var(--sp-4)">
  <div class="field" style="margin:0"><label for="result-voice">Voz da resposta</label>
    <select id="result-voice">{_voice_select(voice)}</select>
    <span class="field-hint">Pode trocar sem repetir a pergunta.</span></div>
  <div class="btn-row" style="align-self:end;margin:0">
    <button class="btn" type="button" id="speak-answer" data-speech-url="{speech_url}">Ouvir resposta</button>
  </div>
</div>
<audio id="spoken-answer" controls preload="none" hidden></audio>
<p id="spoken-status" class="small muted" role="status">Use Ouvir resposta para sintetizar a voz em pt-BR.</p>
<h3 class="panel-sub">Decisões</h3>
{precheck_html}
{v3_html}
<p><strong>Grounding (NLI legado):</strong> {badge(decision.status.value.upper(), 'ok' if allowed else 'warn')} {nli_badge}</p>
<p><strong>Gerador:</strong> {e(observation.generator)}; abstenção da geração: {str(observation.generation_abstained).lower()}</p>
<dl class="kv small" style="margin-top:var(--sp-4)">
  <dt>Retrieval</dt><dd>{lat.retrieval_ms:.2f} ms</dd>
  <dt>Adjudicação</dt><dd>{lat.adjudication_ms:.2f} ms</dd>
  <dt>Geração</dt><dd>{lat.generation_ms:.2f} ms</dd>
  <dt>Grounding</dt><dd>{lat.grounding_ms:.2f} ms</dd>
  <dt>Total</dt><dd>{lat.total_ms:.2f} ms</dd>
</dl>"""
    claims = (
        "<p class='note'>Trechos selecionados por sobreposição lexical; não são comprovação "
        "semântica nem alteram a decisão do NLI.</p>"
        "<div class='table-wrap' tabindex='0' role='region' aria-label='Verificação por afirmação'>"
        "<table><thead><tr><th scope='col'>Afirmação</th><th scope='col'>Decisão</th>"
        "<th scope='col' class='num'>NLI</th><th scope='col'>Fonte</th><th scope='col'>Chunk ID</th>"
        "<th scope='col'>Trecho candidato</th></tr></thead>"
        f"<tbody>{claim_rows or '<tr><td colspan=\"6\">Nenhuma afirmação avaliada.</td></tr>'}</tbody></table></div>"
    )
    facts = (
        "<p class='note'>Compara atributos explícitos e escopos de fontes primárias. "
        "O resultado V3 pode vetar uma resposta no modo enforce, mas valores coincidentes "
        "não comprovam a afirmação inteira nem superam bloqueios do NLI.</p>"
        "<div class='table-wrap' tabindex='0' role='region' aria-label='Fact Validator V3'>"
        "<table><thead><tr><th scope='col'>Valor mencionado</th><th scope='col'>Atributo</th>"
        "<th scope='col'>Resultado</th><th scope='col'>Fonte</th><th scope='col'>Justificativa</th></tr></thead>"
        f"<tbody>{fact_rows or '<tr><td colspan=\"5\">Nenhum atributo tipado identificado.</td></tr>'}</tbody></table></div>"
    )
    rating = f"""
<form method="post" action="/workbench/rate" class="grid">
  <input type="hidden" name="observation_id" value="{e(observation.observation_id)}">
  <input type="hidden" name="grounding_status" value="{e(decision.status.value)}">
  <div class="field" style="margin:0"><label for="rating">A resposta está…</label>
    <select id="rating" name="rating"><option value="correct">Correta</option>
    <option value="partial">Parcialmente correta</option><option value="incorrect">Incorreta</option></select></div>
  <div class="btn-row" style="align-self:end;margin:0"><button class="btn btn-primary" type="submit">Registrar avaliação</button></div>
</form>
<p class="note section-gap">A avaliação é acrescentada ao log sem alterar a observação original.</p>"""
    body = (
        "<div class='grid-2'>"
        + panel("Resultado", summary, id="resultado")
        + panel("Avaliação humana", rating, id="avaliacao")
        + "</div>"
        + panel("Verificação por afirmação", claims, id="afirmacoes")
        + panel("Fact Validator V3 — diagnóstico", facts, id="fatos")
        + "<section class='section-gap' aria-labelledby='evidencias-titulo'>"
          "<h2 id='evidencias-titulo' style='margin-bottom:var(--sp-3)'>Evidências recuperadas</h2>"
          f"<div class='stack'>{evidence}</div></section>"
    )
    return render_page(
        "Resultado da bancada", body, active="workbench", section=SECTION, scripts=SCRIPTS,
        actions="<a class='btn' href='/workbench'>Executar outro teste</a>",
    )


def rating_page(diagnostic_text: str) -> str:
    body = (
        alert("O evento foi acrescentado ao log sem alterar a observação original.", "ok",
              title="Avaliação registrada.", role="status")
        + f"<p><strong>Diagnóstico:</strong> {e(diagnostic_text)}</p>"
        + "<p class='section-gap'><a class='btn' href='/workbench'>Voltar à bancada</a></p>"
    )
    return render_page("Avaliação registrada", body, active="workbench", section=SECTION)
