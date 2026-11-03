> **TIPO: REGISTRO DATADO / HISTÓRICO.** Checkpoint DEPOIS da ingestão de cursos, ANTES da correção de Informática Básica: 18 documentos e 35 chunks. O índice posterior registra 18/36. Para o estado consolidado e as métricas mais recentes, consulte [Estado vigente](current-state.md). Preservar os resultados originais para rastreabilidade.

# Atualização da base de conhecimento — Senac Piauí (29/10/2026)

## Escopo e proveniência

Atualização **incremental e verificável** da camada RAG, sem alterar modelos, thresholds congelados do NLI, retrieval baseline ou fluxo de áudio. Os documentos são retratos datados de portais oficiais, não uma integração de disponibilidade em tempo real.

| Conteúdo | Fonte primária oficial |
|---|---|
| 13 entradas de unidades, em 10 municípios | https://www.pi.senac.br/ |
| Contato central da Administração Regional | https://www.pi.senac.br/contato |
| Informática Básica: 140h, regras e localidades anunciadas | https://pi.senac.br/tecnologia-da-informacao-ti/informatica-basica |
| Excel: 30h, regras e localidades anunciadas | https://pi.senac.br/tecnologia-da-informacao-ti/excel |
| Excel Avançado: 60h, regras e unidade consultada | https://www.pi.senac.br/tecnologia-da-informacao-ti/excel-avancado?unidade_operativa_id=19 |
| PSG: publicação dos Editais 006/2026, 007/2026 e Senac Aprendiz 05/2026, com retificações | https://psg.pi.senac.br/vagas/ |

Os valores publicados em páginas de cursos e os totais *previstos nos editais* devem ser tratados como **referência da consulta**, não como preço ou vagas disponíveis no instante de uma pergunta futura. Não foram inventados horários, telefones ou endereços individuais de unidades sem fonte.

## Arquivos alterados

- `knowledge/sources/unidades/rede-senac-piaui.md`: nova lista institucional de localidades e quatro entradas de Teresina.
- `knowledge/sources/cursos/informatica-basica-2026.md`: novo documento de referência ao curso.
- `knowledge/sources/cursos/excel-2026.md`: novo documento de referência ao curso.
- `knowledge/sources/cursos/excel-avancado-2026.md`: novo documento de referência ao curso.
- `knowledge/sources/cursos/agenda-e-unidades.md`: alinhamento da lista com o portal atual.
- `knowledge/sources/atendimento/canais-institucionais.md`: confirmação do contato central, distinguindo-o dos contatos de unidades.
- `knowledge/sources/psg/vagas-e-editais.md`: atualização da listagem de editais com ressalva de vigência.
- `knowledge/evaluation/retrieval-refresh-2026-10.json`: 17 questões específicas, incluindo abstenção e disponibilidade temporal.
- `tests/knowledge/test_source_refresh.py`: verificação automática de que as novas fontes são carregáveis e possuem metadados de proveniência.

Todos os documentos novos e atualizados informam `source_url`, `retrieved_at: 2026-10-29`, `authority: primary` e `temporal: true`. Não foram inseridos dados de teste ou documentação de auditoria dentro de `knowledge/sources`.

## Evidências da indexação e do benchmark

A reconstrução local do índice aumentou o corpus de **14 documentos/23 chunks** para **18 documentos/35 chunks**. O benchmark de retrieval foi reexecutado com o mesmo dataset original congelado; **não alteramos seu gabarito**:

| Métrica | Antes da atualização | Depois da atualização |
|---|---:|---:|
| Hit@1 | 0,6333 | 0,6000 |
| Hit@k | 0,8000 | 0,8333 |
| MRR | 0,7028 | 0,6972 |
| Acurácia de abstenção | 0,6000 | 0,6000 |

O novo conjunto complementar (17 questões: 12 positivas e 5 de abstenção) atingiu **Hit@1 = 0,8333** e **Hit@k = 1,0000** para as perguntas respondíveis, porém apenas **20% de acurácia de abstenção**. A combinação de maior cobertura e falhas na identificação de ausência de evidência indica que **não devemos habilitar respostas sobre vagas, horário e disponibilidade atuais apenas com o RAG estático**.

As métricas de latência foram executadas no Arch Linux de desenvolvimento, não no Dell OptiPlex 7050 com 8 GB. Comparações únicas de latência não são prova de regressão de desempenho.

## Como validar novamente

```bash
cd /home/wesscosta/Develop/orelhao-ia
source .venv/bin/activate
orelhao knowledge index
orelhao knowledge evaluate --retriever baseline --json
orelhao knowledge evaluate knowledge/evaluation/retrieval-refresh-2026-10.json --retriever baseline --json
pytest -q
```

Para a bancada, a interface administrativa deve ser reiniciada depois de atualizar o índice, porque o retriever pode estar carregado na memória.

## Próximo gate obrigatório

**Grounding e answerability:** ampliar verificação de ausência de informação específica, conflitos entre editais, unidades e datas sem retocar os thresholds congelados. Não promover o retrieval como fonte de disponibilidade em tempo real sem integração com fonte vigente ou validação explícita. Depois ampliar contatos locais por unidade somente com documentos oficiais verificáveis.
