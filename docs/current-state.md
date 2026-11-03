# Estado técnico vigente — Orelhão IA

**Revisado em:** 03/11/2026, a partir do código, testes e serviços em execução no Dell, branch `feat/esp32-hook-serial-20261030`. As métricas e planos de 29–30/10 permanecem abaixo como **checkpoints históricos**, não como situação corrente, homologação ou nova release.

## Estado operacional experimental — 03/11/2026

| Dimensão | Verificação atual |
|---|---|
| Branch de implementação | `feat/esp32-hook-serial-20261030`, derivada de `f2957c9`; `main` anterior à promoção em `351aacd` |
| Testes no Dell Ubuntu 24.04, Python 3.12 | **471 aprovados**, 1 aviso Starlette; Ruff/Mypy sem erros nos componentes verificados |
| Corpus Senac PI | **28 documentos / 59 trechos**, índice local não versionado |
| Retrieval legado (40 casos) | Hit@1 0,600; Hit@4 0,833; MRR 0,697; acurácia de abstenção 0,600: sem regressão |
| Dataset de expansão (11 perguntas) | Hit@1 1,0; **não independente**, não mede respostas da LLM |
| Nova expansão de Saúde/TI (17 perguntas) | Hit@1 1,0; dados derivados das novas fontes, **não é holdout** |
| Catálogo novembro/2026 (11 perguntas) | Hit@1 1,0; fichas de IA, Power BI, Sala de Vacina e atualização de Excel/Informática. **Conjunto derivado, não é holdout**. [Auditoria](atualizacao-catalogo-2026-11-03.md) |
| Teste real de geração/grounding no Dell | Duração do Técnico em Enfermagem corretamente fundamentada; vagas atuais bloqueadas; **nome de curso alterado pelo Qwen passou indevidamente como supported**. [Auditoria](auditoria-knowledge-2026-11-03.md) |
| Voz física | ESP32 GPIO27/GND e USB serial, monofone P3 com entrada PipeWire pré-ativada por 2,6 s durante a saudação, Whisper small CPU e Piper `length_scale: 0.88`; qualidade STT ainda exige validação humana |
| Monitor do atendimento | `/monitor` por SSE, somente leitura da mesma sessão; sem segundo STT/LLM/TTS |
| Saúde da máquina | `/system` e `/system/state` oferecem telemetria leve CPU/RAM/disco, sensores CPU/SSD e estado de serviços, com polling de 5 s e cache de 4 s. [Operação](system-monitor.md) |
| Memória de diálogo | Até 4 interações na RAM da ligação, contexto de navegação e respostas guiadas. Abstenção do monofone: humor no máximo uma vez por ligação e encaminhamento ao atendimento/supervisão, preservando as causas técnicas no monitor e na bancada |
| Limites do atendimento | 12 perguntas válidas, 36 capturas e 180 segundos; silêncio comum: aviso e encerramento após duas escutas (~14 s); pausa solicitada: até quatro (~28 s), retomando automaticamente se houver fala |
| Segurança do Admin | Somente loopback `127.0.0.1:8765`; túnel SSH para outra máquina, sem autenticação para exposição pública |
| Aprovação do piloto | **NO-GO**, até avaliação humana, microfone/STT confiáveis e ensaios físicos repetidos |

O teclado 4×4 e o display do Orelhão **ainda não estão integrados** ao ESP32. Fontes de cursos de 2026 são históricas: **não atestam vagas e matrículas abertas hoje**. Consulte [hardware/voz](esp32-voice-session.md), [monitor](live-monitor.md), [auditoria atual do Knowledge](auditoria-knowledge-2026-11-03.md), [base/memória anterior](context-and-knowledge-2026-11-03.md) e [operação](operations.md).

## Checkpoint histórico — 30/10/2026

## Identificação e promoção

