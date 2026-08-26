# Orelhão IA

Terminal conversacional de voz **offline-first**, projetado para responder perguntas com base em uma fonte de conhecimento controlada.

O projeto não é acoplado a uma instituição ou domínio específico. A aplicação pode ser utilizada em diferentes cenários — atendimento institucional, orientação ao público, educação, eventos, serviços, suporte interno ou outros — conforme a base de conhecimento, configuração e integrações fornecidas à implantação.

## Estado atual — v0.6.0-alpha.4 em desenvolvimento

A baseline de voz v0.3.10 permanece estável. A v0.4 consolidou a camada de conhecimento/RAG com índice persistente local, recuperação híbrida, corpus versionado e interface administrativa local. A v0.5.0 encerrou a instrumentação objetiva do retrieval. A v0.6.0-alpha.1 mediu `semantic-only` local; a alpha.2 avaliou fusão lexical + semântica por ranking; a alpha.3 demonstrou que consenso, scores, margens e cobertura lexical não separam adequadamente respostas suportadas de documentos apenas relacionados. A alpha.4 introduz um gate experimental de answerability local, ainda sem promover o mecanismo.

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

A camada Knowledge mantém os contratos `Document`, `Chunk`, `SearchResult`, `KnowledgeRepository`, `Retriever`, `ContextBuilder` e `KnowledgeService`, acrescentando persistência local, recuperação híbrida lexical + hashing vetorial local, gestão do corpus, administração web e Evaluation Harness. A integração com uma LLM real permanece uma etapa posterior.

## Arquitetura alvo

O fluxo completo previsto é:

`voz → STT local → RAG → LLM local → TTS local → voz`

A base de conhecimento é uma dependência configurável da implantação, e não uma característica fixa do core.

A aplicação permanece um **monólito modular**, com contratos entre Core, Serviços, Interfaces, Hardware e Infraestrutura. Implementações específicas de STT, TTS, LLM, hardware ou base de conhecimento não devem contaminar a lógica central.

## Instalação de desenvolvimento

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,audio,stt,tts,vad,semantic,evidence]'
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

Estado validado antes do benchmark da v0.6.0-alpha.2:

```text
94 passed, 1 skipped
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

## Avaliação do retrieval

Reconstrua o índice e execute o dataset padrão:

```bash
orelhao knowledge index
orelhao knowledge evaluate
```

Baseline final no dataset de 40 casos em pt-BR:

- Hit@1: `0.633`;
- Hit@4: `0.800`;
- MRR: `0.703`;
- acurácia de abstenção: `0.600`;
- latência média observada nesta execução: aproximadamente `2.04 ms`.

## Experimento semântico da v0.6

A implementação experimental utiliza `intfloat/multilingual-e5-small` em ONNX, com revisão fixada, e mantém pesos e índices somente no ambiente local. Provisione uma vez com rede; a indexação e a avaliação seguintes funcionam offline:

```bash
orelhao knowledge semantic-provision
orelhao knowledge semantic-index
orelhao knowledge evaluate --retriever semantic --json
```

Resultados semantic-only no mesmo dataset:

- sem threshold: Hit@1 `0.867`, Hit@4 `0.900`, MRR `0.878` e abstenção `0.000`;
- candidato `min_score=0.852`: Hit@1 `0.833`, Hit@4 `0.833`, MRR `0.833` e abstenção `0.600`;
- latência média aproximada: `33–36 ms`;
- pico de memória observado: aproximadamente `772 MiB`;
- modelo local: `241 MiB`.

O candidato melhorou ranking e preservou a abstenção da baseline, mas não foi promovido devido ao custo operacional e ao risco de calibração sobre o mesmo dataset.

Fusão RRF medida na alpha.2:

```bash
orelhao knowledge evaluate --retriever fusion --json
```

A fusão utiliza os gates `0.40` da baseline e `0.852` do semântico e combina apenas posições. No benchmark, obteve Hit@1 `0.833`, Hit@4 `0.933`, MRR `0.872`, abstenção `0.500` e latência aproximada de `34–36 ms`. Embora tenha melhorado recall e ranking, não foi promovida porque degradou a abstenção em relação à baseline e ao semantic-only calibrado.

Diagnóstico por caso da alpha.3:

```bash
orelhao knowledge evaluate --retriever baseline --diagnostics --json > /tmp/baseline-details.json
orelhao knowledge evaluate --retriever semantic --min-score 0.852 --diagnostics --json > /tmp/semantic-details.json
orelhao knowledge evaluate --retriever fusion --diagnostics --json > /tmp/fusion-details.json
```

A saída preserva as métricas agregadas e acrescenta `results`, contendo consulta, expectativa, fontes, scores, posição relevante e resultado correto/incorreto. Cada resultado também inclui `matches` com identificador, documento, posição, texto e metadados do chunk. Esse diagnóstico não modifica ranking ou abstenção.

## Evidence gate experimental da v0.6.0-alpha.4

O gate usa QA extrativa para estimar se cada chunk contém uma resposta extraível. Ele é aplicado depois da fusão e não altera o ranking dos candidatos preservados. Provisione o artefato ONNX int8 uma vez:

```bash
pip install -e '.[semantic,evidence]'
orelhao knowledge evidence-provision
```

Execute o A/B no dataset congelado:

```bash
orelhao knowledge evaluate --retriever fusion --json
orelhao knowledge evaluate --retriever evidence --evidence-min-score 0.50 --json
```

`0.50` é somente o ponto inicial do experimento. O modelo, o gate e o threshold não são padrão de produção e precisam ser comparados quanto a recall, ranking, abstenção, latência, memória e tamanho local.
Com `--diagnostics`, o metadado `evidence_support` registra o suporte estimado de cada chunk preservado. Use threshold `0.0` para observar a distribuição antes de selecionar um candidato.

Fluxo futuro preservado:

`pergunta transcrita → recuperação (RAG) → contexto → LLM local → resposta → TTS`

A implementação deve preservar o funcionamento offline-first. O próximo incremento deve diagnosticar os casos divergentes antes de experimentar um gate de consenso/confiança; não haverá tuning adicional de RRF nesta etapa.

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
