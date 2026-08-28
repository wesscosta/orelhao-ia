# RAG / Knowledge — baseline v0.5.0 e experimento v0.6

A camada de conhecimento é independente do domínio da implantação e opera localmente no caminho crítico.

## Implementação consolidada

O fluxo atual é:

`fontes Markdown/TXT → ingestão e chunking → índice persistente → retrieval híbrido lexical/hash → threshold → contexto ou abstenção`

A fonte autoritativa fica em `knowledge/sources/`. O diretório `knowledge/index/` contém somente artefatos derivados e reconstruíveis.

O corpo do documento é a evidência principal. Título, categoria, caminho e metadados atuam somente como sinais auxiliares. O mecanismo não contém regras específicas de uma instituição ou implantação.

## Evaluation Harness

A v0.5.0 congela a primeira baseline reproduzível do retrieval. O comando padrão é:

```bash
orelhao knowledge index
orelhao knowledge evaluate
```

Para automação ou comparação A/B:

```bash
orelhao knowledge evaluate --json
```

Também é possível informar outro dataset JSON como argumento posicional.

O dataset `knowledge/evaluation/retrieval-v1.json` utiliza português brasileiro e contém 40 casos:

- 30 consultas positivas;
- 10 consultas que exigem abstenção;
- intenções institucionais, cursos, atendimento, PSG, aprendizagem, empregabilidade, biblioteca, empresas e contrato do aluno;
- perguntas fora do domínio;
- perguntas relacionadas ao domínio cuja resposta não está presente ou atualizada no corpus.

As fontes esperadas ou aceitáveis são declaradas explicitamente por caso. O dataset de avaliação não faz parte do índice de produção.

## Baseline final da v0.5.0

Corpus avaliado: 14 documentos e 23 chunks. Configuração: `limit=4` e `min_score=0.40`.

| Métrica | Resultado |
| --- | ---: |
| Hit@1 | 0.633 |
| Hit@4 | 0.800 |
| MRR | 0.703 |
| Acurácia de abstenção | 0.600 |
| Latência média observada | 2.04 ms |

A latência depende do hardware e deve ser comparada no mesmo ambiente. As métricas de qualidade são determinísticas para o mesmo corpus, índice, dataset e configuração.

## Limitações registradas

- há fontes relevantes recuperadas abaixo da primeira posição;
- algumas paráfrases coloquiais não atingem o threshold;
- perguntas sobre informações atuais ou ausentes ainda podem recuperar documentos apenas relacionados ao assunto;
- a abstenção é o principal ponto de atenção da próxima evolução.

Essas limitações formam a baseline; não devem ser corrigidas com exceções específicas para perguntas do benchmark.

## Experimento semantic-only da v0.6.0-alpha.1

A v0.6.0-alpha.1 introduz um retriever semântico local isolado e mantém o baseline disponível para comparação. O modelo `intfloat/multilingual-e5-small`, na revisão ONNX fixada pelo código, é provisionado uma única vez:

```bash
pip install -e '.[semantic]'
orelhao knowledge semantic-provision
orelhao knowledge semantic-index
orelhao knowledge evaluate --retriever semantic --json
```

O runtime de indexação e busca carrega somente arquivos locais. `semantic-vectors.npy` e `semantic-manifest.json` são reconstruíveis e vinculados ao hash dos mesmos chunks usados pela baseline.

Resultados no dataset congelado da v0.5:

| Configuração | Hit@1 | Hit@4 | MRR | Abstenção |
| --- | ---: | ---: | ---: | ---: |
| Semantic-only, `0.0` | 0.867 | 0.900 | 0.878 | 0.000 |
| Semantic-only, `0.852` | 0.833 | 0.833 | 0.833 | 0.600 |

O candidato `0.852` foi obtido por varredura sistemática e deve ser tratado como provisório, pois calibração e avaliação utilizam o mesmo dataset. A latência média ficou em aproximadamente `33–36 ms`, o pico de memória em cerca de `772 MiB` e o modelo local em `241 MiB`. O mecanismo não foi promovido como padrão.

## Experimento de fusão da v0.6.0-alpha.2

A alpha.2 combina as listas já filtradas da baseline (`0.40`) e do semântico (`0.852`) por Reciprocal Rank Fusion, com constante `60`. O método usa somente posições e não presume equivalência entre scores.

```bash
orelhao knowledge evaluate --retriever fusion --json
```

Não há pesos treinados, regras específicas do benchmark ou confidence gate. A fusão permanece experimental até comparação A/B no mesmo corpus, índice e dataset.

Resultado medido:

