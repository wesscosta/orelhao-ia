# Orelhão IA

**Terminal conversacional de voz offline-first**, modular e reutilizável para atendimento a diferentes instituições e domínios de conhecimento. A implantação piloto utiliza documentos oficiais do Senac Piauí; o core não depende dessa instituição.

> **Estado em 29/10/2026:** a **última tag de release encontrada é `v0.3.10`**; a linha `main` permanece na baseline `v0.6.0-alpha.13`, enquanto o desenvolvimento experimental mais recente está na branch [`feat/grounding-v3-decision-policy-20261029`](https://github.com/wesscosta/orelhao-ia/tree/feat/grounding-v3-decision-policy-20261029). **Ainda não foi homologado nem promovido para produção física.** Consulte sempre [Estado técnico vigente](docs/current-state.md).

## Funcionalidades implementadas e limites

- **Voz em bancada:** PipeWire/VAD, faster-whisper para STT local e Piper pt-BR para TTS. O comando `--voice-test` valida o fluxo legado de entrada → transcrição → síntese, **não** uma conversa com RAG e LLM sem intervenção do usuário.
- **Conhecimento/RAG:** fontes editáveis Markdown/TXT, índice local persistente e retrieval baseline; retrievers semânticos/RRF e outras verificações permanecem experimentais.
- **LLM pt-BR:** servidor local `llama.cpp` com cliente HTTP restrito a loopback. Tucano2 1.5B e Qwen3.5 0.8B foram comparados, **sem vencedor homologado**.
- **Answerability e grounding:** verificação de fonte, entidade e atualidade antes da LLM e avaliação NLI por afirmação após a geração. A bancada oferece `observe` e `enforce` como modos experimentais.
- **Admin e voz de resposta:** `http://127.0.0.1:8765/workbench`, com perguntas por texto ou microfone do navegador, TTS por botão **Ouvir resposta**, visualização de evidências e diagnósticos. **Não expor o Admin diretamente em rede**, pois ainda não tem autenticação de produção.
- **Hardware do Orelhão:** teclado 4×4, gancho, Arduino Uno e monofone original são integrações planejadas, ainda **não homologadas no aparelho**.

## Qualidade da branch experimental

| Verificação | Resultado |
|---|---|
| Pytest (Arch Linux, Python 3.14) | **277 testes aprovados** e 1 aviso de depreciação |
| Ruff / Mypy | Sem erros no escopo analisado |
| Corpus Senac Piauí | **18 documentos informativos, 36 chunks** |
| Retrieval original — 40 perguntas | Hit@1 **0,60**, Hit@k **0,833**, abstenção **0,60** |
| Gate adversarial — 40 perguntas, Tucano2 | 0/20 falsas permissões automáticas nos negativos e **8/20 bloqueios indevidos** nos positivos |
| Gate adversarial — 40 perguntas, Qwen3.5 | 0/20 falsas permissões automáticas nos negativos, **10/20 bloqueios indevidos** e **2 respostas NLI-supported sem fatos esperados** |

**Atenção:** os 40 casos foram curados e rotulados por IA a partir de fontes, sem revisão humana independente. Uma taxa de 0/20 falsas permissões **não comprova ausência de alucinações**. O resultado é **NO-GO** para o terminal de atendimento.

Veja [benchmark adversarial](docs/benchmark-grounding-real-2026-10-29.md), [fila de revisão humana](docs/review-grounding-real-2026-10-29.md) e [benchmarks históricos](docs/index.md).

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

## Alvo de hardware e próximos gates

O piloto está restrito ao **Dell OptiPlex 7050 Micro**, i5-7500T (4 núcleos/4 threads), **8 GiB RAM fixos**, SSD ~256 GB, Ubuntu Server 24.04 LTS minimal e inferência CPU. Desempenho da máquina Arch Linux **não substitui benchmark no Dell**. Ainda faltam validação humana independente, redução de falsos bloqueios, integração autônoma de voz e integração eletrônica do monofone, teclado e gancho.

## Documentação

**[Índice da documentação](docs/index.md)** · **[Estado técnico vigente](docs/current-state.md)** · [Arquitetura](docs/architecture.md) · [RAG](docs/rag.md) · [LLM](docs/llm.md) · [Admin](docs/knowledge-admin.md) · [Áudio](docs/audio.md) · [Hardware](docs/hardware.md) · [Operação](docs/operations.md) · [Changelog](CHANGELOG.md)

O antigo README com a cronologia das versões alpha foi [preservado como documento histórico](docs/history/README-before-consolidation-2026-10-29.md); não use seus valores antigos como estado atual.

**Regra de documentação:** commits e testes comprovam implementação experimental, enquanto a passagem de gate, merge, tag e avaliação no hardware comprovam promoção e homologação. São estados diferentes.
