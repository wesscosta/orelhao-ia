# Orelhão IA

**Terminal conversacional de voz offline-first**, modular e reutilizável para atendimento a diferentes instituições e domínios de conhecimento. A implantação piloto utiliza documentos oficiais do Senac Piauí; o core não depende dessa instituição.

> **Estado em 03/11/2026:** o experimento físico do Dell com ESP32, monofone P3 e monitor web está na branch `feat/esp32-hook-serial-20261030`. A `main` permanece no checkpoint `v0.6.0-alpha.13` até revisão e integração. **Não é release nem homologação para atendimento público.** Veja o [estado técnico](docs/current-state.md) e o [fluxo físico](docs/esp32-voice-session.md).

## Funcionalidades implementadas e limites

- **Voz em bancada:** PipeWire/VAD, faster-whisper para STT local e Piper pt-BR para TTS. O comando `--voice-test` valida o fluxo legado de entrada → transcrição → síntese, **não** uma conversa com RAG e LLM sem intervenção do usuário.
- **Conhecimento/RAG:** fontes editáveis Markdown/TXT, índice local persistente e retrieval baseline; retrievers semânticos/RRF e outras verificações permanecem experimentais.
- **LLM pt-BR:** servidor local `llama.cpp` com cliente HTTP restrito a loopback. Tucano2 1.5B e Qwen3.5 0.8B foram comparados, **sem vencedor homologado**.
- **Answerability e grounding:** verificação de fonte, entidade e atualidade antes da LLM e avaliação NLI por afirmação após a geração. A bancada oferece `observe` e `enforce` como modos experimentais.
- **Admin, bancada e monitor:** `http://127.0.0.1:8765/workbench` para testes no navegador, `/monitor` para espelhar a **mesma sessão física** via SSE e `/system` para acompanhar CPU, RAM, disco, temperaturas e serviços em tempo real, sem segunda inferência nem agente residente. **Não expor o Admin diretamente à rede**, pois não há autenticação de produção.
- **Hardware experimental:** ESP32 DevKit controla o contato seco do gancho via USB serial, iniciando/interrompendo o processo de voz no Dell Ubuntu; há testes físicos do monofone P3 e monitor. **Teclado 4×4 e display continuam pendentes**. Nada disso está homologado para atendimento público.

## Qualidade da branch experimental

| Verificação | Resultado |
|---|---|
| Pytest (Dell Ubuntu 24.04, Python 3.12) | **475 testes aprovados**, 1 aviso de depreciação Starlette (03/11/2026) |
| Ruff / Mypy | Sem erros nos módulos avaliados no Dell |
| Corpus Senac Piauí | **28 documentos indexados, 59 chunks**; índice reconstruível fora do Git |
| Retrieval original — 40 perguntas | Hit@1 **0,60**, Hit@k **0,833**, abstenção **0,60** |
| Gate adversarial — 40 perguntas, Tucano2 | 0/20 falsas permissões automáticas nos negativos e **8/20 bloqueios indevidos** nos positivos |
| Gate adversarial — 40 perguntas, Qwen3.5 | 0/20 falsas permissões automáticas nos negativos, **10/20 bloqueios indevidos** e **2 respostas NLI-supported sem fatos esperados** |

**Atenção:** os 40 casos foram curados e rotulados por IA a partir de fontes, sem revisão humana independente. Uma taxa de 0/20 falsas permissões **não comprova ausência de alucinações**. O resultado é **NO-GO** para o terminal de atendimento.

Veja [benchmark adversarial](docs/benchmark-grounding-real-2026-10-29.md), [fila de revisão humana](docs/review-grounding-real-2026-10-29.md) e [benchmarks históricos](docs/index.md).

## Experimento físico no Dell — 03/11/2026

