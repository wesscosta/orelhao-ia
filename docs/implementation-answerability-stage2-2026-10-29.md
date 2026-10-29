# Implementação experimental — Etapa 2: Answerability e Grounding Adversarial

**Data:** 29/10/2026
**Branch:** `feat/answerability-grounding-stage2-20261029`
**Base:** commit `74f398f`, derivado do corpus atualizado `547a936`
**Estado:** implementado para pesquisa e bancada; **não homologado, sem merge na main nem release oficial**.

## Entregas efetivas

### 1. Gate anterior à LLM

- `query_constraints.py`: detecta restrições explícitas de curso, unidade, atributo e temporalidade ("hoje", "agora", "ainda" etc.), sem afirmar fazer reconhecimento de entidades genérico.
- `source_policy.py`: valida `unit_id` e `entity_id` quando fornecidos. Para **estado atual** exige declaração editorial `current_state_confirmed: true`, fonte `authority: primary`, `source_url` HTTPS, `verified_at` no dia local da consulta e `valid_until` não expirado. `retrieved_at` não equivale a prova de vaga atual.
- `evidence_conflicts.py`: compara exclusivamente fatos explícitos nos metadados (`entity_id`, `fact_key`, `fact_value` e escopo de unidade/data), recusando valores contraditórios de fontes primárias sobre a mesma entidade/atributo. Não tenta resolver divergência semântica entre parágrafos livres.
- `answerability.py`: combina as restrições em uma `EvidenceAssessment`, com motivos de abstenção (ausência de evidência, informação específica faltante quando fatos estruturados não contêm o atributo, entidade incompatível, fonte temporal insuficiente e evidências conflitantes).
- `evidence_decision.py`: amplia razões, preserva mensagens em pt-BR. Um resultado pré-gate `answerable=True` indica **ausência de impedimento detectado**, NÃO certeza de que o texto contém uma resposta — como evidencia `verified_specific_answer=False`.

### 2. Integração do fluxo

- `observation.py`: `ObservationWorkbench` suporta `adjudicator` opcional; a instância padrão da bancada usa o gate. Em `enforce`, uma pergunta rejeitada não chama a LLM; em `observe`, mantém geração para comparação e registra o bloqueio proposto. Em `enforce`, somente chunks admitidos entram na geração e na verificação NLI.
- `claim_grounding.py`: `ClaimAssessment` inclui o `chunk_id` da fonte com maior suporte; mantidos thresholds existentes de NLI. Respostas compostas seguem pela segmentação conservadora anterior.
- `admin/app.py`: exibe status pré-geração, motivo categorizado, quantidade de fontes admitidas, conflitos, se a LLM foi dispensada, ID do chunk de cada afirmação e latência do gate. A voz Piper continua a sintetizar apenas a resposta **apresentada**, preservando abstenção segura.
- `observation.py`: data local de avaliação configurable com `ORELHAO_TIMEZONE`, padrão `America/Fortaleza`.

### 3. Corpus e testes

- Metadados de escopo `entity_id` adicionados aos documentos oficiais de Informática Básica, Excel e Excel Avançado (sem mudar os fatos ou preços originais).
- Avaliador independente do retrieval `answerability_evaluation.py` e CLI `orelhao knowledge answerability-evaluate` com métricas TP/TN/FP/FN, precision, recall, specificity, balanced accuracy, taxa de permissão indevida e falso bloqueio, P50/P95, contagem por categoria e diagnóstico opcional.
- 120 **casos sintéticos de contrato**: 60 de desenvolvimento e 60 rotulados `holdout`, com entidades distintas, porém **gerados por templates equivalentes e NÃO revisados por humanos**. Não são prova de generalização semântica nem substituem holdout externo independente.
- Testes de ausência, vigência, escopo, conflito, fatos históricos, metadados inconsistentes, modo de observação e modo seguro (incluindo áudio da resposta apresentada).

## Métricas observadas no Arch Linux

| Benchmark | Resultado |
|---|---|
| Retrieval original (40 questões) | Hit@1 0,6000; Hit@k 0,8333; MRR 0,6972; abstenção 0,60 |
| Retrieval outubro (17 questões) | Hit@1 0,8333; Hit@k 1,0000; abstenção 0,20 |
| Answerability sintético DEV (60 casos) | TP 25, TN 35, FP 0, FN 0 |
| Answerability sintético HOLDOUT (60 casos) | TP 25, TN 35, FP 0, FN 0 |
| Latência P50 do gate pré-geração, DEV/HOLDOUT | ~0,02 ms nos dados sintéticos (não mede retrieval, NLI ou LLM) |

