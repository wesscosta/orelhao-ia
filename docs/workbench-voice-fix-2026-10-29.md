# Correção de áudio da bancada — 29/10/2026

**Status:** implementada e verificada no Arch Linux, branch `fix/workbench-voice-output`. Não é homologação do Orelhão físico.

## Falha reproduzida

O player da interface administrativa não gerava voz. `GET /workbench/speech/{id}?text=...` retornou HTTP 422, porque `piper` estava instalado em `.venv/bin/piper`, mas a execução `.venv/bin/orelhao admin` não havia acrescentado `.venv/bin` ao `PATH` do processo. O modelo `models/tts/pt_BR-cadu-medium.onnx` e a configuração JSON já existiam.

## Correções aplicadas

- O serviço Piper localiza seu executável também ao lado do interpretador Python atual, sem exigir ativação interativa do virtualenv. Mantém o contrato TTS existente.
- O processo de síntese recebe timeout de 45 segundos; a interface devolve uma falha explícita quando não consegue sintetizar.
- A página de perguntas exibe disponibilidade do TTS, e o resultado apresenta o botão **Ouvir resposta**, status e controles de áudio. A reprodução depende de gesto do usuário e possui fallback caso o navegador bloqueie autoplay.
- A rota de áudio deixa de aceitar texto arbitrário na query string. Exige um UUID de observação registrada e lê **somente a resposta apresentada**, inclusive a abstenção no modo seguro, sem transmitir o texto da resposta na URL.
- A síntese foi isolada em threadpool, evitando bloquear o loop assíncrono do servidor durante a inferência.
- Cabeçalhos de resposta: WAV, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`.

## Evidência do teste real

`GET /workbench/tts-status` retornou `available=true`. `GET /workbench/speech/{id}` retornou HTTP **200**, tipo **audio/wav**, 247.340 bytes, PCM mono, 22.050 Hz, duração de **5,61 segundos**, RMS > 0 (áudio com sinal). O teste foi executado localmente na máquina Arch Linux. A audição subjetiva pelo monofone, a saída física e a latência no Dell não foram verificadas.

### Para testar

```bash
cd /home/wesscosta/Develop/orelhao-ia
# Usar a branch fix/workbench-voice-output e o ambiente Python do projeto
ORELHAO_CONFIG=config/benchmark-tucano2-15b-ptbr.yaml .venv/bin/orelhao admin
```

Abrir `http://127.0.0.1:8765/workbench`, enviar pergunta, e no resultado clicar em **Ouvir resposta**.

## Pendências

- Autoplay automático não é confiável nos navegadores por políticas de interação; o botão visível é o caminho suportado.
- O tempo de geração do áudio varia com o texto e o hardware. O teste real de 5,61 s é *duração do áudio*, não latência de síntese.
- Sem validação da saída analógica do monofone, cancelamento no gancho ou servidor no Dell.
- A interface segue restrita a loopback e sem autenticação; não expor publicamente.
