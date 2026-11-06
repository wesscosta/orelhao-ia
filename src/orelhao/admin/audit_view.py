"""Auditoria agregada e backups, sem bibliotecas externas nem HTML vindo de logs."""
from __future__ import annotations

from .ui import icon, render_page

AUDIT_BODY = f"""
<div class="panel" aria-labelledby="periodo-titulo">
  <div class="panel-head">
    <h2 id="periodo-titulo">Auditoria de atendimentos</h2>
    <div class="panel-aside">
      <label for="period" class="visually-hidden">Período</label>
      <select id="period" style="width:auto">
        <option value="7">Últimos 7 dias</option>
        <option value="30" selected>Últimos 30 dias</option>
        <option value="90">Últimos 90 dias</option>
      </select>
      <a class="btn" id="export" href="/audit/events.csv?days=30">{icon("i-download")}Exportar CSV</a>
    </div>
  </div>
  <p class="note">Dados agregados para melhorar o reconhecimento de voz, a base de conhecimento e
  as respostas do Lumi. Não armazena gravações de áudio.</p>
  <p id="audit-status" role="status" class="small muted">Carregando dados…</p>
  <div id="overview" class="stats" aria-label="Indicadores do período"></div>
</div>
<div class="grid section-gap">
  <section class="panel" aria-labelledby="topics-t"><div class="panel-head"><h2 id="topics-t">Assuntos mais frequentes</h2></div><div id="topics"></div></section>
  <section class="panel" aria-labelledby="questions-t"><div class="panel-head"><h2 id="questions-t">Perguntas recorrentes</h2></div><div id="questions"></div>
    <p class="note section-gap">Aparecem somente se a coleta de frases foi habilitada e se não
    contiverem indicadores de dados pessoais.</p></section>
  <section class="panel" aria-labelledby="stt-t"><div class="panel-head"><h2 id="stt-t">Falhas de reconhecimento de fala</h2></div><div id="stt"></div>
    <p class="note section-gap"><a href="/audit/audio">Investigar no diagnóstico de áudio</a></p></section>
  <section class="panel" aria-labelledby="routes-t"><div class="panel-head"><h2 id="routes-t">Origem das respostas</h2></div><div id="routes"></div></section>
</div>
<section class="panel section-gap" aria-labelledby="latency-t">
  <div class="panel-head"><h2 id="latency-t">Tempo médio por etapa</h2></div>
  <div id="latency"></div>
  <p class="note section-gap">Médias das etapas registradas. Falhas sem transcrição não são
  necessariamente erros do Whisper: podem decorrer de silêncio, ruído ou microfone com baixo ganho.</p>
</section>
<section class="panel section-gap" aria-labelledby="backups-t">
  <div class="panel-head"><h2 id="backups-t">Backups disponíveis</h2></div>
  <p class="note">Arquivos já criados no armazenamento local. O painel não cria backups.
  Arquivos completos podem incluir modelos, configurações e dados de conhecimento: guarde-os
  em local protegido.</p>
  <div id="backups" class="section-gap"><p class="small muted">Carregando lista…</p></div>
</section>
"""


def audit_page() -> str:
    return render_page(
        "Auditoria e backups", AUDIT_BODY, active="audit", section="Administração",
        scripts=("audit.js",),
        lede="Indicadores por período, exportação de eventos e download de backups. "
             "Restrito ao administrador em acesso local.",
    )
