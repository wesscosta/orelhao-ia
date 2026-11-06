// Saúde da máquina: consulta /system/state a cada 5 s apenas com a aba visível.
(() => {
  const byId = id => document.getElementById(id);
  const number = v => Number.isFinite(v) ? v.toLocaleString('pt-BR', {maximumFractionDigits:1}) : '—';
  const storage = v => Number.isFinite(v) ? (v / 1073741824).toLocaleString('pt-BR', {maximumFractionDigits:1}) + ' GiB' : '—';
  const percent = (prefix, v) => {
    byId(prefix + '-percent').textContent = number(v);
    const width = Number.isFinite(v) ? Math.max(0, Math.min(100, v)) : 0;
    byId(prefix + '-percent-bar').style.width = width + '%';
    const meter = byId(prefix + '-percent-meter');
    meter.classList.toggle('is-high', width >= 90);
    meter.classList.toggle('is-mid', width >= 75 && width < 90);
  };
  const uptime = seconds => {
    if (!Number.isFinite(seconds)) return '—';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return [days ? days + 'd' : '', hours + 'h', minutes + 'min'].filter(Boolean).join(' ');
  };
  const SERVICE = {
    active: ['Ativo', 'ok'], inactive: ['Inativo', 'warn'], failed: ['Falha', 'bad'],
    activating: ['Iniciando', 'info'], deactivating: ['Parando', 'warn'], unknown: ['Indisponível', 'neutral']
  };
  const appendRow = (parent, name, value, tone) => {
    const tr = document.createElement('tr');
    const td1 = document.createElement('td');
    const td2 = document.createElement('td');
    td2.className = 'num';
    td1.textContent = name;
    if (tone) {
      const span = document.createElement('span');
      span.className = 'badge badge-' + tone;
      span.textContent = value;
      td2.append(span);
    } else {
      td2.textContent = value;
    }
    tr.append(td1, td2);
    parent.append(tr);
  };
  const fill = (id, records, render) => {
    const tbody = byId(id);
    tbody.replaceChildren();
    if (!records || !records.length) { appendRow(tbody, 'Sem dados disponíveis', '—'); return; }
    records.forEach(item => render(tbody, item));
  };
  const findTemp = (items, group) => {
    const matches = (items || []).filter(t => t.group === group);
    if (!matches.length) return null;
    const preferred = group === 'cpu'
      ? matches.find(t => /package|tctl|tdie/i.test(t.label))
      : matches.find(t => /composite/i.test(t.label));
    return (preferred || matches[0]).celsius;
  };
  function render(data) {
    percent('cpu', data.cpu.percent);
    percent('ram', data.memory.percent);
    percent('disk', data.disk.percent);
    byId('cpu-percent-detail').textContent =
      (data.cpu.logical_cores || '—') + ' processadores lógicos; carga 1 min: ' +
      (data.cpu.load_average.length ? number(data.cpu.load_average[0]) : '—');
    byId('ram-percent-detail').textContent = storage(data.memory.used_bytes) + ' de ' +
      storage(data.memory.total_bytes) + ' em uso';
    byId('disk-percent-detail').textContent = storage(data.disk.used_bytes) + ' de ' +
      storage(data.disk.total_bytes) + ' em uso';
    byId('cpu-temperature').textContent = number(findTemp(data.temperatures, 'cpu'));
    byId('ssd-temperature').textContent = number(findTemp(data.temperatures, 'ssd'));
    byId('uptime').textContent = uptime(data.uptime_seconds);
    byId('swap-detail').textContent = 'Swap: ' + storage(data.memory.swap_used_bytes) +
      ' de ' + storage(data.memory.swap_total_bytes);
    fill('temperature-rows', data.temperatures, (tbody, t) =>
      appendRow(tbody, (t.group === 'cpu' ? 'CPU: ' : 'SSD: ') + t.label, number(t.celsius) + ' °C'));
    fill('service-rows', data.services, (tbody, s) => {
      const [label, tone] = SERVICE[s.state] || SERVICE.unknown;
      appendRow(tbody, s.name, label, tone);
    });
    fill('process-rows', data.processes, (tbody, p) =>
      appendRow(tbody, p.name + (p.instances > 1 ? ' (' + p.instances + ')' : ''), storage(p.rss_bytes)));
    const time = Date.parse(data.sampled_at);
    byId('sample-time').textContent = Number.isFinite(time)
      ? 'Última leitura: ' + new Date(time).toLocaleTimeString('pt-BR') + '.' : '';
    const status = byId('system-status');
    status.className = 'badge badge-ok';
    status.textContent = 'Atualização ativa';
  }
  let busy = false;
  async function refresh() {
    if (busy || document.hidden) return;
    busy = true;
    try {
      const response = await fetch('/system/state', {cache:'no-store'});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      render(await response.json());
    } catch (_) {
      const status = byId('system-status');
      status.className = 'badge badge-bad';
      status.textContent = 'Sem comunicação; tentando reconectar';
    } finally {
      busy = false;
    }
  }
  document.addEventListener('DOMContentLoaded', () => {
    refresh();
    const interval = setInterval(refresh, 5000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    window.addEventListener('pagehide', () => clearInterval(interval), {once:true});
  });
})();