O fluxo em teste é **gancho ESP32 → USB serial → sessão do monofone P3 → Whisper small CPU → consulta guiada ou RAG/LLM com grounding `enforce` → Piper 0.88**. A abertura atual é “Olá! Eu sou o Lumi. Como posso ajudar?”. O fluxo de cursos reconhece a escolha “Programação” após Informática e pode solicitar a cidade, apresentando apenas anúncios históricos identificados como tais. A entrada PipeWire é pré-ativada durante a saudação para evitar o transiente observado no Dell. A captura e reprodução P3 agora usam alvos PipeWire explícitos no perfil local do servidor; o ganho analógico foi reduzido para evitar saturação. [Detalhes e validação pendente de fala real](docs/audio.md). A ligação mantém memória curta, até 12 perguntas válidas, 36 tentativas de captura e 180 segundos. O silêncio normal recebe um aviso e encerra após duas escutas sem fala (~14 s); pedido explícito de pausa permite até quatro escutas (~28 s), com retorno automático quando houver fala. Mensagens fixas possuem WAV em cache local.

O [monitor SSE](docs/live-monitor.md) espelha **a mesma sessão**, sem inferência nem transmissão de áudio adicionais, e apaga a transcrição da visualização ao encerrar. Em recusas, a voz adota humor pontual inspirado no orelhão, com orientação ao atendimento ou à supervisão conforme o assunto, mas mantém as razões de grounding no monitor. O acesso web continua restrito a `localhost`: outras máquinas devem usar túnel SSH. A [base ampliada](docs/atualizacao-catalogo-2026-11-03.md) tem 28 documentos e 59 trechos, incluindo fichas recentes de IA, Power BI e Sala de Vacina, além de Saúde e cursos técnicos de TI por unidade; o benchmark legado de 40 casos **não regrediu**. Um teste real mostrou, porém, que o grounding ainda pode aprovar um nome de curso alterado indevidamente pela LLM. **Não homologado.**

Mais detalhes: [sessão física](docs/esp32-voice-session.md), [memória e base](docs/context-and-knowledge-2026-11-03.md) e [operação](docs/operations.md).

## Desenvolvimento

Requisitos: Python 3.12+ no alvo planejado e ambiente virtual. Os comandos de exemplo pressupõem dependências de áudio, Admin e modelos locais provisionados.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,admin,audio,stt,tts,vad,semantic,evidence]'

# Índice e testes
orelhao knowledge index
orelhao knowledge search "O que é o PSG?" --limit 4
orelhao knowledge evaluate --retriever baseline --json
pytest -q

# Diagnóstico da voz
orelhao --list-audio-devices
orelhao --audio-diagnose
orelhao --stt-test
orelhao --tts-test "Teste de voz do Orelhão IA."
orelhao --voice-test

# Bancada experimental (requer servidor LLM local iniciado em 127.0.0.1:8081)
ORELHAO_CONFIG=config/benchmark-tucano2-15b-ptbr.yaml orelhao admin
```

O servidor `llama-server` não é iniciado automaticamente pela aplicação: seus pesos GGUF devem estar provisionados, com modelo e alias compatíveis com a configuração. Para a bancada, acesse `http://127.0.0.1:8765/workbench`.

Para repetir o gate adversarial completo:

```bash
python scripts/run_live_grounding_gate.py \
  --config config/benchmark-tucano2-15b-ptbr.yaml \
  --dataset knowledge/evaluation/grounding-real-senac-pi-v1.json \
  --output /tmp/orelhao-grounding-report.json
```

## Grounding V3 — implementação iniciada

O primeiro incremento da nova etapa adiciona **auditoria triclasse do NLI** e classificação reproduzível de falhas de retrieval, pré-gate e pós-gate. Não modifica thresholds nem promove modelos. Consulte [PR-01 e resultados do NLI](docs/grounding-v3-pr01-nli-diagnostics-2026-10-29.md) e [estado técnico](docs/current-state.md). O quadro de qualidade acima continua sendo o baseline anterior à V3.

### PR-02 — Evidence Span Extraction (29/10/2026)

A linha experimental do Grounding V3 passou a registrar **trechos literais do chunk com offsets verificáveis** em cada avaliação de afirmação e na bancada. Uma auditoria com o NLI ONNX comparou chunks inteiros com passagens curtas: 48 pares, 23 scores maiores, 24 menores e 1 estável. **Sem alteração da política factual ou promoção de modelo.** Consulte [PR-02 e diagnóstico](docs/grounding-v3-pr02-evidence-spans-2026-10-29.md).

### PR-03 — Fact Validator (29/10/2026)

