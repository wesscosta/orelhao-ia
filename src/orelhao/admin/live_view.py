"""Visualização somente leitura da sessão física do Orelhão IA."""

MONITOR_BODY = """
<section class="card" aria-labelledby="monitor-title">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem">
    <div>
      <h2 id="monitor-title" style="margin:.1rem 0">Monitor de Atendimento</h2>
      <p class="muted" style="margin:.4rem 0">Mesma sessão do monofone físico. Nenhuma captura ou inferência adicional.</p>
    </div>
    <span id="call-status" class="pill" role="status">Aguardando ligação</span>
  </div>
  <p><small id="monitor-connect" class="muted">Conectando ao servidor…</small>
  <small id="session-id" class="muted" style="margin-left:1rem"></small></p>
  <section class="card" aria-label="Etapa atual" style="background:#f8fafc">
    <strong>Etapa:</strong> <span id="phase" aria-live="polite">Aguardando o monofone</span>
  </section>
  <div class="grid">
    <section class="card" aria-labelledby="transcript-title">
      <h3 id="transcript-title">Conversa do monofone</h3>
      <div id="transcript" role="log" aria-label="Transcrições e respostas" aria-live="polite" aria-relevant="additions">
        <p class="muted">As falas aparecerão aqui durante o atendimento.</p>
      </div>
    </section>
    <section class="card" aria-labelledby="metrics-title">
      <h3 id="metrics-title">Diagnóstico da sessão</h3>
      <dl id="metrics" style="display:grid;grid-template-columns:1fr auto;gap:.5rem">
        <dt>Captura</dt><dd>—</dd>
        <dt>STT (Whisper)</dt><dd>—</dd>
        <dt>RAG / LLM / verificação</dt><dd>—</dd>
        <dt>TTS</dt><dd>—</dd>
        <dt>Reprodução</dt><dd>—</dd>
      </dl>
      <p><strong>Última classificação:</strong> <span id="grounding-status">—</span></p>
      <p><strong>Motivo:</strong> <span id="grounding-reason">—</span></p>
    </section>
  </div>
  <p class="muted"><small>Privacidade: transcrições e respostas ficam somente em memória temporária.
  São removidas quando a ligação termina. A página não recebe o áudio bruto.
  O monitor exige acesso à interface administrativa local, sem exposição pública.</small></p>
</section>
<style>
.monitor-turn {padding:.8rem; margin:.7rem 0; border:1px solid #e5e7eb; border-radius:9px; overflow-wrap:anywhere}
.monitor-user {border-left:4px solid #2563eb}
.monitor-lumi {border-left:4px solid #0f766e}
.monitor-error {border-left:4px solid #c2410c}
.monitor-context {border-left:4px solid #64748b;background:#f8fafc}
.monitor-head {font-size:.85rem; font-weight:600; display:flex; justify-content:space-between;gap:.5rem}
.monitor-text {white-space:pre-wrap;margin:.5rem 0 0}
.monitor-tag {font-size:.8rem;color:#475569}
#metrics dd {margin:0; font-variant-numeric:tabular-nums}
</style>
<script>
(() => {
  const byId = id => document.getElementById(id);
  const transcript = byId('transcript');
  const labels = {
    'session.started': 'Inicializando atendimento',
    'session.ended': 'Atendimento encerrado',
    'voice.greeting': 'Lumi apresentando a saudação',
    'voice.listening': 'Microfone escutando',
    'voice.capture': 'Fala capturada',
    'voice.transcription': 'Transcrição concluída',
    'voice.transcription_invalid': 'Não foi possível reconhecer a fala',
    'voice.context': 'Pergunta contextualizada para o RAG',
    'voice.processing': 'Consultando a base de conhecimento',
    'voice.waiting': 'Lumi pedindo para aguardar',
    'voice.response': 'Resposta gerada',
    'voice.playback': 'Reprodução de voz',
    'voice.error': 'Erro no atendimento'
  };
  const timings = [
    ['Captura', 'capture_ms'],
    ['STT (Whisper)', 'stt_ms'],
    ['RAG / LLM / verificação', 'rag_ms'],
    ['TTS', 'tts_ms'],
    ['Reprodução', 'play_ms']
  ];
  function addTurn(ev, speaker, variant) {
    const article = document.createElement('article');
    article.className = 'monitor-turn monitor-' + variant;
    const head = document.createElement('div');
    head.className = 'monitor-head';
    const name = document.createElement('span');
    name.textContent = speaker;
    const details = document.createElement('span');
    details.className = 'monitor-tag';
    const clock = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString('pt-BR') : '';
    details.textContent = [ev.turn ? 'Turno ' + ev.turn : '', clock].filter(Boolean).join(' · ');
    head.append(name, details);
    const content = document.createElement('p');
    content.className = 'monitor-text';
    content.textContent = ev.text || '';
    article.append(head, content);
    if (ev.type === 'voice.response' && ev.status === 'abstencao') {
      const warning = document.createElement('p');
      warning.className = 'monitor-tag warn';
      warning.textContent = 'Abstenção do verificador: ' + (ev.reason || 'sem motivo detalhado');
      article.append(warning);
    }
    transcript.append(article);
  }
  function render(data) {
    const events = Array.isArray(data.events) ? data.events : [];
    const active = Boolean(data.active);
    byId('call-status').textContent = active ? 'Ligação em andamento' : 'Aguardando ligação';
    byId('session-id').textContent = data.session_id
      ? 'Sessão ' + String(data.session_id).slice(0, 8) : '';
    const latest = events.length ? events[events.length - 1] : null;
    byId('phase').textContent = latest
      ? (labels[latest.type] || latest.status || 'Atendimento')
      : 'Aguardando o monofone';
    transcript.replaceChildren();
    let count = 0;
    for (const ev of events) {
      if (ev.type === 'voice.transcription') {
        addTurn(ev, 'Usuário · Whisper', 'user'); count++;
      } else if (ev.type === 'voice.context' && ev.text) {
        addTurn(ev, 'Consulta contextualizada · Busca', 'context'); count++;
      } else if (ev.type === 'voice.transcription_invalid' && ev.text) {
        addTurn(ev, 'Transcrição rejeitada', 'error'); count++;
      } else if ((ev.type === 'voice.response' || ev.type === 'voice.waiting' || ev.type === 'voice.greeting' || ev.type === 'voice.playback')
          && ev.text) {
        addTurn(ev, 'Lumi' + (ev.type === 'voice.waiting' ? ' · Aguarde' : ''), 'lumi'); count++;
      }
    }
    if (!count) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = latest && latest.type === 'session.ended'
        ? 'Ligação encerrada. As transcrições foram removidas.'
        : 'As falas aparecerão aqui durante o atendimento.';
      transcript.append(empty);
    }
    const values = {};
    for (const ev of events) {
      if (ev.metrics) Object.assign(values, ev.metrics);
    }
    const dl = byId('metrics');
    dl.replaceChildren();
    for (const [label, field] of timings) {
      const dt = document.createElement('dt'); dt.textContent = label;
      const dd = document.createElement('dd');
      dd.textContent = Number.isFinite(values[field]) ? Number(values[field]).toFixed(0) + ' ms' : '—';
      dl.append(dt, dd);
    }
    const answer = [...events].reverse().find(ev => ev.type === 'voice.response');
    byId('grounding-status').textContent = answer
      ? (answer.status === 'abstencao' ? 'Abstenção' : answer.route || 'Respondida') : '—';
    byId('grounding-reason').textContent = answer && answer.reason ? answer.reason : '—';
  }
  const events = new EventSource('/monitor/events');
  events.onopen = () => { byId('monitor-connect').textContent = 'Atualização ativa · somente leitura'; };
  events.onmessage = e => {
    try { render(JSON.parse(e.data)); }
    catch (_) { byId('monitor-connect').textContent = 'Evento inválido recebido'; }
  };
  events.onerror = () => {
    byId('monitor-connect').textContent = 'Conexão interrompida · tentando reconectar';
  };
})();
</script>
""";
