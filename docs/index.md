# Índice oficial de documentação — Orelhão IA

Revisão editorial: **30/10/2026**. Este é o ponto de entrada para documentação atual e histórico. Os relatórios datados descrevem o estado **na data do experimento** e não substituem [Estado vigente](current-state.md).

## Documentos operacionais vivos

| Documento | Responsabilidade |
|---|---|
| [Estado vigente](current-state.md) | Versão, branch, testes, métricas, limitações e próximos gates |
| [Arquitetura](architecture.md) | Módulos, integração e fronteiras entre experimental e produção |
| [Knowledge / RAG](rag.md) | Corpus, retrieval e decisões de grounding |
| [LLM](llm.md) | Início do servidor local, modelos, geração e segurança factual |
| [Admin e bancada](knowledge-admin.md) | Indexação, testes de pergunta/voz, segurança e logs |
| [Áudio](audio.md), [entrada](voice-input.md), [STT](stt.md) e [TTS](tts.md) | Captura, reconhecimento, síntese e diagnósticos |
| [Hardware](hardware.md) | Restrição Dell 8 GiB e integração física planejada |
| [Plano de benchmark Dell](benchmark-optiplex-7050.md) | Gates do hardware físico, ainda não executados |
| [Operação](operations.md) | Comandos atuais versus appliance planejado |
| [Changelog](../CHANGELOG.md) | Histórico versionado, com experimental separado de releases |
| [Conhecimento](../knowledge/README.md) e [modelos](../models/README.md) | Organização e provisionamento |

## Relatórios datados — preservar como snapshots

| Evidência | Data / corte | Uso |
|---|---|---|
| [Cobertura inicial](knowledge-coverage-audit-2026-10-29.md) | 14 docs / 23 chunks **antes da ingestão** | diagnóstico histórico |
| [Atualização da base](knowledge-refresh-senac-pi-2026-10-29.md) | 18 docs / 35 chunks **antes da última revisão** | proveniência e benchmark de 17 casos |
| [Cadu/Faber e identidade do Lumi](workbench-piper-voices-lumi-2026-10-30.md) | 30/10/2026, alternância por requisição | experimental, não homologado |
| [Voz na bancada](workbench-voice-fix-2026-10-29.md) | saída Piper restaurada | correção validada no Arch |
| [Etapa pt-BR inicial](ptbr-grounding-stage1.md) | 20 casos sintéticos | comparação exploratória |
| [Plano Etapa 2](plan-grounding-answerability-stage2.md) | proposta aprovada anteriormente | requisitos e gates originais |
| [Implementação Etapa 2](implementation-answerability-stage2-2026-10-29.md) | 210 testes naquela etapa | pré-gate de evidência |
| [Grounding V3 — PR-04: política de decisão](grounding-v3-pr04-decision-policy-2026-10-29.md) | 29/10/2026, veto factual, completude e comparação dos modelos | **experimental, não homologado** |
| [Grounding V3 — PR-03: Fact Validator](grounding-v3-pr03-fact-validator-2026-10-29.md) | 29/10/2026, atributos tipados, divergências e escopo | instrumentação factual experimental; **sem enforcement** |
| [Grounding V3 — PR-02: Evidence Span Extraction](grounding-v3-pr02-evidence-spans-2026-10-29.md) | 29/10/2026, offsets, seleção lexical e NLI chunk × passagem | instrumentação experimental; **não homologada** |
| [Grounding V3 — PR-01: auditoria NLI](grounding-v3-pr01-nli-diagnostics-2026-10-29.md) | 29/10/2026, diagnóstico triclasse sem mudança de decisão | primeira entrega da próxima etapa, **não homologada** |
| [Gate adversarial mais recente](benchmark-grounding-real-2026-10-29.md) | 216 testes, 18/36, NO-GO | avaliação Tucano2 × Qwen |
| [Fila de revisão](review-grounding-real-2026-10-29.md) | 15 casos sinalizados | trabalho humano pendente |
| [README anterior à consolidação](history/README-before-consolidation-2026-10-29.md) | narrativa antiga integral | rastreabilidade, **não vigente** |

## Organização da informação

- **README raiz:** onboarding, resumo atual e navegação.
- **Estado vigente:** números e decisões atuais, sem duplicar páginas longas.
- **Docs operacionais:** como executar, parâmetros e limitações.
- **Relatórios/histórico:** evidências imutáveis de checkpoints; cabeçalho esclarece natureza histórica.
- **Notion:** visão de projeto, requisitos, roadmap e testes; links para relatórios do repositório, sem repetir detalhes de implementação.

Nenhuma documentação deve declarar a v0.6.0-alpha.14 homologada antes de tag, aprovação factual em holdout humano e avaliação no Dell 8 GiB.
