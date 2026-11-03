# Intenções básicas do Lumi — operação por voz

## Objetivo

Responder a perguntas de funcionamento do próprio assistente e orientar o
usuário antes de enviar questões específicas ao RAG. O monitor web continua
mostrando a transcrição original do Whisper e a resposta realmente reproduzida.

## Respostas guiadas no atendimento

- **Quem é o Lumi / O que consegue fazer:** apresentação e capacidades reais
  do terminal, sem alegar matrícula, vagas em tempo real ou acesso a GPS.
- **Qual sua configuração:** resumo não sensível derivado da configuração,
  sistema operacional, CPU e memória do próprio servidor.
- **Quais cursos o Senac oferece:** categorias confirmadas no catálogo local;
  a escolha posterior de comércio, tecnologia ou idiomas recebe orientação
  correspondente sem inventar turmas abertas.
- **Sobre o Senac Piauí:** visão geral respaldada pelas fontes institucionais.
- **Me informe sobre...** sem tema definido: solicita que a pessoa diga o assunto.
- **Onde estou / Senac mais próximo:** pede cidade ou bairro. Não calcula
  distância nem presume GPS ou localização física do monofone.
- **Supervisão mais próxima:** primeiro pergunta qual instituição ou setor
  o usuário procura. Não inventa endereços de supervisões.
- **Só um instante:** responde educadamente e evita o aviso de microfone
  silencioso enquanto a pausa estiver ativa. Os limites de chamada permanecem
  em vigor, portanto não se trata de espera ilimitada.
- **Alucinação STT típica:** uma frase igual ao cabeçalho de transcrição
  do Whisper não segue para a consulta factual.

## Separação de responsabilidades

- O roteador de intenções está em `hardware/voice_intents.py`;
  seu estado é descartado ao encerrar cada ligação.
- As frases fixas ficam em `hardware/voice_prompts.py`, geradas previamente
  com a voz Piper configurada. Mudança de modelo, texto ou velocidade
  invalida o cache de forma automática.
- Perguntas específicas sobre curso, carga horária, matrícula, preço,
  disponibilidade, endereço ou fato institucional **não devem ser respondidas
  por templates gerais**: continuam no pipeline de retrieval e grounding.
- A fonte de verdade para o conteúdo institucional é o corpus
  `knowledge/sources/`. Ampliá-lo não deve exigir novos templates a cada
  pergunta, e respostas guiadas precisam de revisão quando fatos mudarem.

## Validação e limites

Testes principais: `tests/unit/test_voice_intents.py`,
`tests/unit/test_voice_worker.py` e `tests/unit/test_voice_prompts.py`.
A validação automatizada não substitui testar pelo monofone real; ruído,
eco, cortes e falsos positivos do Whisper ainda exigem diagnóstico.


## 03/11/2026 — regressão da sessão física (capturas do monitor)

O monitor revelou que o Whisper reconhecia **"Os Custos Senac"**, o Lumi
perguntava **"cursos ou preços?"** e a resposta **"Eu quero saber os cursos"**
caía indevidamente no RAG, gerando `precheck_blocked`.

Correções:

- Estado explícito `awaiting_courses_or_prices`, respeitando a resposta
  do usuário à pergunta de desambiguação;
- solicitações gerais de cursos encaminhadas à apresentação orientativa,
  sem substituir o RAG nas consultas específicas de preços, vagas e cargas horárias;
- comandos inequívocos como **"Finaliza"**, **"Pode encerrar"** e
  **"Tchau"** terminam o worker pela própria voz, reproduzindo apenas
  uma despedida; o controlador aguarda o próximo ciclo físico do gancho;
- variações de **"espera só um instante"** não seguem ao RAG;
- o orçamento é de **12 transcrições válidas**, com teto de
  **36 tentativas de captura e 180 segundos** por ligação;
  capturas vazias e transcrições explicitamente rejeitadas não consomem
  o orçamento de perguntas. O teto de tentativas e o tempo previnem
  sessões indefinidas;
- testes de regressão: `tests/unit/test_voice_conversation_regressions.py`.

A filtragem de frases de legendagem inventadas pelo Whisper não comprova
melhoria da precisão geral do microfone: esse problema continua exigindo
análise física de ruído, VAD e avaliação STT. Não alterar os limiares de
grounding para contornar perguntas incorretamente transcritas.

## Pausa e encerramento por inatividade (03/11/2026)

O atendimento **não precisa alcançar 12 perguntas ou 36 tentativas** para encerrar. Após uma resposta, a captação fica esperando a próxima fala:

- **Atendimento normal:** cada captura aguarda até aproximadamente **7 segundos** pelo início de uma fala. Na primeira ausência, o Lumi diz **“Você ainda está aí? Pode falar.”**. Na segunda captura consecutiva sem fala (ou com transcrição rejeitada), diz **“Como não ouvi resposta, vou encerrar. Até logo.”** e encerra o processo da ligação.
- **Pausa solicitada:** ao ouvir **“Só um instante”** ou equivalente, responde brevemente e fica escutando sem avisos repetitivos. A pausa comporta até **quatro capturas silenciosas**, aproximadamente **28 segundos**, antes do encerramento automático. Se a pessoa falar antes disso, o Lumi retoma o diálogo e zera a contagem de inatividade.
- **Prioridade do gancho:** recolocar o monofone interrompe imediatamente a sessão, sem esperar captura ou despedida. Para abrir outra chamada após encerramento automático, é necessário recolocar e retirar o monofone.
- Os prazos são aproximados: inicialização do gravador, VAD, calibração e TTS adicionam tempo. Continuam válidos os tetos gerais de **180 segundos, 12 perguntas válidas ou 36 tentativas** como proteções adicionais.
- Eventos `voice.paused`, `voice.idle_timeout` e `voice.listening` com status `aguardando_retorno` permitem acompanhar os estados no monitor web, **sem segunda inferência**.

Os testes de comportamento estão em `tests/unit/test_voice_idle_policy.py`. O método `CallIdlePolicy` separa a política de pausa/encerramento da infraestrutura de gravação. A integração física ainda depende de confirmação com o monofone real.

## Robustez de intenções — 03/11/2026

- Abertura: **“Olá! Eu sou o Lumi. Como posso ajudar?”** com WAV em cache na velocidade Piper 0.88.
- A escolha “Vamos saber sobre os cursos” depois de “cursos ou preços?” abre as categorias sem recorrer ao RAG.
- O relógio local entende vocativos como “Ei, que dia é hoje?” e “Oi, Lumi, que horas são?”, sem herdar o tópico de cursos. Perguntas sobre horários institucionais ou matrículas continuam exigindo fontes.
- Perguntas explícitas sobre a configuração recebem informação local não sensível. Frases ambíguas como “É igual à sua configuração” e fragmentos ininteligíveis pedem esclarecimento.
- A configuração experimental do Whisper no Dell usa um glossário curto de nomes do Senac, sem a frase metalinguística “Transcrição em português brasileiro”. Ainda não existe comparação independente de qualidade do STT.

Regressões em tests/unit/test_voice_real_utterances_20261103.py e tests/knowledge/test_local_clock.py. A qualidade da conversa continua dependente de teste com voz real.
