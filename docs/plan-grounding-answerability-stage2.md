> **TIPO: REGISTRO DATADO / HISTÓRICO.** Plano proposto ANTES da implementação. Itens T0–T5 foram parcialmente implementados; validação humana independente e gate Dell seguem pendentes. Para o estado consolidado e as métricas mais recentes, consulte [Estado vigente](current-state.md). Preservar os resultados originais para rastreabilidade.

# Plano técnico — Etapa 2: Answerability e Grounding Adversarial

**Projeto:** Orelhão IA | **Proposta de marco:** v0.6.0-alpha.14 (sujeito à revisão da sequência de releases)
**Elaborado:** 29/10/2026 | **Estado:** planejado, implementação NÃO iniciada
**Base de leitura:** branch `feat/knowledge-senac-pi-refresh-20261029`, commit `547a936` e páginas 02.2, 04 e 05 do projeto no Notion.

## 1. Objetivo e justificativa

Evitar que o terminal apresente afirmações factuais sem suporte, resolva ambiguidades de entidades sem confirmação, misture informações de fontes contraditórias ou trate ofertas históricas como atuais. Reduzir, simultaneamente, a abstenção indevida de respostas corretas. Manter comportamento rastreável e reproduzível na bancada de texto/voz.

**Estado verificado no início:** 18 documentos informativos, 35 chunks, 187 testes passando (Arch Linux, Python 3.14). Retrieval original: Hit@1 0,6000, Hit@k 0,8333, MRR 0,6972, acurácia de abstenção 0,60. Dataset complementar de 17 casos: Hit@1 0,8333, Hit@k 1,0 e abstenção 0,20 (5 casos negativos). O Tucano2 1.5B funciona localmente, mas permanece candidato. O modo `enforce` já bloqueia após a geração e não está habilitado como política padrão do terminal físico.

**Interpretação:** encontrar um chunk semelhante não significa que ele responda à pergunta. Os percentuais de retrieval não equivalem à precisão factual da resposta final.

## 2. Decisões e restrições

1. Preservar `PersistentVectorRetriever`, índice local, corpus versionado, NLI ONNX, LLM/llama.cpp, STT e Piper. Não reescrever a fusão ou o retriever para favorecer casos do dataset.
2. Preservar `GroundingPolicy` com thresholds congelados `0.1250362694` e `0.7557643056`. Qualquer alteração de calibração exige experimento próprio com holdout isolado, não tuning por pergunta.
3. Introduzir **gate pré-geração** e **verificação pós-geração** como componentes distintos, mantendo o modo `observe` padrão para comparação. Modo `enforce` permanece opção controlada até homologação.
4. Não adicionar LLM remota, API online no caminho de inferência, novo banco ou novo modelo pesado. Roda offline e com CPU no Dell OptiPlex 7050 Micro (i5-7500T, 8 GB fixos).
5. Não tratar o campo `temporal: true` como invalidação automática: uma pergunta histórica é diferente de “há vagas agora?”. Data de consulta não é data de vigência.
6. Não publicar no RAG documentos de auditoria, prompts, perguntas de avaliação ou respostas geradas pela LLM sem validação e fonte primária.

## 3. Arquitetura e sequência

```text
Pergunta / STT
   │
   ├─ QueryConstraints (entidade, unidade, curso, atributo, temporalidade)
   │
   └─ Retriever atual → SearchResult[] e metadados
        │
        ├─ EvidenceAdjudicator (pré-geração)
        │    ├─ presença da informação solicitada / entidade correspondente
        │    ├─ proveniência, autoridade e vigência
        │    └─ contradições entre evidências pertinentes
        │
        ├─ decisão: ANSWERABLE / CLARIFY / ABSTAIN + reason + fontes
        │       └─ se não respondível: mensagem pt-BR curta; NÃO chamar LLM
        │
        └─ AnswerGenerator/LLM atual
             │
             ├─ split_factual_claims / verificador NLI
             ├─ checagem de entidade, atualidade e contradição por claim
             └─ GroundingPolicy -> ALLOW / ABSTAIN
                    │
                    └─ resposta apresentada → TTS
```

**Importante:** o `EvidenceDecision` existente pode ser estendido para motivos de abstenção e a `GroundingDecision` existente continua representando suporte factual. Evitar introduzir enums sobrepostos sem necessidade. Considerar `CLARIFY` como saída específica somente quando a pergunta não especificar a unidade ou entidade necessária; ainda assim não afirmar fatos.

### Contratos sugeridos

