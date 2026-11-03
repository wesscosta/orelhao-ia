# Orelhão IA — memória por ligação e ampliação controlada do Knowledge (03/11/2026)

## Situação implementada

- Memória curta local em `hardware/conversation_context.py`, instanciada
  por ligação em `voice_worker.py` e descartada ao término.
- Armazena somente as últimas **4 interações** em RAM; utiliza o tema
  e o curso citado para interpretar referências de continuidade.
- Perguntas sem entidade identificada, como "e quanto custa?" após
  listar categorias, pedem esclarecimento em vez de adivinhar um preço.
- As respostas anteriores **não** são reenviadas como evidências ao
  retrieval, precheck, NLI ou LLM: apenas a pergunta atual contextualizada.
- Monitor físico mostra a transcrição e um evento `voice.context`
  com a consulta efetivamente enviada ao RAG, quando houver reescrita.
- Novas observações de grounding da chamada física são gravadas em
  tmpfs durante o atendimento e eliminadas junto à sessão no gancho;
  isso não altera os registros históricos já existentes na bancada web.

## Base ativa

Fonte oficial do Senac Piauí consultada em **03/11/2026**.
Três novos documentos entraram no índice:

1. `cursos/gestao-comercio-amostras-2026.md`, catálogo histórico
   de gestão e comércio publicado em 08/06/2026.
2. `cursos/tecnologia-qualificacoes-2026.md`, exemplos de capacitações
   em tecnologia citados na mesma publicação.
3. `psg/edital-004-2026-exemplo.md`, exemplo histórico de processo
   de seleção PSG publicado em 05/05/2026.

Os documentos contêm URL oficial no frontmatter, data de publicação,
`retrieved_at`, `authority: primary` e `temporal: true`.

**Dois materiais foram retirados do índice após avaliação**, sem perdê-los:
`docs/consulta-cursos-senac-2026.md` (redundância de ranking) e
`docs/cursos-tecnicos-anuncio-2026.md` (falso positivo de retrieval
para pergunta sobre vaga aberta hoje). Não reintroduzir automaticamente;
reavaliar com critérios específicos de atualidade.

## Antes x depois — avaliação congelada

Dataset `knowledge/evaluation/retrieval-v1.json`, 40 casos, mesmo
retriever, threshold 0.40 e top-k 4:

| Indicador | Antes | Depois |
|---|---:|---:|
| Documentos | 18 | 21 |
| Chunks | 36 | 43 |
| Hit@1 | 0,600 | 0,600 |
| Hit@4 | 0,833 | 0,833 |
| MRR | 0,697 | 0,697 |
| Acurácia de abstenção de retrieval | 0,600 | 0,600 |

Dataset novo `knowledge/evaluation/lumi-expansion-20261103.json`:
11 consultas positivas derivadas dos novos documentos, Hit@1 = 1,0
e Hit@4 = 1,0. **Não é holdout independente** e não mede abstenção
nem eficácia ponta a ponta do LLM. Não usar esse score como
homologação pública.

Em teste funcional com o modelo Qwen local, a resposta a uma pergunta
histórica de tecnologia foi aprovada; a pergunta sobre vaga aberta hoje
foi bloqueada pelo precheck; uma pergunta ampla sobre gestão encontrou
a fonte correta, mas a LLM se absteve. Isso exige avaliação humana
e evolução de geração/fundamentação, sem baixar limiares artificialmente.

## Ativação e rollback

Índice ativo: `knowledge/index`, 21 documentos e 43 chunks.
Backup anterior:
`/home/lumi/.local/share/orelhao-ia/backups/knowledge-index-before-2026-11-03`.

A troca ocorreu após indexação candidata, comparação de métricas
e verificação de ausência de ligação em andamento. Para rollback,
parar novas ligações, restaurar o diretório de backup de forma segura
e reiniciar a administração para recarregar os dados.

## Limites conhecidos e próxima evolução

- Não existe contexto ilimitado: a chamada agora possui limite de 12 perguntas válidas,
  36 tentativas de captura e 180 segundos no worker experimental; a política de silêncio encerra antes se necessário.
- A memória atual resolve referências simples; não substitui um
  gerenciador geral de diálogo nem aplica identificação semântica
  profunda de intenção.
- STT no monofone ainda apresenta erros em falas curtas/ruído e deve
  ser medido separadamente.
- Ofertas anunciadas em 2026 **não provam vagas, valores ou datas
  vigentes**. Consultas atuais exigem atualização documental.
- O grounding permanece em `enforce`. A expansão da base não
  representa validação de qualidade conversacional para operação pública.
- A web e o futuro display do ESP32 devem consumir eventos da mesma
  sessão, nunca executar novos STT/RAG/LLM.
