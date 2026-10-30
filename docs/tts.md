# TTS local com Piper — síntese em pt-BR

**Atualizado em 29/10/2026.** O backend Piper já funciona na bancada administrativa. A integração física com o monofone e a operação autônoma continuam pendentes. Veja [estado vigente](current-state.md).

## Backend e provisionamento

`TTSService` usa processo local Piper, preferencialmente a voz `pt_BR-cadu-medium`. O provisionamento antecede a operação offline; os arquivos `.onnx`, `.onnx.json` e `MODEL_CARD` não devem ser commitados.

```bash
pip install -e '.[tts]'
orelhao --tts-provision
orelhao --tts-test "Olá, este é um teste de voz do Orelhão IA."
orelhao --voice-test
```

## Correção da bancada em outubro de 2026

O serviço resolve o executável Piper instalado junto ao interpretador do `venv`, mesmo quando o comando `.venv/bin/orelhao admin` é executado sem ativar explicitamente o PATH. Na bancada, `/workbench/tts-status` informa disponibilidade e o botão **Ouvir resposta** inicia síntese. O endpoint `/workbench/speech/{observation_id}` utiliza a resposta apresentada de uma observação registrada, **não o texto de uma query string**.

O teste real no Arch confirmou WAV mono a 22.050 Hz com sinal não silencioso. Essa observação não comprova inteligibilidade, alto-falante físico ou latência no Dell. Detalhes: [correção da voz](workbench-voice-fix-2026-10-29.md).

## Dispositivos e limites

Os índices PortAudio mudam entre reinicializações: preferir nomes estáveis e conferir com `orelhao --list-audio-devices`. É necessário validar interface USB, pinagem, impedância do monofone, aterramento, latência e reprodução após retirada do gancho.

O comando `--voice-test` cobre o fluxo histórico de STT → TTS, não o pipeline de RAG/LLM completo. O navegador pode impedir autoplay sem clique. Operação física autônoma é meta de MVP ainda aberta.


## Seletor Piper no Workbench (30/10/2026)

Na bancada, a voz Cadu ou Faber pode ser escolhida para sintetizar a mesma resposta, sem repetir a geração. A prévia usa a frase **Eu sou o Lumi**. Para instalar Faber, execute python scripts/provision_piper_faber.py. Cadu continua como padrão do runtime e o loop físico não foi alterado. [Detalhes](workbench-piper-voices-lumi-2026-10-30.md).
