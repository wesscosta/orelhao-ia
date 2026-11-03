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
