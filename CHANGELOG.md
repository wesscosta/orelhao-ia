## 0.6.0-alpha.13

- adiciona configuração própria para uma LLM local, com temperatura, limite de tokens, contexto e timeout;
- implementa cliente HTTP compatível com `llama-server` e restringe o endpoint a loopback sem TLS externo;
- valida disponibilidade e identidade do modelo pelo endpoint `/v1/models`;
- conecta `SearchResult` ao contrato `LLMService` por `LocalLLMAnswerGenerator`;
- instrui a LLM a usar apenas evidências explícitas e retornar `INSUFFICIENT_CONTEXT` quando necessário;
- converte a abstenção da geração em mensagem segura ao usuário e score de grounding zero;
- registra gerador e abstenção da geração no JSONL e no diagnóstico do Admin;
- não faz fallback silencioso para o extrator quando a LLM estiver indisponível;
- preserva thresholds NLI, datasets e o modo de observação; grounding por afirmação fica para a alpha.14.

## 0.6.0-alpha.12.1

- prepara o modelo STT em segundo plano ao abrir a bancada e expõe seu estado antes de habilitar o microfone;
- limita gravações do navegador a 12 segundos e requisições STT a 90 segundos;
- troca a concatenação custosa de arrays JavaScript por buffers tipados;
- normaliza WAV mono para 16 kHz e remove silêncio nas bordas antes da transcrição;
- rejeita gravações sem fala, vazias ou longas com diagnóstico explícito;
- substitui a leitura integral do primeiro chunk por até duas frases limpas e relevantes, limitadas a 360 caracteres;
- calcula grounding por chunk e usa o maior suporte, evitando truncar a evidência que originou a resposta;
- preserva thresholds, datasets e o modo de observação da alpha.12.

## 0.6.0-alpha.12

- integra retrieval, resposta candidata e NLI em uma bancada administrativa local;
- mantém a resposta apresentada independente de `GroundingDecision`, em modo `observe`;
- registra pergunta, resposta, chunks, scores, decisão, latências e resposta apresentada em JSONL append-only;
- adiciona avaliação humana `correct`, `partial` ou `incorrect` sem sobrescrever observações;
- adiciona captura de microfone no navegador, transcrição pelo STT local e reprodução pelo TTS local;
- usa resposta extrativa determinística como fallback explícito enquanto não existe backend LLM local de produção;
- não altera thresholds, datasets, retrieval padrão nem ativa o gate fail-closed.

## 0.6.0-alpha.11

- registra a confirmação do NLI no holdout, com ROC AUC `0.965`;
- introduz `GroundingDecision`, `GroundingStatus` e `GroundingPolicy` como contrato isolado;
- classifica scores em `supported`, `unsupported` e `uncertain` usando somente os thresholds já congelados;
- trata `unsupported` e `uncertain` como fail-closed, liberando resposta apenas em `supported`;
- adiciona resumo dos três estados e decisão estruturada por caso aos diagnósticos NLI;
- não integra o contrato ao retrieval, à LLM, ao TTS ou ao caminho crítico.

Os limites permanecem `unsupported < 0.1250362694`, `supported >= 0.7557643056` e `uncertain` no intervalo. Nenhum novo threshold foi calibrado após o holdout.

## 0.6.0-alpha.10

- congela as políticas NLI `nli-balanced=0.1250362694` e `nli-conservative=0.7557643056` antes do holdout;
- adiciona `grounding-v2-holdout.json` com 40 afirmações inéditas e balanceadas;
- distribui os negativos igualmente entre contradição, entidade, informação específica e temporalidade;
- informa `applicable_metric` e `applicable_score` por categoria para evitar balanced accuracy enganosa em categorias de classe única;
- preserva modelo, corpus, `grounding-v1.json`, benchmarks de answerability, retrieval e caminho crítico.

O holdout é estritamente confirmatório. As duas políticas devem ser executadas uma única vez e seus resultados não podem originar outro threshold.

## 0.6.0-alpha.9

- registra a rejeição do mDeBERTa-v3 INT8 na calibração da alpha.8, sem executar o holdout;
- adiciona `nli-minilm`, um verificador ONNX multilíngue de entailment com revisão imutável;
- adiciona `grounding-v1.json`, separado dos benchmarks de retrieval e answerability, com 40 afirmações pt-BR balanceadas;
- usa a passagem como premissa, a afirmação como hipótese e a probabilidade de `entailment` como suporte;
- preserva XLM-RoBERTa INT8 como baseline de answerability e não altera retrieval ou caminho crítico.

