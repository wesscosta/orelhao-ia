# Experimento de voz acionada por jumper (ESP32 GPIO27)

**Status em 03/11/2026:** integração experimental de gancho ESP32 e voz P3 testada no Dell; monitor da mesma sessão ativo, com STT e grounding ainda sujeitos a falhas. **Não homologado para uso público**. Os parágrafos datados de 30/10 abaixo preservam a sequência histórica e não substituem [estado vigente](current-state.md).

- Fechar contato entre GPIO27 e GND, depois de um estado aberto observado, inicia o atendimento somente quando houver dispositivo de áudio disponível.
- Abrir o contato encerra o grupo de processos, incluindo captura, LLM, TTS e player.
- Perda de comunicação serial ou ausência de heartbeat por mais de 15 segundos encerra a sessão.
- Contato fechado na inicialização não inicia conversa sem uma abertura anterior (evita chamada indevida).
- Fluxo implementado: saudação Piper, captura PipeWire + VAD, STT faster-whisper, consulta guiada ou recuperação/LLM local/Grounding V3 enforce, voz Piper. Limite atual: até **12 transcrições válidas**, **36 capturas** ou **180 segundos**; comandos inequívocos de voz podem finalizar o atendimento.
- Logs de serviço não devem incluir a transcrição ou a resposta integral. A bancada de observação possui retenção própria.
- A sessão serial usa a conexão USB do ESP32; o serviço monitor antigo e o serviço de voz não podem abrir essa porta simultaneamente.
- Não é necessário alterar o firmware ESP32 já gravado.

Arquivos relevantes:
- src/orelhao/hardware/hook_runtime.py
- src/orelhao/hardware/voice_worker.py
- firmware/esp32-hook/src/main.cpp
- systemd user unit: orelhao-hook-voice.service

## Diagnóstico pós-reboot

1. Conferir grupos do processo: os serviços de usuário precisam pertencer a audio e dialout. O login atual em SSH pode ter audio, mas o gerenciador systemd do usuário pode conservar grupos antigos.
2. Conferir que a saída e fonte reais aparecem em wpctl status, não Dummy Output.
3. Verificar ganhos/mixer e reprodução real no P3 com volume seguro.
4. Testar gravação física, amplitude RMS, saturação e reconhecimento de fala.
5. Testar contato aberto, contato fechado (saudação + voz) e aberto novamente (interrupção).
6. Validar 30+ ciclos, falhas USB, nível de ruído, latência e segurança antes de considerar pronto para uso público.

Comandos de inspeção:
journalctl --user -u orelhao-hook-voice.service -f
systemctl --user status orelhao-hook-voice.service

Rollback da ativação:
systemctl --user disable --now orelhao-hook-voice.service
systemctl --user enable --now orelhao-hook-monitor.service

**Nota:** enquanto a placa de áudio estiver sem permissão, o controlador não inicia a conversa ao fechar o jumper. Não tentar contornar privilégios com chmod 666 em /dev/snd.

## Roteamento P3 persistente no Dell

Depois da atualização dos grupos audio/dialout e do reinício, a placa apareceu no PipeWire. A porta padrão de saída era a dos alto-falantes, e a entrada Headset Mic saturava. A rota atual selecionada é `analog-output-headphones` + `analog-input-headset-mic` (o modo `analog-input-headphone-mic` foi usado em testes anteriores e não é o vigente). O serviço de usuário orelhao-audio-route.service configura as portas e volume moderado antes do controlador do gancho; veja scripts/configure_headset_audio.py. O programa só autoriza atendimento com essas rotas presentes e não silenciadas.

A captura de 1,73 s na rota Headphone Mic, com nível inicial baixo, apresentou RMS 0,0069, pico 0,072 e zero clipping. Isso não demonstra que a voz humana seja inteligível. O player P3 executou sem erros, mas a audição real ainda precisa de confirmação.

## Reteste físico pós-reboot (30/10/2026)

- O fechamento e abertura do jumper GPIO27/GND iniciaram e encerraram a sessão pelo host, incluindo saudação e cancelamento do worker.
- Captura real em um turno: pico RMS 0,02643, fala detectada, Whisper retornou transcrição de 25 caracteres, RAG/LLM/Grounding V3 concluiu e Piper reproduziu a resposta; o processo avançou para o próximo turno.
- Outros turnos apresentaram pico RMS entre 0,00018 e 0,00301, sem fala detectada após timeout. **Intermitência de sinal do microfone P3 ainda não homologada**; verificar presença e conexão do microfone e realizar gravação controlada falando próximo a ele.
- O PipeWire alternou a fonte para `analog-input-headset-mic`; os testes iniciais tentaram recuperar `analog-input-headphone-mic`, mas a implementação atual passou a exigir e recuperar `analog-input-headset-mic` antes do atendimento e das novas capturas.
- O jumper apresentou alternâncias rápidas que iniciaram subprocessos sucessivos. O controlador agora exige contato fechado estável durante 0,75 s antes de iniciar a sessão, sem alterar o debounce de 70 ms do firmware.
- O serviço atualizado foi reiniciado em repouso, sem sessão de voz ativa, e a verificação da rota retornou AUDIO_READY=True.
- **Não homologado para público**, pois falta validar a inteligibilidade do microfone, a audibilidade no fone, a qualidade de várias trocas e as condições de sinal ao longo do tempo.

## Ajustes de volume e sinal (30/10, 20h UTC)

Volume P3 elevado de 0,18 para 0,35; entrada de 0,12 para 0,30, com 4 s de teste RMS 0,02924, pico 0,44144 e clipping 0. A entrada pode ter variações conforme headset, microfone e conexão: fazer teste acompanhado antes de ajustes adicionais. O serviço de voz reproduz um aviso uma única vez quando não detecta fala para diferenciar silêncio de falha de atendimento. Os valores estão persistidos em scripts/configure_headset_audio.py.

Reteste de ganho: source 0,30 produziu pico RMS 0,91738 durante trecho sinalizado como fala, mas Whisper retornou transcrição vazia; ajustado ganho persistente para 0,20 antes do próximo teste. Saída P3 permanece 0,35. O worker passa a comunicar uma única vez transcrição vazia para distinguir áudio detectado de fala inteligível.