| Dimensão | Estado verificável |
|---|---|
| Última tag Git de release encontrada | `v0.3.10` (baseline histórica de voz) |
| Base da `main` | `351aacd` — linha v0.6.0-alpha.13 (verificar antes de promover) |
| Branch experimental mais recente | `fix/local-clock-and-abstention-20261030` |
| Commit experimental | HEAD da branch acima (ver histórico Git) |
| Suíte de testes, Arch Python 3.14 | **327 aprovados**, 1 aviso de depreciação de Starlette |
| Lint e tipagem | Ruff aprovado; Mypy aprovado no módulo Knowledge |
| Conhecimento Senac PI indexado | **18 documentos, 36 chunks** (após revisão de Informática Básica) |
| Resultado operacional | **NO-GO** para uso público e terminal físico; teste Dell 8 GB e revisão humana faltantes |

**Importante:** `v0.6.0-alpha.14` aparece em planos e experimentos como rótulo de trabalho, mas **não foi criada tag, release ou aprovação da alpha.14**. A branch não foi mesclada na `main`. Não igualar último commit experimental a versão publicada.

## Desenvolvimento em andamento — Grounding V3 (29/10/2026)

A branch experimental `feat/grounding-v3-diagnostics-20261029` iniciou o **PR-01**, a auditoria diagnóstica do NLI. Foram expostas as três probabilidades (`entailment`, `neutral`, `contradiction`) respeitando os IDs da revisão pinada. O script `scripts/audit_grounding_v3.py` reproduziu 48 avaliações de claims dos relatórios de Tucano2 e Qwen sem alterar a decisão de suporte ou thresholds. **Não é release nem homologação**. Consulte o [relatório do PR-01](grounding-v3-pr01-nli-diagnostics-2026-10-29.md).

Os indicadores da tabela abaixo continuam sendo o **baseline anterior à implementação V3**, e não métricas de progresso de acurácia ou aprovação do novo gate.

### Grounding V3 — PR-02 (29/10/2026)

A branch experimental `feat/grounding-v3-evidence-spans-20261029` implementou **Evidence Span Extraction** (offsets Unicode dentro de `Chunk.text`), seleção lexical independente do score NLI, observabilidade do trecho por claim e script comparativo do NLI do chunk versus passagem. **235 testes** passaram nesta branch; 48 pares auditados (23 scores aumentaram, 24 diminuíram, 1 estável). As decisões de ALLOW/ABSTAIN e os thresholds permanecem inalterados. Consulte [relatório do PR-02](grounding-v3-pr02-evidence-spans-2026-10-29.md). As métricas anteriores de falsos bloqueios continuam sendo o baseline histórico, não um resultado novo de homologação.

### Grounding V3 — PR-03 (29/10/2026)

O **Fact Validator** em `fact_extraction.py` e `fact_validation.py` identifica fatos numéricos explícitos e registra coincidência, divergência, ambiguidade e insuficiência de fonte, com escopo de entidade, unidade, data e proveniência. **250 testes** aprovados, Ruff/Mypy sem erros. Em avaliação retrospectiva de 48 claims: 14 coincidências tipadas, 33 afirmações sem padrão tipado e uma sem fonte admissível. Isso não constitui validação semântica ou revisão humana; o novo resultado **não participa da decisão ALLOW/ABSTAIN** até PR-04. Consulte [relatório PR-03](grounding-v3-pr03-fact-validator-2026-10-29.md).

### Grounding V3 — PR-04 (29/10/2026)

O orquestrador V3 determina o texto apresentado em enforce; observe permanece diagnóstico. A ordem de veto considera pré-gate, recusa da geração, entidade, atributo solicitado ausente, divergência factual, ambiguidade e fontes insuficientes. NLI incerto continua bloqueado mesmo com números coincidentes. **277 testes** aprovados. No benchmark automatizado de 40 casos por modelo: **0/20 falsas permissões** em ambos e **8/20** falsos bloqueios positivos no Tucano2, **11/20** no Qwen. Não há validação humana independente. [Relatório PR-04](grounding-v3-pr04-decision-policy-2026-10-29.md).

