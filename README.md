# Orelhão IA

Terminal conversacional de voz **offline-first**, projetado para responder perguntas com base em uma fonte de conhecimento controlada.

O projeto não é acoplado a uma instituição ou domínio específico. A aplicação pode ser utilizada em diferentes cenários — atendimento institucional, orientação ao público, educação, eventos, serviços, suporte interno ou outros — conforme a base de conhecimento, configuração e integrações fornecidas à implantação.

## Estado atual — v0.6.0-alpha.12.1 em desenvolvimento

A baseline de voz v0.3.10 permanece estável. A v0.4 consolidou a camada de conhecimento/RAG com índice persistente local, recuperação híbrida, corpus versionado e interface administrativa local. A v0.5.0 encerrou a instrumentação objetiva do retrieval. A v0.6.0-alpha.1 mediu `semantic-only` local; a alpha.2 avaliou fusão lexical + semântica por ranking; a alpha.3 produziu diagnósticos por caso. A alpha.4 rejeitou a promoção do primeiro gate de answerability ponta a ponta. A alpha.5 separou a avaliação de evidência e identificou boa ordenação, mas scores mal calibrados. A alpha.6 mediu generalização em holdout categorizado. A alpha.7 rejeitou FP32 por ganho insuficiente diante do custo. A alpha.8 rejeitou mDeBERTa-v3 INT8 na calibração. A alpha.9 mediu grounding factual por NLI. A alpha.10 confirmou a generalização em holdout próprio. A alpha.11 formalizou a decisão em três estados. A alpha.12 integra essa decisão à bancada administrativa em modo observação, sem bloquear respostas.

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
pip install -e '.[dev,admin,audio,stt,tts,vad,semantic,evidence]'
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

## Gate de evidência — resultado da v0.6.0-alpha.4

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

No dataset de retrieval, o threshold `0.50` obteve Hit@1/Hit@4/MRR `0.533`, abstenção `1.000` e latência média aproximada de `228 ms`. O processo atingiu aproximadamente `1.30 GiB` de RAM e o modelo ocupa cerca de `283 MiB`. A varredura posterior não encontrou threshold que preservasse recall e abstenção simultaneamente. O gate e o modelo não foram promovidos.
Com `--diagnostics`, o metadado `evidence_support` registra o suporte estimado de cada chunk preservado. Use threshold `0.0` para observar a distribuição antes de selecionar um candidato.

## Benchmark de answerability da v0.6.0-alpha.5

O benchmark separado mede diretamente se um chunk contém resposta para uma pergunta. Ele não executa retrieval e não modifica `retrieval-v1.json`:

```bash
orelhao knowledge evidence-evaluate --json
orelhao knowledge evidence-evaluate --threshold 0.50 --diagnostics --json
```

O dataset `evidence-v1.json` contém 40 pares pt-BR balanceados. Cada caso referencia um `chunk_id` reconstruível do índice e declara `answerable`. O relatório inclui acurácia balanceada, precisão, recall, especificidade, F1, ROC AUC e latência. `--model-dir` permite avaliar outro modelo ONNX compatível no mesmo conjunto.

Este primeiro dataset serve para desenvolvimento e calibração. A promoção de um modelo exige confirmação em um conjunto independente, evitando selecionar modelo e threshold sobre os mesmos exemplos.

## Holdout categorizado da v0.6.0-alpha.6

O holdout `evidence-v2-holdout.json` contém 40 consultas inéditas: 20 respondíveis e 20 não respondíveis. Os negativos distinguem ausência de atualidade, entidade incorreta e informação específica ausente. Execute exatamente as três políticas congeladas:

```bash
for policy in initial conservative balanced; do
  orelhao knowledge evidence-evaluate \
    knowledge/evaluation/evidence-v2-holdout.json \
    --threshold-policy "$policy" \
    --diagnostics \
    --json \
    > "/tmp/orelhao-evidence-holdout-${policy}.json"
done
```

As políticas são `initial=0.50`, `conservative=0.69740408` e `balanced=0.00016509`. Elas foram definidas antes da execução no holdout e não devem ser recalibradas nesse conjunto. O relatório inclui métricas agregadas e `category_metrics`.

Quando a decisão for abster, `EvidenceDecision` representa o motivo sem delegar a decisão à LLM. A mensagem pt-BR informa ausência de evidência suficiente, específica, atualizada ou compatível com a entidade solicitada. A LLM futura poderá apenas verbalizar essa decisão estruturada.

## Ablação de precisão da v0.6.0-alpha.7

INT8 contém a arquitetura completa quantizada; não é uma fração do modelo. Para medir isoladamente o efeito da quantização, a alpha.7 permite manter INT8 e FP32 lado a lado:

```bash
orelhao knowledge evidence-provision --variant fp32
orelhao knowledge evidence-evaluate --model-variant fp32 --diagnostics --json
```

INT8 continua sendo o padrão. A comparação deve usar os mesmos datasets e registrar ROC AUC, métricas por categoria, latência, pico de memória e tamanho do artefato. Um threshold escolhido em `evidence-v1.json` deve ser congelado antes de qualquer avaliação confirmatória; `evidence-v2-holdout.json` não deve ser reutilizado para calibrar FP32.

