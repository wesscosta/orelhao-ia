# Base de conhecimento

- `sources/`: fonte da verdade editável da implantação. Markdown (`.md`) é o formato preferencial; `.txt` também é aceito nesta etapa.
- `index/`: artefatos derivados e reconstruíveis. Pode ser apagado e recriado com `orelhao knowledge index`.
- `evaluation/retrieval-v1.json`: benchmark congelado do retrieval, executado com `orelhao knowledge evaluate`.
- `evaluation/evidence-v1.json`: benchmark pt-BR separado de answerability por pergunta/chunk, executado com `orelhao knowledge evidence-evaluate`.
- `evaluation/evidence-v2-holdout.json`: conjunto independente e categorizado para validar generalização das políticas congeladas da alpha.6.

A alpha.7 reutiliza esses mesmos datasets para comparar INT8 e FP32 da mesma arquitetura. Não crie casos específicos para favorecer uma variante e não calibre thresholds no holdout.

A alpha.8 reutiliza os datasets sem alterações para comparar XLM-RoBERTa INT8 com mDeBERTa-v3 INT8. Apenas uma arquitetura muda; corpus e rótulos permanecem congelados.

- `evaluation/grounding-v1.json`: calibração separada da alpha.9 para NLI. Cada caso contém uma afirmação e um chunk rotulados como suportado ou não suportado. Não substitui nem modifica os benchmarks anteriores.

O holdout de evidência não é aplicável ao novo benchmark de grounding. Um conjunto confirmatório próprio só deve ser criado depois que modelo e threshold NLI forem congelados em `grounding-v1.json`.

- `evaluation/grounding-v2-holdout.json`: confirmação independente da alpha.10, com 20 afirmações suportadas e 20 não suportadas. Os thresholds `nli-balanced=0.1250362694` e `nli-conservative=0.7557643056` foram congelados antes de sua execução.

Não ajuste thresholds, afirmações ou categorias depois de observar resultados do holdout.

A alpha.11 não altera os datasets. Ela adiciona um contrato de decisão sobre scores NLI: `supported`, `unsupported` e `uncertain`. Apenas `supported` libera resposta; os demais estados são fail-closed.

Os dois datasets medem tarefas diferentes e não devem ser combinados. O primeiro avalia recuperação e ranking; o segundo avalia se um trecho fornecido contém resposta.

Não edite manualmente o conteúdo de `index/`. A aplicação deve continuar funcionando conceitualmente com `sources/` como única fonte autoritativa.

Conteúdo sensível ou restrito não deve ser publicado em repositório público.
