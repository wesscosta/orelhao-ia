> **TIPO: REGISTRO DATADO / HISTÓRICO.** Último benchmark documental disponível; seus rótulos continuam assistidos por IA e não houve homologação humana. Para o estado consolidado e as métricas mais recentes, consulte [Estado vigente](current-state.md). Preservar os resultados originais para rastreabilidade.

# Gate factual adversarial — execução com modelos reais (29/10/2026)

**Situação: IMPLEMENTAÇÃO E MEDIÇÃO CONCLUÍDAS; HOMOLOGAÇÃO REPROVADA (NO-GO).**

## Escopo

A avaliação executou o pipeline textual retrieval → answerability → LLM local → NLI → resposta apresentada, com modo seguro (enforce) e evidências do corpus Senac PI. A gravação STT, a qualidade acústica do Piper e a operação no Dell OptiPlex de 8 GB **não** foram incluídas.

Foram preparadas 40 perguntas naturalísticas: 20 com fatos verificáveis nos documentos versionados e 20 com respostas não demonstráveis pelo corpus estático. A redação e os rótulos foram criados com auxílio de IA, partindo de documentos institucionais e de consultas a páginas oficiais. Não representam perguntas coletadas de visitantes nem constituem holdout adjudicado por humanos.

A comparação ocorreu sequencialmente, com os servidores locais de Tucano2 1.5B e Qwen3.5 0.8B, no Arch Linux de desenvolvimento. As respostas e as decisões por afirmação estão preservadas em knowledge/evaluation/results/. O script reproduzível é scripts/run_live_grounding_gate.py.

## Resultado após a correção de escopo

| Métrica | Tucano2 1.5B | Qwen3.5 0.8B |
|---|---:|---:|
| Casos executados sem erro | 40/40 | 40/40 |
| Permissões indevidas no conjunto negativo, segundo rubrica automática | 0/20 | 0/20 |
| Bloqueios no conjunto positivo | 8/20 | 10/20 |
| Positivos apresentados contendo todas as âncoras esperadas | 12/20 | 8/20 |
| Fonte de referência recuperada entre os resultados positivos | 18/20 | 18/20 |
| Positivos com NLI supported sem âncoras esperadas | 0 | 2 |
| Latência total P50 | 741 ms | 302 ms |
| Latência total P95 | 1.358 ms | 980 ms |

Não interpretar os 0 falsos ALLOW nos 20 casos negativos como garantia de segurança: o conjunto é pequeno, os rótulos não passaram por avaliação humana e existem erros entre os positivos, inclusive afirmações sustentadas incorretamente pelo NLI. As âncoras lexicais são sinais auxiliares, não comprovação semântica.

Antes da intervenção, Tucano2 bloqueava 9 de 20 positivos e apresentou uma resposta sobre 60 horas de Excel Avançado para uma pergunta que solicitava Excel, marcando NLI supported; após a intervenção, bloqueou 8 de 20 e respondeu Excel: 30 horas. As diferenças entre rodadas também podem refletir variação do modelo (temperatura 0.1). Não atribuir toda diferença observada à correção.

## Correções técnicas realizadas

1. Resolução genérica de entidade a partir de IDs documentais recuperados, com preferência por menção de nome completo para diferenciar entidades sobrepostas (ex.: Excel e Excel Avançado). Não foram incluídas heurísticas por nome de curso.
2. Contexto de geração em modo enforce restringido a documentos da entidade explicitamente solicitada; evidência de entidade diferente não deve validar a afirmação, mesmo que seu score NLI seja elevado.
3. Bloqueio pós-geração para respostas que introduzem explicitamente outra entidade documentada, com log e indicação administrativa do motivo.
4. Identificação de consultas temporais com “atual” e “vigente”, além de “hoje”, “agora” e outros sinais já existentes.
5. Correção factual do documento de Informática Básica: o portal oficial apresenta turmas de 140 e 80 horas por oferta/unidade, não uma carga horária universal. Fonte: https://www.pi.senac.br/tecnologia-da-informacao-ti/informatica-basica.
6. Fila de revisão com 15 casos sinalizados por um ou ambos os modelos: docs/review-grounding-real-2026-10-29.md. O formulário de revisão e as classificações humanas permanecem PENDENTES.

Após a revisão documental, o índice contém 18 documentos e 36 chunks. Os benchmarks congelados de retrieval permaneceram estáveis: original Hit@1=0,60, Hit@k=0,8333, MRR=0,6972, abstenção=0,60; complementar Hit@1=0,8333, Hit@k=1,00, abstenção=0,20. Essas métricas são de recuperação, **não do pipeline final**.

## Erros não resolvidos

- A recuperação falha para paráfrases naturais como “A partir de qual idade é possível acessar o Excel Avançado?”, apesar de a informação existir na fonte. Não foi ajustado o threshold do retriever.
- NLI ainda bloqueia afirmações aparentemente corretas na faixa uncertain: prazo da Ouvidoria, contato central, número de unidades e outras. Não reduzir os thresholds congelados sem estudo independente.
- Qwen3.5 foi mais rápido na bancada, mas houve duas respostas positivas com NLI supported sem as âncoras esperadas. Uma confundiu a missão institucional do Senac com o processo de contratação de aprendizes, demonstrando falso suporte semântico.
- A política de escopo depende de IDs de entidade verificáveis; a base ainda contém diversas fontes institucionais não estruturadas.
- Esses 40 casos foram usados para detectar e corrigir a mistura de cursos, logo a segunda execução é **regressão de desenvolvimento**; não é um holdout cego.
- Revisão humana independente, validação do ranking e falsos positivos no corpus ampliado, auditoria do comportamento por voz e benchmark no Dell 8 GB continuam obrigatórios.

## Reproduzir a avaliação

Com modelos servidos em loopback nas portas configuradas, executar:

1. .venv/bin/python scripts/run_live_grounding_gate.py --config config/benchmark-tucano2-15b-ptbr.yaml --dataset knowledge/evaluation/grounding-real-senac-pi-v1.json --output /tmp/orelhao-tucano-rerun.json
2. .venv/bin/python scripts/run_live_grounding_gate.py --config config/benchmark-qwen35-08b.yaml --dataset knowledge/evaluation/grounding-real-senac-pi-v1.json --output /tmp/orelhao-qwen-rerun.json
3. .venv/bin/pytest -q
4. .venv/bin/ruff check src/orelhao/services/knowledge tests/knowledge scripts/run_live_grounding_gate.py
5. .venv/bin/mypy src/orelhao/services/knowledge

As instâncias devem ser avaliadas sequencialmente para evitar concorrência de CPU. A avaliação foi executada no Arch Linux com Python 3.14; o CI usa Python 3.12, mas não havia Python 3.12 local disponível nesta máquina para uma execução adicional.

## Critério de decisão

**NO-GO para produção.** O gate diagnóstico foi executado e os registros estão disponíveis. O Tucano2 permanece o candidato experimental prioritário, mas o bloqueio de 40% dos positivos é excessivo, e a precisão semântica não foi homologada. O próximo passo é revisão humana de todos os 15 casos sinalizados e de amostra dos 25 restantes, novo conjunto cego, otimização do grounding sem recalibração oportunista, e aferição no Dell com voz completa.
