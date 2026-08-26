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