**Interpretação obrigatória:** o resultado perfeito nos 120 casos é previsível, pois são casos unitários gerados para cobrir regras determinísticas implementadas. Não representa acurácia factual em perguntas reais. A **abstenção do retriever original continua em 60%** (20% no novo dataset) porque deliberadamente não foi alterada; sua métrica é diferente da decisão pré-geração. Não somar percentuais nem apresentar um como melhoria direta do outro.

### Smoke em serviços reais

Com `ORELHAO_CONFIG=config/benchmark-tucano2-15b-ptbr.yaml` no Admin:
- `Há vagas abertas hoje para o curso Excel?`, modo `enforce`: `temporal_evidence_unavailable`, `generation_skipped=True`, sem chamada à LLM, resposta curta de abstenção. Latência total observada em uma execução ~3,0 ms.
- `O que é o Senac Piauí?`, modo `observe`: passou por retrieval → Tucano2 → NLI, pré-gate sem impedimento detectado e grounding `SUPPORTED`. Latência total observada ~1,85 s.
- Sanidade NLI ONNX: mesma hipótese/premissa: suporte ~0,991; hipótese contraditória "60 horas" diante de premissa "40 horas": ~0,024; conteúdo não relacionado: ~0,001. Isto verifica comportamento da **probabilidade de suporte**; não prova a classificação completa das três labels nem calibração de contradição.

## Comandos de validação

```bash
cd /home/wesscosta/Develop/orelhao-ia
source .venv/bin/activate

pytest -q
ruff check src/orelhao/services/knowledge src/orelhao/services/llm \
  src/orelhao/services/tts src/orelhao/admin tests/knowledge tests/llm tests/tts tests/admin
mypy src/orelhao/services/knowledge src/orelhao/services/llm src/orelhao/services/tts
orelhao knowledge answerability-evaluate \
  knowledge/evaluation/answerability-stage2-dev.json --json --diagnostics
orelhao knowledge answerability-evaluate \
  knowledge/evaluation/answerability-stage2-holdout.json --json --diagnostics
orelhao knowledge evaluate --retriever baseline --json
orelhao knowledge evaluate knowledge/evaluation/retrieval-refresh-2026-10.json --retriever baseline --json
```

O CI no GitHub usa Python 3.12. A máquina remota usada na implementação está em Python 3.14. A avaliação em **Dell OptiPlex 7050, Core i5-7500T, 8 GB RAM** ainda é necessária.

## Critérios NÃO cumpridos e trabalho remanescente

1. **T5: holdout independente e revisão humana real.** Os 120 casos atuais são sintéticos; criar conjunto externo com evidências reais, entidades inéditas, fatos conflitantes em prosa, intenções de fala/transcrição e rótulos adjudicados. Medir métricas do **pipeline completo** (permissão/abstenção final), não só da regra.
2. **Answerability semântica em texto livre.** O gate é deliberadamente limitado a campos e evidências verificáveis. Se documentos não trazem `entity_id`/`unit_id` ou fatos estruturados, não pode comprovar sua compatibilidade nem detectar toda omissão de atributo. Em modo seguro, a verificação NLI posterior continua necessária e pode produzir falsos positivos/negativos.
3. **Contradição por NLI.** Verificar mapping de entailment/neutral/contradiction do artefato e comparar evidências não estruturadas por escopo antes de usar um score de contradição no caminho crítico. Não inferir só pela desigualdade de frases.
4. **T6: desempenho e homologação física.** Rodar no Dell com apenas uma LLM carregada e fluxo real voz → STT → RAG → geração → TTS; revisão humana, estabilidade térmica, RAM P95 e latência total.
5. **Release e merge:** nenhuma promoção sem critério de segurança factual e compatibilidade com Python 3.12; a `main` continua intacta.

**Próximo gate sugerido:** T5 semântico com casos reais e revisão humana, seguido de T6 no hardware final. Não reduzir thresholds NLI apenas para elevar recall em um exemplo.
