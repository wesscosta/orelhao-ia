# Audio Engine — v0.1

> **ATUALIZAÇÃO OPERACIONAL — 29/10/2026.** Os trechos marcados v0.1/v0.2/v0.3 são HISTÓRICOS. Hoje o backend de captura usado no benchmark é PipeWire/`pw-record`, com VAD `webrtc`, 16 kHz mono no pipeline e configuração de silêncio em `1800ms`. `RMS` permanece como fallback/diagnóstico. A homologação no monofone físico e a sessão de voz completa com RAG/LLM continuam pendentes. Consulte [Entrada de voz](voice-input.md) e [Estado vigente](current-state.md).

## Objetivo
Validar o caminho físico de voz antes de adicionar STT, LLM ou RAG reais.

## Formato de referência
- PCM16 little-endian;
- mono;
- 16 kHz;
- blocos de 30 ms.

## VAD atual
A v0.1 usa um detector por RMS/energia. É propositalmente simples para medir microfone, ruído e níveis do monofone. Não deve ser interpretado como decisão definitiva para produção.

Parâmetros configuráveis:
- `rms_threshold`;
- `pre_roll_ms`;
- `silence_ms`;
- `max_record_seconds`;
- dispositivo de entrada/saída.

## Teste de bancada
1. Listar interfaces: `orelhao --list-audio-devices`.
2. Selecionar input/output em `config/development.yaml` quando necessário.
3. Executar `orelhao --audio-loopback`.
4. Falar em volume normal.
5. Verificar se o início da frase não é cortado e se a captura encerra após o silêncio.
6. Repetir em ambiente silencioso e com ruído representativo.

## Métricas a registrar
- nível RMS em silêncio;
- nível RMS durante fala;
- threshold escolhido;
- falsos disparos;
- cortes no início/fim;
- duração média capturada;
- falhas/overflows de dispositivo.

## Taxa nativa do hardware
O pipeline interno utiliza 16 kHz mono PCM16, mas a interface física pode operar em 44,1 ou 48 kHz. A partir da v0.2.1, a aplicação consulta automaticamente a taxa nativa anunciada pelo PortAudio/ALSA, captura nessa taxa e reamostra para 16 kHz. Na reprodução, faz o caminho inverso quando necessário. Isso evita `PaErrorCode -9997 (Invalid sample rate)` em dispositivos `hw:*`.


## Backend de captura PipeWire (v0.3.4)

Em produção/desenvolvimento Linux, `audio.capture_backend: pipewire` usa `pw-record` em modo raw PCM16. Isso remove PortAudio do caminho crítico de captura e evita que erros nativos de ALSA/JACK corrompam o processo Python.

Por padrão o PipeWire escolhe a fonte de entrada ativa. Para fixar uma fonte específica, configure `audio.pipewire_target` com o `node.name` ou `object.serial` aceito por `pw-record --target`.


### PipeWire capture implementation

Production capture uses `pw-record` to a temporary RAW PCM16 file. The application tails that file in blocks while the recorder is active, preserving real-time VAD without routing native audio through Python stdout/PortAudio.
