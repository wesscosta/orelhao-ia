## 0.6.0-alpha.1 — em desenvolvimento

- adiciona `SemanticVectorizer` como contrato independente do retriever baseline;
- implementa embeddings locais com `multilingual-e5-small` quantizado em ONNX e revisão fixada;
- separa os artefatos semânticos do índice lexical/hash e valida sua coerência por hashes;
- adiciona provisionamento explícito do modelo e reconstrução do índice semântico;
- permite medir `semantic-only` com `orelhao knowledge evaluate --retriever semantic` no dataset congelado da v0.5;
- mantém threshold semântico em `0.0` na primeira medição, sem fusão, tuning ou confidence gate;
- não promove o retriever experimental antes de uma comparação A/B completa.

As métricas semantic-only permanecem pendentes até que o modelo opcional seja provisionado e executado no ambiente de benchmark.

## 0.5.0

- adiciona benchmark reproduzível para qualidade do retrieval;
- consolida dataset versionado em português brasileiro com 40 casos, sendo 30 positivos e 10 de abstenção;
- cobre intenções institucionais, cursos, atendimento, PSG, aprendizagem, empregabilidade, biblioteca, empresas e contrato do aluno;
- inclui consultas fora do domínio e perguntas do domínio cuja resposta não está disponível no corpus;
- mede Hit@1, Hit@k, MRR, acurácia de abstenção e latência média;
- adiciona `orelhao knowledge evaluate` com dataset padrão e saída humana ou JSON;
- amplia testes de validação do dataset, ranking, fontes alternativas, abstenção e parâmetros inválidos;
- congela a baseline final do retriever híbrido lexical/hash antes da introdução de embeddings semânticos.

Baseline final no corpus versionado de 14 documentos e 23 chunks: Hit@1 `0.633`, Hit@4 `0.800`, MRR `0.703`, acurácia de abstenção `0.600` e latência média observada de aproximadamente `2.04 ms` no ambiente de validação.

## 0.4.0-alpha.4

- normaliza Markdown com frontmatter YAML, preservando metadados fora do texto recuperável;
- ignora documentos de controle (`00-README.md`) e fontes `category: evaluation` durante indexação;
- consolida recuperação híbrida lexical + hashing vetorial local com abstenção explícita;
- adiciona testes de regressão para ingestão, persistência e ranking do retriever;
- adiciona criação manual de fontes Markdown pelo Admin;
- adiciona exclusão de fontes com confirmação;
- calcula SHA-256 das fontes para indicar `novo`, `alterado`, `indexado` ou `ignorado`;
- exibe estado global `ATUALIZADO`/`DESATUALIZADO` comparando apenas fontes indexáveis com o manifest;
- mantém reindexação explícita para permitir edição em lote.

## 0.4.0-alpha.3

- adiciona interface web administrativa local para `knowledge/sources/`;
- permite upload de Markdown/TXT, normalização de TXT para Markdown e edição;
- adiciona reindexação pelo mesmo pipeline persistente da CLI;
- grava fontes de forma atômica e rejeita path traversal/uploads acima de 2 MiB;
- mantém bind em `127.0.0.1` por padrão e documenta ausência de autenticação nesta alpha.

## 0.4.0-alpha.2

- adiciona `knowledge/sources/` como fonte da verdade e `knowledge/index/` como artefato reconstruível;
- adiciona ingestão local de Markdown e TXT;
- adiciona índice vetorial persistente com NumPy;
- adiciona `orelhao knowledge index` e `orelhao knowledge search`;
- adiciona threshold explícito para abstenção quando não há evidência suficiente;
- mantém embeddings semânticos de modelo para a próxima evolução.

## 0.4.0-alpha.1

- inicia a camada Knowledge/RAG desacoplada do domínio;
- adiciona contratos Document, Chunk, SearchResult e KnowledgeContext;
- adiciona KnowledgeRepository e implementação em memória;
- adiciona retriever lexical determinístico como baseline;
- adiciona ContextBuilder com orçamento de contexto e preservação de fontes;
- adiciona KnowledgeService como facade substituível;
- adiciona `orelhao --rag-test`;
- remove acoplamento Senac dos mocks/prompts de RAG/LLM;
- sem embeddings, vector DB ou LLM real nesta alpha.

## 0.3.10

- aumenta a janela de encerramento WebRTC VAD de 600 ms para 1500 ms, tolerando pausas naturais;
- mantém início de fala rápido e `max_record_seconds` apenas como failsafe;
- mantém o idioma do Whisper como `pt`, código suportado para português;
- adiciona contexto explícito de português brasileiro via `initial_prompt`;
- aumenta `beam_size` de 1 para 5 para priorizar precisão sobre uma pequena parcela de latência;
- mantém a voz Piper `pt_BR-cadu-medium`; nenhuma troca de timbre nesta revisão.

## 0.3.9

