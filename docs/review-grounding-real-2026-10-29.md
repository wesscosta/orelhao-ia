# Fila de adjudicação humana — Orelhão IA

29/10/2026. NÃO revisado por humanos; rótulos provisórios criados com auxílio de IA.

**15 dos 40 casos** sinalizados por pelo menos um modelo. Revisar também os casos com aprovação automática, pois o avaliador lexical pode não detectar uma resposta falsa.

| ID | Pergunta | Esperado | Tucano2 | Qwen | Julgamento humano |
|---|---|---|---|---|---|
| P01 | Qual é a missão oficial do Senac? | Responder: educar, trabalho | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | O Senac é uma empresa que contrata jovens de 14 a 24 anos para atuarem como jovens aprendiz, alternando atividades entre educação básica, no Senac e na empresa. | PENDENTE |
| P04 | Qual é o limite de renda por pessoa para o PSG? | Responder: dois, salarios | O limite de renda por pessoa para o Programa Senac de Gratuidade (PSG) é de dois salários mínimos federais. | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | PENDENTE |
| P08 | Qual é o prazo padrão para resposta da Ouvidoria? | Responder: 15, dias | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | O prazo padrão para resposta da Ouvidoria é de até 15 dias úteis. | PENDENTE |
| P09 | Qual plataforma de biblioteca virtual é mencionada pelo Senac Piauí? | Responder: cachola | A plataforma de biblioteca virtual mencionada pelo Senac Piauí é a Cachola. | A biblioteca virtual mencionada pelo Senac Piauí é a biblioteca virtual especializada do Senac, com e-books, materiais didáticos, vídeos, artigos e outros recursos. | PENDENTE |
| P10 | Em quais três cidades há bibliotecas físicas segundo a página consultada? | Responder: teresina, parnaiba, picos | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | Teresina, Parnaíba e Picos. | PENDENTE |
| P11 | Qual carga horária estava informada para Excel na consulta de outubro de 2026? | Responder: 30, horas | A carga horária informada para o curso Excel na consulta de outubro de 2026 era de 30 horas . | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | PENDENTE |
| P12 | Quantas horas tem o Excel Avançado segundo a página de referência? | Responder: 60, horas | Segundo a página de referência, o curso Excel Avançado possui 60 horas . | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | PENDENTE |
| P13 | A partir de qual idade é possível acessar o Excel Avançado? | Responder: 14 | Não encontrei essa informação na minha base no momento. | Não encontrei essa informação na minha base no momento. | PENDENTE |
| P14 | Qual idade mínima foi informada para Informática Básica? | Responder: 12 | A idade mínima informada para o curso de Informática Básica era de 12 anos ou mais . | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | PENDENTE |
| P15 | Qual o telefone geral da Administração Regional do Senac PI? | Responder: 3228, 9500 | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | PENDENTE |
| P16 | Quantas entradas de unidades apareciam na seção de unidades do portal? | Responder: 13 | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | 13 entradas de unidades apareciam na seção de unidades do portal. | PENDENTE |
| P17 | Quantas vagas foram previstas na publicação do edital 006/2026 do PSG? | Responder: 437 | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | PENDENTE |
| P18 | Qual quantitativo estava previsto no edital 007/2026 do PSG? | Responder: 25 | O quantitativo previsto no edital 007/2026 do PSG era de 25 vagas. | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | PENDENTE |
| P19 | Em qual data foi firmado o Programa Senac de Gratuidade? | Responder: 22, julho, 2008 | O Programa Senac de Gratuidade foi firmado em 22 de julho de 2008. | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | PENDENTE |
| P20 | O Banco de Oportunidades é um serviço gratuito? | Responder: gratuito | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | Não encontrei evidências suficientes na base de conhecimento para responder com segurança. | PENDENTE |

## Revisão caso a caso

### P01: missao

Pergunta: Qual é a missão oficial do Senac?

Fonte esperada: institucional/missao-visao-valores.md
URL: https://www.pi.senac.br/institucional/sobresenac

**Tucano2** — resposta bruta: A missão oficial do Senac é ampliar o acesso à educação profissional para pessoas de baixa renda.

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.3795)
Fontes recuperadas: aprendizagem/jovem-aprendiz.md, cursos/agenda-e-unidades.md, psg/programa-senac-gratuidade.md, unidades/rede-senac-piaui.md

