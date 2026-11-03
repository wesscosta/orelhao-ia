# Monitor da sessão física do Orelhão IA

## Objetivo

Acompanhar **a mesma ligação do monofone** pela interface administrativa, sem criar
outra captura de áudio, transcrição STT, consulta RAG, inferência LLM ou síntese TTS.

## Componentes

- `hook_runtime.py`: abre e encerra a sessão quando o ESP32 informa o estado do gancho.
- `voice_worker.py`: publica eventos ao longo do pipeline já existente.
- `live_monitor.py`: transporta eventos JSONL por arquivo efêmero do Linux em
  `$XDG_RUNTIME_DIR/orelhao-ia/live-session.jsonl` (por padrão, `/run/user/1000`
  na máquina de desenvolvimento), com diretório 0700 e arquivo 0600.
- `admin/app.py`: disponibiliza `GET /monitor`, `GET /monitor/state` e
  `GET /monitor/events` via Server-Sent Events (SSE), somente leitura.
- `admin/live_view.py`: apresenta a transcrição, a resposta falada, a
  classificação de abstention e os tempos de captura/STT/RAG/TTS/reprodução.

A interface web já existente permanece no **localhost:8765**; o serviço não
deve ser exposto diretamente à rede, pois ainda não há autenticação própria.
Para acesso remoto, usar túnel SSH ou solução de acesso administrativo autorizada.

## Contrato mínimo de evento

Cada evento contém `session_id`, `type`, `timestamp` ISO UTC e campos opcionais:

- `turn`: número da interação.
- `text`: transcrição reconhecida ou texto que o Lumi pretende falar.
- `status`: estado operacional ou classificação da resposta.
- `route`: origem (por exemplo `guided`, `rag`, `prompt`).
- `reason`: motivo de recusa, quando disponível.
- `metrics`: tempos em milissegundos e medições diagnósticas.

Tipos: `session.started`, `session.ended`, `voice.greeting`,
`voice.listening`, `voice.capture`, `voice.transcription`,
`voice.transcription_invalid`, `voice.context`, `voice.processing`, `voice.waiting`,
`voice.response`, `voice.playback` e `voice.error`.

**Sem nova inferência:** o monitor somente espelha eventos já conhecidos pelo
processo principal. O SSE envia dados apenas quando a sessão muda.

## Privacidade e limites

- Nenhum áudio PCM/WAV é copiado para o monitor ou transmitido ao navegador.
- Textos são limitados a 1.800 caracteres/evento; o arquivo a 128 KiB;
  a view lê no máximo os últimos 100 eventos.
- **Ao desligar o monofone, as transcrições e respostas são apagadas do tmpfs**;
  resta apenas o evento de encerramento sem conteúdo conversacional.
- O armazenamento em `/run/user` é volátil e some após reinicialização.
- Uma falha de publicação de evento não deve derrubar ou atrasar a conversa.
- O diagnóstico não substitui avaliação de qualidade: precisão do Whisper
  e excesso de recusas do grounding ainda exigem correções próprias.

## Futuro display ESP32

O display deve consumir eventos derivados da **mesma** sessão já publicada,
com texto paginado/resumido pelo servidor, sem iniciar outra IA. A implementação
da saída serial de texto, identificação do display e integração do teclado
permanecem trabalhos futuros. Não usar o ESP32 para rodar STT/LLM/TTS.

## Validação

Executar `pytest -q`, `ruff check` e `mypy src/orelhao/hardware`.
Na máquina, abrir `http://127.0.0.1:8765/monitor`, retirar o monofone,
fazer perguntas, verificar o texto reconhecido e a resposta apresentada,
e recolocar o monofone para conferir o apagamento dos textos.
