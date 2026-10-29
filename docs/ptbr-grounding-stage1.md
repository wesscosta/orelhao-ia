# Etapa 1 — LLM pt-BR, abstenção e bancada de grounding (29/10/2026)

**Status:** implementação experimental concluída na branch `feat/ptbr-grounding-eval-stage1`; não homologada nem promovida à main.

## Restrições vigentes

- Computador final: Dell OptiPlex 7050 Micro, Core i5-7500T, 8 GB RAM, sem upgrade.
- Computador de desenvolvimento e resultados abaixo: ASUS i7-13620H, Arch Linux, ~24 GB RAM. **Não extrapolar as latências para o Dell.**
- Uma LLM carregada por vez no Dell; só na bancada Arch foram usados servidores em portas distintas.
- Software Python com inferência nativa (`llama.cpp`, ONNX, faster-whisper, Piper); arquitetura modular preservada.

## Entregas

1. Normalização conservadora de recusas completas de evidência e marcadores `INSUFFICIENT_CONTEXT` repetidos/com pontuação; o texto original fica no campo `raw_text` e no relatório comparativo.
2. Prompt explícito de saída curta pt-BR, sem explicação no lugar do marcador de abstenção.
3. Grounding dividido por frases e algumas conjunções/contraposições; uma oração sem suporte bloqueia o todo em modo `enforce`. Isso **não** representa análise semântica atômica garantida.
4. Seleção na interface administrativa entre **Observação** e **Seguro**, exibindo cada afirmação, score NLI e fonte associada.
5. `orelhao llm-benchmark` aceita `--base-url` local, permitindo testes de modelos distintos sem alterar `production.yaml`.
6. Dataset `knowledge/evaluation/llm-ptbr-v1.json`: 20 perguntas sintéticas, 10 com resposta conhecida e 10 envolvendo ausência, troca de entidade, ambiguidade ou conflito.
7. Perfis `config/benchmark-qwen35-08b.yaml` e `config/benchmark-tucano2-15b-ptbr.yaml` apenas para bancada.

## Modelos provisionados — arquivos fora do Git

| Modelo | Proveniência | Artefato GGUF | SHA-256 |
|---|---|---|---|
| Qwen3.5 0.8B Q4_K_M | `bartowski/Qwen_Qwen3.5-0.8B-GGUF` | `models/llm/qwen3.5-0.8b/Qwen_Qwen3.5-0.8B-Q4_K_M.gguf` | `fb044e93939a70469c905781334f5de1e6c8b608ced6cbc8c9249bd4127d9526` |
| Tucano2-qwen-1.5B-Instruct Q4_K_M | upstream `Polygl0t/Tucano2-qwen-1.5B-Instruct` (Apache-2.0), conversão `ayodkay/tucano2-qwen-1.5b-instruct-Q4_K_M`, revisão `05a088d8308da352680773496ab4bed9459c70cd` | `models/llm/tucano2-1.5b-q4/tucano2-qwen-1.5b-instruct-Q4_K_M.gguf` | `f1b749d3076edfe986686114b2585ca5a14ba7ec9ab7b934e9781ad011f938ea` |

A conversão de Tucano2 é um artefato de terceiro. Verificar integridade, tokenizer/chat-template, licenciamento e qualidade antes de distribuição.

## Benchmark de referência (20 casos, versão com normalização)

| Métrica | Qwen3.5 0.8B | Tucano2 1.5B |
|---|---:|---:|
| Execuções concluídas | 20/20 | 20/20 |
| Verificações mecânicas (substring/abstenção) | 13/20 (65%) | 17/20 (85%) |
| Latência P50 | 421,69 ms | 429,09 ms |
| Latência P95 | 607,11 ms | 752,03 ms |
| Taxa média aproximada de geração, casos com tokens | 44,63 tokens/s | 30,83 tokens/s |

**Estes percentuais não são precisão factual, não incluem revisão humana nem medem RAG+NLI+voz no Dell.** Temperatura 0.1 permite alguma variação entre rodadas. A seleção final depende do gate factual e do custo no i5-7500T.

### Riscos detectados

