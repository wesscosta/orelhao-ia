# LLM local e grounding — operação experimental

**Atualizado em 29/10/2026.** A evolução da alpha.13 passou por implementação do pré-gate e pelo benchmark adversarial, mas **não existe release alpha.14 homologada**. Estado, modelos e erros conhecidos: [Estado vigente](current-state.md), [gate adversarial](benchmark-grounding-real-2026-10-29.md).

## Runtime

O Orelhão IA utiliza cliente HTTP compatível com `POST /v1/chat/completions`, restrito a `127.0.0.1`, `localhost` ou `::1`. O `llama-server` é um serviço **externo ao processo Python** e precisa estar iniciado antes da bancada. Exemplo CPU conservador:

```bash
llama-server --model /caminho/absoluto/modelo.gguf \
  --alias tucano-ptbr --host 127.0.0.1 --port 8081 \
  --ctx-size 2048 --threads 3 --n-gpu-layers 0
curl -s http://127.0.0.1:8081/v1/models | python -m json.tool

ORELHAO_CONFIG=config/benchmark-tucano2-15b-ptbr.yaml orelhao admin
```

A configuração de benchmark utiliza `llm.model: tucano-ptbr`, `base_url: http://127.0.0.1:8081/v1`, `max_tokens: 96`, `max_context_chars: 1800`, `temperature: 0.1` e timeout de 45 segundos. Configurações distintas são possíveis; sempre confira o alias de `/v1/models`. Modelos não são baixados automaticamente pelo atendimento.

## Geração e verificação

```text
Pergunta → Retrieval → EvidenceAdjudicator → LLM → claims/NLI → GroundingPolicy → presented_answer
```

- **Pré-gate:** verifica ausência de fontes, entidade/unidade, temporalidade de estado atual e conflitos nos metadados estruturados. Em `enforce`, pode **não chamar a LLM**.
- **LLM:** recebe somente contexto admissível no modo seguro. Gera resposta curta fundamentada no corpus e usa `INSUFFICIENT_CONTEXT` quando não encontra resposta; o sentinel é convertido em abstenção local.
- **Pós-gate:** separação determinística de afirmações, maior score de suporte por chunk, mínimo entre claims e decisão de três estados. `UNCERTAIN` e `UNSUPPORTED` bloqueiam a resposta no modo seguro; a voz só sintetiza `presented_answer`.
- **Entidade:** IDs documentais reduzem mistura entre nomes sobrepostos; resposta mencionando outra entidade conhecida pode ser bloqueada mesmo com score alto de NLI.
- **Limitações:** não se garante atomicidade de proposições compostas nem identificação universal de entidades/contradições em prosa. `SUPPORTED` não é certificação de fato verdadeiro.

Os thresholds NLI continuam **congelados**, `unsupported < 0.1250362694` e `supported >= 0.7557643056`. Não retocar com base nos casos de desenvolvimento.

## Modelos observados

| Modelo | Status na máquina Arch de desenvolvimento |
|---|---|
| Tucano2-qwen-1.5B-Instruct Q4_K_M | candidato pt-BR preferido para próximas avaliações; 8/20 bloqueios indevidos em dataset naturalístico |
| Qwen3.5-0.8B Q4_K_M | mais rápido no Arch, porém 10/20 bloqueios indevidos e duas respostas NLI-supported sem âncoras esperadas |

Nenhum possui aprovação de produção, e não foi realizado benchmark completo no Dell 8GB. Os 20 casos iniciais de LLM eram sintéticos. O dataset novo de 40 perguntas foi curado por IA e usado para corrigir o projeto, **não é holdout cego**.

## Execução de avaliação

```bash
orelhao llm-benchmark knowledge/evaluation/llm-ptbr-v1.json \
  --base-url http://127.0.0.1:8081/v1 --model tucano-ptbr \
  --max-tokens 96 --max-context-chars 1800 \
  --output /tmp/llm-ptbr.json

python scripts/run_live_grounding_gate.py \
  --config config/benchmark-tucano2-15b-ptbr.yaml \
  --dataset knowledge/evaluation/grounding-real-senac-pi-v1.json \
  --output /tmp/grounding-tucano.json
```

**Atenção:** `llm-benchmark` testa respostas da LLM com contextos fornecidos; o segundo script testa retrieval → pré-gate → LLM → NLI, mas não integra STT/TTS do monofone.

Relatórios: [etapa pt-BR inicial](ptbr-grounding-stage1.md), [implementação do pré-gate](implementation-answerability-stage2-2026-10-29.md), [comparação realística](benchmark-grounding-real-2026-10-29.md), [plano do Dell](benchmark-optiplex-7050.md).
