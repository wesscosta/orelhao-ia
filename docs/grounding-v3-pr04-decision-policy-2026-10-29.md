# Grounding V3 — PR-04: política de decisão factual e completude da resposta

**Data:** 29/10/2026. **Status:** implementação experimental; **não homologada**. Branch `feat/grounding-v3-decision-policy-20261029` derivada do PR-03 `bf9ff55`. Sem alteração da `main`, sem criação de release alpha.14.

## Objetivo

Combinar a decisão NLI anterior, o pré-gate de Answerability, a checagem de entidade, o Fact Validator tipado e a verificação do atributo solicitado para que uma resposta incorreta ou insuficiente **não seja apresentada nem enviada ao Piper em modo seguro**.

A política V3 **não eleva NLI `UNCERTAIN` ou `UNSUPPORTED` para `ALLOW`**, mesmo diante de correspondência numérica ou lexical. Os thresholds congelados permanecem inalterados.

## Componentes e contratos

- `grounding_v3.py`: `GroundingV3Decision`, `V3Disposition` (`allow`, `abstain`, `clarify`) e `V3Reason`; decisões determinísticas e serialização no JSONL, com `enforced` indicando se a decisão foi aplicada à resposta.
- `answer_requirements.py`: detecta **perguntas que solicitam atributos explícitos** (lotação, duração, idade, preço, telefone, vagas e prazo). Impede que uma frase verdadeira sobre o assunto seja confundida com resposta a um número solicitado.
- `fact_extraction.py`: suporte a lotação em pessoas/lugares e faixas etárias `14 a 24 anos`, com comparação tipada e offsets.
- `observation.py`: usa `GroundingV3Decision` depois do pré-gate e da geração; mantém os campos NLI e pré-gate para auditoria. Em `observe`, preserva texto bruto; em `enforce`, aplica a decisão ao `presented_answer`.
- `admin/app.py`: apresenta **decisão final V3**, NLI legado, motivo, fact checks e passagens selecionadas separadamente.
- `live_pipeline_evaluation.py`: registra estado V3 e considera `CLARIFY`/abstenção como recusa adequada, sem depender de regex da mensagem.
- Testes: cláusulas incorretas, prazos úteis versus corridos, fonte expirada, múltiplas durações, NLI alto mas dado divergente, atributo faltante, `observe` sem enforcement, `enforce` com voz apenas da resposta segura.

## Política de precedência

1. **Pré-gate bloqueou** (entidade, unidade, disponibilidade atual, falta de fonte): preservar abstenção, não chamar a LLM em `enforce`.
2. **Geração recusou**: manter abstenção.
3. **Entidade incorreta explícita**: abstenção mesmo que o NLI apoie texto de outro curso.
4. **Atributo solicitado ausente**: abstenção por informação específica não respondida.
5. **Fato tipado incompatível**: abstenção com explicação segura, sem informar o valor gerado.
6. **Fatos ambíguos entre ofertas**: `CLARIFY` e solicitação de unidade/turma, sem inventar dado.
7. **Fonte inválida/insuficiente para valor tipado**: abstenção.
8. **NLI unsupported/uncertain**: abstenção; `value_match` não é autorização positiva.
9. **ALLOW somente quando o NLI pré-existente permite e não há veto identificado**.

Essas regras fazem **fail closed**, mas não resolvem integralmente perguntas sem atributos tipados nem contradições semânticas de linguagem natural. O NLI triclasse segue instrumentado e não tem thresholds de contradição novos calibrados.

## Segurança e privacidade

- A síntese no endpoint `/workbench/speech/{observation_id}` resolve apenas a resposta **apresentada** já registrada, sem aceitar texto arbitrário.
- As comparações de fatos mantêm fonte, `chunk_id` e offsets; referência lexical não prova frase inteira.
- A interface Admin não deve ser exposta na rede, pois não tem autenticação de produção.
- A implementação é offline-first e não adiciona novo modelo pesado, API externa ou dependência de nuvem.

## Qualidade e reprodução

A suíte automatizada da branch tem **273 testes aprovados**; Ruff e Mypy sem erros, com aviso de depreciação conhecido do Starlette. Foram executados regressões de retrieval e answerability sintética e benchmarks completos com Tucano2 e Qwen3.5 em CPU no Arch, no conjunto de 40 perguntas **não revisado por humanos**.

Os resultados completos do benchmark são apresentados na seção seguinte. Mudanças aparentes de cobertura entre execuções não devem ser atribuídas integralmente à política V3 porque a geração local da LLM pode variar de uma execução para outra. Um conjunto cego e um estudo pareado são necessários para estimar efeito causal.

## Resultados de benchmark (gate de desenvolvimento)

Benchmarks reais em CPU no Arch com retrieval, Answerability, geração local, NLI e Grounding V3. Mesmo conjunto de **40 perguntas** da etapa anterior (20 positivas e 20 negativas); rótulos curados com auxílio de IA e usados no próprio desenvolvimento, portanto não independentes.

| Métrica automatizada | Tucano2 1.5B | Qwen3.5 0.8B |
|---|---:|---:|
| Casos / erros técnicos | 40 / 0 | 40 / 0 |
| Falsas permissões em 20 negativos | **0** | **0** |
| Falsos bloqueios em 20 positivos | **8** | **11** |
| Respostas positivas apresentadas com âncoras esperadas | **12** | **8** |
| P50 pipeline textual no Arch | **682 ms** | **259 ms** |
| P95 pipeline textual no Arch | **1278 ms** | **824 ms** |

O Tucano2 manteve os oito falsos bloqueios históricos, mas as respostas podem variar entre execuções. O Qwen registrou 11 contra dez no checkpoint anterior, com regressões e melhorias distintas. A política passou a bloquear respostas semanticamente relacionadas mas incapazes de informar o atributo solicitado, como a lotação máxima de biblioteca. A faixa etária curta de 14 a 24 anos foi reconhecida após nova normalização.

Os resultados por pergunta ficam em knowledge/evaluation/results/grounding-v3-{tucano2,qwen35}-2026-10-29.json. **Nenhum desses números comprova taxa real de alucinação igual a zero.** Não foi testada a voz completa, memória ou temperatura no Dell.

### Riscos remanescentes

- Bloqueios indevidos elevados, incluindo perguntas sobre a Ouvidoria, prazos e detalhes de cursos; é inadequado promover o sistema para atendimento.
- O NLI ainda pode classificar como suportada uma frase verdadeira que não responde a perguntas abstratas sem atributos tipados.
- Não há revisão humana independente e as âncoras textuais não são avaliação semântica completa.
- Não foi criada regra de aprovação acima do NLI nem novo threshold; o Fact Validator atua por veto ou esclarecimento.

## Pendências e próximo gate

- **PR-05:** interface de revisão humana com adjudicação independente de casos sinalizados, anotação de evidência e diagnóstico de falsa aprovação/bloqueio.
- **PR-06:** novo holdout verdadeiramente independente, comparação estatística de políticas, avaliação do custo e regressão de memória/latência.
- **T6 físico:** execução no Dell OptiPlex 7050 Micro, 8 GiB; integração STT/LLM/TTS no monofone e ensaios térmicos.

**Decisão:** PR-04 habilita uma política factual mais conservadora para a bancada experimental. Até aprovação humana independente, o terminal físico permanece **NO-GO**.