| Configuração | Hit@1 | Hit@4 | MRR | Abstenção | Latência média |
| --- | ---: | ---: | ---: | ---: | ---: |
| RRF, baseline `0.40` + semântico `0.852` | 0.833 | 0.933 | 0.872 | 0.500 | 34–36 ms |

O pico de memória permaneceu em aproximadamente `772 MiB`, pois o custo dominante continua sendo o modelo semântico. A fusão recuperou mais fontes relevantes e melhorou o ranking, mas a união das listas permitiu um falso positivo adicional em casos de abstenção. Como houve regressão de `0.600` para `0.500`, o mecanismo não foi promovido.

O próximo incremento deve expor os casos divergentes do benchmark e testar uma política de gate isolada, sem alterar simultaneamente RRF, thresholds ou corpus. A promoção continua exigindo ganho A/B sem regressão relevante de ranking, abstenção, latência, memória ou operação offline.

## Diagnóstico da v0.6.0-alpha.3

O Evaluation Harness pode expor o resultado individual dos casos sem alterar o retriever:

```bash
orelhao knowledge evaluate --retriever baseline --diagnostics --json
orelhao knowledge evaluate --retriever semantic --min-score 0.852 --diagnostics --json
orelhao knowledge evaluate --retriever fusion --diagnostics --json
```

Cada item informa fontes e scores retornados, posição da fonte esperada e se o comportamento foi correto. O campo `matches` inclui identificador, documento, posição, texto e metadados de cada chunk recuperado. Dataset, corpus, thresholds e RRF permanecem congelados. A política de gate será escolhida somente após a comparação dessas divergências.

## Evidence gate experimental da v0.6.0-alpha.4

Os diagnósticos demonstraram que consenso, score, margem e cobertura lexical não separam os casos suportados dos documentos apenas relacionados. A alpha.4 testa QA extrativa com capacidade de indicar ausência de resposta:

```text
baseline + semântico → RRF → EvidenceVerifier por chunk → ranking preservado ou abstenção
```

O candidato é `onnx-community/xlm-roberta-base-squad2-distilled-ONNX`, revisão fixa, usando apenas `model_int8.onnx`. O provisionamento baixa aproximadamente 279 MB; tokenizer, pesos e execução permanecem locais:

```bash
pip install -e '.[semantic,evidence]'
orelhao knowledge evidence-provision
orelhao knowledge evaluate --retriever evidence --evidence-min-score 0.50 --json
```

O mecanismo não corrige as falhas conhecidas de recall para missão e telefone geral; esta etapa mede isoladamente suporte da evidência e abstenção. Nenhum threshold deve ser promovido sem varredura sistemática e avaliação A/B completa.
Nos diagnósticos, chunks preservados recebem o metadado efêmero `evidence_support`. Uma execução com threshold `0.0` permite inspecionar toda a distribuição sem filtrar candidatos.

### Resultado

O threshold `0.50` elevou a abstenção para `1.000`, mas reduziu Hit@1, Hit@4 e MRR para `0.533`. A latência média foi de aproximadamente `228 ms`, o pico de memória ficou em aproximadamente `1.30 GiB` e o modelo local ocupa cerca de `283 MiB`. Thresholds próximos de zero também eliminaram chunks positivos legítimos. O candidato foi rejeitado para promoção.

## Benchmark de answerability da v0.6.0-alpha.5

`retrieval-v1.json` mede se o mecanismo recupera uma fonte aceitável. Ele não determina se cada chunk individual contém a resposta. A alpha.5 introduz `evidence-v1.json` para medir essa segunda tarefa isoladamente:

```bash
orelhao knowledge evidence-evaluate --json
orelhao knowledge evidence-evaluate --threshold 0.50 --diagnostics --json
```

O dataset contém 20 pares respondíveis e 20 não respondíveis em pt-BR. Os casos referenciam chunks do índice por ID, evitando duplicar o texto do corpus. O comando falha explicitamente se uma referência deixar de existir após reconstrução do índice.

Métricas: acurácia, acurácia balanceada, precisão, recall, especificidade, F1, ROC AUC e latência média por par. A ROC AUC permite comparar ordenação dos scores sem fixar antecipadamente um threshold. O argumento `--model-dir` permite avaliar candidatos locais compatíveis usando exatamente os mesmos pares.

`evidence-v1.json` é um conjunto de desenvolvimento/calibração. Um modelo não deve ser promovido sem validação posterior em casos independentes e sem novo A/B ponta a ponta no benchmark congelado de retrieval.

## Holdout da v0.6.0-alpha.6