- substitui o RMS como decisão primária por WebRTC VAD (speech-aware);
- mantém RMS apenas para noise floor, peak e diagnóstico;
- usa janelas independentes para início e fim da fala com histerese;
- tolera pausas naturais e exige baixa atividade sustentada para endpoint;
- adiciona post-roll de 300 ms para preservar finais de palavras;
- mantém PipeWire, Whisper e Piper inalterados.

## 0.3.7

- adiciona telemetria `peak_rms` ao diagnóstico de captura;
- reduz o multiplicador padrão do VAD adaptativo de 3.0 para 1.8;
- limita o threshold adaptativo padrão a 0.05 para microfones com menor amplitude útil;
- mantém gate temporal de 180 ms para evitar falso início após o aumento de sensibilidade;
- nenhuma alteração no backend PipeWire, sample rate, STT ou TTS.

## 0.3.6

- trata encerramento intencional do `pw-record` como fluxo normal;
- usa `SIGINT` para finalizar a captura, equivalente ao `Ctrl+C` validado manualmente;
- diferencia término inesperado do recorder de timeout/ausência de fala;
- evita falso `RuntimeError` após uma sessão sem fala detectada.

- PipeWire capture now uses a temporary RAW file instead of stdout.
- The RAW file is consumed incrementally so adaptive VAD remains real-time.
- Matches the capture path validated manually with `pw-record`.


## 0.3.4

- captura principal migrada de PortAudio/sounddevice para `pw-record` (PipeWire);
- PCM16 mono é entregue diretamente ao VAD/Whisper sem biblioteca nativa de áudio dentro do processo Python;
- `sounddevice` e o processo isolado anterior permanecem como backends de fallback/diagnóstico;
- novo `audio.pipewire_target` permite fixar um `node.name`/serial do PipeWire quando necessário;
- `pw-record` é encerrado de forma controlada ao fim da fala ou timeout.

## 0.3.3
- captura de áudio isolada em processo filho para conter crashes nativos de PortAudio/ALSA;
- máquina de estados temporal WAITING/SPEAKING/COMPLETE no VAD;
- debounce de início de fala e rejeição de falsos inícios;
- pausa natural aumentada para 1,8 s antes de encerrar a pergunta;
- calibração robusta pela metade mais silenciosa das amostras;
- CLI só avisa "Pode falar agora" após finalizar a calibração;
- timeouts de início e duração total continuam separados.

## v0.3.2

- playback preferencial isolado via `pw-play`/`aplay`, evitando crashes nativos do PortAudio no processo principal;
- preservação da taxa original do WAV do TTS durante playback pelo sistema;
- caminhos de configuração/modelos resolvidos a partir da raiz da aplicação, independentes do diretório atual;
- `ORELHAO_ROOT` disponível para instalações/appliances;
- fallback `sounddevice` mantido como backend explícito.

## 0.3.1
- seleção de áudio por nome/capacidade, evitando índices PortAudio instáveis;
- provisionamento da voz Piper `pt_BR-cadu-medium`;
- dependência TTS explícita e mensagens de erro orientativas;
- novos testes de resolução de dispositivos e provisionamento.


## 0.3.0
- Adiciona TTS local desacoplado via Piper CLI.
- Adiciona `--tts-test` e `--voice-test`.
- Mede latência e RTF da síntese.
- Aumenta silêncio pós-fala para 1600 ms para tolerar pausas naturais.
- Mantém RAG/LLM fora do caminho real nesta etapa.

## 0.2.2
- Substitui o encerramento por threshold fixo por VAD adaptativo com calibração de noise floor.
- Separa timeout aguardando fala, silêncio pós-fala e duração máxima de segurança.
- Adiciona diagnósticos de captura: noise floor, threshold, motivo de encerramento e overflows.
- Adiciona `--audio-diagnose` para validar os dispositivos configurados.
- Adiciona fallback explícito para CPU INT8 quando GPU/CUDA está visível mas o runtime está incompleto.
- Mantém captura na taxa nativa do hardware e pipeline interno em 16 kHz.

## 0.2.1
- Corrige captura ALSA em interfaces que não aceitam 16 kHz diretamente.
- Detecta automaticamente o sample rate nativo de entrada/saída.
- Normaliza áudio para 16 kHz no pipeline usando resampling local.
- Reamostra saída para a taxa nativa antes da reprodução.

## 0.2.0
- STT local real com faster-whisper/CTranslate2.
- Resultado estruturado de transcrição e métricas de latência/RTF.
- CLI `--stt-test` para microfone e `--stt-file` para WAV.
- Configuração de modelo, idioma, device e compute type.
- Estratégia explícita de provisionamento offline do modelo.
- Testes unitários do contrato STT e conversão PCM16.
- Mantido Audio Engine + VAD validados na v0.1.

## 0.1.0
- Captura e reprodução de áudio reais.
- PCM16 mono 16 kHz.
- VAD local por energia com pre-roll e encerramento por silêncio.
- Listagem de dispositivos e loopback de áudio.