```python
@dataclass(frozen=True)
class QueryConstraints:
    entity_id: str | None
    unit_id: str | None
    attribute: str | None
    requires_current_state: bool
    reference_date: date | None

@dataclass(frozen=True)
class EvidenceAssessment:
    answerable: bool
    reason: AbstentionReason | None
    admissible_chunk_ids: tuple[str, ...]
    conflicting_chunk_ids: tuple[str, ...]
    diagnostics: dict[str, str]

class EvidenceAdjudicator(Protocol):
    def assess(
        self, question: str, evidence: list[SearchResult],
        *, as_of: date,
    ) -> EvidenceAssessment: ...
```

O contrato é **proposta**, não API implementada. Na integração efetiva, tipar os diagnósticos, preservar compatibilidade dos logs e evitar que `QueryConstraints` seja um mecanismo de NER genérico frágil. Identificadores canônicos opcionais devem vir do corpus verificado ou de normalização validada.

## 4. Plano de implementação por gates

### Gate T0 — Congelar base e preparar execução reprodutível

**Arquivos existentes:** `knowledge/evaluation/{retrieval-v1,retrieval-refresh-2026-10,evidence-v2-holdout,grounding-v2-holdout,llm-ptbr-v1}.json`, `docs/knowledge-refresh-senac-pi-2026-10-29.md`.

- Criar branch isolada a partir de `547a936`; conferir que as mudanças de voz da branch ancestral continuam presentes.
- Registrar hash do corpus/index, revisão do NLI, modelo LLM, configurações, semente e versões Python/ONNX/llama.cpp. `temperature=0` para comparação determinística quando suportada, sem assumir equivalência bit a bit.
- Executar os datasets existentes **sem alterar seus gabaritos**; salvar relatórios em `/tmp` ou diretório de resultados ignorado pelo Git.
- Criar matriz de erros: pergunta → chunks → resposta bruta/normalizada → decisão → fonte → causa e avaliação humana.

**Aceite:** baseline reproduzível, relatórios versionados apenas quando não contiverem dados pessoais e nenhum arquivo pré-existente de benchmark modificado.

### Gate T1 — Query constraints, entidade e temporalidade

**Criar:** `src/orelhao/services/knowledge/query_constraints.py`, `source_policy.py`; testes homônimos.

- Identificar restrições **explícitas** da pergunta: município/unidade, nome de curso/edital, atributo pedido (valor, horário, duração, endereço, vaga) e tempo (“hoje”, “agora”, data histórica).
- Não inferir unidade de forma silenciosa. Fonte de Teresina não responde por Parnaíba; inscrição do edital 006 não comprova inscrição do edital 007.
- Normalizar tipos de frontmatter `retrieved_at`, `valid_from`, `valid_until`, `authority`, `source_url`, `category`, `unit_id`/ `entity_id` quando explicitamente conhecidos. O parser YAML pode retornar valores tipados; validar sem quebrar documentos legados.
- Para perguntas sobre estado **atual**, bloquear fonte sem vigência adequada ou cujo dado seja apenas publicação histórica. `retrieved_at` sozinho NÃO comprova vaga disponível.
- Em ausência de metadados: `UNCERTAIN/ABSTAIN` apenas quando a pergunta exigir confirmação específica; não bloquear automaticamente missão, história e outros fatos estáveis.

**Aceite:** testes de mesma unidade/diferente unidade, edital errado, preço histórico/atual e pergunta histórica com conteúdo válido; fontes legadas continuam carregáveis.

### Gate T2 — Answerability pré-geração e conflitos de evidência

**Criar:** `answerability.py`, `evidence_conflicts.py`; estender `evidence_decision.py` para razões `CONFLICTING_EVIDENCE`, `STALE_EVIDENCE`, `AMBIGUOUS_ENTITY` se o novo desenho validar essa necessidade.

- Determinar se **o atributo requisitado** está realmente presente em evidência compatível, distinguindo “há um edital” de “estão abertas as inscrições”.
- Confrontar fontes de mesmo `entity_id` + atributo + período. Se dois valores relevantes e autoritativos divergirem e não houver precedência explícita comprovada, bloquear e registrar conflito; não escolher apenas o maior score.
- Utilizar somente metadados/valores estruturados validados como fatos comparáveis, sem extrair relações irrestritas de qualquer frase através de regras frágeis.
- Avaliar o NLI/QA local existente apenas como **sinal auxiliar** de answerability. As avaliações anteriores já detectaram má calibração de modelos de QA; não reutilizar o score sem nova validação.
- Em caso de falha da verificação, bloquear a resposta factual, registrar motivo e seguir mensagem curta em pt-BR.

