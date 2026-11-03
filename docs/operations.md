# Operação do Orelhão IA — estado atual e appliance planejado

**Atualizado em 29/10/2026.** O projeto ainda funciona como **ambiente de desenvolvimento e bancada experimental**; a operação autônoma em produção **não está homologada**. Consulte [Estado vigente](current-state.md).

## Operação experimental verificada em 03/11/2026

**Dell OptiPlex 7050 Micro, Ubuntu Server 24.04:** o serviço de usuário `orelhao-hook-voice.service` lê o gancho do ESP32 via USB serial. Cada retirada inicia um processo de sessão; recolocar o monofone ou perder a serial interrompe a sessão. O serviço `orelhao-workbench-benchmark.service` disponibiliza a bancada e o monitor físico **somente** em `127.0.0.1:8765`.

```bash
systemctl --user status orelhao-hook-voice.service orelhao-workbench-benchmark.service
journalctl --user -u orelhao-hook-voice.service -f
ls -l /dev/ttyUSB0
curl -sS http://127.0.0.1:8765/monitor/state
```

De outra máquina na rede local, usar **túnel SSH**, por exemplo `ssh -N -L 8765:127.0.0.1:8765 lumi@10.42.0.174`, e abrir `http://127.0.0.1:8765/monitor` na máquina cliente. O IP local pode mudar com DHCP; o IP Tailscale depende da conexão autorizada. **Não expor a porta 8765 publicamente**, pois a interface ainda não dispõe de autenticação própria.

A síntese de voz do monofone usa Piper `length_scale: 0.88`, com WAVs fixos pré-gerados no cache do usuário. O limite experimental é **12 perguntas válidas / 180 s / até 36 capturas**. O [monitor SSE](live-monitor.md) espelha apenas a sessão física, sem segunda inferência. A memória contextual da ligação é efêmera e a política factual permanece `enforce`.

O corpus ativo no Dell tem **21 documentos e 43 trechos**. O índice `knowledge/index` é um derivado local (não entra no Git). Backup anterior preservado em `~/.local/share/orelhao-ia/backups/knowledge-index-before-2026-11-03`. Ao atualizar fontes, construir um índice candidato, executar avaliações de retrieval e só depois promover de modo reversível e reiniciar o Admin, evitando chamadas em andamento. Consulte [corpus e benchmark](context-and-knowledge-2026-11-03.md).

**Status:** desenvolvimento experimental, **NO-GO** para atendimento público. Persistem erros de transcrição por ruído e falsos bloqueios no RAG; faltam testes físicos repetidos, avaliação humana e integração de teclado/display.

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

A bancada utiliza `127.0.0.1:8765/workbench`, e o monitor da sessão física usa `127.0.0.1:8765/monitor`. O `llama-server` deve ser iniciado separadamente e seu alias deve corresponder a `llm.model`. O player TTS da página depende de clique em **Ouvir resposta**, respeitando políticas do navegador. `--voice-test` **não** representa integração autônoma de RAG/LLM com o monofone.

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
- homologação da sessão por gancho com ESP32/monofone e futura integração de teclado/display;
- política de atualização atômica de fontes e modelos;
- criptografia, retenção/expurgo de dados e controle de acesso local;
- aferição de RSS agregado, P50/P95, estabilidade térmica e 30+ ciclos.

Não marcar esses itens como entregues antes de ensaio no hardware físico e registro de aprovação no [plano de testes](benchmark-optiplex-7050.md).