**Qwen3.5** — resposta bruta: O Senac é uma empresa que contrata jovens de 14 a 24 anos para atuarem como jovens aprendiz, alternando atividades entre educação básica, no Senac e na empresa.

Resposta apresentada: O Senac é uma empresa que contrata jovens de 14 a 24 anos para atuarem como jovens aprendiz, alternando atividades entre educação básica, no Senac e na empresa.
NLI: supported (0.9719)
Fontes recuperadas: aprendizagem/jovem-aprendiz.md, cursos/agenda-e-unidades.md, psg/programa-senac-gratuidade.md, unidades/rede-senac-piaui.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P04: programa

Pergunta: Qual é o limite de renda por pessoa para o PSG?

Fonte esperada: psg/programa-senac-gratuidade.md
URL: https://psg.pi.senac.br/

**Tucano2** — resposta bruta: O limite de renda por pessoa para o Programa Senac de Gratuidade (PSG) é de dois salários mínimos federais.

Resposta apresentada: O limite de renda por pessoa para o Programa Senac de Gratuidade (PSG) é de dois salários mínimos federais.
NLI: supported (0.8427)
Fontes recuperadas: psg/programa-senac-gratuidade.md, aprendizagem/jovem-aprendiz.md

**Qwen3.5** — resposta bruta: O limite de renda por pessoa para o PSG é dois salários mínimos federais.

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.4768)
Fontes recuperadas: psg/programa-senac-gratuidade.md, aprendizagem/jovem-aprendiz.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P08: ouvidoria

Pergunta: Qual é o prazo padrão para resposta da Ouvidoria?

Fonte esperada: atendimento/ouvidoria.md
URL: https://www.pi.senac.br/

**Tucano2** — resposta bruta: O prazo padrão para resposta da Ouvidoria é de até 15 dias úteis, prorrogável por mais 15 dias mediante justificativa.

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.7266)
Fontes recuperadas: atendimento/ouvidoria.md

**Qwen3.5** — resposta bruta: O prazo padrão para resposta da Ouvidoria é de até 15 dias úteis.

Resposta apresentada: O prazo padrão para resposta da Ouvidoria é de até 15 dias úteis.
NLI: supported (0.834)
Fontes recuperadas: atendimento/ouvidoria.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P09: biblioteca

Pergunta: Qual plataforma de biblioteca virtual é mencionada pelo Senac Piauí?

Fonte esperada: biblioteca/bibliotecas-e-cachola.md
URL: https://www.pi.senac.br/

**Tucano2** — resposta bruta: A plataforma de biblioteca virtual mencionada pelo Senac Piauí é a Cachola.

Resposta apresentada: A plataforma de biblioteca virtual mencionada pelo Senac Piauí é a Cachola.
NLI: supported (0.9912)
Fontes recuperadas: biblioteca/bibliotecas-e-cachola.md, biblioteca/bibliotecas-e-cachola.md, empregabilidade/banco-de-oportunidades.md

**Qwen3.5** — resposta bruta: A biblioteca virtual mencionada pelo Senac Piauí é a biblioteca virtual especializada do Senac, com e-books, materiais didáticos, vídeos, artigos e outros recursos.

Resposta apresentada: A biblioteca virtual mencionada pelo Senac Piauí é a biblioteca virtual especializada do Senac, com e-books, materiais didáticos, vídeos, artigos e outros recursos.
NLI: supported (0.9922)
Fontes recuperadas: biblioteca/bibliotecas-e-cachola.md, biblioteca/bibliotecas-e-cachola.md, empregabilidade/banco-de-oportunidades.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P10: biblioteca

Pergunta: Em quais três cidades há bibliotecas físicas segundo a página consultada?

Fonte esperada: biblioteca/bibliotecas-e-cachola.md
URL: https://www.pi.senac.br/

**Tucano2** — resposta bruta: De acordo com a página consultada, as três cidades que possuem bibliotecas físicas são: 1. Teresina Centro 2. Parnaíba 3.

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.2158)
Fontes recuperadas: biblioteca/bibliotecas-e-cachola.md

**Qwen3.5** — resposta bruta: Teresina, Parnaíba e Picos.

Resposta apresentada: Teresina, Parnaíba e Picos.
NLI: supported (0.9031)
Fontes recuperadas: biblioteca/bibliotecas-e-cachola.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P11: curso