- Qwen respondeu incorretamente a preço, data, relação entre cursos e contexto insuficiente.
- Tucano2 respondeu incorretamente diante de **duas fontes contraditórias** e inventou um horário específico ausente; não foi aprovado para produção.
- O NLI atual usa o maior score encontrado entre fontes. Isso não resolve conflitos de fontes, atualidade e especificidade de entidade. **Bloqueio por frase não basta** para esses casos.
- A bancada administrativa mantém logs com conteúdo de perguntas. A operação real exige política de retenção, privacidade e autenticação.

## Como usar os modelos na bancada Arch

Terminal A — Qwen (se não estiver rodando):

```bash
cd /home/wesscosta/Develop/orelhao-ia
llama-server --model "$PWD/models/llm/qwen3.5-0.8b/Qwen_Qwen3.5-0.8B-Q4_K_M.gguf" \
  --alias local-model --host 127.0.0.1 --port 8080 --ctx-size 2048 \
  --threads 3 --n-gpu-layers 0 --reasoning off --no-webui
```

Terminal B — Tucano2:

```bash
llama-server --model "$PWD/models/llm/tucano2-1.5b-q4/tucano2-qwen-1.5b-instruct-Q4_K_M.gguf" \
  --alias tucano-ptbr --host 127.0.0.1 --port 8081 --ctx-size 2048 \
  --threads 3 --n-gpu-layers 0 --reasoning off --no-webui
```

Terminal C — selecionar o Tucano2 na bancada:

```bash
source .venv/bin/activate
ORELHAO_CONFIG=config/benchmark-tucano2-15b-ptbr.yaml orelhao admin
```

Abrir `http://127.0.0.1:8765/workbench`. Para retornar ao Qwen use
`ORELHAO_CONFIG=config/benchmark-qwen35-08b.yaml orelhao admin`, após parar o admin anterior.

Benchmark reproduzível:

```bash
orelhao llm-benchmark knowledge/evaluation/llm-ptbr-v1.json \
  --model tucano-ptbr --base-url http://127.0.0.1:8081/v1 \
  --max-tokens 96 --max-context-chars 1800 \
  --output /tmp/orelhao-tucano2-15b-ptbr20.json
```

## Próximos gates, em sequência

- **Etapa 2 — Grounding adversarial:** resolver conflitos entre fontes, entidade/município, atualidade e avaliação de cada proposição. Criar holdout independente e métricas de falsos positivos.
- **Etapa 3 — Voz ponta a ponta:** execução efetiva de VAD → STT → RAG → NLI → LLM → TTS, incluindo latência por etapa e testes com áudio real.
- **Etapa 4 — Dell 8 GB:** Linux minimal, inferência CPU, testes de STT base/small INT8, quantização/threads, RSS agregado, P50/P95 e estabilidade térmica.
- **Etapa 5 — Hardware:** Arduino Uno, teclado 4×4, gancho, monofone e cancelamento imediato do atendimento.
- **Etapa 6 — Appliance:** systemd real, watchdog, offline, recuperação, atualização segura da base, privacidade e homologação.

Não fazer release/merge automático enquanto os gates de qualidade e hardware não forem cumpridos.

## Smoke test real adicional — 29/10/2026

O Admin foi iniciado com `ORELHAO_CONFIG=config/benchmark-tucano2-15b-ptbr.yaml`; `GET /workbench/llm-status` confirmou `tucano-ptbr` disponível e a rota `POST /workbench/run` foi testada no modo `enforce`.

Foi encontrada uma falha do gerador que truncava o texto após 600 caracteres **no meio de uma oração**, deixando evidências incompletas. A correção substitui o recorte arbitrário por até três frases completas, até 360 caracteres, com abstenção se nenhuma frase couber. Há teste de regressão.

Com a pergunta "Qual é o PSG?", o Tucano2 produziu duas frases completas, porém o verificador NLI classificou a resposta como `UNSUPPORTED` (score mínimo aproximado 0.041) e o modo seguro exibiu abstenção. O bloqueio funcionou; resta analisar possível **falso negativo** do NLI contra a fonte correta. Não alterar thresholds para esta pergunta sem nova calibração em holdout independente.

O modo `enforce` ainda é experimental e não está habilitado automaticamente no terminal físico. O administrador da bancada permanece restrito a loopback; não expor a rede sem autenticação.
