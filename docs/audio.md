# Audio Engine — v0.1

> **ATUALIZAÇÃO OPERACIONAL — 29/10/2026.** Os trechos marcados v0.1/v0.2/v0.3 são HISTÓRICOS. Hoje o backend de captura usado no benchmark é PipeWire/`pw-record`, com VAD `webrtc`, 16 kHz mono no pipeline e configuração de silêncio em `1800ms`. `RMS` permanece como fallback/diagnóstico. A homologação no monofone físico e a sessão de voz completa com RAG/LLM continuam pendentes. Consulte [Entrada de voz](voice-input.md) e [Estado vigente](current-state.md).

## Objetivo
Validar o caminho físico de voz antes de adicionar STT, LLM ou RAG reais.

## Formato de referência
- PCM16 little-endian;
- mono;
- 16 kHz;
- blocos de 30 ms.

## VAD atual
A v0.1 usa um detector por RMS/energia. É propositalmente simples para medir microfone, ruído e níveis do monofone. Não deve ser interpretado como decisão definitiva para produção.

Parâmetros configuráveis:
- `rms_threshold`;
- `pre_roll_ms`;
- `silence_ms`;
- `max_record_seconds`;
- dispositivo de entrada/saída.

## Teste de bancada
1. Listar interfaces: `orelhao --list-audio-devices`.
2. Selecionar input/output em `config/development.yaml` quando necessário.
3. Executar `orelhao --audio-loopback`.
4. Falar em volume normal.
5. Verificar se o início da frase não é cortado e se a captura encerra após o silêncio.
6. Repetir em ambiente silencioso e com ruído representativo.

## Métricas a registrar
- nível RMS em silêncio;
- nível RMS durante fala;
- threshold escolhido;
- falsos disparos;
- cortes no início/fim;
- duração média capturada;
- falhas/overflows de dispositivo.

## Taxa nativa do hardware
O pipeline interno utiliza 16 kHz mono PCM16, mas a interface física pode operar em 44,1 ou 48 kHz. A partir da v0.2.1, a aplicação consulta automaticamente a taxa nativa anunciada pelo PortAudio/ALSA, captura nessa taxa e reamostra para 16 kHz. Na reprodução, faz o caminho inverso quando necessário. Isso evita `PaErrorCode -9997 (Invalid sample rate)` em dispositivos `hw:*`.


## Backend de captura PipeWire (v0.3.4)

Em produção/desenvolvimento Linux, `audio.capture_backend: pipewire` usa `pw-record` em modo raw PCM16. Isso remove PortAudio do caminho crítico de captura e evita que erros nativos de ALSA/JACK corrompam o processo Python.

Por padrão o PipeWire escolhe a fonte de entrada ativa. Para fixar uma fonte específica, configure `audio.pipewire_target` com o `node.name` ou `object.serial` aceito por `pw-record --target`.


### PipeWire capture implementation

Production capture uses `pw-record` to a temporary RAW PCM16 file. The application tails that file in blocks while the recorder is active, preserving real-time VAD without routing native audio through Python stdout/PortAudio.

## Diagnóstico do transiente do PipeWire — 03/11/2026

A primeira abertura do microfone P3 após inatividade apresentava forte transiente no Dell mesmo após reduzir o ganho de captura a 40%, mantendo saída em 35%. Medição sem fala intencional: RMS do primeiro segundo de **0,5883**, com **32,25%** das amostras próximas da saturação. Após aquecer a entrada por **2,6 segundos**, a gravação seguinte apresentou RMS de **0,01086** no primeiro segundo e zero amostras saturadas.

A implementação PipeWireAudioCapture.prime() faz uma gravação curta descartável, apaga o arquivo temporário e encerra o gravador. O voice_worker executa esse procedimento **em paralelo à saudação**, sem segunda transcrição ou inferência. Em caso de falha de pré-aquecimento, registra o erro e preserva a tentativa de captura normal.

O parâmetro audio.pipewire_warmup_seconds está em 2.6 no perfil experimental e a execução está coberta por tests/audio/test_pipewire_prime.py. A redução de clipping não comprova, sozinha, a precisão da transcrição. Ainda precisamos de ensaios de voz real, tempo de resposta e retenção do início das falas.

O glossário experimental do STT do Dell substitui instruções metalinguísticas; seu efeito sobre a taxa de erros de transcrição ainda não foi medido.

