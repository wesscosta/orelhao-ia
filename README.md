# Orelhão IA — v0.1

Base do MVP do **Orelhão IA Senac**, projetada como appliance offline-first.

## Estado desta versão

A v0.1 inaugura o **Audio Engine real**. O core de IA continua desacoplado e os serviços STT/RAG/LLM/TTS ainda usam mocks no pipeline padrão.

### Implementado

- monólito modular;
- máquina de estados com validação de transições;
- contratos de captura e playback;
- áudio PCM16/WAV;
- captura real via dispositivo de áudio;
- VAD local por energia com pre-roll e parada por silêncio;
- reprodução real via dispositivo de áudio;
- comando de loopback para validar microfone/monofone;
- Resource Manager inicial;
- testes unitários, integração e áudio;
- `.venv` excluído do projeto/versionamento.

Fluxo alvo do MVP:

`gancho -> áudio -> STT -> RAG -> LLM -> TTS -> áudio`

Nesta versão, o que já pode ser validado em hardware é:

`microfone -> captura PCM16 -> VAD -> reprodução`

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,audio]'
```

Em Linux, o `sounddevice` depende da infraestrutura de áudio do sistema (ALSA/PipeWire/PortAudio).

## Comandos

Pipeline mock, sem exigir hardware de áudio:

```bash
orelhao
```

Listar dispositivos de áudio:

```bash
orelhao --list-audio-devices
```

Teste real de captura + VAD + reprodução:

```bash
orelhao --audio-loopback
```

Ajuste `config/development.yaml` para threshold, silêncio, duração e dispositivos.

## Testes

```bash
pytest
ruff check src tests
```

## Critério de aceite da v0.1

- captura estável em PCM16 mono 16 kHz;
- detecção de fala sem cortes relevantes;
- encerramento por silêncio;
- reprodução sem travamento;
- funcionamento repetível no dispositivo de áudio escolhido;
- latência e threshold registrados para o ambiente de bancada.

## Próxima etapa — v0.2

**STT local real.** Integrar um engine de transcrição offline mantendo a interface `STTService` e medir precisão/latência em português com o áudio capturado pela v0.1.

A escolha do engine/modelo será feita por benchmark, sem acoplar o core a um fornecedor específico.
