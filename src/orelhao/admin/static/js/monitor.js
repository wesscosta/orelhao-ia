// Monitor somente leitura da ligação física. Dados via SSE existente (/monitor/events).
// Toda fala é inserida com textContent; nenhum HTML vindo dos eventos é interpretado.
(() => {
  const labels = {
    'session.started': 'Inicializando atendimento',
    'session.ended': 'Atendimento encerrado',
    'voice.greeting': 'Lumi apresentando a saudação',
    'voice.listening': 'Microfone escutando',
    'voice.paused': 'Pausa solicitada; aguardando a pessoa falar',
    'voice.idle_timeout': 'Encerrando por inatividade',
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
  const STEPS = ['listen', 'stt', 'rag', 'grounding', 'llm', 'tts', 'play'];
  const NOT_RAG_ROUTES = new Set(['prompt', 'guided', 'local_clock', 'clarification']);
  const ms = v => Number.isFinite(v) ? Math.round(v).toLocaleString('pt-BR') + ' ms' : '';

  let byId, transcript;

  function addTurn(ev, speaker, variant) {
    const article = document.createElement('article');
    article.className = 'turn turn-' + variant;
    const head = document.createElement('div');
    head.className = 'turn-head';
    const name = document.createElement('strong');
    name.textContent = speaker;
    const details = document.createElement('span');
    details.className = 'turn-meta';
    const clock = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString('pt-BR') : '';
    details.textContent = [ev.turn ? 'Turno ' + ev.turn : '', clock].filter(Boolean).join(', ');
    head.append(name, details);
    const content = document.createElement('p');
    content.className = 'turn-text';
    content.textContent = ev.text || '';
    article.append(head, content);
    if (ev.type === 'voice.response' && ev.status === 'abstencao') {
      const warning = document.createElement('p');
      warning.className = 'turn-flag';
      warning.textContent = 'Abstenção do verificador: ' + (ev.reason || 'sem motivo detalhado');
      article.append(warning);
    }
    transcript.append(article);
  }

  // Estado de cada etapa derivado SOMENTE dos eventos publicados pelo worker de voz.
  function pipelineState(events, active) {
    const state = Object.fromEntries(STEPS.map(step => [step, ['idle', 'Aguardando']]));
    if (!active) return state;
    let start = -1;
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].type === 'voice.listening') { start = i; break; }
    }
    if (start < 0) return state;
    const turn = events.slice(start);
    const set = (step, s, text) => { state[step] = [s, text]; };
    set('listen', 'active', 'Escutando');
    for (const ev of turn) {
      const m = ev.metrics || {};
      switch (ev.type) {
        case 'voice.capture':
          if (m.speech_detected === 0 || ev.status === 'speech_start_timeout') {
            set('listen', 'failed', 'Sem fala detectada');
          } else {
            set('listen', 'done', ms(m.capture_ms) || 'Concluída');
            set('stt', 'active', 'Transcrevendo');
          }
          break;
        case 'voice.transcription':
          set('stt', 'done', ms(m.stt_ms) || 'Reconhecida');
          break;
        case 'voice.transcription_invalid':
          set('stt', 'failed', ev.status === 'sem_fala' ? 'Sem fala' : 'Rejeitada');
          break;
        case 'voice.processing':
          for (const step of ['rag', 'grounding', 'llm']) set(step, 'active', 'Em andamento');
          break;
        case 'voice.response':
          if (NOT_RAG_ROUTES.has(ev.route) || ev.status === 'aviso') {
            for (const step of ['rag', 'grounding', 'llm']) set(step, 'skipped', 'Não executado');
          } else {
            const total = ms(m.rag_ms);
            set('rag', 'combined', 'Concluído');
            set('llm', 'combined', total ? 'Total ' + total : 'Concluído');
            set('grounding', ev.status === 'abstencao' ? 'warn' : 'done',
              ev.status === 'abstencao' ? 'Abstenção' : 'Resposta liberada');
          }
          set('tts', 'active', 'Em andamento');
          break;
        case 'voice.playback':
          if (ev.status === 'concluida') {
            if (Number.isFinite(m.tts_ms) && m.tts_ms > 0) set('tts', 'done', ms(m.tts_ms));
            else set('tts', 'skipped', 'Áudio pré-gravado');
            set('play', 'done', ms(m.play_ms) || 'Concluída');
          }
          break;
        case 'voice.error': {
          const current = STEPS.find(step => state[step][0] === 'active') || 'listen';
          set(current, 'failed', 'Erro: ' + (ev.reason || 'sem detalhe'));
          break;
        }
      }
    }
    return state;
  }

  function renderPipeline(state) {
    for (const item of document.querySelectorAll('#pipeline [data-step]')) {
      const [s, text] = state[item.dataset.step];
      item.dataset.state = s;
      item.querySelector('.step-state').textContent = text;
      if (s === 'active') item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    }
  }

  function render(data) {
    const events = Array.isArray(data.events) ? data.events : [];
    const active = Boolean(data.active);
    const status = byId('call-status');
    status.textContent = active ? 'Ligação em andamento' : 'Aguardando ligação';
    status.className = 'badge ' + (active ? 'badge-live' : 'badge-neutral');
    byId('session-id').textContent = data.session_id
      ? 'Sessão ' + String(data.session_id).slice(0, 8) : '';
    const latest = events.length ? events[events.length - 1] : null;
    byId('phase').textContent = latest
      ? (latest.type === 'voice.listening' && latest.status === 'aguardando_retorno'
          ? 'Em pausa; aguardando retorno'
          : (labels[latest.type] || latest.status || 'Atendimento'))
      : 'Aguardando o monofone';
    renderPipeline(pipelineState(events, active));

    transcript.replaceChildren();
    let count = 0;
    for (const ev of events) {
      if (ev.type === 'voice.transcription') {
        addTurn(ev, 'Visitante (Whisper)', 'user'); count++;
      } else if (ev.type === 'voice.context' && ev.text) {
        addTurn(ev, 'Consulta contextualizada para a busca', 'context'); count++;
      } else if (ev.type === 'voice.transcription_invalid' && ev.text) {
        addTurn(ev, 'Transcrição rejeitada', 'error'); count++;
      } else if ((ev.type === 'voice.response' || ev.type === 'voice.waiting' || ev.type === 'voice.greeting' || ev.type === 'voice.playback')
          && ev.text) {
        addTurn(ev, 'Lumi' + (ev.type === 'voice.waiting' ? ' pedindo para aguardar' : ''), 'lumi'); count++;
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
    let capture = null;
    for (const ev of events) {
      if (ev.metrics) Object.assign(values, ev.metrics);
      if (ev.type === 'voice.capture' && ev.metrics) capture = ev.metrics;
    }
    const dl = byId('metrics');
    dl.replaceChildren();
    for (const [label, field] of timings) {
      const dt = document.createElement('dt'); dt.textContent = label;
      const dd = document.createElement('dd');
      dd.textContent = Number.isFinite(values[field]) ? Number(values[field]).toFixed(0) + ' ms' : '—';
      dl.append(dt, dd);
    }
    window.orelhao.signal(byId('signal'), capture);
    const answer = [...events].reverse().find(ev => ev.type === 'voice.response');
    byId('grounding-status').textContent = answer
      ? (answer.status === 'abstencao' ? 'Abstenção' : answer.route || 'Respondida') : '—';
    byId('grounding-reason').textContent = answer && answer.reason ? answer.reason : '—';
  }

  document.addEventListener('DOMContentLoaded', () => {
    byId = id => document.getElementById(id);
    transcript = byId('transcript');
    const events = new EventSource('/monitor/events');
    // O servidor encerra cada fluxo a cada ~15 s e o navegador reconecta sozinho;
    // só avisamos se a reconexão demorar.
    let lostTimer = null;
    events.onopen = () => {
      clearTimeout(lostTimer); lostTimer = null;
      byId('monitor-connect').textContent = 'Atualização ativa, somente leitura';
    };
    events.onmessage = e => {
      try { render(JSON.parse(e.data)); }
      catch (_) { byId('monitor-connect').textContent = 'Evento inválido recebido'; }
    };
    events.onerror = () => {
      if (lostTimer) return;
      lostTimer = setTimeout(() => {
        byId('monitor-connect').textContent = 'Conexão interrompida; tentando reconectar';
      }, 3000);
    };
  });
})();
