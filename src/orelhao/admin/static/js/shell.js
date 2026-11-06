// Comportamentos comuns do shell: menu móvel e confirmação de formulários.
document.documentElement.classList.add('js');
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.querySelector('.nav-toggle');
  const menu = document.getElementById('menu-principal');
  if (toggle && menu) {
    const setOpen = open => {
      menu.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', String(open));
    };
    toggle.addEventListener('click', () => setOpen(!menu.classList.contains('is-open')));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.classList.contains('is-open')) {
        setOpen(false);
        toggle.focus();
      }
    });
  }
  // Após um envio com erro, leva o foco à mensagem para que seja anunciada e vista.
  const error = document.querySelector('main .alert-bad');
  if (error) {
    error.tabIndex = -1;
    error.focus({preventScroll: true});
    error.scrollIntoView({block: 'center'});
  }
  // Formulários com data-guard avisam antes de sair com alterações não salvas.
  let dirty = false;
  for (const form of document.querySelectorAll('form[data-guard]')) {
    form.addEventListener('input', () => { dirty = true; });
    form.addEventListener('submit', () => { dirty = false; });
  }
  window.addEventListener('beforeunload', event => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = '';
  });
  // Formulários com data-busy mostram progresso e evitam envio duplo.
  for (const form of document.querySelectorAll('form[data-busy]')) {
    form.addEventListener('submit', () => {
      const button = form.querySelector('button[type="submit"]');
      if (!button) return;
      button.setAttribute('aria-busy', 'true');
      button.dataset.label = button.textContent;
      button.textContent = form.dataset.busy;
      setTimeout(() => { button.disabled = true; }, 0);
    });
  }
  // Ao voltar pelo histórico (bfcache), reabilita botões que ficaram em envio.
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    for (const button of document.querySelectorAll('button[aria-busy="true"]')) {
      button.disabled = false;
      button.removeAttribute('aria-busy');
      if (button.dataset.label) button.textContent = button.dataset.label;
    }
  });
});

// Utilitários compartilhados pelas telas (sem dependências externas).
window.orelhao = {
  number(value, digits = 1) {
    return Number.isFinite(value) ? value.toLocaleString('pt-BR', {maximumFractionDigits: digits}) : '—';
  },
  // Barra proporcional entre piso de ruído, limiar do VAD e pico RMS de UMA captura.
  // Escala linear relativa ao maior valor informado; não representa forma de onda.
  signal(root, metrics) {
    if (!root) return;
    const num = v => (v === null || v === undefined || v === '') ? NaN : Number(v);
    const peak = num(metrics && metrics.peak_rms);
    const noise = num(metrics && metrics.noise_floor);
    const threshold = num(metrics && (metrics.threshold ?? metrics.speech_threshold));
    const values = [peak, noise, threshold].filter(Number.isFinite);
    const fmt = v => Number.isFinite(v) ? v.toFixed(4) : '—';
    const part = sel => root.querySelector(sel);
    const legend = id => document.getElementById(id);
    if (!values.length) {
      root.setAttribute('aria-label', 'Sem medição de sinal disponível');
      part('.signal-peak').style.width = '0';
      for (const sel of ['.signal-noise', '.signal-threshold']) part(sel).hidden = true;
      return;
    }
    const scale = Math.max(...values) * 1.25;
    const pct = v => Math.max(0, Math.min(100, (v / scale) * 100)) + '%';
    part('.signal-peak').style.width = Number.isFinite(peak) ? pct(peak) : '0';
    const noiseMark = part('.signal-noise');
    noiseMark.hidden = !Number.isFinite(noise);
    if (!noiseMark.hidden) noiseMark.style.left = pct(noise);
    const thresholdMark = part('.signal-threshold');
    thresholdMark.hidden = !Number.isFinite(threshold);
    if (!thresholdMark.hidden) thresholdMark.style.left = pct(threshold);
    const verdict = Number.isFinite(peak) && Number.isFinite(threshold)
      ? (peak >= threshold ? 'pico acima do limiar do VAD' : 'pico abaixo do limiar do VAD') : '';
    root.setAttribute('aria-label', `Pico RMS ${fmt(peak)}, piso de ruído ${fmt(noise)}, limiar ${fmt(threshold)}${verdict ? '; ' + verdict : ''}`);
    if (root.id) {
      const set = (suffix, v) => { const el = legend(root.id + suffix); if (el) el.textContent = fmt(v); };
      set('-peak-value', peak); set('-noise-value', noise); set('-threshold-value', threshold);
    }
  }
};