Pergunta: Qual carga horária estava informada para Excel na consulta de outubro de 2026?

Fonte esperada: cursos/excel-2026.md
URL: https://pi.senac.br/tecnologia-da-informacao-ti/excel

**Tucano2** — resposta bruta: A carga horária informada para o curso Excel na consulta de outubro de 2026 era de 30 horas .

Resposta apresentada: A carga horária informada para o curso Excel na consulta de outubro de 2026 era de 30 horas .
NLI: supported (0.9619)
Fontes recuperadas: cursos/excel-avancado-2026.md, cursos/excel-2026.md, cursos/informatica-basica-2026.md, unidades/rede-senac-piaui.md

**Qwen3.5** — resposta bruta: 30 horas

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.3238)
Fontes recuperadas: cursos/excel-avancado-2026.md, cursos/excel-2026.md, cursos/informatica-basica-2026.md, unidades/rede-senac-piaui.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P12: curso

Pergunta: Quantas horas tem o Excel Avançado segundo a página de referência?

Fonte esperada: cursos/excel-avancado-2026.md
URL: https://pi.senac.br/tecnologia-da-informacao-ti/excel-avancado

**Tucano2** — resposta bruta: Segundo a página de referência, o curso Excel Avançado possui 60 horas .

Resposta apresentada: Segundo a página de referência, o curso Excel Avançado possui 60 horas .
NLI: supported (0.958)
Fontes recuperadas: cursos/excel-avancado-2026.md, cursos/excel-2026.md

**Qwen3.5** — resposta bruta: 60 horas

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.4369)
Fontes recuperadas: cursos/excel-avancado-2026.md, cursos/excel-2026.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P13: curso

Pergunta: A partir de qual idade é possível acessar o Excel Avançado?

Fonte esperada: cursos/excel-avancado-2026.md
URL: https://pi.senac.br/tecnologia-da-informacao-ti/excel-avancado

**Tucano2** — resposta bruta: Não encontrei essa informação na minha base no momento.

Resposta apresentada: Não encontrei essa informação na minha base no momento.
NLI: unsupported (0.0)
Fontes recuperadas:

**Qwen3.5** — resposta bruta: Não encontrei essa informação na minha base no momento.

Resposta apresentada: Não encontrei essa informação na minha base no momento.
NLI: unsupported (0.0)
Fontes recuperadas:

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P14: curso

Pergunta: Qual idade mínima foi informada para Informática Básica?

Fonte esperada: cursos/informatica-basica-2026.md
URL: https://pi.senac.br/tecnologia-da-informacao-ti/informatica-basica

**Tucano2** — resposta bruta: A idade mínima informada para o curso de Informática Básica era de 12 anos ou mais .

Resposta apresentada: A idade mínima informada para o curso de Informática Básica era de 12 anos ou mais .
NLI: supported (0.8142)
Fontes recuperadas: cursos/informatica-basica-2026.md

**Qwen3.5** — resposta bruta: 12 anos ou mais

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.6805)
Fontes recuperadas: cursos/informatica-basica-2026.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P15: contato

Pergunta: Qual o telefone geral da Administração Regional do Senac PI?

Fonte esperada: atendimento/canais-institucionais.md
URL: https://www.pi.senac.br/contato

**Tucano2** — resposta bruta: O telefone geral da Administração Regional do Senac PI é (86) 3228-9500.

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.517)
Fontes recuperadas: atendimento/canais-institucionais.md, unidades/rede-senac-piaui.md, unidades/rede-senac-piaui.md, institucional/sobre-o-senac-piaui.md

**Qwen3.5** — resposta bruta: O telefone geral da Administração Regional do Senac PI é (86) 3228-9500.

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.517)
Fontes recuperadas: atendimento/canais-institucionais.md, unidades/rede-senac-piaui.md, unidades/rede-senac-piaui.md, institucional/sobre-o-senac-piaui.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P16: unidades

Pergunta: Quantas entradas de unidades apareciam na seção de unidades do portal?

Fonte esperada: unidades/rede-senac-piaui.md
URL: https://www.pi.senac.br/

**Tucano2** — resposta bruta: A seção "Conheça Nossas Unidades" do portal oficial do Senac Piauí em 29 de outubro de 2026 apresentava 13 entradas , distribuídas em 10 municípios .

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.3678)
Fontes recuperadas: unidades/rede-senac-piaui.md, unidades/rede-senac-piaui.md, cursos/agenda-e-unidades.md

