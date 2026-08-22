# Orelhão IA

Terminal conversacional offline-first para atendimento por voz baseado em conteúdo institucional do Senac.

## Estado atual — v0.2.0

Pipeline implementado nesta etapa:

`microfone → VAD → STT local → texto`

A v0.1 validou fisicamente captura, VAD e reprodução. A v0.2 adiciona transcrição local real e métricas para começarmos a medir o workload da máquina.

RAG, LLM e TTS permanecem desacoplados/mocados no pipeline principal e serão ativados por etapas posteriores.

## Instalação de desenvolvimento

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,audio,stt]'
```

## Áudio

```bash
orelhao --list-audio-devices
orelhao --audio-loopback
```

## STT local

```bash
orelhao --stt-test
```

A primeira execução do modelo configurado por nome pode exigir internet para download. O terminal de produção será provisionado com os pesos locais e não dependerá desse download.

Veja `docs/stt.md`.

## Testes

```bash
pytest -q
```

## Arquitetura

A aplicação permanece um monólito modular com contratos entre Core, Serviços, Interfaces, Hardware e Infraestrutura. Touch é apenas uma extensão futura e não faz parte do MVP.
