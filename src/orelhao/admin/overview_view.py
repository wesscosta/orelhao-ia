"""Visão geral: estado operacional reunido a partir de endpoints existentes.

Nenhum número é inventado: cada bloco declara a origem e mostra "—" ou
"indisponível" quando a fonte não responde ou exige credencial.
"""
from __future__ import annotations

from .ui import badge, icon, render_page


def overview_page(*, index_ready: bool, index_stale: bool, sources: int) -> str:
    if not index_ready:
        index_badge, index_text = badge("Não gerado", "bad"), "Gere o índice em Fontes e índice."
    elif index_stale:
        index_badge = badge("Desatualizado", "warn")
        index_text = "Há fontes novas ou alteradas fora do índice em uso."
    else:
        index_badge, index_text = badge("Atualizado", "ok"), f"{sources} fonte(s) cadastrada(s)."
    index_state = "missing" if not index_ready else ("stale" if index_stale else "ok")
    body = f"""
<section aria-labelledby="estado-titulo">
  <h2 id="estado-titulo" class="visually-hidden">Estado operacional</h2>
  <ul class="status-list">
    <li class="status-item"><h3>{icon("i-phone")}Monofone</h3>
      {badge("Verificando", "neutral", attrs=' id="ov-hook" role="status"')}
      <p id="ov-hook-detail">Estado da sessão de atendimento publicada pelo worker de voz.</p>
      <a href="/monitor">Abrir monitor da ligação</a></li>
    <li class="status-item"><h3>{icon("i-chat")}Serviço de IA (LLM)</h3>
      {badge("Verificando", "neutral", attrs=' id="ov-llm" role="status"')}
      <p id="ov-llm-detail">Consulta única ao servidor local da LLM.</p></li>
    <li class="status-item"><h3>{icon("i-book")}Base de conhecimento</h3>
      {index_badge}<p>{index_text}</p><a href="/">Fontes e índice</a></li>
    <li class="status-item"><h3>{icon("i-server")}Serviços da máquina</h3>
      {badge("Verificando", "neutral", attrs=' id="ov-services" role="status"')}
      <p id="ov-services-detail">systemd do usuário e disco.</p><a href="/system">Saúde da máquina</a></li>
  </ul>
</section>
<section class="panel section-gap" aria-labelledby="alertas-titulo">
  <div class="panel-head"><h2 id="alertas-titulo">Alertas</h2></div>
  <ul class="alert-list" id="ov-alerts" aria-live="polite" data-index="{index_state}"><li class="small muted">Reunindo informações…</li></ul>
</section>
<section class="panel section-gap" aria-labelledby="semana-titulo">
  <div class="panel-head"><h2 id="semana-titulo">Últimos 7 dias</h2>
    <div class="panel-aside"><a href="/audit">Detalhar na auditoria</a></div></div>
  <p class="small muted" id="ov-audit-status" role="status">Carregando indicadores da auditoria…</p>
  <div class="stats" id="ov-stats"></div>
  <p class="note section-gap">Origem: auditoria local agregada, restrita ao administrador.
  Falhas de voz somam capturas sem fala e transcrições rejeitadas.</p>
</section>
<section class="panel section-gap" aria-labelledby="atalhos-titulo">
  <div class="panel-head"><h2 id="atalhos-titulo">Tarefas frequentes</h2></div>
  <div class="btn-row" style="margin-top:0">
    <a class="btn" href="/audit/faq">Revisar perguntas sem resposta</a>
    <a class="btn" href="/workbench">Testar uma pergunta</a>
    <a class="btn" href="/audit/audio">Investigar o microfone</a>
  </div>
</section>
"""
    return render_page(
        "Central de operações", body, active="overview", section="Visão geral",
        scripts=("overview.js",),
        lede="Situação do Orelhão IA agora e nos últimos dias, com atalhos para agir.",
    )
