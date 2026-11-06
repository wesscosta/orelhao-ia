// Indicadores agregados de captura/STT para o diagnóstico de áudio (sem acesso a gravações).
(() => {
  const byId = id => document.getElementById(id);
  const fmt = v => Number.isFinite(Number(v)) && v !== null ? new Intl.NumberFormat('pt-BR').format(Number(v)) : '—';
  function stat(label, value, hint) {
    const box = document.createElement('div'); box.className = 'stat';
    const l = document.createElement('p'); l.className = 'stat-label'; l.textContent = label;
    const v = document.createElement('p'); v.className = 'stat-value'; v.textContent = value;
    box.append(l, v);
    if (hint) { const h = document.createElement('p'); h.className = 'stat-hint'; h.textContent = hint; box.append(h); }
    return box;
  }
  async function load() {
    const status = byId('audio-summary-status');
    if (!status) return;
    try {
      const res = await fetch('/audit/summary?days=7', {cache: 'no-store'});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      const lat = data.latency_ms || {};
      byId('audio-stats').replaceChildren(
        stat('Capturas sem fala', fmt(data.capture_without_speech)),
        stat('Transcrições rejeitadas', fmt(data.stt_invalid)),
        stat('Captura (média)', lat.capture == null ? '—' : fmt(lat.capture) + ' ms'),
        stat('STT (média)', lat.stt == null ? '—' : fmt(lat.stt) + ' ms'),
        stat('Overflows de áudio', fmt(lat.overflows), 'Perdas de buffer na captura')
      );
      const holder = byId('audio-stt-failures');
      holder.replaceChildren();
      const items = data.stt_failures || [];
      if (!items.length) {
        const p = document.createElement('p'); p.className = 'small muted';
        p.textContent = 'Nenhuma falha de reconhecimento registrada no período.';
        holder.append(p);
      } else {
        const wrap = document.createElement('div'); wrap.className = 'table-wrap';
        const table = document.createElement('table');
        table.innerHTML = '<thead><tr><th scope="col">Motivo</th><th scope="col" class="num">Ocorrências</th></tr></thead>';
        const body = document.createElement('tbody');
        for (const item of items) {
          const tr = document.createElement('tr');
          const a = document.createElement('td'); a.textContent = item.label;
          const b = document.createElement('td'); b.className = 'num'; b.textContent = fmt(item.count);
          tr.append(a, b); body.append(tr);
        }
        table.append(body); wrap.append(table); holder.append(wrap);
      }
      status.textContent = 'Atualizado às ' + new Date().toLocaleTimeString('pt-BR') + '.';
    } catch (error) {
      status.textContent = 'Indicadores indisponíveis (' + error.message + '). As amostras abaixo continuam acessíveis.';
    }
  }
  document.addEventListener('DOMContentLoaded', load);
})();