Esta etapa é apenas de calibração. O holdout de answerability não deve ser usado para NLI. Promoção exige threshold congelado, holdout próprio e medição de latência, memória e armazenamento.

## 0.6.0-alpha.8

- encerra a ablação da alpha.7 sem promover FP32: no holdout, a ROC AUC ficou em `0.907` contra `0.905` do INT8, com custo muito superior de memória, latência e armazenamento;
- preserva `xlm-roberta` INT8 como modelo padrão experimental;
- adiciona `mdeberta-v3` INT8 como único candidato de arquitetura diferente;
- generaliza provisionamento e avaliação por `--model`, mantendo revisão imutável, artefatos locais separados e runtime offline;
- não altera corpus, datasets, retrieval, RRF, thresholds promovidos ou caminho crítico.

A alpha.8 mede primeiro o candidato em `evidence-v1.json`. Thresholds serão definidos apenas nesse conjunto e congelados antes do holdout. Nenhuma regra específica por pergunta será introduzida.

## 0.6.0-alpha.7

- adiciona uma ablação controlada entre os artefatos ONNX INT8 e FP32 da mesma arquitetura de QA extrativa;
- mantém INT8 como variante padrão e preserva o retriever, o corpus, os datasets e as políticas já congeladas;
- permite provisionar as variantes lado a lado com `evidence-provision --variant`;
- permite selecionar a variante em `evidence-evaluate --model-variant`;
- registra variante e tamanho do artefato no relatório JSON para tornar a comparação reproduzível;
- mantém manifestos separados e revisão imutável do modelo, preservando a operação offline após o provisionamento.

Esta etapa mede se a quantização explica parte da perda de separação observada. FP32 não deve ser promovido apenas por melhorar um threshold: a comparação principal usa ROC AUC, métricas congeladas, latência, memória e tamanho do artefato.

No holdout, FP32 balanced obteve acurácia balanceada `0.825`, recall `0.900`, especificidade `0.750`, F1 `0.837` e ROC AUC `0.907`. O modo conservative obteve acurácia balanceada `0.700`, recall `0.400` e especificidade `1.000`. O artefato ocupa aproximadamente `1.059 MiB`, usou cerca de `2.155 MiB` de RAM e apresentou latência média de `47–49 ms`. Como a ROC AUC INT8 no mesmo holdout foi `0.905`, a diferença de ordenação não compensou o custo nem a regressão de abstenção.

## 0.6.0-alpha.6

- adiciona `evidence-v2-holdout.json` com 40 pares pt-BR inéditos e balanceados, sem reutilizar consultas da calibração;
- categoriza casos como `literal`, `paraphrase`, `temporal`, `entity` e `related_negative`;
- rotula abstenções esperadas por ausência de atualidade, incompatibilidade de entidade ou informação específica ausente;
- congela as políticas `initial=0.50`, `conservative=0.69740408` e `balanced=0.00016509` antes da execução no holdout;
- adiciona métricas por categoria e mantém métricas agregadas no mesmo relatório;
- introduz `EvidenceDecision` e `AbstentionReason` como contrato independente da LLM;
- fornece mensagens seguras em pt-BR para abstenção sem afirmar que a informação não existe fora da base;
- não altera o retriever, RRF, corpus, dataset de retrieval ou gate padrão.

O holdout deve ser executado uma única vez com as três políticas congeladas. O resultado mede generalização; não deve iniciar nova calibração sobre `evidence-v2-holdout.json`.

## 0.6.0-alpha.5

- registra a alpha.4 como experimento não promovido: o gate alcançou abstenção `1.000`, mas reduziu Hit@4 de `0.933` para `0.533` no threshold `0.50`;
- preserva `retrieval-v1.json`, o RRF, o corpus e todos os thresholds anteriores;
- adiciona o dataset independente `knowledge/evaluation/evidence-v1.json`, com 40 pares pt-BR balanceados entre chunks respondíveis e não respondíveis;
- adiciona `orelhao knowledge evidence-evaluate` para medir o verificador sem interferência do retrieval;
- mede acurácia, acurácia balanceada, precisão, recall, especificidade, F1, ROC AUC e latência;
- permite comparar diretórios de modelos locais pelo mesmo dataset e expor diagnósticos por par pergunta/chunk;
- adiciona validação de schema, classes, duplicidade, referências de chunks e threshold.

