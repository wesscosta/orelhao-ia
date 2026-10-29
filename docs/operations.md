# Operação do Orelhão IA — estado atual e appliance planejado

**Atualizado em 29/10/2026.** O projeto ainda funciona como **ambiente de desenvolvimento e bancada experimental**; a operação autônoma em produção **não está homologada**. Consulte [Estado vigente](current-state.md).

## Desenvolvimento local

Os comandos a seguir pressupõem instalação local com ambiente virtual ativado e modelos já provisionados:

```bash
orelhao --list-audio-devices
orelhao --audio-diagnose
orelhao --stt-test
orelhao --tts-test "Teste da voz em português."
orelhao --voice-test
orelhao knowledge index
orelhao knowledge evaluate --retriever baseline --json

# Bancada de recuperação + LLM + validação
ORELHAO_CONFIG=config/benchmark-tucano2-15b-ptbr.yaml orelhao admin
```

A bancada utiliza `127.0.0.1:8765/workbench`. O `llama-server` deve ser iniciado separadamente e seu alias deve corresponder a `llm.model`. O player TTS da página depende de clique em **Ouvir resposta**, respeitando políticas do navegador. `--voice-test` **não** representa integração autônoma de RAG/LLM com o monofone.

## Conhecimento e mudanças de conteúdo

`knowledge/sources/` é a fonte controlada; `knowledge/index/` é derivado. Reindexar após edições e refazer benchmark. A data `retrieved_at` não atesta vaga atual. Atualizar o conteúdo apenas com evidência oficial e validade por unidade/oferta.

## Segurança e privacidade

- A interface Admin não possui autenticação de produção; escutar apenas em loopback, nunca publicar diretamente na internet.
- Logs `knowledge/observations/` podem incluir perguntas e textos, portanto manter acesso restrito, retenção definida antes de produção e não versioná-los.
- Os pesos GGUF, ONNX e outras dependências são locais; o caminho crítico não deve depender da rede.
- Conservar backup de fontes e configurações; não usar o índice reconstruível como fonte única.

## Appliance — trabalho ainda pendente

- Provisionamento reprodutível em Ubuntu Server 24.04 LTS / Python 3.12 no Dell 7050 de 8 GiB;
- `systemd`/watchdog, reinício, health checks e rollback;
- modo de sessão por gancho com Arduino Uno, teclado e monofone;
- política de atualização atômica de fontes e modelos;
- criptografia, retenção/expurgo de dados e controle de acesso local;
- aferição de RSS agregado, P50/P95, estabilidade térmica e 30+ ciclos.

Não marcar esses itens como entregues antes de ensaio no hardware físico e registro de aprovação no [plano de testes](benchmark-optiplex-7050.md).
