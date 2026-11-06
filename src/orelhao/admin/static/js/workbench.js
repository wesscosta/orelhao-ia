// Bancada de testes: estado dos serviços, gravação local (WAV PCM16) e síntese de voz.
(() => {
  const byId = id => document.getElementById(id);
  const setState = (el, tone, text) => {
    if (!el) return;
    el.className = 'badge badge-' + tone;
    el.textContent = text;
  };

  function initForm() {
    const recordButton = byId('record');
    if (!recordButton) return;
    const statusBox = byId('voice-status');
    const runButton = byId('run');
    const llmBadge = byId('llm-badge');
    const llmDetail = byId('llm-status');
    const sttBadge = byId('stt-badge');
    const ttsBadge = byId('tts-badge');
    const ttsDetail = byId('tts-status');
    const voiceSelector = byId('voice');
    const previewVoiceButton = byId('preview-voice');
    let previewAudio = null;

    async function updateTtsStatus() {
      setState(ttsBadge, 'neutral', 'Verificando');
      try {
        const response = await fetch('/workbench/tts-status?voice=' + encodeURIComponent(voiceSelector.value));
        const payload = await response.json();
        setState(ttsBadge, payload.available ? 'ok' : 'bad', payload.available ? 'Pronta' : 'Indisponível');
        ttsDetail.textContent = payload.detail;
      } catch (error) {
        setState(ttsBadge, 'bad', 'Sem resposta');
        ttsDetail.textContent = 'Não foi possível verificar a voz: ' + error.message;
      }
    }
    voiceSelector.addEventListener('change', updateTtsStatus);
    updateTtsStatus();

    previewVoiceButton.addEventListener('click', async () => {
      previewVoiceButton.disabled = true;
      previewVoiceButton.setAttribute('aria-busy', 'true');
      try {
        const url = '/workbench/voice-preview?voice=' + encodeURIComponent(voiceSelector.value);
        const response = await fetch(url);
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || 'Falha HTTP ' + response.status);
        }
        if (previewAudio) previewAudio.pause();
        previewAudio = new Audio(URL.createObjectURL(await response.blob()));
        previewAudio.onended = () => URL.revokeObjectURL(previewAudio.src);
        await previewAudio.play();
        ttsDetail.textContent = 'Reproduzindo apresentação com ' + voiceSelector.selectedOptions[0].text + '.';
      } catch (error) {
        ttsDetail.textContent = 'Não foi possível ouvir a voz: ' + error.message;
      } finally {
        previewVoiceButton.disabled = false;
        previewVoiceButton.removeAttribute('aria-busy');
      }
    });

    let llmAttempts = 0;
    async function updateLlmStatus() {
      try {
        const response = await fetch('/workbench/llm-status');
        const payload = await response.json();
        if (payload.available) {
          runButton.disabled = false;
          setState(llmBadge, 'ok', 'Pronta');
          llmDetail.textContent = payload.detail;
          return;
        }
        setState(llmBadge, 'bad', 'Indisponível');
        llmDetail.textContent = payload.detail + ' Nova verificação automática em instantes.';
      } catch (error) {
        setState(llmBadge, 'bad', 'Sem resposta');
        llmDetail.textContent = 'Falha ao consultar a LLM: ' + error.message;
      }
      // Recuo progressivo para não pressionar o servidor local.
      llmAttempts += 1;
      setTimeout(updateLlmStatus, Math.min(15000, 2000 * llmAttempts));
    }
    updateLlmStatus();

    let sttAttempts = 0;
    async function updateSttStatus() {
      let payload;
      try {
        const response = await fetch('/workbench/stt-status', {cache: 'no-store'});
        if (!response.ok) throw new Error('HTTP ' + response.status);
        payload = await response.json();
      } catch (error) {
        // Falha transitória (reinício do Admin): continuar consultando com recuo.
        sttAttempts += 1;
        setState(sttBadge, 'warn', 'Sem resposta');
        statusBox.textContent = 'Não foi possível consultar o STT (' + error.message + '). Nova tentativa em instantes.';
        setTimeout(updateSttStatus, Math.min(15000, 1000 * 2 ** Math.min(sttAttempts, 4)));
        return;
      }
      sttAttempts = 0;
      if (payload.status === 'ready') {
        recordButton.disabled = false;
        recordButton.textContent = 'Gravar pergunta';
        setState(sttBadge, 'ok', 'Pronto');
        statusBox.textContent = `Modelo carregado em ${payload.elapsed_ms.toFixed(1)} ms. O microfone envia WAV PCM16 ao STT local.`;
        return;
      }
      if (payload.status === 'error') {
        setState(sttBadge, 'bad', 'Falhou');
        statusBox.textContent = `Falha ao carregar o STT: ${payload.error}`;
        return;
      }
      setState(sttBadge, 'info', 'Carregando');
      setTimeout(updateSttStatus, 1000);
    }
    updateSttStatus();

    let audioContext, processor, source, stream, samples = [], stopTimer;
    async function stopRecording() {
      if (!processor) return;
      // Liberar as referências antes do await: um clique durante o auto-stop
      // não pode encerrar o AudioContext nem transcrever duas vezes.
      const context = audioContext, node = processor;
      processor = null; audioContext = null;
      clearTimeout(stopTimer);
      node.disconnect(); source.disconnect();
      stream.getTracks().forEach(track => track.stop());
      const inputRate = context.sampleRate;
      await context.close();
      recordButton.textContent = 'Gravar pergunta';
      recordButton.setAttribute('aria-pressed', 'false');
      statusBox.textContent = 'Transcrevendo. O primeiro uso também carrega o modelo STT…';
      const wav = encodeWav(resample(concatenate(samples), inputRate, 16000), 16000);
      const form = new FormData();
      form.append('file', wav, 'question.wav');
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 90000);
      try {
        const response = await fetch('/workbench/transcribe', {method: 'POST', body: form, signal: controller.signal});
        const payload = await response.json();
        if (!response.ok) { statusBox.textContent = payload.detail || 'Falha no STT'; return; }
        byId('question').value = payload.text;
        statusBox.textContent = `Transcrição concluída em ${payload.total_ms.toFixed(1)} ms. Revise o texto antes de executar.`;
        byId('question').focus();
      } catch (error) {
        statusBox.textContent = error.name === 'AbortError'
          ? 'O STT excedeu 90 segundos. Aguarde o carregamento do modelo e tente novamente.'
          : `Falha ao enviar áudio: ${error.message}`;
      } finally { clearTimeout(timeout); }
    }
    recordButton.addEventListener('click', async () => {
      if (processor) { await stopRecording(); return; }
      try {
        stream = await navigator.mediaDevices.getUserMedia({audio: true});
      } catch (error) {
        statusBox.textContent = 'O navegador não liberou o microfone: ' + error.message;
        return;
      }
      audioContext = new AudioContext();
      source = audioContext.createMediaStreamSource(stream);
      processor = audioContext.createScriptProcessor(4096, 1, 1);
      samples = [];
      processor.onaudioprocess = event => samples.push(Array.from(event.inputBuffer.getChannelData(0)));
      source.connect(processor); processor.connect(audioContext.destination);
      stopTimer = setTimeout(stopRecording, 12000);
      recordButton.textContent = 'Parar gravação';
      recordButton.setAttribute('aria-pressed', 'true');
      statusBox.textContent = 'Gravando. A gravação para sozinha em 12 segundos.';
    });
  }

  function concatenate(blocks) {
    const length = blocks.reduce((total, block) => total + block.length, 0);
    const output = new Float32Array(length);
    let offset = 0;
    blocks.forEach(block => { output.set(block, offset); offset += block.length; });
    return output;
  }
  function resample(input, fromRate, toRate) {
    if (fromRate === toRate) return input;
    const ratio = fromRate / toRate, output = new Array(Math.round(input.length / ratio));
    for (let i = 0; i < output.length; i++) {
      const position = i * ratio, left = Math.floor(position), right = Math.min(left + 1, input.length - 1);
      output[i] = input[left] + (input[right] - input[left]) * (position - left);
    }
    return output;
  }
  function encodeWav(input, sampleRate) {
    const buffer = new ArrayBuffer(44 + input.length * 2), view = new DataView(buffer);
    const write = (offset, value) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
    write(0, 'RIFF'); view.setUint32(4, 36 + input.length * 2, true); write(8, 'WAVE');
    write(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
    view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    write(36, 'data'); view.setUint32(40, input.length * 2, true);
    input.forEach((sample, index) => view.setInt16(44 + index * 2, Math.max(-1, Math.min(1, sample)) * (sample < 0 ? 32768 : 32767), true));
    return new Blob([view], {type: 'audio/wav'});
  }

  function initSpeech() {
    const button = byId('speak-answer');
    if (!button) return;
    const player = byId('spoken-answer');
    const status = byId('spoken-status');
    const voice = byId('result-voice');
    const speechUrl = button.dataset.speechUrl;
    let currentUrl = null;
    button.addEventListener('click', async () => {
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      status.textContent = 'Gerando áudio com ' + voice.selectedOptions[0].text + '…';
      try {
        const response = await fetch(speechUrl + '?voice=' + encodeURIComponent(voice.value));
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || 'Falha HTTP ' + response.status);
        }
        if (currentUrl) URL.revokeObjectURL(currentUrl);
        currentUrl = URL.createObjectURL(await response.blob());
        player.src = currentUrl;
        player.hidden = false;
        try {
          await player.play();
          status.textContent = 'Reproduzindo a resposta.';
        } catch (_) {
          status.textContent = 'Áudio pronto. Use o botão de reprodução do player.';
        }
      } catch (error) {
        status.textContent = 'Não foi possível gerar o áudio: ' + error.message;
      } finally {
        button.disabled = false;
        button.removeAttribute('aria-busy');
      }
    });
    window.addEventListener('pagehide', () => { if (currentUrl) URL.revokeObjectURL(currentUrl); });
  }

  document.addEventListener('DOMContentLoaded', () => { initForm(); initSpeech(); });
})();
