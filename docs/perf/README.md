# Auditoria de latência de voz — 11/11/2026

## Escopo verificado

Branch isolada: `perf/voice-latency-20261111`, baseada em `ee41647`
(`feat/admin-ui-ux-20261106`). Nenhum serviço do Orelhão foi reiniciado.

**Limite:** o equipamento `orelhao-server` estava offline no Desktop Commander
e no Tailscale; SSH não conectou. A inspeção e os benchmarks foram realizados
no notebook Arch Linux, não no Dell de 8 GB. A configuração efetivamente
implantada no servidor, o consumo de recursos e a experiência no monofone
**não foram verificados**.

## Pipeline confirmado no código

1. ESP32/gancho: `hardware/hook_runtime.py` inicia processo por atendimento.
2. Captura: `interfaces/voice/capture.py` abre `pw-record`, usa arquivo RAW
   temporário incremental e WebRTC VAD com pré-roll.
3. STT: `services/stt/service.py`, `faster-whisper` em processo Python;
   modelo lazy, reutilizado durante uma ligação.
4. Conhecimento: `hardware/voice_worker.py` chama
   `workbench.observe(..., mode="enforce")`: recuperação, LLM e validação
   de evidências antes de apresentar uma resposta.
5. LLM: `services/llm/service.py`, servidor HTTP em loopback,
   resposta não-streaming; não há TTFT medido por token.
6. TTS: `services/tts/service.py` invoca novo Piper CLI para cada resposta,
   gera WAV temporário. Alternativa opt-in:
   `services/tts/resident.py`, modelo ONNX carregado uma vez por ligação e
   PCM em memória.
7. Playback: `interfaces/voice/playback.py` abre processo `pw-play`/`aplay`
   e WAV temporário. O tempo de despacho **não é** a primeira amostra audível.

## Pontos de latência identificados por inspeção (não quantificados no Dell)

- O VAD configurado em um perfil local privado tinha janela de fim de 1.500 ms
  e pós-roll de 300 ms; depende de presença/ausência dos frames de voz.
  Não confundir esses parâmetros com um tempo efetivo fixo de 1.800 ms.
- O perfil local traz calibração de 700 ms na abertura da captura; no backend
  WebRTC a calibração RMS é telemetria, não o classificador da fala.
- O tempo antieco `turn_taking.py` é 300 ms após finalizar o playback.
- O aviso de espera pode surgir após 650 ms no `voice_worker.py` e bloquear
  o primeiro áudio da resposta até terminar de tocar.
- `FasterWhisperSTTService` carrega o modelo na primeira transcrição;
  depois reutiliza-o durante a ligação.
- O novo TTS residente exige memória adicional no processo de voz; a diferença
  real de RSS/CPU no Dell ainda é desconhecida.

## Benchmark reproduzível do TTS (30 por configuração)

Mesma voz `pt_BR-cadu-medium`, 6 frases representativas do Senac repetidas
5 vezes em cada modo, `length_scale=0.88`, Python 3.14.8 no Arch Linux.
Aquecimento não foi contabilizado. Medição monotônica de síntese até PCM
disponível em memória, **sem captura, STT, RAG, LLM e reprodução física**.

| Métrica | CLI (atual) | Residente (alternativa) |
|---|---:|---:|
| amostras | 30 | 30 |
| p50 | 814,93 ms | 113,81 ms |
| p90 | 877,80 ms | 129,09 ms |
| p95 | 880,34 ms | 130,87 ms |
| média | 822,50 ms | 111,63 ms |
| aquecimento explícito | 0 ms | 604,29 ms |
| intervalo da duração gerada | 2,80–4,70 s | 2,81–4,69 s |
| pico RSS observado | 241.084 KiB (subprocessos) | 299.692 KiB (processo Python) |
| CPU usuário acumulada | 213,93 s (filhos) | 40,07 s (Python) |

Dados brutos: `tts-cli-notebook-20261111.json` e
`tts-resident-notebook-20261111.json`.
**Interpretação:** redução local comprovada da espera pela síntese
em regime aquecido. Não é uma comparação fim-da-fala → primeira palavra.
Os valores da tabela são de uma segunda rodada, que coletou também uso de
recursos. A primeira rodada (também 30 amostras por motor) registrou p50 de
853,03 ms (CLI) e 114,30 ms (residente), evidenciando variação normal entre
execuções. RSS e CPU usam escopos diferentes (filhos do CLI x processo Python
residente); não representam a utilização total de memória da aplicação nem
são comparações isoladas de RSS no Dell. O tempo de CPU pode exceder o tempo
de parede por utilizar múltiplas threads/núcleos.

