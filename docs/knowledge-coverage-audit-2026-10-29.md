# Auditoria de cobertura da base Senac Piauí — 29/10/2026

**Natureza:** diagnóstico baseado no corpus local, não uma atualização de fatos institucionais. Este arquivo deve permanecer **fora** de `knowledge/sources`, para não ser indexado como evidência.

## Estado observado

- Existem **16 documentos Markdown** em `knowledge/sources`.
- O carregador exclui corretamente `00-README.md` e `faq/faq-rag.md` (categoria `evaluation`).
- O índice ativo possui **14 documentos informativos** e **23 chunks**.
- Os 14 documentos possuem `source_url` e `retrieved_at`.
- Todos os documentos informativos foram registrados em **24/08/2026**, há **66 dias**.
- **12 de 14** declaram `temporal: true`, mesmo alguns descrevendo regras relativamente duradouras.
- Principais categorias: PSG (3), institucional (3), atendimento (2), cursos (1), aprendizagem (1), empresas (1), biblioteca (1), empregabilidade (1), aluno (1).

## Lacunas prioritárias para alimentação **verificada**

| Prioridade | Tema | Evidência desejável | Critério de vigência |
|---|---|---|---|
| P0 | Unidades do Senac Piauí | Uma fonte por unidade: nome oficial, cidade, endereço, contato, horário, serviços | Data de consulta e confirmação recente no canal oficial |
| P0 | Cursos por unidade | Nome, modalidade, carga horária, pré-requisitos e público | Data e unidade; não presumir turma, disponibilidade, preço ou matrículas abertas |
| P0 | PSG | Regras vigentes, oportunidades abertas, editais e respectivos comunicados | Usar edital específico com revisão, abertura/encerramento e situação atual |
| P0 | Canais de atendimento | WhatsApp, telefones, e-mails e horário por unidade | Fonte oficial consultada recentemente |
| P1 | Matrícula e documentação | Passos, documentos, critérios, pagamento, cancelamento, rematrícula | Documento institucional vigente e oferta aplicável |
| P1 | Acessibilidade e suporte | Libras, atendimento especial, estruturas, encaminhamento | Unidade, canal e disponibilidade explicitamente documentados |
| P1 | Biblioteca e empregabilidade | Endereços, serviços, elegibilidade e procedimentos | Data e regra aplicável |
| P1 | FAQ de atendimento | Perguntas naturais e respostas ligadas às fontes primárias | Não indexar perguntas de avaliação como se fossem fontes factuais |

## Processo de ingestão proposto

1. Buscar fontes **oficiais**, preferindo portal Senac PI, páginas de unidades, catálogo/agenda e PSG. Nunca indexar uma redação gerada pela LLM como nova fonte sem validação humana.
2. Registrar `title`, `category`, `authority`, `source_url`, `retrieved_at`, `temporal`, `unit` (quando aplicável), `valid_from` e `valid_until` quando houver informação verificável.
3. Preservar distinções entre **fato institucional duradouro**, **curso cadastrado** e **oferta/turma com prazo**. As duas últimas não são equivalentes.
4. Criar um arquivo Markdown curto por assunto/unidade/edital, com fatos checados. Arquivos sem fonte verificável ficam em `knowledge/research`, **nunca** no corpus ativo.
5. Reindexar e executar os datasets de retrieval, abstenção, grounding e casos conversacionais. Registrar acertos, falsos positivos e a evolução do índice antes de publicar.
6. Definir rotina de revisão para documentos temporais e abstention quando data, unidade ou disponibilidade não forem demonstráveis.

## Restrições técnicas

- A base de conhecimento não deve fornecer informação atual apenas porque existia em agosto de 2026.
- O retriever deve separar contexto e fontes por entidade e localidade (Teresina, Parnaíba, Picos etc.).
- Evidências conflitantes exigem tratamento explícito; usar apenas o maior score NLI entre os trechos é insuficiente.
- Não são dados novos ou homologação: esta auditoria identifica **o que falta pesquisar, conferir e indexar**.

Próximo gate de dados: alimentar e validar o conjunto de unidades e canais oficiais por município, com evidência de origem e data. Em paralelo, incorporar testes de perguntas por município, oferta vigente e entidade homônima.
