// Central de operações: reúne estado real de endpoints existentes, sem métricas simuladas.
(() => {
  const byId = id => document.getElementById(id);
  const fmt = v => Number.isFinite(Number(v)) ? new Intl.NumberFormat('pt-BR').format(Number(v)) : '—';
  const setBadge = (id, tone, text) => { const el = byId(id); el.className = 'badge badge-' + tone; el.textContent = text; };
  const alerts = new Map();   // chave -> [tom, texto, link, rótulo]
  let pending = 3;            // llm, sistema e auditoria
  let systemFirst = true;

  function renderAlerts() {
    const list = byId('ov-alerts');
    list.replaceChildren();
    const index = list.dataset.index;
    const items = [...alerts.values()];
    if (index === 'missing') items.unshift(['bad', 'O índice da base ainda não foi gerado.', '/', 'Gerar índice']);
    if (index === 'stale') items.unshift(['warn', 'Há fontes novas ou alteradas fora do índice em uso.', '/', 'Reindexar']);
    if (!items.length) {
      const li = document.createElement('li'); li.className = 'small muted';
      li.textContent = pending ? 'Reunindo informações…' : 'Nenhum alerta no momento.';
      list.append(li); return;
    }
    for (const [tone, text, href, label] of items) {
      const li = document.createElement('li');
      li.className = 'alert alert-' + tone;
      const body = document.createElement('div');
      body.textContent = text + ' ';
      if (href) { const a = document.createElement('a'); a.href = href; a.textContent = label; body.append(a); }
      li.append(body); list.append(li);
    }
  }
  const done = () => { pending = Math.max(0, pending - 1); renderAlerts(); };

  function hook() {
    const source = new EventSource('/monitor/events');
    source.onmessage = e => {
      try {
        const data = JSON.parse(e.data);
        const events = Array.isArray(data.events) ? data.events : [];
        const last = events[events.length - 1];
        if (data.active) {
          setBadge('ov-hook', 'live', 'Em atendimento');
          byId('ov-hook-detail').textContent = 'Ligação em andamento' +
            (last && last.timestamp ? '; último evento às ' + new Date(last.timestamp).toLocaleTimeString('pt-BR') + '.' : '.');
        } else {
          setBadge('ov-hook', 'neutral', 'Livre');
          byId('ov-hook-detail').textContent = last && last.type === 'session.ended'
            ? 'Última ligação encerrada às ' + new Date(last.timestamp).toLocaleTimeString('pt-BR') + '.'
            : 'Nenhuma ligação ativa registrada.';
        }
      } catch (_) { setBadge('ov-hook', 'neutral', 'Indeterminado'); }
    };
    source.onerror = () => {
      if (byId('ov-hook').textContent === 'Verificando') setBadge('ov-hook', 'neutral', 'Indeterminado');
    };
  }

  async function llm() {
    try {
      const res = await fetch('/workbench/llm-status', {cache: 'no-store'});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      setBadge('ov-llm', data.available ? 'ok' : 'bad', data.available ? 'Disponível' : 'Indisponível');
      byId('ov-llm-detail').textContent = data.detail;
      if (!data.available) alerts.set('llm', ['bad', 'A LLM local não respondeu: o Lumi não consegue gerar respostas da base.', '/system', 'Ver serviços']);
    } catch (error) {
      setBadge('ov-llm', 'neutral', 'Indeterminado');
      byId('ov-llm-detail').textContent = 'Não foi possível consultar (' + error.message + ').';
    }
    done();
  }

  async function system() {
    try {
      const res = await fetch('/system/state', {cache: 'no-store'});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      const services = data.services || [];
      const down = services.filter(s => s.state !== 'active');
      const unknown = services.length && services.every(s => s.state === 'unknown');
      if (unknown) setBadge('ov-services', 'neutral', 'Indeterminado');
      else setBadge('ov-services', down.length ? 'bad' : 'ok', down.length ? down.length + ' com problema' : 'Todos ativos');
      const disk = data.disk && data.disk.percent;
      byId('ov-services-detail').textContent = (unknown ? 'systemd do usuário não respondeu. ' : '') +
        'Disco em ' + (Number.isFinite(disk) ? fmt(disk) + '%' : '—') + '.';
      alerts.delete('services'); alerts.delete('disk');
      if (down.length && !unknown) alerts.set('services', ['bad', 'Serviço fora do ar: ' + down.map(s => s.name).join(', ') + '.', '/system', 'Ver máquina']);
      if (Number.isFinite(disk) && disk >= 90) alerts.set('disk', ['warn', 'Disco do sistema acima de 90%.', '/system', 'Ver máquina']);
    } catch (error) {
      setBadge('ov-services', 'neutral', 'Indeterminado');
      byId('ov-services-detail').textContent = 'Sem resposta da coleta local (' + error.message + ').';
    }
    if (systemFirst) { systemFirst = false; done(); } else renderAlerts();
  }

  async function audit() {
    const status = byId('ov-audit-status');
    try {
      const res = await fetch('/audit/summary?days=7', {cache: 'no-store', credentials: 'same-origin'});
      if (res.status === 401 || res.status === 403) {
        status.textContent = 'Indicadores restritos ao administrador. Entre pela página de auditoria para vê-los.';
        done(); return;
      }
      if (res.status === 503) {
        status.textContent = 'Auditoria indisponível: senha administrativa não configurada no servidor.';
        done(); return;
      }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const d = await res.json();
      const voiceFailures = Number(d.capture_without_speech || 0) + Number(d.stt_invalid || 0);
      const cards = [
        ['Atendimentos', d.sessions, ''],
        ['Perguntas reconhecidas', d.questions, ''],
        ['Falhas de voz', voiceFailures, voiceFailures ? 'warn' : ''],
        ['Perguntas sem resposta', d.abstentions, d.abstentions ? 'warn' : ''],
        ['Erros de execução', d.errors, d.errors ? 'bad' : '']
      ];
      byId('ov-stats').replaceChildren(...cards.map(([label, value, tone]) => {
        const box = document.createElement('div'); box.className = 'stat' + (tone ? ' stat-' + tone : '');
        const l = document.createElement('p'); l.className = 'stat-label'; l.textContent = label;
        const v = document.createElement('p'); v.className = 'stat-value'; v.textContent = fmt(value);
        box.append(l, v); return box;
      }));
      status.textContent = d.sessions ? '' : 'Nenhum atendimento registrado nos últimos 7 dias.';
      if (d.abstentions) alerts.set('faq', ['warn', fmt(d.abstentions) + ' resposta(s) sem evidência nos últimos 7 dias.', '/audit/faq', 'Revisar no FAQ']);
      if (d.errors) alerts.set('errors', ['bad', fmt(d.errors) + ' erro(s) de execução no atendimento nos últimos 7 dias.', '/audit', 'Ver auditoria']);
      if (voiceFailures) alerts.set('voice', ['warn', fmt(voiceFailures) + ' falha(s) de captura ou reconhecimento de voz.', '/audit/audio', 'Diagnosticar áudio']);
    } catch (error) {
      status.textContent = 'Não foi possível carregar a auditoria (' + error.message + ').';
    }
    done();
  }

  document.addEventListener('DOMContentLoaded', () => {
    renderAlerts(); hook(); llm(); system(); audit();
    const timer = setInterval(() => { if (!document.hidden) system(); }, 30000);
    window.addEventListener('pagehide', () => clearInterval(timer), {once: true});
  });
})();