**Qwen3.5** — resposta bruta: 13 entradas de unidades apareciam na seção de unidades do portal.

Resposta apresentada: 13 entradas de unidades apareciam na seção de unidades do portal.
NLI: supported (0.9777)
Fontes recuperadas: unidades/rede-senac-piaui.md, unidades/rede-senac-piaui.md, cursos/agenda-e-unidades.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P17: psg_historico

Pergunta: Quantas vagas foram previstas na publicação do edital 006/2026 do PSG?

Fonte esperada: psg/vagas-e-editais.md
URL: https://psg.pi.senac.br/vagas/

**Tucano2** — resposta bruta: O edital do Programa Senac de Gratuidade nº 006/2026 — PSG apresentava um quantitativo de 437 vagas previstas na publicação.

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.311)
Fontes recuperadas: psg/vagas-e-editais.md, psg/vagas-e-editais.md, psg/vagas-e-editais.md

**Qwen3.5** — resposta bruta: O edital 006/2026 do PSG prevê 437 vagas previstas na publicação.

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.3564)
Fontes recuperadas: psg/vagas-e-editais.md, psg/vagas-e-editais.md, psg/vagas-e-editais.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P18: psg_historico

Pergunta: Qual quantitativo estava previsto no edital 007/2026 do PSG?

Fonte esperada: psg/vagas-e-editais.md
URL: https://psg.pi.senac.br/vagas/

**Tucano2** — resposta bruta: O quantitativo previsto no edital 007/2026 do PSG era de 25 vagas.

Resposta apresentada: O quantitativo previsto no edital 007/2026 do PSG era de 25 vagas.
NLI: supported (0.7609)
Fontes recuperadas: psg/vagas-e-editais.md, psg/vagas-e-editais.md

**Qwen3.5** — resposta bruta: O edital 007/2026 do PSG apresentava 25 vagas previstas na publicação.

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.5124)
Fontes recuperadas: psg/vagas-e-editais.md, psg/vagas-e-editais.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P19: programa

Pergunta: Em qual data foi firmado o Programa Senac de Gratuidade?

Fonte esperada: psg/programa-senac-gratuidade.md
URL: https://psg.pi.senac.br/

**Tucano2** — resposta bruta: O Programa Senac de Gratuidade foi firmado em 22 de julho de 2008.

Resposta apresentada: O Programa Senac de Gratuidade foi firmado em 22 de julho de 2008.
NLI: supported (0.8262)
Fontes recuperadas: psg/programa-senac-gratuidade.md, psg/vagas-e-editais.md, aprendizagem/jovem-aprendiz.md, institucional/sobre-o-senac-piaui.md

**Qwen3.5** — resposta bruta: 22 de julho de 2008

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.5891)
Fontes recuperadas: psg/programa-senac-gratuidade.md, psg/vagas-e-editais.md, aprendizagem/jovem-aprendiz.md, institucional/sobre-o-senac-piaui.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

### P20: empregabilidade

Pergunta: O Banco de Oportunidades é um serviço gratuito?

Fonte esperada: empregabilidade/banco-de-oportunidades.md
URL: https://www.pi.senac.br/

**Tucano2** — resposta bruta: O Banco de Oportunidades é um serviço gratuito.

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.6344)
Fontes recuperadas: empregabilidade/banco-de-oportunidades.md, institucional/sobre-o-senac-piaui.md, institucional/sobre-o-senac-piaui.md

**Qwen3.5** — resposta bruta: Sim, o serviço gratuito é o Banco de Oportunidades.

Resposta apresentada: Não encontrei evidências suficientes na base de conhecimento para responder com segurança.
NLI: uncertain (0.4724)
Fontes recuperadas: empregabilidade/banco-de-oportunidades.md, institucional/sobre-o-senac-piaui.md, institucional/sobre-o-senac-piaui.md

- [ ] Conferir fonte, unidade, curso, período e eventual valor
- [ ] Classificar cada resposta: correta, parcial, incorreta, abstenção adequada ou indevida
- [ ] Registrar avaliador, data, justificativa e URL/página da evidência

## Itens sem alerta automático (revisar amostra)

P02, P03, P05, P06, P07, N01, N02, N03, N04, N05, N06, N07, N08, N09, N10, N11, N12, N13, N14, N15, N16, N17, N18, N19, N20
