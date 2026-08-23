# Voice input hardening — v0.3.3

A captura de áudio é isolada por padrão em um processo filho. Isso protege o processo principal contra aborts/segfaults nativos de ALSA/PortAudio.

## Estados de fala

`WAITING → SPEAKING → COMPLETE`

- WAITING exige uma sequência mínima de blocos de voz antes de iniciar a captura;
- ruídos/picos curtos são tratados como falsos inícios;
- SPEAKING tolera pausas naturais;
- COMPLETE ocorre somente após fala mínima válida seguida de silêncio contínuo.

## UX

A calibração acontece antes do aviso de fala. Em modo `capture_backend: process`, a CLI só imprime `Pode falar agora.` quando o processo filho já terminou a calibração.

## Configuração

- `capture_backend`: `process` (produção/recomendado) ou `sounddevice` (diagnóstico);
- `speech_start_timeout_seconds`: tempo máximo aguardando início de fala;
- `speech_start_min_ms`: voz contínua mínima para iniciar;
- `min_speech_ms`: quantidade mínima de voz válida;
- `false_start_silence_ms`: silêncio para descartar um falso início;
- `silence_ms`: silêncio contínuo para encerrar uma fala válida.