**Resolução de entidades:** o adjudicador da bancada recebe catálogo de identidades de todos os chunks persistidos na inicialização, não somente do top-k; curso nomeado sem fonte recuperada recebe abstenção específica. Essa alteração não corrige ranking, e os números do benchmark devem ser comparados após reconstruir o índice.

### Workbench: seleção de voz e identidade (30/10/2026)

Cadu/Faber podem ser selecionados por requisição para sintetizar a mesma resposta, sem alterar o Grounding V3. A prévia de voz usa texto fixo e caminhos de modelos não são aceitos do navegador. A identidade da LLM usa **o Lumi**; o texto corrigido passa pelo grounding e a saída bruta existe na conclusão da LLM, mas não é persistida no JSONL da bancada. Faber deve ser provisionada localmente; o TTS físico permanece inalterado. **285 testes** aprovados. [Relatório do experimento](workbench-piper-voices-lumi-2026-10-30.md).

### Correção de data/hora local e abstenção repetida (30/10/2026)

O Workbench roteia perguntas exclusivamente sobre dia e horário ao serviço determinístico `local_clock`. RAG/LLM/NLI não são executados; a fonte é o relógio local, com fuso `ORELHAO_TIMEZONE`, timestamp ISO e NLI marcado como não aplicável, sem score artificial. Perguntas institucionais temporais (vagas, atendimento) continuam no RAG. A normalização de recusas cobre marcadores repetidos `INSUFFICIENT CONTEXT` do Tucano2 e impede leitura dos marcadores antigos no TTS. **327 testes**, Ruff/Mypy Knowledge/LLM sem erros e smoke HTTP com Cadu/Faber. [Relatório](local-clock-abstention-fix-2026-10-30.md).

## O que realmente existe

- **Áudio:** captura PipeWire, VAD, STT local faster-whisper pt-BR e Piper TTS, com comandos de diagnóstico e `--voice-test`. O teste de voz histórico `STT → TTS` não demonstra fluxo `STT → RAG → LLM → TTS` autônomo.
- **Conhecimento:** fontes versionadas `knowledge/sources`, índice local derivado, retrieval baseline híbrido lexical + hashing, Semantic/RRF/QA experimentais não promovidos e Evaluation Harness.
- **LLM:** cliente HTTP exclusivamente loopback, compatível com API OpenAI; servidores `llama.cpp` são processos independentes provisionados. Candidatos testados em CPU Arch: Tucano2-qwen-1.5B-Instruct GGUF e Qwen3.5-0.8B GGUF.
- **Grounding:** `EvidenceAdjudicator` anterior à geração para situações verificáveis de entidade, unidade, atributo, conflito estruturado e atualidade; pós-verificação NLI por afirmação, `GroundingPolicy` com estados `supported/uncertain/unsupported` e `chunk_id` de suporte. Identificação de entidade reduz mistura entre `Excel` e `Excel Avançado` quando IDs estão presentes.
- **Admin:** `http://127.0.0.1:8765/workbench`, modo `observe` para diagnóstico ou `enforce` para testar bloqueio; estado de LLM/TTS, captura de navegador, transcrição, síntese ao clicar em **Ouvir resposta**, motivos de decisão e logs locais de observações.
- **Sem garantia:** texto livre sem entidade estruturada, contradições semânticas entre documentos e pontuação NLI `supported` não garantem veracidade factual; aplicações podem sofrer bloqueios indevidos.

## Métricas recentes — não confundir tarefas

| Avaliação | Resultado da branch experimental | Interpretação |
|---|---|---|
| Retrieval v1, 40 casos | Hit@1 **0,600**; Hit@k **0,833**; MRR **0,697**; abstenção **0,600** | Ranking/seleção de fontes, não acerto da resposta |
| Retrieval refresh, 17 casos | Hit@1 **0,833**; Hit@k **1,000**; abstenção **0,200** | Evidência adicional de falha do retriever em negativos |
| Answerability sintética, 120 casos | 60/60 dev e 60/60 holdout sintético (modelados por templates semelhantes) | Teste de contratos e lógica, **não** holdout semântico independente |
| Grounding realístico, 40 perguntas (Tucano2) | 0/20 falsos `ALLOW` nos negativos, **8/20 falsos bloqueios** nos positivos, 12/20 positivos com termos esperados | Rótulos e checagens automáticos, sem adjudicação humana |
| Grounding realístico, 40 perguntas (Qwen) | 0/20 falsos `ALLOW` nos negativos, **10/20 falsos bloqueios**, **2 respostas NLI-supported sem âncoras esperadas** | Risco de falso suporte semântico; candidato não homologado |
| Latência textual no Arch | P50 **741 ms** Tucano2; **302 ms** Qwen | Não inclui STT/TTS nem representa Dell |

