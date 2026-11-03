"""Painel compacto de telemetria do Dell, sem captura nem inferência adicionais."""

SYSTEM_BODY = """
<section class="card" aria-labelledby="system-title">
  <div style="display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap">
    <div>
      <h2 id="system-title" style="margin:0">Saúde do Servidor</h2>
      <p class="muted" style="margin:.4rem 0 0">CPU, memória, temperaturas, disco e serviços do Orelhão IA.</p>
    </div>
    <span id="system-status" class="pill" role="status">Coletando dados…</span>
  </div>
  <p class="muted" style="font-size:.86rem">Leitura local a cada 5 segundos, sem gravação de histórico.
    <span id="sample-time">—</span></p>
  <div class="system-grid">
    <section class="system-tile" aria-label="Uso do processador">
      <h3>Processador</h3>
      <p class="system-value"><span id="cpu-percent">—</span><small> %</small></p>
      <div class="system-bar" aria-hidden="true"><div id="cpu-bar"></div></div>
      <p id="cpu-detail" class="muted">Calculando uso entre duas leituras…</p>
    </section>
    <section class="system-tile" aria-label="Memória RAM">
      <h3>Memória RAM</h3>
      <p class="system-value"><span id="ram-percent">—</span><small> %</small></p>
      <div class="system-bar" aria-hidden="true"><div id="ram-bar"></div></div>
      <p id="ram-detail" class="muted">—</p>
    </section>
    <section class="system-tile" aria-label="Armazenamento">
      <h3>Disco do sistema</h3>
      <p class="system-value"><span id="disk-percent">—</span><small> %</small></p>
      <div class="system-bar" aria-hidden="true"><div id="disk-bar"></div></div>
      <p id="disk-detail" class="muted">—</p>
    </section>
    <section class="system-tile" aria-label="Temperatura do processador">
      <h3>Temperatura CPU</h3>
      <p class="system-value"><span id="cpu-temperature">—</span><small> °C</small></p>
      <p class="muted">Sensor térmico do processador, quando disponível.</p>
    </section>
    <section class="system-tile" aria-label="Temperatura do armazenamento">
      <h3>Temperatura SSD</h3>
      <p class="system-value"><span id="ssd-temperature">—</span><small> °C</small></p>
      <p class="muted">Sensor NVMe, quando disponível.</p>
    </section>
    <section class="system-tile" aria-label="Tempo ligado">
      <h3>Tempo ligado</h3>
      <p class="system-value" style="font-size:1.6rem" id="uptime">—</p>
      <p id="swap-detail" class="muted">Swap —</p>
    </section>
  </div>
  <div class="grid">
    <section class="card" aria-labelledby="sensors-title">
      <h3 id="sensors-title">Sensores térmicos</h3>
      <table><thead><tr><th>Sensor</th><th>Temperatura</th></tr></thead>
        <tbody id="temperature-rows"><tr><td colspan="2">Aguardando leitura…</td></tr></tbody>
      </table>
    </section>
    <section class="card" aria-labelledby="services-title">
      <h3 id="services-title">Serviços e processos</h3>
      <table><thead><tr><th>Componente</th><th>Estado</th></tr></thead>
        <tbody id="service-rows"><tr><td colspan="2">Aguardando leitura…</td></tr></tbody>
      </table>
      <p class="muted" style="margin-top:1rem">Memória dos processos essenciais</p>
      <table><thead><tr><th>Processo</th><th>RAM</th></tr></thead>
        <tbody id="process-rows"><tr><td colspan="2">Aguardando leitura…</td></tr></tbody>
      </table>
    </section>
  </div>
  <p class="muted"><small>Monitor somente leitura. CPU calculada entre amostras, RAM usada
    exclui cache recuperável; leituras térmicas dependem dos sensores expostos pelo kernel.
    O estado dos serviços não substitui testes de áudio/STT. Sem GPU dedicada detectável,
    a temperatura gráfica não é exibida. A interface deve permanecer em loopback/túnel SSH.</small></p>
</section>
<style>
.system-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:.9rem;margin-top:1.1rem}
.system-tile {border:1px solid #d1d5db;border-radius:10px;padding:1rem;min-width:0}
.system-tile h3 {margin:0;font-size:1rem}
.system-value {font-size:2rem;font-weight:700;margin:.8rem 0;letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.system-value small {font-size:1rem;font-weight:400}
.system-tile .muted {font-size:.84rem;line-height:1.4}
.system-bar {height:8px;background:#e5e7eb;border-radius:50px;overflow:hidden}
.system-bar div {height:100%;width:0;background:#0f766e;transition:width .35s}
.system-state {font-size:.88rem;font-weight:600}
.system-state.active {color:#047857}
.system-state.failed {color:#b91c1c}
.system-state.unknown {color:#6b7280}
#temperature-rows td:last-child, #service-rows td:last-child, #process-rows td:last-child {text-align:right;font-variant-numeric:tabular-nums}
@media (prefers-reduced-motion: reduce) {.system-bar div {transition:none}}
</style>
<script>
(() => {
  const byId = id => document.getElementById(id);
  const number = v => Number.isFinite(v) ? v.toLocaleString('pt-BR', {maximumFractionDigits:1}) : '—';
  const storage = v => Number.isFinite(v) ? (v / 1073741824).toLocaleString('pt-BR', {maximumFractionDigits:1}) + ' GiB' : '—';
  const percent = (prefix, v) => {
    byId(prefix + '-percent').textContent = number(v);
    byId(prefix + '-bar').style.width = Number.isFinite(v) ? Math.max(0,Math.min(100,v)) + '%' : '0%';
  };
  const uptime = seconds => {
    if (!Number.isFinite(seconds)) return '—';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return [days ? days + 'd' : '', hours + 'h', minutes + 'min'].filter(Boolean).join(' ');
  };
  const appendRow = (parent, name, value, css) => {
    const tr = document.createElement('tr');
    const td1 = document.createElement('td');
    const td2 = document.createElement('td');
    td1.textContent = name;
    td2.textContent = value;
    if (css) td2.className = 'system-state ' + css;
    tr.append(td1,td2);
    parent.append(tr);
  };
  const fill = (id, records, render) => {
    const tbody = byId(id);
    tbody.replaceChildren();
    if (!records || !records.length) {
      appendRow(tbody, 'Sem dados disponíveis', '—');
      return;
    }
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
    byId('cpu-detail').textContent =
      (data.cpu.logical_cores || '—') + ' processadores lógicos · carga 1 min: ' +
      (data.cpu.load_average.length ? number(data.cpu.load_average[0]) : '—');
    byId('ram-detail').textContent = storage(data.memory.used_bytes) + ' de ' +
      storage(data.memory.total_bytes) + ' utilizados';
    byId('disk-detail').textContent = storage(data.disk.used_bytes) + ' de ' +
      storage(data.disk.total_bytes) + ' utilizados';
    byId('cpu-temperature').textContent = number(findTemp(data.temperatures, 'cpu'));
    byId('ssd-temperature').textContent = number(findTemp(data.temperatures, 'ssd'));
    byId('uptime').textContent = uptime(data.uptime_seconds);
    byId('swap-detail').textContent = 'Swap: ' + storage(data.memory.swap_used_bytes) +
      ' de ' + storage(data.memory.swap_total_bytes);
    fill('temperature-rows', data.temperatures, (tbody,t) =>
      appendRow(tbody, (t.group === 'cpu' ? 'CPU · ' : 'SSD · ') + t.label, number(t.celsius) + ' °C'));
    fill('service-rows', data.services, (tbody,s) =>
      appendRow(tbody, s.name, s.state === 'active' ? 'Ativo' :
        s.state === 'inactive' ? 'Inativo' :
        s.state === 'failed' ? 'Falha' : 'Indisponível',
        s.state === 'active' ? 'active' : s.state === 'unknown' ? 'unknown' : 'failed'));
    fill('process-rows', data.processes, (tbody,p) =>
      appendRow(tbody, p.name + (p.instances > 1 ? ' (' + p.instances + ')' : ''),
        storage(p.rss_bytes)));
    const time = Date.parse(data.sampled_at);
    byId('sample-time').textContent = Number.isFinite(time)
      ? 'Última leitura: ' + new Date(time).toLocaleTimeString('pt-BR') : '';
    byId('system-status').textContent = 'Atualização ativa · somente leitura';
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
      byId('system-status').textContent = 'Sem comunicação · tentando reconectar';
    } finally {
      busy = false;
    }
  }
  refresh();
  const interval = setInterval(refresh, 5000);
  document.addEventListener('visibilitychange', () => {if (!document.hidden) refresh();});
  window.addEventListener('pagehide', () => clearInterval(interval), {once:true});
})();
</script>
""";
