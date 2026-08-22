# Changelog

## 0.2.2
- Substitui o encerramento por threshold fixo por VAD adaptativo com calibração de noise floor.
- Separa timeout aguardando fala, silêncio pós-fala e duração máxima de segurança.
- Adiciona diagnósticos de captura: noise floor, threshold, motivo de encerramento e overflows.
- Adiciona `--audio-diagnose` para validar os dispositivos configurados.
- Adiciona fallback explícito para CPU INT8 quando GPU/CUDA está visível mas o runtime está incompleto.
- Mantém captura na taxa nativa do hardware e pipeline interno em 16 kHz.

## 0.2.1
- Corrige captura ALSA em interfaces que não aceitam 16 kHz diretamente.
- Detecta automaticamente o sample rate nativo de entrada/saída.
- Normaliza áudio para 16 kHz no pipeline usando resampling local.
- Reamostra saída para a taxa nativa antes da reprodução.

## 0.2.0
- STT local real com faster-whisper/CTranslate2.
- Resultado estruturado de transcrição e métricas de latência/RTF.
- CLI `--stt-test` para microfone e `--stt-file` para WAV.
- Configuração de modelo, idioma, device e compute type.
- Estratégia explícita de provisionamento offline do modelo.
- Testes unitários do contrato STT e conversão PCM16.
- Mantido Audio Engine + VAD validados na v0.1.

## 0.1.0
- Captura e reprodução de áudio reais.
- PCM16 mono 16 kHz.
- VAD local por energia com pre-roll e encerramento por silêncio.
- Listagem de dispositivos e loopback de áudio.