Benchmarks com respostas e diagnóstico: [Relatório adversarial](benchmark-grounding-real-2026-10-29.md), [resultados JSON](../knowledge/evaluation/results/) e [fila de revisão humana](review-grounding-real-2026-10-29.md).

**Não afirmar taxa de alucinação igual a zero:** os 20 casos negativos são insuficientes; a validação de âncoras não captura todos os erros semânticos.

## Configuração e execução válidas

```bash
# Instalação isolada (Arch de desenvolvimento, com dependências opcionais)
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,admin,audio,stt,tts,vad,semantic,evidence]'

# Fontes editáveis, índice reconstruível
orelhao knowledge index
orelhao knowledge evaluate --retriever baseline --json

# Conjunto com perguntas reais de domínio, ainda não adjudicado por humanos
python scripts/run_live_grounding_gate.py \
  --config config/benchmark-tucano2-15b-ptbr.yaml \
  --dataset knowledge/evaluation/grounding-real-senac-pi-v1.json \
  --output /tmp/orelhao-grounding-report.json

# A LLM local e os modelos ONNX precisam estar provisionados/iniciados previamente.
ORELHAO_CONFIG=config/benchmark-tucano2-15b-ptbr.yaml orelhao admin
# Acesse http://127.0.0.1:8765/workbench
pytest -q
```

A configuração benchmark Tucano2 pressupõe servidor compatível em `127.0.0.1:8081` com alias `tucano-ptbr`. A instalação dos pesos e a execução do `llama-server` são separadas. Os pesos GGUF/ONNX, índice e logs de observação **não entram no Git**.

## Restrições físicas e gates ainda pendentes

- **Hardware alvo:** Dell OptiPlex 7050 Micro, i5-7500T 4C/4T, 8 GiB RAM sem expansão e SSD ~256GB; Ubuntu Server 24.04 LTS minimal e Python 3.12, uma sessão por vez, inferência inicial em CPU. Benchmarks executados apenas no Arch de desenvolvimento.
- **Periféricos:** Arduino Uno, teclado matricial 4×4 IDC, interruptor do gancho e monofone original com interface de áudio apropriada; cabeamento/pinagem/impedância e ciclos de uso **não validados fisicamente**.
- **Operação:** `systemd`, watchdog, segurança/privacidade da administração, sessão de voz totalmente autônoma e testes térmicos são metas de MVP, não funcionalidades homologadas.
- **Qualidade:** revisão humana dos 15 casos adversariais sinalizados, amostra dos 25 outros, novo holdout cego e redução de falso bloqueio são pré-requisitos. Não recalibrar NLI nos casos que já serviram ao desenvolvimento.

## Fonte de verdade e manutenção

1. **Implementação:** código e testes da branch identificada; `main` e tags para estado promovido.
2. **Situação viva:** este arquivo e o [índice documental](index.md), atualizados após cada novo gate.
3. **Decisões históricas:** [CHANGELOG](../CHANGELOG.md), [README histórico arquivado](history/README-before-consolidation-2026-10-29.md) e relatórios datados; seus números não são métricas vigentes.
4. **Notion:** visão institucional, requisitos, roadmap e testes com link para esta fonte técnica; evitar duplicar integralmente logs ou relatórios extensos.

**Regra de manutenção:** a cada alteração do estado da branch, atualizar hash/indicadores neste documento somente após testes confirmados, preservando histórico e anotando NO-GO/GO explicitamente.
