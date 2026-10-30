# Arquitetura de software — Orelhão IA

**Revisão 29/10/2026.** Monólito modular e **offline-first**. Esta página separa a arquitetura existente da arquitetura-alvo; leia [Estado vigente](current-state.md).

## Política V3 — PR-04 (29/10/2026)

O pipeline registra a decisão grounding legada, as fact_validations e a decisão final grounding_v3. Apenas em enforce esta última determina presented_answer e o texto do Piper. Precedência: pré-gate, recusa de geração, identidade, completude do atributo, valores tipados e NLI. A decisão permanece limitada à precisão das evidências e não é homologada. [Relatório](grounding-v3-pr04-decision-policy-2026-10-29.md).

## Arquitetura experimental implementada

```text
Pergunta textual / transcrição da bancada
           |
        Retrieval local
           |
   EvidenceAdjudicator (pré-gate)
           |  bloqueio seguro quando há impedimento verificável
           v
 LLM local (llama-server HTTP loopback)
           |
  ClaimGrounding NLI por afirmação
           |
  GroundingPolicy (supported/uncertain/unsupported)
           |
  Resposta apresentada e TTS Piper (player da bancada)
```

No modo `observe`, as decisões são registradas, mas respostas inadequadas podem aparecer para diagnóstico. No modo `enforce`, lacunas verificáveis bloqueiam a geração; `uncertain` e `unsupported` bloqueiam a resposta; a síntese só usa a **resposta apresentada**. O resultado de `answerable=True` significa apenas que nenhum impedimento foi detectado, **não** que exista prova semântica de resposta.

### Limites conhecidos

O NLI pode apoiar afirmações de outra entidade, especialmente sem `entity_id` no corpus; filtros de identidade e fontes estruturadas foram acrescentados após a falha Excel × Excel Avançado, mas não corrigem toda contradição textual. Existem falsos bloqueios importantes e não há homologação.

## Camadas e diretórios

| Camada | Papel |
|---|---|
| `src/orelhao/core` | Sessão, estados e contratos de domínio |
| `src/orelhao/services` | Audio, STT, TTS, RAG, LLM, verificação de evidências |
| `src/orelhao/admin` | Interface administrativa e workbench em loopback |
| `src/orelhao/hardware` | Contratos/adaptação física, integração ainda não validada |
| `src/orelhao` + `config/` | Inicialização, configuração e rotinas de execução |
| `knowledge/sources` | Fontes Markdown oficiais da implantação |
| `knowledge/index` | Artefatos reconstruíveis de retrieval |

## Arquitetura-alvo do MVP (não implementada ponta a ponta)

```text
Gancho / Arduino → sessão de chamada
Microfone do monofone → VAD → STT → RAG → gate → LLM → NLI → Piper → monofone
Teclado 4x4 ──────────→ comandos de sessão / seleção
systemd, watchdog, métricas, retenção e atualização offline
```

O hardware Dell i5-7500T com 8 GiB é limite físico fixo. Não há GPU dedicada nem expansão de RAM. Priorizar inferência CPU, apenas uma sessão e um modelo por vez; benchmark da máquina de desenvolvimento não valida o Dell.

Referências: [Knowledge](rag.md), [LLM](llm.md), [áudio](audio.md), [hardware](hardware.md), [operações](operations.md), [plano de benchmark](benchmark-optiplex-7050.md).
