# Orelhão IA — Auditoria do Knowledge, fontes e RAG (03/11/2026)

**Escopo:** branch experimental `feat/esp32-hook-serial-20261030` no Dell Ubuntu 24.04. Avaliação de fontes oficiais, índice hashing-word-char, recuperação, precheck, Qwen local, grounding V3, roteamento por cidade e conteúdos de voz. **Não constitui homologação do atendimento público.**

## 1. Diagnóstico da base anterior

O índice anterior continha **21 documentos e 43 trechos**, predominantemente institucionais, PSG, unidades, tecnologia, Excel e gestão. Não havia documento próprio de **Saúde** por segmento/unidade, nem ficha do **Técnico em Enfermagem**. O documento de tecnologia de 08/06 omitira **Aprendendo Programação com Minecraft em Parnaíba (40 h)**, embora a fonte o mencione.

O loader exclui deliberadamente `00-README.md` e arquivos da categoria `evaluation`. Portanto, 23 arquivos Markdown na pasta não equivalem a 23 documentos indexados.

### Recuperação não equivale a compreensão

O retriever usa `hashing-word-char-v1` (384 dimensões) e alinhamento lexical do **corpo do chunk**, com filtro de score. O chunker corta a cada 700 caracteres com sobreposição de 120, sem respeitar os limites de entidades/cursos/unidades. Os metadados `segmento`, município e unidade não compõem um filtro de catálogo. Consultas genéricas com “Senac Piauí 2026” podem favorecer documentos de outra área mesmo quando há informação relevante de Saúde.

O benchmark legado de 40 perguntas mede apenas recuperação: Hit@1 0,600, Hit@4 0,833, MRR 0,697 e acurácia de abstenção do retriever 0,600. A acurácia de 60% revela fragilidade em consultas negativas; **não confundir com a abstenção do grounding**.

## 2. Fontes oficiais verificadas

