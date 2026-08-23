# TTS local — v0.3.0

## Objetivo
Fechar o ciclo local `fala → STT → texto → TTS → áudio`, sem LLM/RAG nesta etapa.

## Backend
A implementação usa Piper por processo local, atrás de `TTSService`. O binário e o modelo devem ser provisionados previamente na appliance. Não há dependência de rede durante a síntese.

## Testes manuais
```bash
orelhao --tts-test "Olá, eu sou o assistente virtual do Senac."
orelhao --voice-test
```

## Critério de aceite
- síntese em português com modelo local provisionado;
- reprodução pelo Audio Engine;
- métricas de tempo de síntese e RTF;
- `voice-test` executa captura → STT → TTS → playback;
- nenhuma API externa no caminho crítico.

## Observação de áudio
A v0.3 aumenta `silence_ms` para 1600 ms, reduzindo cortes em pausas naturais observados na validação da v0.2.2. A homologação final do VAD será feita com o transdutor do monofone.


## Provisionamento da voz PT-BR

A referência atual é `pt_BR-cadu-medium`, uma voz Piper de qualidade medium. Os pesos não são versionados no Git.

```bash
pip install -e '.[tts]'
orelhao --tts-provision
orelhao --tts-test "Olá, eu sou o assistente virtual do Senac."
```

O provisionamento baixa o `.onnx`, o `.onnx.json` e o `MODEL_CARD`. Em produção, esse passo ocorre antes da instalação; a síntese não depende de internet.

## Dispositivos de áudio

Índices PortAudio podem mudar após reboot/hotplug. Para a appliance, configure entrada/saída por nome estável. Use `orelhao --list-audio-devices` e copie o nome do dispositivo desejado para `input_device`/`output_device`.