**Aceite:** sem chamada à LLM em perguntas reconhecidas como não respondíveis; conflitos detectados geram motivo rastreável; perguntas comprovadamente respondíveis não são barradas sem diagnóstico.

### Gate T3 — Grounding de afirmações pós-geração

**Evoluir:** `claim_grounding.py`, `evidence.py`, `grounding_decision.py` (sem alteração silenciosa dos thresholds); testes adversariais.

- Manter segmentação determinística como baseline, mas validar proposições compostas (`A e B`, `A mas B`) e casos em que uma oração contém múltiplos fatos.
- Guardar `chunk_id` e fonte de cada afirmação; impedir que evidência de uma entidade sustente afirmação sobre outra.
- Verificar o mapeamento **real** dos índices de classes NLI (entailment, neutral, contradiction) contra o artefato/versionamento, antes de adicionar score de contradição; nunca supor índice pelo nome.
- Contradição comprovada ou suporte apenas parcial → abstenção para o conjunto em modo `enforce`.
- Se a segmentação for ambígua, longa ou exceder os limites, falhar fechado e registrar razão. Evitar regexes específicos para perguntas do Senac e não alterar NLI por observação isolada do PSG.

**Aceite:** nenhuma frase adicionada sem suporte passa em casos adversariais críticos; testes explícitos para horários, preço, entidades e duas fontes discordantes; falsos negativos documentados.

### Gate T4 — Integração na bancada administrativa

**Evoluir:** `observation.py`, `admin/app.py`, `tests/admin/test_workbench.py`.

- Adicionar o gate **entre** `retriever.search` e `answer_generator.generate`.
- Mostrar decisão **pré-geração** e **pós-geração**, justificativa categorizada, fonte/ID, status temporal, motivo de conflito e latência das etapas.
- Preservar `observe` para benchmarking (registrar o que a LLM teria dito) e `enforce` para testar bloqueio antes da LLM, sem confundir resultados desses dois modos.
- Logs JSONL devem ser aditivos e manter compatibilidade; evitar armazenar transcrição e áudio desnecessários, prever política de retenção e acesso à bancada apenas por loopback.
- Em modo seguro, TTS deve vocalizar somente `presented_answer`, inclusive a frase de abstenção, nunca a resposta bruta bloqueada.

**Aceite:** observabilidade clara, sem quebra da rota `/workbench`, e testes de modo seguro/observação, erro de NLI, evidência ausente, áudio e preservação da resposta original para diagnóstico.

### Gate T5 — Evaluation Harness adversarial e CI

**Criar:** `knowledge/evaluation/answerability-v3-dev.json`, `answerability-v3-holdout.json`, `tests/knowledge/test_answerability.py`, `test_evidence_conflicts.py`, `test_source_policy.py` e, se justificado, `src/orelhao/services/knowledge/answerability_evaluation.py`.

- Produzir no mínimo **120 casos revisados**, com **60 desenvolvimento e 60 holdout bloqueado**, cada grupo equilibrado por casos respondíveis e não respondíveis.
- Categorizar: `supported_literal`, `supported_paraphrase`, `specific_information_missing`, `entity_mismatch`, `temporal_evidence_unavailable`, `conflicting_sources`, `multi_claim`, `unsupported_generation`. Um caso pode possuir mais de uma tag.
- Separar entidades/fontes de desenvolvimento e holdout quando possível. Os casos de calibração existentes e as 17 novas questões não devem ser reutilizados como holdout independente.
- Criar CLI sem conflito com `orelhao knowledge evidence-evaluate` e `knowledge evaluate`: proposta `orelhao knowledge answerability-evaluate <dataset> --json --diagnostics`.
- Métricas: `TP/FP/TN/FN`, precision, recall, specificity, balanced accuracy, **false-allow rate**, false-block rate, por categoria, P50/P95 de adjudicação e de resposta completa. Diferenciar retrieval de answerability.
- CI: `pytest -q`, Ruff, Mypy no escopo novo, invariância dos thresholds, teste de esquemas/datasets e snapshots de decisões.
- Testar versão Python 3.12 para implantação, além do Arch Python 3.14 de desenvolvimento.

**Aceite proposto para iniciar homologação:** zero casos críticos com `ALLOW` indevido no subconjunto adversarial de alto risco (mínimo 30), abstenção correta ≥95% na classe negativa do holdout e queda ≤5 pontos percentuais na aprovação de casos positivos em relação ao baseline **medido pela mesma métrica do pipeline**. Esses números são **gates propostos, não resultados medidos**; com amostras pequenas não garantem segurança estatística.