- [Cursos técnicos por segmento, Senac PI, 05/06/2026](https://www.pi.senac.br/noticias/senac-piaui-oferta-cursos-tecnicos-em-areas-estrat): Saúde (Técnico em Enfermagem, Podologia, Estética, Instrumentação Cirúrgica) e TI (Informática e Desenvolvimento de Sistemas), com relação de unidades.
- [Cursos inéditos por unidade e segmento, 08/06/2026](https://www.pi.senac.br/noticias/senac-piaui-amplia-portfolio-com-cursos-ineditos-e): capacitações e durações, incluindo Saúde e o exemplo de Minecraft em **Teresina Zona Leste e Parnaíba**.
- [Página do Técnico em Enfermagem](https://www.pi.senac.br/saude/tecnico-em-enfermagem), consultada em 03/11/2026: **1.600 horas**, descrição profissional e listagens de turmas por unidade. As turmas ou condições exibidas **não são garantia de vagas hoje**.
- [Portal de cursos do Senac PI](https://www.pi.senac.br/cursos): possui filtros de unidade, segmento e outras condições. [Links de consulta por unidade](catalogo-por-unidade-2026.md) ficam como **documentação operacional fora do índice**, por impacto negativo na avaliação de MRR ao indexá-los.

### Novos documentos de corpus

1. `cursos/saude-tecnicos-2026.md`: técnicos de Saúde por unidade no anúncio de 05/06/2026.
2. `cursos/saude-capacitacoes-2026.md`: capacitações de Saúde e duração por município no anúncio de 08/06/2026.
3. `cursos/tecnicos-ti-2026.md`: cursos técnicos de TI por unidade no anúncio de 05/06/2026. O nome histórico **Audir Lages** não foi presumido sinônimo de Zona Leste.
4. `cursos/tecnico-enfermagem-catalogo-2026.md`: 1.600 horas, descrição e localidades da página oficial do curso.

Além disso, `cursos/tecnologia-qualificacoes-2026.md` foi corrigido para incluir **Parnaíba → Programação com Minecraft, 40 horas**, e o fluxo guiado do monofone passou a reconhecer essa cidade.

Os novos registros usam `authority: primary`, `source_url`, `retrieved_at`, `published_at` quando aplicável, `segmento` e `temporal: true`. **Não recebem** `current_state_confirmed`; anúncios históricos não comprovam disponibilidade, valor ou inscrição atual.

## 3. Gates e métricas

| Conjunto / indicador | Índice anterior | Candidato |
|---|---:|---:|
| Documentos / chunks | 21 / 43 | **25 / 51** |
| Legado, 40 casos: Hit@1 | 0,600 | 0,600 |
| Legado: Hit@4 | 0,833 | 0,833 |
| Legado: MRR | 0,697 | 0,697 |
| Legado: abstenção do retriever | 0,600 | 0,600 |
| Novas 17 consultas de Saúde/TI, Hit@1 | não medido | **1,000** |
| Conjunto antigo de expansão (11 consultas), Hit@1 | 1,000 | 1,000 |

O conjunto de 17 casos em `knowledge/evaluation/expansion-health-ti-20261103.json` foi **derivado das novas fontes** e serve como regressão local, **não como holdout independente**.

Uma quinta fonte candidata, com links de catálogo por unidade, foi **retirada do índice** porque reduziu o MRR do conjunto legado para 0,6889. Foi mantida em `docs/catalogo-por-unidade-2026.md` como referência, não evidência ativa.

## 4. Teste ponta a ponta e achado crítico

No perfil Qwen local do Dell, utilizando o índice candidato e `mode=enforce`:

1. Pergunta sobre Saúde em Teresina em junho de 2026: fontes de Saúde recuperadas, precheck aprovado, resposta gerada em aproximadamente 6,15 s. **Falha:** o Qwen trocou o nome oficial *Alta Performance em Urgência e Emergência: Treinamento Imersivo com Simulação Realística* por *Unidade de Especialização em Saúde e Emergência com Simulação Realística*. O grounding **incorretamente classificou como `supported`**.
2. Pergunta sobre carga horária do Técnico em Enfermagem: respondeu **1.600 horas** com evidências recuperadas, `supported`, cerca de 3,45 s.
3. Pergunta sobre vagas abertas hoje para Técnico em Enfermagem: recuperou texto histórico, mas `precheck_blocked` com `temporal_evidence_unavailable`, sem chamada ao LLM.

**Consequência:** mesmo uma resposta aceita pelo NLI pode inventar uma denominação de curso. Esse é um defeito concreto de fundamentação, não solucionado apenas por adicionar documentos. Não reduzir limiares nem liberar o modo `enforce`.

## 5. Arquitetura recomendada para a próxima etapa

**P0 — Qualidade factual:** validar nomes próprios de cursos/unidades contra um catálogo estruturado e exigir correspondência exata antes de falar uma oferta. Mensagens de listas podem usar modelos determinísticos extraídos dos registros, em vez de deixar a LLM rebatizar os títulos. Adicionar avaliação humana de casos positivos, negativos, datas e erros de transcrição.

**P1 — Catálogo separado do RAG:** modelar `segmento → curso → unidade → oferta`, com IDs estáveis, relações, fonte oficial, versão, data de coleta, vigência e estado de matrícula. Uma implementação inicial com SQLite/local é suficiente para o MVP; o índice vetorial continua útil para documentos institucionais e explicações.

**P1 — Atualidade real:** o precheck exige `current_state_confirmed=true`, fonte primária e verificação no mesmo dia, com `valid_until` vigente. Como as fontes estáticas não cumprem isso, perguntas “tem vaga hoje?” são bloqueadas **por desenho**. Precisam de uma consulta confiável ao portal de matrículas ou confirmação humana, **não de um PDF antigo com data alterada**.

**P2 — Recuperação e áudio:** avaliar filtragem explícita por segmento/unidade em vez de buscar simultaneamente em todo o corpus; rever chunking por entidade e curso, avaliar reranking e sinônimos para erros reais de Whisper. Preservar o monitor como observador da mesma sessão, com motivo da abstenção e fonte utilizada. Medir latência total, WER e falsos positivos separadamente.

**Pendências:** checagem humana das frases de Saúde, teste físico do monofone e revisão do problema de nomes reescritos pela LLM. **Status de produção: NO-GO.**

## 6. Ativação e reversibilidade (03/11/2026)

Após comparar o índice candidato com a versão anterior e confirmar ausência de
chamada física ativa, o índice de **25 documentos e 51 chunks** foi promovido
atomicamente para `knowledge/index`. O Admin foi reiniciado e respondeu HTTP
200, com o monitor ativo em loopback. O ESP32 continuou enumerado em
`/dev/ttyUSB0`.

**Backup da versão anterior (21/43):**
`/home/lumi/.local/share/orelhao-ia/backups/knowledge-index-before-health-ti-20261103`.
A substituição não apagou o backup nem versionou os vetores binários no Git.

O código passou em **460 testes**, Ruff e Mypy. Novas mensagens de voz
foram geradas previamente com Piper `length_scale: 0.88`. O fluxo específico
de Parnaíba aguarda confirmação no monofone físico.

**Importante:** a expansão melhora a recuperação e não equivale à aprovação
do Qwen. A incongruência entre nome de curso emitido e denominação publicada
permanece **P0 para avaliação e validação de títulos exatos**.
