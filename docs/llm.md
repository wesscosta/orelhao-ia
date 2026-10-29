# LLM local — v0.6.0-alpha.13

A bancada usa um servidor de inferência local compatível com a rota OpenAI `POST /v1/chat/completions`. O cliente rejeita hosts externos e aceita apenas `127.0.0.1`, `localhost` ou `::1` por HTTP.

## Contrato operacional

O servidor e o modelo são dependências da implantação. A aplicação não baixa pesos durante o atendimento e não inicia processos externos silenciosamente. O exemplo abaixo pressupõe um GGUF já provisionado:

```bash
llama-server \
  --model /caminho/absoluto/modelo-instruct.gguf \
  --alias local-model \
  --host 127.0.0.1 \
  --port 8080 \
  --ctx-size 4096 \
  --n-gpu-layers auto
```

O `llama.cpp` documenta `llama-server` como servidor com Chat Completions compatível com OpenAI. Por padrão, ele usa `127.0.0.1:8080`; `--alias` define o identificador exposto por `/v1/models` e usado pela aplicação.

Confirme antes de abrir o Admin:

```bash
curl -s http://127.0.0.1:8080/v1/models | python -m json.tool
```

O ID retornado deve coincidir com `llm.model` em `config/development.yaml` ou `config/production.yaml`.

## Política de geração

A LLM recebe somente os chunks recuperados, com fonte e texto, limitada a 6.000 caracteres. A configuração padrão usa temperatura `0.1`, até 180 tokens e timeout de 45 segundos. A saída deve ter no máximo três frases sem Markdown.

Se as evidências não responderem diretamente à pergunta, a LLM deve retornar exatamente `INSUFFICIENT_CONTEXT`. O adaptador converte esse sentinel em uma mensagem segura e o grounding recebe score zero. A indisponibilidade da LLM produz erro explícito; não há fallback silencioso para o gerador extrativo.

Esta etapa permanece em modo de observação. A alpha.14 deverá decompor respostas em afirmações e exigir suporte para todas antes de ativar o gate fail-closed.


## Desenvolvimento experimental posterior à alpha.13 (branch, não release)

A alpha.14 experimental inclui `assess_answer`, que divide uma resposta
em frases e verifica cada uma com NLI contra os chunks recuperados. O menor
score determina `GroundingDecision`; em `ObservationWorkbench(mode="enforce")`,
`UNSUPPORTED` ou `UNCERTAIN` substituem a saída exibida por abstenção.
O modo `observe` permanece padrão e registra decisões por frase e fonte.
Este verificador é conservador, mas a decomposição por frases não garante
atomicidade semântica quando há várias proposições na mesma frase.

O comando `orelhao llm-benchmark` prepara comparações seriais de candidatos
leves e exige servidor previamente configurado em loopback. Sem pesos
provisionados e sem benchmark no Dell, não há modelo vencedor.

Consulte [plano de avaliação do OptiPlex](benchmark-optiplex-7050.md).

## Etapa 1 pt-BR — 29/10/2026

A branch de pesquisa `feat/ptbr-grounding-eval-stage1` implementa normalização conservadora de saída, seleção entre observação e bloqueio na bancada, e benchmark serial de Qwen3.5 0.8B e Tucano2-qwen-1.5B-Instruct com 20 casos sintéticos. **Nenhum modelo está homologado**. Persistem falhas diante de fontes conflitantes e lacunas temporais; não promover sem holdout e benchmark no Dell de 8 GB. [Relatório e execução](ptbr-grounding-stage1.md).
