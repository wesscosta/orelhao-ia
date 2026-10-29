# Grounding V3 — PR-03: Fact Validator (diagnóstico factual)

**Data:** 29/10/2026. **Status:** implementado na branch experimental `feat/grounding-v3-fact-validator-20261029`; **NO-GO para homologação/produção**. Base: PR-02 `98a619f`. Sem release alpha.14, sem merge na `main`.

## Objetivo e limites

Identificar **valores explícitos e tipados** em afirmações geradas e compará-los com fontes indexadas, respeitando escopo, publicação, unidade e vigência. O resultado é **diagnóstico**, não prova de entailment nem decisão de apresentação de resposta. A autorização permanece com os gates anteriores (`EvidenceAdjudicator` + NLI/GroundingPolicy); integração decisória é assunto do PR-04.

## Entregas

| Artefato | Função |
|---|---|
| `fact_extraction.py` | `ExtractedFact` imutável com tipo, valor normalizado, unidade, qualificador, referência de edital e offsets literais; reconhece R$, horas, idade mínima, dias úteis/corridos, vagas anunciadas/disponíveis, telefone brasileiro e datas explícitas contextualizadas |
| `fact_validation.py` | `validate_claim_facts()`, `FactStatus` e `FactCheck`; exige fonte com `authority=primary`, URL HTTPS, compatibilidade de entidade/unidade, período de validade e confirmação editorial para estado atual |
| `fact_evaluation.py` e `scripts/audit_grounding_v3_facts.py` | Reexecutam o validador sobre claims e chunks históricos, **sem gerar novas respostas** nem reescrever gabaritos |
| `observation.py` | Acrescenta `fact_validations` ao evento JSONL de observação, com resultado por claim e metadados de rastreabilidade; mantém leitura dos registros anteriores |
| `admin/app.py` | Mostra tabela de atributos, valores, resultados, fontes e offsets na bancada, com escape HTML e aviso de caráter diagnóstico |
| `live_pipeline_evaluation.py` | Inclui os novos diagnósticos em futuras avaliações do pipeline |
| `query_constraints.py` | Corrige limites de palavra na resolução dos nomes de entidades, evitando identificar Excel dentro de palavras não relacionadas |
| `tests/knowledge/test_fact_validation.py` | Validação de preços, números, horas, idade, dias, documentos do PSG, contatos, datas, fontes expiradas e entidades distintas |

## Contratos de segurança

- `value_match` informa apenas coincidência **tipada** entre um atributo extraído e uma fonte admitida, não certifica a afirmação inteira (`full_claim_verified=false`).
- `value_mismatch` identifica divergência quando o atributo, qualificador e escopo são comparáveis e há uma única alternativa de valor; **não bloqueia automaticamente** nesta etapa (`enforced=false`).
- `ambiguous` preserva múltiplas ofertas, como Informática Básica com **80 ou 140 horas** e preços diferentes, sem escolher uma por pontuação de retrieval.
- `no_admissible_source` aparece quando faltam dados com escopo, unidade, validade ou proveniência compatíveis. Não é uma afirmação de que o fato seja falso no mundo real.
- Prazos de **15 dias úteis** não equivalem a **15 dias corridos**. A condição de prorrogação é separada do prazo base. Prazos sem unidade explícita não comprovam que sejam úteis.
- As **437 vagas previstas** para o edital PSG 006/2026 não representam 437 vagas disponíveis atualmente. A referência do edital evita utilizar os números dos editais 007/2026 e 05/2026 na comparação.
- `retrieved_at` isolado **não confirma estado atual**: estado atual exige confirmação editorial, `verified_at` na data local, `valid_until` vigente e fonte primária HTTPS.
- Valores de fontes secundárias, sem HTTPS, vencidas ou de entidade/unidade incompatível não autorizam confirmação de um valor.
- Os offsets do valor encontrado são índices de caracteres Unicode relativos ao `Chunk.text`; o texto extraído é literalmente `chunk.text[start:end]`.
- O reconhecimento de atributos é intencionalmente restrito. Paráfrases sem marcador numérico, condições comerciais complexas, endereço, qualificadores em múltiplas frases e relações semânticas exigem revisão humana e/ou PR-04.

## Qualidade verificada

| Avaliação | Resultado |
|---|---:|
| Pytest na branch experimental, Arch Python 3.14 | **250 testes aprovados**; 1 aviso preexistente de Starlette |
| Ruff e Mypy | Sem erros (Mypy: 35 arquivos Knowledge) |
| Benchmark retrieval v1 congelado | Hit@1 0,60; Hit@k 0,8333; MRR 0,6972; abstenção 0,60 |
| Harness de answerability sintético | 60/60 acertos mecânicos no dataset holdout sintético (não humano) |
| Auditoria de 48 claims de Tucano2 + Qwen já arquivadas | **14** correspondências tipadas, **33** sem atributo tipado, **1** sem fonte admissível e **0** chunks ausentes |

**Interpretação obrigatória:** as 48 claims foram selecionadas pelo pipeline com NLI antes desta implementação; as 14 correspondências não comprovam precisão factual, e a ausência de divergência nessa amostra não testa a capacidade de bloquear erros. Testes adversariais novos verificam que um NLI artificialmente alto pode aprovar 60 horas para fonte Excel de 30 horas, enquanto o validador identifica `value_mismatch`; a apresentação da resposta permanece inalterada até PR-04.

## Reproduzir

```bash
cd /home/wesscosta/Develop/orelhao-ia
source .venv/bin/activate
python scripts/audit_grounding_v3_facts.py \
  --tucano knowledge/evaluation/results/grounding-tucano2-2026-10-29.json \
  --qwen knowledge/evaluation/results/grounding-qwen35-2026-10-29.json \
  --index knowledge/index \
  --output /tmp/orelhao-grounding-v3-facts-20261029.json
pytest -q
ruff check src/orelhao/services/knowledge src/orelhao/admin tests/knowledge tests/admin scripts/audit_grounding_v3_facts.py
mypy src/orelhao/services/knowledge
```

## Próximos gates

**PR-04:** orquestrador de decisão V3 com regras de precedência, falha segura e distinção entre fato **comprovadamente inconsistente** e fato **insuficientemente verificado**; medir impacto em falsos bloqueios, recuperação e falsas permissões sem afrouxar thresholds NLI. **PR-05/06:** revisão humana independente e holdout cego. Depois, validação no Dell i5-7500T de 8 GiB e fluxo de voz completo.

**Decisão formal:** implementação experimental entregue; não homologada. O Fact Validator não substitui NLI nem reclassifica fatos históricos por si só.
