# Entrada de voz e endurecimento da captura

**Revisão: 29/10/2026.** A documentação abaixo distingue o legado da v0.3.3 da configuração vigente. Consulte [áudio](audio.md), [STT](stt.md) e [estado técnico](current-state.md).

## Estados de captura

`WAITING → SPEAKING → COMPLETE`

- WAITING exige fala contínua mínima antes de iniciar, descartando picos breves;
- SPEAKING mantém a captura enquanto detecta fala, com tolerância a pausas;
- COMPLETE decorre de uma fala válida seguida de silêncio contínuo ou de um limite de proteção.

## Configuração vigente no desenvolvimento

A configuração `config/benchmark-tucano2-15b-ptbr.yaml` usa `audio.capture_backend: pipewire`, `pw-record`, VAD `webrtc`, `silence_ms: 1800`, calibração de `700ms`, `speech_start_timeout_seconds: 12`, `min_speech_ms: 360` e amostragem interna 16 kHz, mono. O PortAudio/`sounddevice` pode permanecer como recurso de diagnóstico ou fallback. Para conferir a instalação: `orelhao --audio-diagnose` e `orelhao --stt-test`.

## Histórico v0.3.3

A etapa inicial utilizava `capture_backend: process` para isolar a captura nativa em processo filho, reduzindo risco de falha ALSA/PortAudio. Essa orientação não é a configuração PipeWire recomendada atualmente. O aviso `Pode falar agora` depende de preparação/calibração do capturador.

## Gate físico pendente

O VAD ainda não foi homologado no monofone original, no gabinete fechado, com gancho e ruído do ambiente. Testes com microfone do navegador não equivalem a ensaio do hardware final.