## Diagnóstico e correção do microfone P3 — 03/11/2026

### Falhas observadas no Dell

O problema do reconhecimento **não era exclusivamente o modelo Whisper**. A sessão física apresentou ganho excessivo da entrada analógica, frames saturados e dificuldade de roteamento da fonte PipeWire.

- O mixer ALSA havia voltado para **Capture 75% (+18 dB)**. Alguns turnos do monofone registraram `peak_rms=1.000`, e houve uma captura de **15,72 s**.
- O comando `wpctl get-volume @DEFAULT_AUDIO_SOURCE@`/ `@DEFAULT_AUDIO_SINK@` falhava com `-1 is not a valid ID`, mesmo com a placa listada pelo WirePlumber e com o servidor Pulse apontando as fontes corretas.
- Sem `--target`, o `pw-record` falhou com **`no target node available`** e gerou apenas o cabeçalho de arquivo WAV, sem amostras de voz.
- Ao gravar com `--target=alsa_input.pci-0000_00_1f.3.analog-stereo`, o mesmo `pw-record` funcionou normalmente. A primeira amostragem com Capture em 40%, **sem uma pessoa falando**, durou aproximadamente 3,88 s e apresentou ausência de clipping (não é medição de inteligibilidade).
- A captura interna `PipeWireAudioCapture.capture()` com esse alvo concluiu os **7 s de silêncio** com `speech_detected=False`, sem invocar o STT e sem gerar frase fictícia.

### Correções experimentais

- O perfil local **não versionado** `config/orelhao-server.qwen.local.yaml` fixa:
  - `audio.pipewire_target: alsa_input.pci-0000_00_1f.3.analog-stereo`
  - `audio.pipewire_playback_target: alsa_output.pci-0000_00_1f.3.analog-stereo`
- `PipeWireAudioCapture` já aceitava `pipewire_target`; o player `pw-play` agora aceita `pipewire_playback_target` opcional, sem depender dos dispositivos padrão.
- `scripts/configure_headset_audio.py` foi corrigido para ajustar a saída usando a fonte Pulse nomeada, sem `wpctl @DEFAULT_...@`, e **usar `amixer -c 0 sset Capture 40% cap`** para evitar que a fonte PipeWire em 20% reative ganho de +18 dB. A saída permanece em 35%.
- O nome de dispositivo é específico deste Dell. Outros computadores ou adaptadores USB exigem identificação dos próprios `node.name`; não copiar o nome indiscriminadamente.

Essas medidas corrigem falhas reproduzidas de abertura e saturação, mas **não comprovam que a voz do monofone é reconhecida com precisão**. Uma fonte pode abrir corretamente e ainda apresentar falhas por cabo RJ9/P3, pinagem CTIA/OMTP, alimentação/bias do microfone, mau contato, blindagem, posicionamento ou relação sinal/ruído. O `analog-input-headset-mic` estava selecionado, mas a porta aparecia como `available=no`; isso também recomenda verificar o conector físico.

### Protocolo de validação com fala real

1. Sem outra captura concorrente, retirar o monofone e observar `/monitor`.
2. Dizer, em tom e distância usuais: **“Olá, Lumi, estou testando o microfone.”**, depois **“Quais são os cursos de Informática do Senac?”** e **“Que dia é hoje?”**, sempre após a saudação ou a resposta do Lumi.
3. Comparar a transcrição literal, verificar `noise_floor`, `peak_rms`, duração da captura e se há perdas de início/fim. Repetir cinco vezes. Registrar o texto **realmente falado** e o texto do Whisper para medir os erros; o monitor não capta áudio bruto.
4. Se houver clipping ou voz inaudível, validar fisicamente a sequência **microfone/bias/terra no TRRS P3** e o adaptador RJ9; comparar com um microfone USB reconhecido como **outra fonte PipeWire**, com roteamento explicitamente ajustado, mantendo os demais parâmetros. Não aumentar ganho automaticamente até 75%.
5. Só depois considerar VAD mais agressivo/menos agressivo, `initial_prompt` ou outro tamanho de modelo. Ajustes sem amostra de voz poderão mascarar o problema.

Regressões automatizadas para alvo explícito e rota P3 em `tests/audio/test_server_p3_routing.py`; versões genéricas continuam com `pipewire_playback_target=None` para compatibilidade. Esse teste de bancada não substitui ensaio no monofone real.