No holdout, a ROC AUC FP32 foi `0.907`, praticamente igual à INT8 (`0.905`). FP32 balanced elevou recall para `0.900`, mas reduziu especificidade para `0.750`; o conservative preservou especificidade `1.000`, mas recall caiu para `0.400`. Com aproximadamente `2.155 MiB` de RAM e artefato de `1.059 MiB`, FP32 foi rejeitado.

## Candidato mDeBERTa da v0.6.0-alpha.8

A alpha.8 testa somente `mdeberta-v3-base-squad2` em ONNX INT8, sem alterar o padrão:

```bash
orelhao knowledge evidence-provision --model mdeberta-v3
orelhao knowledge evidence-evaluate \
  knowledge/evaluation/evidence-v1.json \
  --model mdeberta-v3 --diagnostics --json
```

O candidato usa arquitetura multilíngue diferente e foi treinado com casos sem resposta. O primeiro objetivo é comparar ROC AUC, distribuição dos scores, categorias, latência, memória e tamanho contra XLM-RoBERTa INT8. Thresholds serão calibrados somente em `evidence-v1.json` e congelados antes do holdout.

Resultado: o mDeBERTa-v3 INT8 obteve ROC AUC `0.875`, acurácia balanceada `0.800`, especificidade `0.800`, latência média `263.21 ms` e artefato de `302.3 MiB`. O XLM-RoBERTa INT8 obteve ROC AUC `0.943`, acurácia balanceada `0.825`, especificidade `1.000`, latência média `125.23 ms` e `265.7 MiB` na mesma rodada. O candidato foi rejeitado antes do holdout.

## Grounding factual por NLI da v0.6.0-alpha.9

A alpha.9 separa uma nova tarefa: verificar se uma passagem implica uma afirmação factual. O candidato inicial é `multilingual-MiniLMv2-L6-mnli-xnli`, treinado em MNLI/XNLI e executado localmente em ONNX. A passagem é a premissa; a afirmação é a hipótese; o score é a probabilidade da classe `entailment`.

```bash
orelhao knowledge evidence-provision --model nli-minilm --variant fp32
orelhao knowledge evidence-evaluate \
  knowledge/evaluation/grounding-v1.json \
  --model nli-minilm \
  --model-variant fp32 \
  --threshold 0.5 \
  --diagnostics --json
```

`grounding-v1.json` possui 20 afirmações suportadas e 20 não suportadas. Ele é somente de desenvolvimento e calibração. `evidence-v2-holdout.json` não será usado porque mede outra tarefa. Nenhum gate será integrado antes de congelar threshold, confirmar em holdout próprio e medir custo.

Na calibração, o NLI obteve ROC AUC `0.973`, latência média `9.14 ms`, pico de memória de aproximadamente `1.139 MiB` e artefato de `408.3 MiB`. As políticas foram congeladas como `nli-balanced=0.1250362694` e `nli-conservative=0.7557643056`.

## Holdout NLI da v0.6.0-alpha.10

`grounding-v2-holdout.json` contém 40 afirmações inéditas: 20 suportadas e 20 não suportadas. Os negativos são divididos igualmente entre contradição, incompatibilidade de entidade, informação específica ausente e temporalidade.

```bash
for policy in nli-balanced nli-conservative; do
  orelhao knowledge evidence-evaluate \
    knowledge/evaluation/grounding-v2-holdout.json \
    --model nli-minilm \
    --model-variant fp32 \
    --threshold-policy "$policy" \
    --diagnostics --json \
    > "/tmp/orelhao-grounding-holdout-${policy}.json"
done
```

Cada categoria agora expõe `applicable_metric` e `applicable_score`: recall para categorias positivas, especificidade para categorias negativas e acurácia balanceada somente quando a categoria contém ambas as classes. O holdout não será usado para calibrar um terceiro threshold.

No holdout, a ROC AUC foi `0.965`. A política balanced obteve acurácia balanceada `0.900`, recall `0.850` e especificidade `0.950`; a conservative obteve `0.775`, recall `0.550` e especificidade `1.000`. Contradição, informação específica e temporalidade mantiveram especificidade `1.000`; entidade ficou em `0.800` na balanced e `1.000` na conservative.

## GroundingDecision da v0.6.0-alpha.11

O contrato de decisão usa os dois limites congelados sem criar um terceiro threshold:

- score `>= 0.7557643056`: `supported`;
- score `< 0.1250362694`: `unsupported`;
- intervalo intermediário: `uncertain`.

Somente `supported` permite resposta. `unsupported` e `uncertain` exigem abstenção no MVP. Em avaliações NLI, o JSON inclui `grounding_policy`, `grounding_summary` e `grounding_decision` por caso quando `--diagnostics` está ativo. Esta etapa não conecta o contrato ao retrieval ou à LLM.

Fluxo futuro preservado:

`pergunta transcrita → recuperação (RAG) → contexto → LLM local → resposta → TTS`

A implementação deve preservar o funcionamento offline-first. Não haverá tuning adicional de RRF nesta etapa.

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
