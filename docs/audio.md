# Audio Engine — v0.1

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
