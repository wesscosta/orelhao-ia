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

## Experimento semantic-only da v0.6

A v0.6.0-alpha.1 introduz um retriever semântico local isolado e mantém o baseline disponível para comparação. O modelo `intfloat/multilingual-e5-small`, na revisão ONNX fixada pelo código, é provisionado uma única vez:

```bash
pip install -e '.[semantic]'
orelhao knowledge semantic-provision
orelhao knowledge semantic-index
orelhao knowledge evaluate --retriever semantic --json
```

O runtime de indexação e busca carrega somente arquivos locais. `semantic-vectors.npy` e `semantic-manifest.json` são reconstruíveis e vinculados ao hash dos mesmos chunks usados pela baseline.

Nesta primeira medição, `min_score=0.0` é intencional. Assim, o benchmark mede ranking semantic-only sem introduzir simultaneamente calibração de threshold; a abstenção esperada será medida e registrada, não ocultada. Ainda não há resultado A/B validado nem promoção do mecanismo.

Fusão lexical + semântica, novos thresholds e confidence gate pertencem a incrementos posteriores e só devem ser promovidos mediante ganho A/B sem regressão relevante de ranking, abstenção, latência, memória ou operação offline.
