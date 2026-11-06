"""Visualização somente leitura da sessão física do Orelhão IA."""
from __future__ import annotations

from .ui import badge, render_page

_STEPS = (
    ("listen", "Escuta"), ("stt", "STT"), ("rag", "RAG"), ("grounding", "Grounding"),
    ("llm", "LLM"), ("tts", "TTS"), ("play", "Reprodução"),
)

_PIPELINE = "".join(
    f'<li data-step="{key}" data-state="idle"><span class="node" aria-hidden="true"></span>'
    f'<span class="step-name">{label}</span><span class="step-state">Aguardando</span></li>'
    for key, label in _STEPS
)

MONITOR_BODY = f"""
<div class="panel" aria-labelledby="fluxo-titulo">
  <div class="panel-head">
    <h2 id="fluxo-titulo">Fluxo do turno atual</h2>
    <div class="panel-aside">
      {badge("Aguardando ligação", "neutral", attrs=' id="call-status" role="status"')}
      <span class="connection"><span id="monitor-connect">Conectando ao servidor…</span>
      <span id="session-id"></span></span>
    </div>
  </div>
  <p><strong>Etapa:</strong> <span id="phase" aria-live="polite">Aguardando o monofone</span></p>
  <ol class="pipeline" id="pipeline" aria-label="Etapas do atendimento">{_PIPELINE}</ol>
  <p class="note section-gap">RAG, Grounding e LLM são reportados pelo worker em um único
  evento ao final da consulta; o painel não os confirma separadamente. Respostas guiadas,
  avisos e o relógio local não executam essas etapas.</p>
</div>
<div class="grid-2 section-gap">
  <section class="panel" aria-labelledby="transcript-title">
    <div class="panel-head"><h2 id="transcript-title">Conversa do monofone</h2></div>
    <div id="transcript" class="transcript" role="log" aria-label="Transcrições e respostas"
      aria-live="polite" aria-relevant="additions">
      <p class="muted">As falas aparecerão aqui durante o atendimento.</p>
    </div>
  </section>
  <div class="stack">
    <section class="panel" aria-labelledby="metrics-title">
      <div class="panel-head"><h2 id="metrics-title">Tempos da sessão</h2></div>
      <dl id="metrics" class="kv">
        <dt>Captura</dt><dd>—</dd>
        <dt>STT (Whisper)</dt><dd>—</dd>
        <dt>RAG / LLM / verificação</dt><dd>—</dd>
        <dt>TTS</dt><dd>—</dd>
        <dt>Reprodução</dt><dd>—</dd>
      </dl>
      <h3 class="panel-sub">Última decisão</h3>
      <dl class="kv">
        <dt>Classificação</dt><dd id="grounding-status">—</dd>
        <dt>Motivo</dt><dd id="grounding-reason">—</dd>
      </dl>
    </section>
    <section class="panel" aria-labelledby="signal-title">
      <div class="panel-head"><h2 id="signal-title">Sinal da última captura</h2></div>
      <div id="signal" class="signal" role="img" aria-label="Sem captura nesta sessão">
        <span class="signal-peak" id="signal-peak" style="width:0"></span>
        <span class="signal-mark signal-noise" id="signal-noise" hidden></span>
        <span class="signal-mark signal-threshold" id="signal-threshold" hidden></span>
      </div>
      <ul class="signal-legend">
        <li><span class="swatch swatch-peak"></span>Pico RMS <strong id="signal-peak-value">—</strong></li>
        <li><span class="swatch swatch-noise"></span>Piso de ruído <strong id="signal-noise-value">—</strong></li>
        <li><span class="swatch swatch-threshold"></span>Limiar do VAD <strong id="signal-threshold-value">—</strong></li>
      </ul>
      <p class="note section-gap">Valores informados pelo detector de voz ao fim de cada
      captura. Não é forma de onda nem medição contínua.</p>
    </section>
  </div>
</div>
<p class="note section-gap">Privacidade: transcrições e respostas ficam somente em memória
temporária e são removidas quando a ligação termina. A página não recebe o áudio bruto.</p>
"""


def monitor_page() -> str:
    return render_page(
        "Monitor de Atendimento", MONITOR_BODY, active="monitor",
        section="Atendimento ao vivo", scripts=("monitor.js",),
        lede="Acompanhe a ligação do monofone físico em tempo real. Somente leitura: "
             "nenhuma captura ou inferência adicional.",
    )
