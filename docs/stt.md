# STT local — v0.2

## Objetivo
A v0.2 substitui o mock de Speech-to-Text por uma implementação local usando `faster-whisper`/CTranslate2, preservando o contrato de serviço para permitir troca futura do backend.

## Pipeline validado nesta etapa

`microfone → Audio Engine → VAD → PCM16 16 kHz mono → faster-whisper → texto + métricas`

O VAD continua sendo executado pelo Audio Engine. O VAD interno do Whisper fica desativado nesta etapa para evitar duas políticas concorrentes de corte de fala.

## Desenvolvimento

Instalação:

```bash
pip install -e '.[dev,audio,stt]'
```

Teste com microfone:

```bash
orelhao --stt-test
```

Teste com arquivo WAV PCM16 mono 16 kHz:

```bash
orelhao --stt-file arquivo.wav
```

## Modelo
Em desenvolvimento, `model: small` pode ser resolvido pelo faster-whisper e baixado na primeira utilização. Depois do download, ele permanece em cache.

Em produção offline, **não depender de download**. O modelo deve ser provisionado previamente e `stt.model` deve apontar para um caminho local, por exemplo:

```yaml
stt:
  model: /opt/models/whisper-small
```

## CPU e GPU
A configuração expõe `device` e `compute_type`. Para a primeira medição, usamos `auto/default` para obter uma baseline funcional. Depois dos primeiros resultados vamos fixar combinações explícitas e comparar:

- CPU + int8;
- GPU + float16;
- eventualmente GPU + int8_float16, quando fizer sentido no hardware alvo.

Não otimize antes de medir.

## Métricas
Cada transcrição retorna:

- texto;
- duração do áudio;
- tempo de processamento;
- RTF (real-time factor);
- idioma detectado;
- probabilidade do idioma;
- quantidade de segmentos.

### RTF
`RTF = tempo de STT / duração do áudio`

- RTF < 1: processamento mais rápido que tempo real;
- RTF = 1: processamento no mesmo tempo do áudio;
- RTF > 1: mais lento que tempo real.

Para uma experiência conversacional, queremos margem confortável abaixo de 1 e, idealmente, tempo de STT bem menor que a duração da fala.

## Critério de aceite v0.2
- capturar fala real com o Audio Engine já validado;
- transcrever português localmente;
- não depender de API de nuvem;
- exibir tempo de STT e RTF;
- manter testes automatizados passando;
- permitir execução em CPU e GPU por configuração.
