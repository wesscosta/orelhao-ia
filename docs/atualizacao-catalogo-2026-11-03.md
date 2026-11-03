# Atualização do catálogo do Senac Piauí — 03/11/2026

## Escopo e proveniência

Auditoria incremental do corpus ativo do **Orelhão IA**, alimentado por documentos Markdown indexados no Dell Ubuntu Server. As páginas de catálogo do **Senac Piauí** foram verificadas em **03/11/2026**. Trata-se de um instantâneo **histórico/datado**, não de consulta ao estoque de vagas no momento do atendimento.

Foram adicionadas fichas para:
- **Introdução à IA: Inteligência Artificial na Prática** (40h), com exemplos em Teresina, Severino Ramos Brasil, e Floriano. Fonte: https://pi.senac.br/tecnologia-da-informacao-ti/introducao-a-ia-inteligencia-artificial-na-pratica
- **Business Intelligence com Power BI** (40h), com exemplo de turma em Teresina, Severino Ramos Brasil. Fonte: https://www.pi.senac.br/tecnologia-da-informacao-ti/business-intelligence-com-power-bi?unidade_operativa_id=19
- **Procedimentos Técnicos em Sala de Vacina: tecnologias e inovações** (40h), com exemplos de turmas em Teresina, Centro, e Picos. Fonte: https://matricula.pi.senac.br/saude/procedimentos-tecnicos-em-sala-de-vacina-tecnologias-e-inovacoes

As fichas existentes de **Informática Básica** e **Excel** receberam informações complementares de turmas anunciadas em novembro, mantendo registros antigos e destacando a possibilidade de alterações. Fontes:
- https://www.pi.senac.br/tecnologia-da-informacao-ti/informatica-basica
- https://www.pi.senac.br/tecnologia-da-informacao-ti/excel

### Cuidado com a agenda genérica

A página institucional https://www.pi.senac.br/agenda-de-cursos ainda se descreve como agenda do **primeiro semestre de 2026**, mesmo com páginas individuais anunciando turmas em novembro. Para detalhes de curso, carga horária, município e unidade, usar a página específica, com data da coleta. Evitar tratar a página geral como a única fonte de oferta.

Os documentos têm frontmatter com `source_url`, `retrieved_at`, `authority: primary` e `temporal: true`. Nenhum deles possui `current_state_confirmed: true`, pois exibição de turma anunciada **não garante vagas, preços ou matrículas disponíveis em tempo real**.

## Diagnóstico técnico

O índice utiliza `hashing-word-char-v1` de 384 dimensões, com reforço lexical e chunks de 700 caracteres, sem normalização explícita `segmento → curso → unidade → oferta`. Como consequência:

1. Uma pergunta pode recuperar trechos relevantes, mas com **top-k misto** de segmentos e municípios.
2. A presença de uma fonte não significa que a **LLM formulou corretamente** a resposta. A auditoria anterior [auditoria-knowledge-2026-11-03.md](auditoria-knowledge-2026-11-03.md) demonstrou um falso positivo grave: o Qwen alterou a denominação de um curso e o NLI aceitou como `supported`.
3. Perguntas `hoje`, `agora`, `vagas abertas` e `preço atual` continuam impedidas pelo precheck até existir verificação da oferta no mesmo dia com declaração explícita de autoridade/validade, independentemente do novo índice.
4. `abstention_accuracy` de zero em um dataset **somente de perguntas positivas** não informa a taxa real de abstenção. Avaliar negativos em um conjunto próprio.
5. O monitor espelha a sessão física, mas **não substitui** um relatório estruturado por estágio: STT → rota → fontes/score → precheck → resposta bruta → verificação → fala final.

## Resultados de recuperação

| Medida | Base anterior | Índice candidato |
|---|---:|---:|
| Documentos | 25 | 28 |
| Trechos | 51 | 59 |
| Hit@1 legado, 40 casos | 0,600 | 0,600 |
| Hit@4 legado, 40 casos | 0,833 | 0,833 |
| MRR legado, 40 casos | 0,697 | 0,697 |
| Acurácia de abstenção do retriever, 40 casos | 0,600 | 0,600 |
| Expansão anterior 11 casos (Hit@1) | 1,000 | 1,000 |
| Expansão Saúde/TI 17 casos (Hit@1) | 1,000 | 1,000 |
| Catálogo novembro 11 casos novos (Hit@1) | não medido | 1,000 |

As 11 novas consultas foram **construídas a partir dos documentos incluídos**, por isso o resultado é de regressão e **não um benchmark independente**. A comparação de três conjuntos anteriores passou sem regressões. Os testes adicionais validam as fontes, a temporalidade e a recuperação dos novos documentos.

## Recomendações, em ordem de risco

**P0. Integridade factual da geração:** cadastrar cursos e unidades com identificadores e nomes oficiais. Para listagens de ofertas, preferir respostas determinísticas montadas a partir de registros estruturados, sem permitir que o Qwen altere denominações. Adicionar testes adversariais com nomes de cursos inexistentes, variações de cidade e ofertas expiradas. Não baixar os limiares do grounding.

**P1. Catálogo separado do RAG textual:** modelar `segmento`, `curso`, `unidade`, `turma/oferta`, `fonte`, `consultado_em` e `validade`. Para o MVP, SQLite é suficiente. O RAG continua atendendo perguntas conceituais/institucionais.

**P1. Política de atualização e disponibilidade:** sincronizar páginas específicas com proveniência e checagem de alterações; consulta ao vivo ou validação pela unidade para vagas e preços atuais. Nunca marcar `current_state_confirmed` apenas porque uma página está acessível.

**P2. Busca e experiência de voz:** filtros por segmento e município/unidade, chunking por entidade, deduplicação de trechos, re-ranking avaliado com holdout e teste do Whisper em linguagem natural. Mostrar no monitor a fonte encontrada e a **causa precisa** da recusa.

**Homologação:** **NO-GO** para orientação pública irrestrita enquanto persistir falso positivo do NLI para nomes de cursos e não houver avaliação humana ponta a ponta.

## Operação, registro e reversão

Os arquivos fonte e o dataset novo são versionáveis; os vetores e modelos locais não entram no Git. A publicação do índice exige comparação com a versão ativa, ausência de ligação física em andamento, backup e teste do serviço Admin após a troca.

**Datas/valores de exemplo neste relatório são observações da consulta em 03/11/2026, não confirmação de disponibilidade atual.**

## Ativação verificada em 03/11/2026

A promoção ocorreu após nova confirmação de **ausência de chamada física ativa**. O índice foi reconstruído, comparado aos três conjuntos legados e ao novo conjunto de 11 consultas, e promovido de forma atômica. O manifesto ativo agora registra **28 documentos e 59 trechos**.

Backup preservado da versão anterior (25/51):
`/home/lumi/.local/share/orelhao-ia/backups/knowledge-index-before-november-20261103`.

A interface administrativa foi reiniciada sem interferência em ligação física e posteriormente voltou a responder **HTTP 200** em `127.0.0.1:8765/monitor`. O serviço do gancho permaneceu ativo e `/dev/ttyUSB0` conectado.

**Validação do código:** 464 testes aprovados, 1 aviso de depreciação Starlette; Ruff e Mypy sem erros. A avaliação ponta a ponta complementar com Qwen **não foi realizada** porque uma ligação física se iniciou durante a preparação do teste. Preservar a prioridade do atendimento sobre cargas adicionais de inferência.

O aumento de cobertura textual **não corrige** o falso positivo de denominação de curso já detectado no grounding. Homologação pública permanece **NO-GO**.