## Reproduzir na máquina de testes

Com dependências do projeto e modelo Piper já instalados:

```bash
PYTHONPATH=src python scripts/benchmark_tts_local.py \
  --engine cli --model /CAMINHO/pt_BR-cadu-medium.onnx \
  --model-config /CAMINHO/pt_BR-cadu-medium.onnx.json \
  --samples 30 --output /tmp/tts-cli.json

PYTHONPATH=src python scripts/benchmark_tts_local.py \
  --engine resident --model /CAMINHO/pt_BR-cadu-medium.onnx \
  --model-config /CAMINHO/pt_BR-cadu-medium.onnx.json \
  --samples 30 --output /tmp/tts-resident.json
```

## Instrumentação instalada na branch

As marcações usam `time.monotonic_ns()`. Ambos os backends de captura
registram início detectado e último frame positivo de VAD. O trace separa:
captura, estimativa de endpointing, STT, grounding/RAG, TTS, execução do
player, tempo do último frame positivo até despacho ao player, tamanho do
texto e duração do áudio. O último frame VAD é uma **aproximação** do fim da
fala. O despacho ao player é **anterior** ao áudio audível: não chamar de
latência até a primeira palavra realmente ouvida.

Registro local explícito, com permissão 0600, só números e metadados mínimos;
sem transcrição, resposta ou amostras de áudio, limite 5 MB por arquivo.

```bash
# Configurar somente em um ambiente de homologação:
export ORELHAO_LATENCY_ENABLED=1
export ORELHAO_LATENCY_VARIANT=baseline
# O supervisor já propaga ORELHAO_MONITOR_SESSION_ID.

# Ao concluir 30 ou mais interações válidas:
python scripts/summarize_voice_latency.py \
  --path ~/.local/state/orelhao-ia/latency/voice-latency.jsonl
```

Repetir 30 perguntas representativas com `ORELHAO_LATENCY_VARIANT=resident`
após alterar o perfil YAML de homologação para `tts.engine: resident`,
sem mudar microfone, áudio, RAG ou modelo. O valor padrão continua `cli`.
O script de resumo separa grupos por variante e alerta quando n < 30.

**Separar na análise:** respostas guiadas, de esclarecimento e com RAG;
saudação; falas curtas/longas; cenários de pausa, ruído e interrupção.
O pipeline real deve ser homologado *com* o monofone. O benchmark presente
não fornece p50/p90/p95 do ciclo completo.

## Testes, riscos e rollback

Testar com `python -m pytest`, `python -m ruff check` e
`python -m mypy`; inspeção manual de áudio, gancho e grounding é obrigatória
antes de produção.

- A alternativa residente elimina o isolamento nativo do subprocesso CLI
  e aumenta a memória do processo de voz. Medir RSS e CPU no Dell.
- O warmup ocorre durante a saudação quando `resident` está ativo; medir se
  isso muda o tempo até a saudação ou o primeiro início de escuta.
- Falhas do backend residente devem ser tratadas antes de homologação,
  não presumidas ausentes a partir de testes no notebook.
- Para rollback funcional, voltar `tts.engine` a `cli` no perfil
  de homologação e retornar ao código anterior. Nenhuma mudança de rede,
  firmware, modelo LLM, conteúdo do RAG ou ambiente produtivo foi feita.
- Qualquer aplicação de configuração nova, reinício ou atualização do serviço
  do Dell exige janela/autorizações específicas.

## Pendências antes da conclusão integral

1. Baseline de 30 interações físicas por configuração no Dell.
2. Coleta p50/p90/p95 **fim da fala → primeiro som real** por método externo ou
   captura/loopback calibrado; a telemetria atual mede até o despacho.
3. Avaliação WER/CER e falsos acionamentos em PT-BR com ruído, pausas,
   cursos/unidades e diferentes microfones.
4. Observabilidade de TTFT real e fases internas de recuperação/grounding;
   o atual cliente HTTP LLM não é streaming.
5. Medição CPU/RSS/swap por etapa e durante concorrência.
6. Validação auditiva de inteligibilidade, entonação, cortes de palavras,
   interrupção ao recolocar o monofone e queda/recuperação do player.
7. Avaliação da política de espera de 650 ms e da calibração por turno, depois
   de obter a linha de base real.

Não alterar os limiares VAD, hardware, Wi-Fi ou SSH sem os testes necessários.
