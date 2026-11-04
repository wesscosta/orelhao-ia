"""Painel administrativo simples, sem bibliotecas externas ou HTML de logs."""
AUDIT_BODY = """
<section class="card">
  <h2>Auditoria de atendimentos</h2>
  <p>Informações agregadas para melhorar o reconhecimento de voz, a base de
     conhecimento e as respostas do Lumi. Não armazena gravações de áudio.</p>
  <label for="period">Período</label>
  <select id="period" style="max-width:180px">
    <option value="7">Últimos 7 dias</option>
    <option value="30" selected>Últimos 30 dias</option>
    <option value="90">Últimos 90 dias</option>
  </select>
  <p><a id="export" href="/audit/events.csv?days=30">Exportar eventos (CSV)</a></p>
  <p id="audit-status" role="status" class="muted">Carregando dados...</p>
  <div id="overview" class="grid" aria-label="Indicadores do período"></div>
</section>
<div class="grid">
  <section class="card"><h3>Assuntos mais frequentes</h3><div id="topics"></div></section>
  <section class="card"><h3>Perguntas recorrentes (opt-in)</h3><div id="questions"></div>
    <p class="muted"><small>Aparecem somente se a coleta de frases foi habilitada
    e se não contiverem indicadores de dados pessoais.</small></p></section>
  <section class="card"><h3>Falhas de reconhecimento de fala</h3>
    <div id="stt"></div></section>
  <section class="card"><h3>Origem das respostas</h3><div id="routes"></div></section>
</div>
<section class="card">
  <h3>Tempo médio por etapa</h3>
  <div id="latency"></div>
  <p class="muted">Valores agregados das etapas registradas.
  Falhas sem transcrição não são necessariamente erros do Whisper:
  podem decorrer de silêncio, ruído ou microfone com baixo ganho.</p>
</section>
<section class="card">
  <h2>Backups disponíveis</h2>
  <p>Arquivos já criados, em armazenamento local. O painel não cria backups automaticamente.</p>
  <div id="backups"></div>
  <p class="muted"><small>Os downloads são restritos à sessão autenticada e ao acesso local.
    Arquivos completos podem incluir modelos, configurações e dados de conhecimento.</small></p>
</section>
<script>
(() => {
  const byId = id => document.getElementById(id);
  const numeric = v => Number.isFinite(Number(v)) ? Number(v) : 0;
  const fmt = n => new Intl.NumberFormat('pt-BR').format(numeric(n));
  const clear = id => { byId(id).replaceChildren(); };
  function message(id, value) {
    const p = document.createElement('p'); p.className = 'muted';
    p.textContent = value; byId(id).append(p);
  }
  function table(id, headers, items) {
    clear(id);
    if (!items.length) { message(id, 'Ainda não há registros para este período.'); return; }
    const t = document.createElement('table'); const head = document.createElement('thead');
    const hr = document.createElement('tr');
    for (const h of headers) { const th = document.createElement('th'); th.textContent = h; hr.append(th); }
    head.append(hr); t.append(head);
    const body = document.createElement('tbody');
    for (const item of items) {
      const tr = document.createElement('tr');
      for (const value of item) {
        const td = document.createElement('td');
        td.textContent = String(value ?? '—'); tr.append(td);
      }
      body.append(tr);
    }
    t.append(body); byId(id).append(t);
  }
  async function refresh() {
    const days = Number(byId('period').value);
    byId('export').href = '/audit/events.csv?days=' + days;
    byId('audit-status').textContent = 'Consultando auditoria...';
    try {
      const res = await fetch('/audit/summary?days=' + days, {cache:'no-store'});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      clear('overview');
      const cards = [
        ['Atendimentos', data.sessions], ['Perguntas reconhecidas', data.questions],
        ['Transcrições rejeitadas', data.stt_invalid],
        ['Capturas sem fala', data.capture_without_speech],
        ['Respostas sem evidência', data.abstentions], ['Erros de execução', data.errors]
      ];
      for (const [label, count] of cards) {
        const section = document.createElement('div'); section.className = 'card';
        const title = document.createElement('strong'); title.textContent = label;
        const n = document.createElement('p'); n.textContent = fmt(count); n.style.fontSize = '1.8rem';
        n.style.margin = '.4rem 0'; section.append(title, n); byId('overview').append(section);
      }
      for (const [id, list] of [
        ['topics', data.topics], ['questions', data.questions_top],
        ['stt', data.stt_failures], ['routes', data.answer_routes]
      ]) table(id, ['Classificação', 'Ocorrências'],
                (list || []).map(r => [r.label, fmt(r.count)]));
      table('latency', ['Etapa / métrica', 'Valor'], Object.entries(data.latency_ms || {})
        .map(([k,v]) => [k === 'overflows' ? 'Overflows registrados' : k.toUpperCase(),
          v == null ? '—' : (k === 'overflows' ? fmt(v) : fmt(v) + ' ms')]));
      byId('audit-status').textContent = 'Resumo do período atualizado.';
    } catch (e) {
      byId('audit-status').textContent = 'Não foi possível carregar: ' + e.message;
    }
  }
  async function backupList() {
    try {
      const res = await fetch('/audit/backups', {cache:'no-store'});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      clear('backups');
      if (!data.files || !data.files.length) {
        message('backups', 'Nenhum backup localizado no diretório configurado.'); return;
      }
      const ul = document.createElement('ul');
      for (const entry of data.files) {
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = '/audit/backups/' + encodeURIComponent(entry.name);
        a.textContent = entry.name;
        li.append(a, document.createTextNode(' (' +
          (Number(entry.bytes) / 1024 / 1024).toFixed(1) + ' MB)'));
        ul.append(li);
      }
      byId('backups').append(ul);
    } catch (e) { clear('backups'); message('backups', 'Falha ao listar backups.'); }
  }
  byId('period').addEventListener('change', refresh);
  refresh(); backupList();
})();
</script>
""";
