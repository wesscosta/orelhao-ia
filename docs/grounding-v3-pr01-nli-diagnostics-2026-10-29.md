# Grounding V3 — PR-01: auditoria de NLI e diagnóstico por etapa

**Data:** 29/10/2026
**Status:** Implementado e testado na branch experimental; **não homologado**.
**Base:** `12e6607` (`docs/consolidate-current-status-20261029`), com código do gate adversarial `2c0495a`.
**Branch:** `feat/grounding-v3-diagnostics-20261029`.

## Objetivo e entregas

Começar a implementação do [plano Grounding V3](plan-grounding-answerability-stage2.md) pela auditoria do NLI e do estágio de falha, **sem mudar thresholds, retriever ou política de respostas**.

- `OnnxNliEvidenceVerifier.classify(hypothesis, premise)` passa a expor `NliProbabilities(entailment, neutral, contradiction)`. A API antiga `support_score()` continua devolvendo entailment com o mesmo score e a mesma semântica, preservando comportamento.
- O contrato de labels do modelo `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli`, revisão exata `0a71e92a985b6e1ad1828cf67ce9c459639c1dca`, foi confirmado no `config.json` oficial: `0=entailment, 1=neutral, 2=contradiction`. Quando `config.json` está presente, a implementação verifica o mapeamento e recusa drift silencioso. O provisionamento de modelos NLI novos passa a baixar `config.json` da revisão pinada. Instalações legadas usam o contrato verificado pela versão fixa da especificação.
- `grounding_diagnostics.py` atribui, **como hipótese diagnóstica**, o estágio `retrieval`, `pre_generation`, `generation`, `post_generation`, `abstention` ou `passed_checks` a cada caso arquivado.
- `scripts/audit_grounding_v3.py` cruza os 40 casos de avaliação com as saídas completas de Tucano2 e Qwen3.5, exige IDs correspondentes e opcionalmente executa de novo o NLI ONNX sobre **os chunks originais pelo ID**. Escreve relatório JSON em caminho explicitamente selecionado, preferencialmente `/tmp`.
- Testes novos validam rótulos, distribuição, ausência de evidência, falso suporte, preservação de casos e detecção de problemas no modelo. Os testes de `support_score()` continuam compatíveis.

O script de auditoria **não chama as LLMs**, não otimiza valores, não modifica gabaritos e não conclui revisão humana automaticamente.

## Linha de comando

```bash
cd /home/wesscosta/Develop/orelhao-ia
source .venv/bin/activate
python scripts/audit_grounding_v3.py \
  --dataset knowledge/evaluation/grounding-real-senac-pi-v1.json \
  --tucano knowledge/evaluation/results/grounding-tucano2-2026-10-29.json \
  --qwen knowledge/evaluation/results/grounding-qwen35-2026-10-29.json \
  --nli-model models/evidence/multilingual-minilm-l6-nli \
  --index knowledge/index \
  --output /tmp/orelhao-grounding-v3-diagnostics.json

pytest -q
ruff check src/orelhao/services/knowledge tests/knowledge scripts/audit_grounding_v3.py
mypy src/orelhao/services/knowledge
```

## Resultado efetivamente medido

O modelo ONNX real em CPU foi carregado para reavaliar **48 pares afirmação/evidência** presentes nos resultados históricos. Os **48 chunks foram encontrados no índice local** e a probabilidade de entailment reproduziu o valor original (nenhuma diferença superior a 0,01).

**Distribuição diagnóstica (40 casos de cada modelo, incluindo positivos e negativos):**

| Estágio identificado | Tucano2 1.5B | Qwen3.5 0.8B |
|---|---:|---:|
| `retrieval` — fonte esperada não recuperada | 2 | 2 |
| `pre_generation` — bloqueio pelo gate anterior | 13 | 13 |
| `post_generation` — avaliação NLI/atributos | 13 | 17 |
| `passed_checks` — somente âncoras lexicais verificadas | 12 | 8 |
| Total | 40 | 40 |

**Nos oito falsos bloqueios positivos do Tucano2:** dois são `retrieval_miss` (P01, P13), os demais são `nli_uncertain` (P08, P10, P15, P16, P17, P20). Isso diferencia defeitos do ranking de defeitos da validação semântica.

**Amostra de probabilidades NLI (reavaliadas sobre os chunks originais):**

| Caso | Modelo | Entailment | Neutral | Contradiction | Observação |
|---|---|---:|---:|---:|---|
| P08 — prazo da Ouvidoria | Tucano2 | 0,7266 | 0,2334 | 0,0400 | Resposta documentada bloqueada como `uncertain` |
| P15 — telefone geral | Tucano2 | 0,5170 | 0,1171 | 0,3659 | Divergência potencial entre escopo/trecho e afirmação |
| P17 — 437 vagas previstas PSG 006/2026 | Tucano2 | 0,3110 | 0,0284 | 0,6606 | NLI interpreta forte contradição; verificar contexto e numeração |
| P01 — missão institucional | Qwen | 0,9719 | 0,0170 | 0,0111 | Alto entailment para afirmação fora da intenção da pergunta |

Os casos acima permanecem **candidatos a erro**, não conclusões de revisão humana. Uma resposta pode conter os termos esperados e ainda estar semanticamente incorreta.

## Invariantes preservadas

- Thresholds `0.1250362694` e `0.7557643056` intactos.
- Modelo `nli-minilm` e artefato GGUF/ONNX inalterados; nenhuma nova dependência de runtime.
- Sem mudança na apresentação de respostas ou em `observe`/`enforce`.
- Baseline de 216 testes permanece coberto, acrescido dos novos testes.
- `main` continua intacta. Não existe promoção ou release alpha.14 neste PR.

## Pendências

1. **PR-02:** extração de spans com offsets verificáveis, avaliação de diferença NLI chunk × sentença e diagnóstico de retrieval misses.
2. **PR-03:** Fact Validator por entidade, atributo, valor, unidade e período.
3. **PR-04:** decisão V3 com precedência explícita e justificativas; não recalibrar thresholds pelos 40 casos vistos.
4. **PR-05:** adjudicação humana independente na bancada; separar rótulos humanos de sinais automáticos.
5. **PR-06:** holdout novo, independente e revisão de regressões; só então decidir homologação e hardware Dell 8 GB.

**Decisão:** PR-01 habilita diagnóstico reproduzível e triclasse; **NO-GO** permanece para operação física até avaliação independente de qualidade factual.

### Referência externa da ordem das classes
- https://huggingface.co/MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli/blob/0a71e92a985b6e1ad1828cf67ce9c459639c1dca/config.json
