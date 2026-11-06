// Auditoria agregada: tabelas montadas com textContent a partir de /audit/summary.
(() => {
  const byId = id => document.getElementById(id);
  const numeric = v => Number.isFinite(Number(v)) ? Number(v) : 0;
  const fmt = n => new Intl.NumberFormat('pt-BR').format(numeric(n));
  const clear = id => { byId(id).replaceChildren(); };
  function message(id, value) {
    const p = document.createElement('p'); p.className = 'small muted';
    p.textContent = value; byId(id).append(p);
  }
  function table(id, headers, items, numericCols = [1]) {
    clear(id);
    if (!items.length) { message(id, 'Ainda não há registros para este período.'); return; }
    const wrap = document.createElement('div'); wrap.className = 'table-wrap';
    const t = document.createElement('table'); const head = document.createElement('thead');
    const hr = document.createElement('tr');
    headers.forEach((h, i) => {
      const th = document.createElement('th'); th.scope = 'col'; th.textContent = h;
      if (numericCols.includes(i)) th.className = 'num';
      hr.append(th);
    });
    head.append(hr); t.append(head);
    const body = document.createElement('tbody');
    for (const item of items) {
      const tr = document.createElement('tr');
      item.forEach((value, i) => {
        const td = document.createElement('td');
        td.textContent = String(value ?? '—');
        if (numericCols.includes(i)) td.className = 'num';
        tr.append(td);
      });
      body.append(tr);
    }
    t.append(body); wrap.append(t); byId(id).append(wrap);
  }
  const LATENCY = {capture: 'Captura', stt: 'STT', rag: 'RAG / LLM / verificação', tts: 'TTS', play: 'Reprodução', overflows: 'Overflows registrados'};
  let pending;
  async function refresh() {
    const days = Number(byId('period').value);
    byId('export').href = '/audit/events.csv?days=' + days;
    byId('audit-status').textContent = 'Consultando auditoria…';
    // Troca rápida de período: cancelar a consulta anterior para que uma
    // resposta antiga não sobrescreva os números do período selecionado.
    if (pending) pending.abort();
    const controller = pending = new AbortController();
    try {
      const res = await fetch('/audit/summary?days=' + days, {cache:'no-store', signal: controller.signal});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (controller !== pending) return;
      clear('overview');
      const cards = [
        ['Atendimentos', data.sessions], ['Perguntas reconhecidas', data.questions],
        ['Transcrições rejeitadas', data.stt_invalid],
        ['Capturas sem fala', data.capture_without_speech],
        ['Respostas sem evidência', data.abstentions], ['Erros de execução', data.errors]
      ];
      for (const [label, count] of cards) {
        const section = document.createElement('div'); section.className = 'stat';
        const title = document.createElement('p'); title.className = 'stat-label'; title.textContent = label;
        const n = document.createElement('p'); n.className = 'stat-value'; n.textContent = fmt(count);
        section.append(title, n); byId('overview').append(section);
      }
      for (const [id, list] of [
        ['topics', data.topics], ['questions', data.questions_top],
        ['stt', data.stt_failures], ['routes', data.answer_routes]
      ]) table(id, ['Classificação', 'Ocorrências'], (list || []).map(r => [r.label, fmt(r.count)]));
      table('latency', ['Etapa / métrica', 'Média'], Object.entries(data.latency_ms || {})
        .map(([k, v]) => [LATENCY[k] || k,
          v == null ? '—' : (k === 'overflows' ? fmt(v) : fmt(v) + ' ms')]));
      byId('audit-status').textContent = 'Resumo do período atualizado às ' + new Date().toLocaleTimeString('pt-BR') + '.';
    } catch (e) {
      if (e.name === 'AbortError' || controller !== pending) return;
      byId('audit-status').textContent = 'Não foi possível carregar a auditoria (' + e.message + '). Recarregue a página para tentar de novo.';
    }
  }
  async function backupList() {
    try {
      const res = await fetch('/audit/backups', {cache:'no-store'});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      clear('backups');
      if (!data.files || !data.files.length) {
        message('backups', 'Nenhum backup encontrado no diretório configurado (ORELHAO_BACKUP_DIR).'); return;
      }
      const rows = data.files.map(entry => [entry.name, (Number(entry.bytes) / 1024 / 1024).toLocaleString('pt-BR', {maximumFractionDigits: 1}) + ' MB']);
      table('backups', ['Arquivo', 'Tamanho', 'Download'], rows.map(r => [...r, '']), [1]);
      const cells = byId('backups').querySelectorAll('tbody tr');
      data.files.forEach((entry, i) => {
        const a = document.createElement('a');
        a.className = 'btn btn-small';
        a.href = '/audit/backups/' + encodeURIComponent(entry.name);
        a.textContent = 'Baixar';
        a.setAttribute('aria-label', 'Baixar ' + entry.name);
        cells[i].lastElementChild.append(a);
      });
    } catch (e) { clear('backups'); message('backups', 'Falha ao listar backups (' + e.message + ').'); }
  }
  document.addEventListener('DOMContentLoaded', () => {
    byId('period').addEventListener('change', refresh);
    refresh(); backupList();
  });
})();
