# STT local — faster-whisper em português

**Revisão: 29/10/2026.** O STT foi introduzido na v0.2 e continua sendo um componente da bancada de voz. Consulte [estado vigente](current-state.md), [entrada de áudio](voice-input.md) e [hardware](hardware.md).

## Pipeline de reconhecimento

`microfone → PipeWire/VAD → PCM16 mono 16 kHz → faster-whisper → transcrição + métricas`.

O projeto mantém VAD externo ao Whisper para evitar regras concorrentes de corte. A configuração experimental de pt-BR utiliza `stt.backend: faster-whisper`, `model: small`, `language: pt`, CPU e `compute_type: int8` no arquivo de benchmark. As escolhas devem ser confirmadas no Dell i5-7500T / 8GB; resultados no Arch não substituem sua aferição.

## Testes

```bash
pip install -e '.[dev,audio,stt]'
orelhao --list-audio-devices
orelhao --audio-diagnose
orelhao --stt-test
orelhao --stt-file arquivo.wav
orelhao --voice-test
```

`--stt-file` espera WAV mono PCM16 a 16 kHz. O primeiro carregamento de um modelo por nome pode exigir download; na implantação offline, utilizar pesos previamente provisionados por caminho local.

## Métricas e aceitação

Registrar tempo de transcrição, duração do áudio, RTF (tempo STT dividido por duração), idioma e segmentação. Medir sotaques, ruídos, nomes próprios, números, início/fim de fala e quantidade de falsos disparos. `RTF < 1` é objetivo de desempenho, não prova de qualidade de transcrição.

A integração automática `gancho → STT → RAG → LLM → TTS` e o teste físico pelo monofone **ainda não estão homologados**. Não depender de APIs externas durante o atendimento.
