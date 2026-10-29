# Grounding V3 — PR-02: Evidence Span Extraction e auditoria do Retrieval

**Data:** 29/10/2026. **Situação:** implementado experimentalmente; **NO-GO para produção**.
**Branch:** `feat/grounding-v3-evidence-spans-20261029`, base commit `43d3447` (PR-01). Não foi criada nova release.

## Objetivo e implementação

Identificar passagens **literais com offsets** dentro do chunk recuperado, exibir o trecho candidato na bancada, comparar entailment no texto integral e na passagem curta e diagnosticar fontes oficiais indexadas que não foram recuperadas. Não alterar thresholds, RAG baseline ou decisão factual.

| Módulo | Responsabilidade |
|---|---|
| `evidence_span.py` | `EvidenceSpan` imutável com `chunk_id`, fonte, offsets `start/end`, texto extraído literalmente e metadados de fonte/entidade/atributo |
| `evidence_selector.py` | Seleção determinística por sobreposição lexical sem pontuar candidatos com NLI; `support_verified=False` |
| `claim_grounding.py` | Associa `span_selection` opcional a cada claim **após** o NLI ter escolhido o chunk; score e decisão preservados |
| `admin/app.py` | Exibe candidato, offsets e cobertura lexical com HTML escapado e aviso de que não comprova suporte |
| `observation.py` e `live_pipeline_evaluation.py` | JSONL de observação e avaliações posteriores incluem span candidato, sem quebrar leitura de logs antigos |
| `span_evaluation.py` | Compara NLI chunk-versus-span e identifica fontes esperadas não recuperadas, somente em modo diagnóstico retrospectivo |
| `scripts/audit_grounding_v3_spans.py` | Comando reproduzível sem gerar novas respostas pela LLM |

### Limites de provenance

- Os offsets são **índices de caracteres Unicode em `Chunk.text`**, não bytes nem posições no Markdown original. O chunker pode ter normalizado quebras de linha.
- O texto de cada span é verificado como fatia `chunk.text[start:end]` e a seleção só analisa trechos da evidência recuperada, sem geração de conteúdo.
- Um trecho com palavras semelhantes **não é evidência suficiente** de entailment. Nem a pontuação lexical nem o NLI calculado nos spans autorizam respostas na aplicação.
- O NLI extra por span roda **somente no script de auditoria**. A bancada executa apenas o seletor lexical adicional, preservando a política anterior e os thresholds `0.1250362694` / `0.7557643056`.
- As fontes esperadas dos rótulos são usadas apenas para avaliação retrospectiva, **nunca para melhorar artificialmente a recuperação na operação**.

## Resultado com o NLI ONNX real (Arch Linux, CPU)

| Indicador | Resultado |
|---|---:|
| Pares claim/chunk avaliados | **48** |
| Seleções sem sobreposição lexical / chunks ausentes | **0 / 0** |
| Entailment no span maior que no chunk por mais de 0,01 | **23** |
| Entailment no span menor que no chunk por mais de 0,01 | **24** |
| Variação de até 0,01 em valor absoluto | **1** |
| Mediana de (span − chunk) | **−0,0170** |
| Fontes esperadas ausentes no retrieval arquivado | **4 ocorrências; 4/4 indexadas** |

Exemplos relevantes, **ainda sem revisão humana independente**: P17 (437 vagas PSG 006/2026), entailment **0,311 → 0,992**; P08 (prazo da Ouvidoria), **0,727 → 0,296**; P15 (telefone central), **0,517 → 0,015**; Qwen P01 (missão do Senac respondida indevidamente com aprendizagem), **0,972 → 0,010**. Não se pode concluir que trecho curto é melhor em todos os casos; scores maiores podem coexistir com erro factual.

Os dois modelos deixaram de recuperar as fontes esperadas de P01 (missão) e P13 (idade mínima de Excel Avançado), apesar de ambas existirem no índice. A causa pode estar em consulta, ranking ou threshold, a investigar em conjunto **independente**.

## Reproduzir

```bash
cd /home/wesscosta/Develop/orelhao-ia
source .venv/bin/activate
python scripts/audit_grounding_v3_spans.py \
  --dataset knowledge/evaluation/grounding-real-senac-pi-v1.json \
  --tucano knowledge/evaluation/results/grounding-tucano2-2026-10-29.json \
  --qwen knowledge/evaluation/results/grounding-qwen35-2026-10-29.json \
  --nli-model models/evidence/multilingual-minilm-l6-nli \
  --index knowledge/index \
  --output /tmp/orelhao-grounding-v3-spans-20261029.json
pytest -q
ruff check src/orelhao/services/knowledge src/orelhao/admin tests/knowledge tests/admin scripts/audit_grounding_v3_spans.py
mypy src/orelhao/services/knowledge
```

**Qualidade:** 235 testes Pytest passando, Ruff e Mypy aprovados, um aviso já conhecido do Starlette. O benchmark é **regressão de desenvolvimento com rótulos assistidos por IA**, não holdout humano cego.

## Próximo gate

PR-03: Fact Validator tipado (entidade, duração, valor, prazo, quantidade, vigência). Em seguida PR-04 orquestra a decisão V3 com precedência factual verificável; PR-05/06 exigem revisão humana e holdout independente. **Sem promoção para main ou homologação no Dell i5-7500T/8 GiB**.