O dataset `evidence-v1.json` é de desenvolvimento e calibração. Ele não autoriza promoção por si só: um modelo candidato ainda precisa ser confirmado em um conjunto independente antes de integrar o caminho crítico.

## 0.6.0-alpha.4

- introduz o contrato `EvidenceVerifier`, independente do retrieval e do corpus;
- adiciona `EvidenceFilteredRetriever` como gate experimental após a fusão RRF;
- utiliza QA extrativa com suporte a ausência de resposta, em vez de aplicar NLI diretamente a perguntas;
- adiciona provisionamento explícito de `xlm-roberta-base-squad2-distilled` em ONNX int8, com revisão fixada e operação offline após download;
- adiciona `orelhao knowledge evaluate --retriever evidence --evidence-min-score` ao mesmo benchmark congelado;
- mantém scores, thresholds, RRF, corpus e dataset anteriores sem alteração;
- adiciona testes de preservação de ranking, filtragem, abstenção e validação do threshold.

O evidence gate permaneceu experimental. Na validação posterior, nenhum threshold apresentou equilíbrio suficiente para promoção.

## 0.6.0-alpha.3

- adiciona `orelhao knowledge evaluate --diagnostics` sem alterar o comportamento dos retrievers;
- expõe, por caso, fontes retornadas, scores, posição da fonte esperada e resultado correto/incorreto;
- inclui no diagnóstico o identificador, documento, posição, texto e metadados de cada chunk recuperado;
- mantém dataset, corpus, thresholds e RRF congelados para permitir a comparação causal entre baseline, semantic-only e fusão;
- adiciona testes do relatório detalhado e da nova opção da CLI.

Esta primeira parte da alpha.3 é exclusivamente diagnóstica. O confidence gate somente será definido após comparar os casos divergentes produzidos pelos três retrievers no mesmo benchmark.

## 0.6.0-alpha.2

- adiciona `ReciprocalRankFusionRetriever` para combinar rankings sem misturar scores de escalas diferentes;
- preserva os gates independentes da baseline (`0.40`) e do semântico experimental (`0.852`);
- adiciona `orelhao knowledge evaluate --retriever fusion` no mesmo Evaluation Harness;
- utiliza RRF com constante `60`, sem pesos treinados, regras por pergunta ou confidence gate;
- adiciona testes de consenso, candidatos complementares, abstenção e parâmetros inválidos;
- mantém a fusão como experimento até a comparação A/B.

No dataset congelado, a fusão obteve Hit@1 `0.833`, Hit@4 `0.933`, MRR `0.872` e abstenção `0.500`, com latência média aproximada de `34–36 ms` e pico de memória de aproximadamente `772 MiB`. O ganho de recall e ranking veio acompanhado de regressão de abstenção; por isso, a fusão não foi promovida.

## 0.6.0-alpha.1

- adiciona `SemanticVectorizer` como contrato independente do retriever baseline;
- implementa embeddings locais com `multilingual-e5-small` quantizado em ONNX e revisão fixada;
- separa os artefatos semânticos do índice lexical/hash e valida sua coerência por hashes;
- adiciona provisionamento explícito do modelo e reconstrução do índice semântico;
- permite medir `semantic-only` com `orelhao knowledge evaluate --retriever semantic` no dataset congelado da v0.5;
- mede ranking semantic-only inicialmente com threshold `0.0` e calibra sistematicamente um candidato semântico, sem fusão ou confidence gate;
- não promove o retriever experimental antes de uma comparação A/B completa.

No mesmo dataset da v0.5, semantic-only sem threshold obteve Hit@1 `0.867`, Hit@4 `0.900`, MRR `0.878` e abstenção `0.000`. O candidato `min_score=0.852` obteve Hit@1 `0.833`, Hit@4 `0.833`, MRR `0.833` e abstenção `0.600`, com latência média aproximada de `33–36 ms`. O processo semântico atingiu aproximadamente `772 MiB` de RAM e os artefatos locais do modelo ocuparam `241 MiB`; portanto, o mecanismo não foi promovido como padrão.

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
