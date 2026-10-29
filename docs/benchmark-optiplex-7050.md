# Plano de avaliação de LLMs — Dell OptiPlex 7050 Micro (2026-10-28)

## Restrição fixa

- Dell OptiPlex 7050 Micro, Intel Core i5-7500T (4 núcleos/4 threads), 8 GiB de RAM instalada e armazenamento da classe 256 GB.
- Não há autorização ou disponibilidade para ampliar RAM, GPU ou substituir a máquina.
- Sistema alvo: Ubuntu Server 24.04 LTS minimal, Python 3.12; operação offline-first, uma sessão por vez.
- O computador Arch Linux de desenvolvimento NÃO é o hardware homologável. Benchmarks feitos nele não substituem testes no Dell.

## Ordem de experimentação

1. Qwen3.5-0.8B em GGUF quantizado e compatível com o runtime.
2. Qwen3.5-2B Q4 (ou quantização equivalente com revisão explícita).
3. Bonsai 2 2B Q2_0; PQ2_0 apenas em runtime separado e validado.
4. Tucano2 1.5B-Instruct como comparação linguística, se houver artefato de inferência compatível.

Não há promoção automática de candidatos nem download de pesos durante o atendimento.
Cada rodada usa somente um servidor e um modelo carregado por vez. Registrar revisão,
checksum e licença de cada arquivo. Testar todos os candidatos com o mesmo dataset.

## Benchmark isolado

Após provisionar legalmente o GGUF escolhido, executar servidor SOMENTE em loopback:

```bash
llama-server --model /caminho/para/modelo.gguf \
  --alias local-model --host 127.0.0.1 --port 8080 \
  --ctx-size 2048 --threads 3 --n-gpu-layers 0
```

Na aplicação, conferir se `llm.model` corresponde ao alias `local-model` e executar:

```bash
orelhao llm-benchmark knowledge/evaluation/llm-smoke-v1.json \
  --model local-model --max-tokens 96 --max-context-chars 1800 \
  --output /tmp/llm-smoke-local-model.json
```

Opcionalmente: `--server-pid PID` registra RSS do processo local no Linux.
O relatório registra P50/P95 de latência (incluindo geração), tokens usados se
retornados pela API, tokens/s quando fornecidos pelo servidor e verificações
mecânicas. O conjunto `llm-smoke-v1.json` é sintético e NÃO certifica qualidade.

## Gate antes da promoção

- Avaliar um corpus representativo e congelado de português brasileiro, com
  entidades, informações ausentes, atualidade, contradições e perguntas coloquiais.
- Revisar respostas humanas às cegas; uma verificação de substring não é prova factual.
- Confirmar abstenção em casos sem evidência e nenhuma regressão crítica de grounding.
- Registrar VAD, STT, retrieval, NLI, LLM e TTS isoladamente e no pipeline completo.
- Medir RAM residente dos processos combinados, ausência de swap sustentado,
  temperatura, consumo, falhas, P50/P95 e tempo até primeiro áudio.
- Validar offline e 30+ ciclos seguidos de uso, antes de qualquer decisão de produção.

## Grounding alpha.14: status experimental

`ObservationWorkbench(mode="enforce")` aplica decisão conservadora por frases:
todas devem ser suportadas; o menor score define a decisão. Se houver
`UNCERTAIN` ou `UNSUPPORTED`, somente a mensagem segura é apresentada.
`mode="observe"` permanece a configuração padrão na bancada.

A segmentação determinística ainda não decompõe todas as conjunções, entidades
ou relações temporais dentro de uma mesma frase. Não há certificação de
atomicidade semântica, nem promoção do gate ao terminal físico. O dataset
adversarial precisa cobrir esses casos antes da homologação.
