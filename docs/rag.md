# RAG / Knowledge — v0.4.0-alpha.1

A camada de conhecimento é independente do domínio da implantação.

## Objetivo da alpha.1

Validar os contratos do RAG antes de introduzir embeddings, banco vetorial ou LLM real.

Fluxo atual:

`Document → chunking → KnowledgeRepository → LexicalRetriever → ContextBuilder → KnowledgeContext`

## Contratos

- `Document`: fonte lógica fornecida pela implantação;
- `Chunk`: unidade recuperável;
- `SearchResult`: chunk + score normalizado;
- `KnowledgeRepository`: persistência/consulta dos chunks;
- `Retriever`: estratégia substituível de recuperação;
- `ContextBuilder`: aplica orçamento de contexto e preserva fonte;
- `KnowledgeService`: facade utilizada pelas camadas superiores.

## Implementação atual

A alpha.1 usa `InMemoryKnowledgeRepository` e `LexicalRetriever`. O ranking é lexical e determinístico, propositalmente sem dependências externas.

Essa implementação **não é o retriever final**. Ela serve como baseline de comportamento e testes para que embeddings e vector stores possam ser avaliados sem alterar o core.

## Próxima etapa

- escolher modelo de embeddings local;
- criar índice vetorial persistente;
- implementar ingestão de arquivos da base configurada;
- adicionar avaliação de recuperação (Recall@K/MRR);
- conectar o contexto ao LLM local;
- adicionar política de resposta sem evidência.

## Alpha.2 — base em disco

A fonte autoritativa passa a ser `knowledge/sources/`; `knowledge/index/` contém apenas artefatos reconstruíveis.
Os comandos operacionais são `orelhao knowledge index` e `orelhao knowledge search <consulta>`.

A alpha.2 usa um vetor determinístico de hashing (palavras + trigramas) para validar persistência, CLI, threshold de abstenção e desempenho sem baixar outro modelo. Ele **não substitui embeddings semânticos de modelo**, previstos para a evolução seguinte.