O Grounding V3 passou a registrar comparações **diagnósticas** de valores, horas, idade mínima, prazos, vagas, telefones e datas, sob escopo de entidade/unidade/vigência. Sem alteração de thresholds nem do comportamento de aprovação. A auditoria retrospectiva encontrou 14 correspondências tipadas em 48 claims arquivadas; isso **não** é medida de acurácia. Consulte [relatório PR-03](docs/grounding-v3-pr03-fact-validator-2026-10-29.md).

### PR-04 — Grounding Decision V3 (29/10/2026)

A decisão final agora combina NLI, pré-gate, entidade e Fact Validator. Em modo seguro, divergências verificáveis e atributos faltantes bloqueiam texto e áudio; ofertas múltiplas podem exigir esclarecimento. Correspondência lexical/numérica não eleva NLI incerto para resposta aprovada. **277 testes** aprovados; avaliação com 40 casos por modelo: 0 falsas permissões nos 20 negativos de cada, **8/20** falsos bloqueios Tucano2 e **11/20** Qwen. Conjunto não independente. Veja [Relatório PR-04](docs/grounding-v3-pr04-decision-policy-2026-10-29.md).

**Escopo do catálogo:** a bancada carrega todas as entidades indexadas para verificar cursos nomeados, evitando confundir ausência de evidência para Excel com ofertas de Informática Básica. Novas fontes requerem reindexação e reinício do Admin.

### Alternância de vozes no Workbench (30/10/2026)

A bancada agora permite alternar Piper Cadu e Faber sem reiniciar e ouvir a mesma resposta sem recomputar retrieval/LLM/Grounding. A saudação utiliza o masculino **o Lumi**; a LLM também recebe essa instrução e a correção é aplicada antes do grounding. Cadu continua como padrão; instale a Faber com python scripts/provision_piper_faber.py. Veja [relatório técnico](docs/workbench-piper-voices-lumi-2026-10-30.md).

### Data/hora e abstenção segura (30/10/2026)

Perguntas exclusivas de data/hora agora usam o relógio local com fuso `ORELHAO_TIMEZONE` (padrão America/Fortaleza), sem RAG ou LLM. O Grounding registra a origem `local_clock` e NLI `not_applicable`, sem score artificial. A normalização reconhece repetições de `INSUFFICIENT CONTEXT` com espaços e impede que o marcador seja sintetizado. **327 testes** aprovados. [Relatório de correção](docs/local-clock-abstention-fix-2026-10-30.md).

## Alvo de hardware e próximos gates

O piloto está restrito ao **Dell OptiPlex 7050 Micro**, i5-7500T (4 núcleos/4 threads), **8 GiB RAM fixos**, SSD ~256 GB, Ubuntu Server 24.04 LTS minimal e inferência CPU. Desempenho no Arch Linux **não substitui benchmark no Dell**. A sessão pelo gancho/ESP32 e áudio P3 já funcionam em testes físicos, mas ainda faltam validação humana independente, redução de falsos bloqueios, confiabilidade do STT, estabilidade em ciclos prolongados, teclado e display.

## Documentação

**[Índice da documentação](docs/index.md)** · **[Estado técnico vigente](docs/current-state.md)** · [Gancho e voz](docs/esp32-voice-session.md) · [Monitor web](docs/live-monitor.md) · [Contexto e base ampliada](docs/context-and-knowledge-2026-11-03.md) · [Arquitetura](docs/architecture.md) · [RAG](docs/rag.md) · [LLM](docs/llm.md) · [Admin](docs/knowledge-admin.md) · [FAQ supervisionado e diagnóstico de áudio](docs/faq-supervisionado-audio-diagnostico.md) · [Áudio](docs/audio.md) · [Hardware](docs/hardware.md) · [Operação](docs/operations.md) · [Changelog](CHANGELOG.md)

O antigo README com a cronologia das versões alpha foi [preservado como documento histórico](docs/history/README-before-consolidation-2026-10-29.md); não use seus valores antigos como estado atual.

**Regra de documentação:** commits e testes comprovam implementação experimental, enquanto a passagem de gate, merge, tag e avaliação no hardware comprovam promoção e homologação. São estados diferentes.
