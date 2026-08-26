# Base de conhecimento

- `sources/`: fonte da verdade editável da implantação. Markdown (`.md`) é o formato preferencial; `.txt` também é aceito nesta etapa.
- `index/`: artefatos derivados e reconstruíveis. Pode ser apagado e recriado com `orelhao knowledge index`.
- `evaluation/retrieval-v1.json`: benchmark congelado do retrieval, executado com `orelhao knowledge evaluate`.
- `evaluation/evidence-v1.json`: benchmark pt-BR separado de answerability por pergunta/chunk, executado com `orelhao knowledge evidence-evaluate`.
- `evaluation/evidence-v2-holdout.json`: conjunto independente e categorizado para validar generalização das políticas congeladas da alpha.6.

A alpha.7 reutiliza esses mesmos datasets para comparar INT8 e FP32 da mesma arquitetura. Não crie casos específicos para favorecer uma variante e não calibre thresholds no holdout.

Os dois datasets medem tarefas diferentes e não devem ser combinados. O primeiro avalia recuperação e ranking; o segundo avalia se um trecho fornecido contém resposta.

Não edite manualmente o conteúdo de `index/`. A aplicação deve continuar funcionando conceitualmente com `sources/` como única fonte autoritativa.

Conteúdo sensível ou restrito não deve ser publicado em repositório público.