O dataset `evidence-v2-holdout.json` congela 40 pares inéditos e balanceados. Nenhuma consulta de `evidence-v1.json` foi reutilizada. As categorias permitem distinguir capacidade extrativa de limitações temporais, incompatibilidade de entidade e documentos apenas relacionados.

As três políticas foram congeladas antes da execução:

- `initial`: `0.50`;
- `conservative`: `0.69740408`;
- `balanced`: `0.00016509`.

```bash
for policy in initial conservative balanced; do
  orelhao knowledge evidence-evaluate \
    knowledge/evaluation/evidence-v2-holdout.json \
    --threshold-policy "$policy" \
    --diagnostics --json \
    > "/tmp/orelhao-evidence-holdout-${policy}.json"
done
```

O holdout mede generalização e não deve ser usado para escolher um novo threshold. O relatório expõe `category_metrics`, categoria e motivo esperado de abstenção por caso.

### Contrato de abstenção

`EvidenceDecision` separa decisão factual de formulação linguística. Uma abstenção sempre possui `AbstentionReason`: `no_relevant_evidence`, `specific_information_missing`, `temporal_evidence_unavailable` ou `entity_mismatch`. Mensagens pt-BR curtas podem ser geradas pelo contrato, sem permitir que uma LLM complete valores, datas, vagas, contatos ou entidades ausentes.

## Ablação INT8 × FP32 da v0.6.0-alpha.7

O artefato INT8 preserva todas as camadas da arquitetura, mas quantiza seus pesos. A alpha.7 isola essa variável usando o FP32 do mesmo repositório e da mesma revisão:

```bash
orelhao knowledge evidence-provision --variant fp32
orelhao knowledge evidence-evaluate \
  knowledge/evaluation/evidence-v1.json \
  --model-variant fp32 --diagnostics --json
```

As variantes são armazenadas como `model_int8.onnx` e `model_fp32.onnx`, com manifestos separados. O JSON registra `model_variant` e `model_size_bytes`. INT8 permanece padrão e nenhum resultado altera automaticamente o gate experimental.

O protocolo compara primeiro ROC AUC e distribuição dos scores, que não dependem de reutilizar o threshold INT8. Se houver ganho material, um threshold FP32 pode ser definido apenas no conjunto de calibração `evidence-v1.json` por regra declarada previamente e então congelado. O holdout não deve ser usado para escolher esse threshold. Também devem ser registrados tempo de parede, pico de memória residente e tamanho local do modelo.

### Resultado da alpha.7

FP32 não foi promovido. No holdout, sua ROC AUC foi `0.907`, contra `0.905` do INT8. A política balanced obteve recall `0.900` e especificidade `0.750`; a conservative obteve recall `0.400` e especificidade `1.000`. O processo FP32 utilizou aproximadamente `2.155 MiB` de RAM, artefato de `1.059 MiB` e latência média de `47–49 ms`. A quantização explica casos isolados, mas não a limitação estrutural de answerability.

## Candidato mDeBERTa-v3 da v0.6.0-alpha.8

A próxima hipótese troca uma única dimensão: arquitetura. `mdeberta-v3-base-squad2` INT8 é avaliado lado a lado sem substituir XLM-RoBERTa:

```bash
orelhao knowledge evidence-provision --model mdeberta-v3
orelhao knowledge evidence-evaluate \
  knowledge/evaluation/evidence-v1.json \
  --model mdeberta-v3 --diagnostics --json
```

Cada modelo possui diretório, revisão e manifesto próprios. `--model xlm-roberta` continua sendo o padrão. O candidato somente avança ao holdout depois de comparação no conjunto de calibração e congelamento explícito de thresholds.

Na calibração, mDeBERTa-v3 INT8 obteve ROC AUC `0.875`, contra `0.943` do XLM-RoBERTa INT8, e levou `263.21 ms`, contra `125.23 ms`, na mesma rodada. Também reduziu especificidade de `1.000` para `0.800` no threshold inicial. O candidato foi rejeitado sem consultar o holdout.

## Grounding factual por NLI da v0.6.0-alpha.9

Answerability e grounding não são equivalentes. A alpha.9 cria um benchmark separado no qual cada entrada é uma afirmação factual e um chunk. O modelo NLI recebe o chunk como premissa e a afirmação como hipótese, retornando a probabilidade de `entailment`.

```bash
orelhao knowledge evidence-provision --model nli-minilm --variant fp32
orelhao knowledge evidence-evaluate \
  knowledge/evaluation/grounding-v1.json \
  --model nli-minilm \
  --model-variant fp32 \
  --threshold 0.5 \
  --diagnostics --json
```

