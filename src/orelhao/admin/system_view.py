"""Painel compacto de telemetria do Dell, sem captura nem inferência adicionais."""
from __future__ import annotations

from .ui import badge, render_page


def _tile(title: str, key: str, unit: str, detail: str, *, bar: bool = True) -> str:
    meter = (f'<div class="meter" id="{key}-meter" aria-hidden="true"><span id="{key}-bar"></span></div>'
             if bar else "")
    return (f'<section class="stat" aria-label="{title}"><p class="stat-label">{title}</p>'
            f'<p class="stat-value"><span id="{key}">—</span><small> {unit}</small></p>'
            f'{meter}<p class="stat-hint" id="{key}-detail">{detail}</p></section>')


SYSTEM_BODY = f"""
<div class="panel-head" style="margin-bottom:var(--sp-3)">
  <p class="muted" style="margin:0">Leitura local a cada 5 segundos, sem gravar histórico.
  <span id="sample-time"></span></p>
  {badge("Coletando dados…", "neutral", attrs=' id="system-status" role="status"')}
</div>
<div class="stats">
  {_tile("Processador", "cpu-percent", "%", "Calculando uso entre duas leituras…")}
  {_tile("Memória RAM", "ram-percent", "%", "—")}
  {_tile("Disco do sistema", "disk-percent", "%", "—")}
  {_tile("Temperatura CPU", "cpu-temperature", "°C", "Sensor térmico do processador, quando disponível.", bar=False)}
  {_tile("Temperatura SSD", "ssd-temperature", "°C", "Sensor NVMe, quando disponível.", bar=False)}
  <section class="stat" aria-label="Tempo ligado"><p class="stat-label">Tempo ligado</p>
    <p class="stat-value" id="uptime" style="font-size:var(--fs-2xl)">—</p>
    <p class="stat-hint" id="swap-detail">Swap —</p></section>
</div>
<div class="grid section-gap">
  <section class="panel" aria-labelledby="services-title">
    <div class="panel-head"><h2 id="services-title">Serviços</h2></div>
    <div class="table-wrap"><table><thead><tr><th scope="col">Componente</th><th scope="col" class="num">Estado</th></tr></thead>
      <tbody id="service-rows"><tr><td colspan="2">Aguardando leitura…</td></tr></tbody></table></div>
    <h3 class="panel-sub">Memória dos processos essenciais</h3>
    <div class="table-wrap"><table><thead><tr><th scope="col">Processo</th><th scope="col" class="num">RAM</th></tr></thead>
      <tbody id="process-rows"><tr><td colspan="2">Aguardando leitura…</td></tr></tbody></table></div>
  </section>
  <section class="panel" aria-labelledby="sensors-title">
    <div class="panel-head"><h2 id="sensors-title">Sensores térmicos</h2></div>
    <div class="table-wrap"><table><thead><tr><th scope="col">Sensor</th><th scope="col" class="num">Temperatura</th></tr></thead>
      <tbody id="temperature-rows"><tr><td colspan="2">Aguardando leitura…</td></tr></tbody></table></div>
  </section>
</div>
<p class="note section-gap">Monitor somente leitura. CPU calculada entre amostras; RAM usada
exclui cache recuperável; leituras térmicas dependem dos sensores expostos pelo kernel.
O estado dos serviços não substitui testes de áudio/STT. Sem GPU dedicada detectável,
a temperatura gráfica não é exibida.</p>
"""


def system_page() -> str:
    return render_page(
        "Saúde do Servidor", SYSTEM_BODY, active="system", section="Diagnóstico",
        scripts=("system.js",),
        lede="CPU, memória, temperaturas, disco e serviços do Orelhão IA na máquina local.",
    )