### Gate T6 — Decisão de promoção ou rejeição

- Reexecutar os mesmos casos com Qwen3.5 0.8B e Tucano2 1.5B, um servidor por vez; registrar custo extra do adjudicador/NLI e RSS.
- Fazer pelo menos uma revisão humana cega de respostas apoiadas/não apoiadas, inclusive os exemplos sobre PSG, novas unidades e editais.
- Exigir testes estáticos no Dell 7050 de 8 GB antes de qualquer promoção para o terminal de produção. Não comparar latência do Arch com o Dell como se fosse equivalente.
- Em regressão, reverter o **gate novo** por configuração e manter o modo observação; não reduzir thresholds para forçar aprovação.

**Aceite:** relatório de decisão **promover/rejeitar**, limitações conhecidas, comando reproduzível, hashes de modelo/dataset/corpus, resultado dos testes, impacto de latência e memória, e documentação Notion/README atualizada. Só então decidir nomenclatura definitiva da release.

## 5. Matriz de situações para testes

| Cenário | Exemplo | Resultado esperado |
|---|---|---|
| Fato institucional estável | Qual é a missão do Senac? | Responder com fonte correspondente |
| Entidade correta | Qual é a carga horária de Excel Avançado? | Responder conforme curso/fonte |
| Troca de unidade | Telefone da unidade Parnaíba com fonte apenas de Teresina | Abster ou pedir unidade/fonte adequada |
| Temporalidade | Há vagas no PSG hoje com apenas edital publicado? | Abster de afirmar disponibilidade |
| Data histórica | Quais editais apareciam em outubro de 2026? | Responder como retrato da publicação |
| Conflito | Duas fontes oficiais com cargas horárias diferentes para mesmo curso/período | Bloquear até resolver precedência |
| Informação específica ausente | Há WhatsApp da unidade se só consta telefone geral? | Abster |
| LLM acrescenta fato | Fonte diz “40 horas”; LLM acrescenta preço | Bloquear resposta final |
| Texto composto | “Curso é gratuito, mas acaba amanhã” | Exigir evidência para cada afirmação |
| Verdadeiro negativo / falso negativo | PSG explicado com fonte primária adequada | Não bloquear sem motivo verificável |

## 6. Ordem de PRs e responsabilidades técnicas

| PR | Escopo | Dependência | Conclusão observável |
|---|---|---|---|
| PR-01 | Baseline, esquema e dataset adversarial dev/holdout | Nenhuma | Relatório reprodutível |
| PR-02 | QueryConstraints e SourcePolicy | PR-01 | Testes de entidade e tempo |
| PR-03 | Answerability/ConflictAdjudicator | PR-02 | LLM não chamada em casos sem suporte |
| PR-04 | Claims + proveniência/contradição | PR-01 a 03 | Sem falso ALLOW crítico no dataset |
| PR-05 | Admin, logs, áudio seguro e gates | PR-03/04 | Caminho integrado em bancada |
| PR-06 | Evaluation CLI, CI e decisão | PR-01 a 05 | Métricas + relatório de go/no-go |

Evitar pull requests grandes e sobrepostos; manter escopo de código/testes/revisão claro e histórico de alterações. Nome da branch e commits de implementação serão definidos quando a execução começar.

## 7. Fora do escopo desta etapa

- Conectar o Arduino, teclado, gancho ou monofone.
- Alterar modelo TTS/STT ou trocar definitivamente a LLM.
- Iniciar automaticamente uma sessão por hardware e implementar `systemd` de produção.
- Raspagem contínua ou consulta online de disponibilidade em produção.
- Adicionar frameworks pesados, banco vetorial remoto, re-treinamento de NLI ou heurísticas específicas para passar no benchmark.
- Garantir que uma fonte coletada no dia da consulta continuará vigente meses depois.

## 8. Definition of Done

A etapa só pode ser declarada **implementada e candidata à homologação** quando: T0–T5 estiverem verificados com testes automatizados; dados e resultados puderem ser reproduzidos; não houver falso ALLOW crítico no holdout definido; ambos os modos da bancada funcionarem; a UI explicar recusas e fontes; TTS vocalizar a **resposta apresentada**; e a documentação registrar explicitamente limitações. A etapa só é **homologada no terminal** depois do gate T6 no Dell.

**Primeiro passo de implementação recomendado:** executar PR-01 e PR-02 sem tocar nos modelos, thresholds ou áudio; só depois integrar a decisão pré-geração.
