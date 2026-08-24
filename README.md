# Orelhão IA

Terminal conversacional de voz **offline-first**, projetado para responder perguntas com base em uma fonte de conhecimento controlada.

O projeto não é acoplado a uma instituição ou domínio específico. A aplicação pode ser utilizada em diferentes cenários — atendimento institucional, orientação ao público, educação, eventos, serviços, suporte interno ou outros — conforme a base de conhecimento, configuração e integrações fornecidas à implantação.

## Estado atual — v0.4.0-alpha.4

A baseline de voz v0.3.10 permanece estável. A v0.4.0-alpha.4 consolida a camada de conhecimento/RAG com índice persistente local, recuperação híbrida, corpus versionado e interface administrativa local.

Pipeline de voz já validado:

`microfone → captura/VAD → STT local → texto → TTS local → reprodução`

A versão v0.3.10 estabiliza a captura de áudio via PipeWire, detecção de início e fim de fala, transcrição local em português e síntese/reprodução local de voz.

Estado validado:

- captura primária via `pw-record`/PipeWire;
- `sounddevice` mantido como fallback e ferramenta de diagnóstico;
- VAD com tolerância a pausas naturais e ruído ambiente;
- STT local com `faster-whisper`;
- configuração de reconhecimento em português com contexto voltado a português brasileiro;
- TTS local com Piper;
- provisionamento local do modelo de voz;
- diagnóstico e seleção de dispositivos de áudio;
- pipeline de voz `STT → TTS` funcional;
- 40 testes automatizados passando na v0.3.10.

A alpha.4 mantém os contratos `Document`, `Chunk`, `SearchResult`, `KnowledgeRepository`, `Retriever`, `ContextBuilder` e `KnowledgeService`, acrescentando persistência local, recuperação híbrida lexical + hashing vetorial local, gestão do corpus e administração web. A integração com uma LLM real permanece uma etapa posterior.

## Arquitetura alvo

O fluxo completo previsto é:

`voz → STT local → RAG → LLM local → TTS local → voz`

A base de conhecimento é uma dependência configurável da implantação, e não uma característica fixa do core.

A aplicação permanece um **monólito modular**, com contratos entre Core, Serviços, Interfaces, Hardware e Infraestrutura. Implementações específicas de STT, TTS, LLM, hardware ou base de conhecimento não devem contaminar a lógica central.

## Instalação de desenvolvimento

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,audio,stt,tts,vad]'
```

## Diagnóstico de áudio

Liste os dispositivos disponíveis:

```bash
orelhao --list-audio-devices
```

Valide a configuração selecionada:

```bash
orelhao --audio-diagnose
```

Para a captura principal, o projeto utiliza PipeWire quando disponível.

## STT local

Teste somente reconhecimento de fala:

```bash
orelhao --stt-test
```

O STT utiliza `faster-whisper`. Modelos configurados por nome podem exigir download durante o provisionamento inicial. Uma instalação de produção deve manter os pesos necessários localmente.

## TTS local

Provisione a voz configurada:

```bash
orelhao --tts-provision
```

Teste a síntese:

```bash
orelhao --tts-test "Olá. Este é um teste de síntese de voz."
```

O backend atual utiliza Piper e mantém o modelo provisionado localmente.

## Teste ponta a ponta de voz

```bash
orelhao --voice-test
```

O teste executa captura, detecção de fala, STT, TTS e reprodução local.

As métricas exibidas permitem observar, entre outros dados:

- sample rate de captura e pipeline;
- nível de ruído;
- threshold de detecção;
- pico de áudio;
- motivo do encerramento da captura;
- falsos inícios;
- overflows;
- latência de STT;
- latência e RTF do TTS.

O encerramento normal de uma fala deve ocorrer por `fim=silence`. `max_duration` e timeouts são mecanismos de proteção, não o comportamento esperado para uma interação normal.

## Testes automatizados

```bash
pytest
```

Baseline validada da v0.3.10:

```text
40 passed
```

## Princípios de implantação

O Orelhão IA é **offline-first**: o caminho crítico da conversa deve funcionar sem depender de serviços externos.

A rede pode ser utilizada para funções auxiliares, como:

- atualização controlada da base de conhecimento;
- atualização autorizada de software ou modelos;
- telemetria;
- manutenção;
- integrações opcionais.

A indisponibilidade da rede não deve impedir uma conversa quando os modelos e a base necessários estiverem provisionados localmente.

## Base de conhecimento

O conteúdo respondido pelo terminal deve ser determinado pela base configurada para cada implantação.

Exemplos possíveis:

- informações institucionais;
- catálogo de produtos ou serviços;
- cursos e programas educacionais;
- documentação técnica;
- orientação em eventos;
- procedimentos internos;
- FAQs e atendimento ao público.

Essa separação é intencional: **Orelhão IA é a plataforma conversacional; a base define o domínio da aplicação.**

## Próxima etapa

A próxima etapa da série v0.4 é substituir a recuperação lexical de baseline por embeddings e índice vetorial local, preservando os mesmos contratos:

`pergunta transcrita → recuperação (RAG) → contexto → LLM local → resposta → TTS`

A implementação deve preservar o funcionamento offline-first e manter RAG e LLM substituíveis por meio de contratos internos.

## Escopo futuro

Após RAG e LLM, permanecem previstas etapas como:

- integração com controlador físico/gancho;
- integração com monofone;
- benchmarks completos de CPU/GPU/RAM/VRAM e latência;
- dimensionamento do hardware definitivo;
- integração física;
- operação como appliance;
- health checks, watchdog e recuperação automática;
- homologação e piloto.

Interface touch é uma extensão possível, mas não é dependência do fluxo de voz.


## Smoke test do RAG — v0.4.0-alpha.4

```bash
orelhao --rag-test "como funciona a base de conhecimento?"
```

Esse comando usa uma base em memória deliberadamente pequena e determinística. O objetivo é validar ingestão, chunking, ranking e construção de contexto sem baixar modelos adicionais.


## Administração da base

A partir da v0.4.0-alpha.3, a base pode ser administrada por uma interface web local:

```bash
pip install -e '.[admin]'
orelhao admin
```

A interface abre por padrão em `http://127.0.0.1:8765` e manipula apenas
`knowledge/sources/`. O índice é derivado e pode ser reconstruído pela própria
interface ou com `orelhao knowledge index`.