O candidato inicial é o `multilingual-MiniLMv2-L6-mnli-xnli` ONNX, revisão imutável. O dataset de calibração contém 20 afirmações suportadas e 20 não suportadas, incluindo contradição, temporalidade, entidade e informação específica ausente. O score deve ser analisado por ROC AUC e categoria antes de selecionar threshold. O holdout de answerability permanece intocado e não valida NLI; a confirmação exigirá um holdout próprio criado somente após o congelamento do protocolo.

Na calibração, o candidato atingiu ROC AUC `0.973`. A política balanced foi congelada em `0.1250362694`, com recall e especificidade de `0.950`; a conservative foi congelada em `0.7557643056`, com recall `0.650` e especificidade `1.000`. A latência média foi `9.14 ms`, o pico de memória aproximadamente `1.139 MiB` e o artefato `408.3 MiB`.

## Holdout próprio da v0.6.0-alpha.10

`grounding-v2-holdout.json` possui 20 afirmações suportadas e 20 não suportadas sem repetir afirmações da calibração. Contradição, entidade, informação específica e temporalidade possuem cinco negativos cada. As duas políticas congeladas são executadas uma única vez:

```bash
for policy in nli-balanced nli-conservative; do
  orelhao knowledge evidence-evaluate \
    knowledge/evaluation/grounding-v2-holdout.json \
    --model nli-minilm \
    --model-variant fp32 \
    --threshold-policy "$policy" \
    --diagnostics --json
done
```

Para categorias de classe única, o relatório usa recall nas positivas e especificidade nas negativas. `balanced_accuracy` permanece disponível por compatibilidade, mas não deve ser interpretada isoladamente nessas categorias. Nenhum threshold será escolhido após observar o holdout.

### Resultado do holdout

O NLI manteve ROC AUC `0.965`, contra `0.973` na calibração. A política balanced obteve acurácia balanceada `0.900`, recall `0.850` e especificidade `0.950`; a conservative obteve `0.775`, recall `0.550` e especificidade `1.000`. A única regressão categórica da balanced foi entidade, com especificidade `0.800`. Os casos e thresholds permanecem congelados.

## Contrato de três estados da v0.6.0-alpha.11

`GroundingPolicy` transforma o score NLI em uma decisão explícita:

```text
score >= 0.7557643056  -> supported
score <  0.1250362694  -> unsupported
demais scores           -> uncertain
```

`GroundingDecision.allows_response` é verdadeiro apenas para `supported`. Os estados `unsupported` e `uncertain` são fail-closed. O relatório NLI expõe os limites, a contagem por estado e a decisão de cada caso nos diagnósticos. O contrato permanece isolado: ainda não filtra retrieval nem controla geração ou voz.

## Bancada em modo observação da v0.6.0-alpha.12

A rota `/workbench` do Admin executa o primeiro fluxo integrado experimental:

```text
pergunta -> retrieval persistente -> resposta candidata -> NLI -> GroundingDecision -> log
```

`presented_answer` permanece igual a `answer` em todos os três estados. Isso é deliberado: a alpha.12 mede o comportamento real antes de permitir que `unsupported` ou `uncertain` bloqueiem uma interação. O JSONL local registra as latências de retrieval, geração e grounding, todos os chunks recuperados com scores e avaliações humanas append-only.

Como ainda não existe um backend LLM local de produção no projeto, o gerador padrão da bancada usa o primeiro chunk recuperado como resposta extrativa. O contrato `AnswerGenerator` permite injetar a futura LLM sem acoplar o Admin ao backend. A captura do navegador é convertida para WAV PCM16 mono de 16 kHz antes do STT; a resposta pode ser sintetizada pelo Piper configurado.

Para executar:

```bash
orelhao admin
```

Abra `http://127.0.0.1:8765/workbench`. O índice, o modelo NLI, o STT e o TTS precisam estar provisionados localmente. O modo observação não deve ser interpretado como autorização para ativar o gate fail-closed.

### Correções da alpha.12.1

Ao abrir a bancada, o modelo STT passa a ser preparado em segundo plano; o botão de gravação só é habilitado quando estiver pronto. A captura para automaticamente em 12 segundos, é convertida para WAV mono de 16 kHz, tem o silêncio das bordas removido e recebe timeout explícito de 90 segundos.

A resposta extrativa deixa de enviar um chunk Markdown inteiro ao TTS. O fallback seleciona no máximo duas frases relevantes, remove marcação e limita o texto a 360 caracteres. O NLI compara essa resposta separadamente contra cada chunk recuperado e utiliza o maior suporte, preservando a semântica do benchmark de pares afirmação/premissa.
