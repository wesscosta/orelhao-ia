# Knowledge Admin e bancada de conversação — estado experimental

**Atualização: 30/10/2026.** A versão inicial da interface foi entregue na v0.4; a bancada incorporou posteriormente a LLM local, o NLI, o gate de answerability e a reprodução por Piper. Consulte [Estado vigente](current-state.md).

## Diagnósticos Grounding V3 (PR-03)

A bancada exibe comparações de valores explícitos entre a resposta e as fontes primárias recuperadas, com resultado por atributo, proveniência e offsets. Os estados de valor **não modificam** a decisão do NLI nem a fala apresentada. Consulte [Fact Validator PR-03](grounding-v3-pr03-fact-validator-2026-10-29.md).

## Grounding V3 — política de decisão integrada

Em observe, a bancada mostra a resposta da LLM e o diagnóstico V3. Em enforce, o V3 determina a resposta exibida e sintetizada pelo Piper, com estados ALLOW, ABSTAIN ou CLARIFY e motivos no JSONL. NLI incerto/unsupported continua bloqueado mesmo com match numérico. A autenticação do Admin não é de produção; mantenha loopback. [PR-04](grounding-v3-pr04-decision-policy-2026-10-29.md).

**Atualização de fontes e identidade:** o catálogo completo de entidades é carregado na inicialização da bancada. Depois de editar e reindexar cursos, reinicie o processo Admin para atualizar o catálogo, evitando reconhecer nomes com um snapshot antigo.

## Seleção TTS por requisição (30/10/2026)

Escolha Cadu ou Faber no formulário, ou selecione outra voz para ouvir a mesma resposta apresentada. A prévia de voz fala uma saudação fixa: **Eu sou o Lumi**. Os parâmetros de voz são validados contra catálogo fechado, sem aceitar caminhos de arquivo; o endpoint de fala só sintetiza observações registradas. Faber pode ser provisionada pelo script scripts/provision_piper_faber.py. [Relatório técnico](workbench-piper-voices-lumi-2026-10-30.md).

## Requisitos e execução

```bash
pip install -e '.[admin,tts,stt,evidence]'
orelhao knowledge index
# O servidor local de LLM deve estar ativo previamente:
ORELHAO_CONFIG=config/benchmark-tucano2-15b-ptbr.yaml orelhao admin
```

Endereço padrão: `http://127.0.0.1:8765`; testes: `http://127.0.0.1:8765/workbench`.

## Gerenciamento da base

- Criar, editar e excluir documentos Markdown; TXT UTF-8 é convertido para Markdown conforme a interface;
- Fontes em `knowledge/sources` são a verdade editável; `knowledge/index` é reconstruído pelo botão **Reindexar base** ou `orelhao knowledge index`;
- Mostrar status de fontes: novo, alterado, indexado ou ignorado. Documentos de controle e categoria `evaluation` não devem contaminar o índice;
- Fontes temporais exigem URL, data de consulta e, quando relevante, unidade/curso e vigência. Uma página de cursos não comprova vaga atual.

## Bancada

1. Consultar disponibilidade de LLM/STT/TTS, selecionar `observe` ou `enforce`;
2. Digitar pergunta ou gravar fala pelo microfone do navegador; validar a transcrição;
3. Executar a consulta: retrieval, decisão pré-geração, resposta da LLM quando admissível e grounding por NLI;
4. Examinar resposta bruta, resposta apresentada, motivos, `chunk_id`, fontes, scores e latências;
5. Usar **Ouvir resposta** para sintetizar e reproduzir pelo Piper, somente a resposta apresentada. Reprodução automática pode ser bloqueada pelo navegador;
6. Registrar avaliação humana quando disponível, sem sobrescrever observações.

O modo `observe` é **somente diagnóstico**: pode exibir texto sem suporte. No modo `enforce`, falta de evidência bloqueia e apresenta mensagem segura. Isso não elimina erros do NLI nem transforma o terminal em solução homologada.

## Segurança e retenção

O Admin **não possui autenticação de produção** e deve escutar exclusivamente em loopback; nunca expor publicamente. Os logs JSONL em `knowledge/observations/` registram perguntas e respostas e são ignorados pelo Git. Definir retenção, acesso, exclusão e base legal antes de uso real com visitantes.

## Histórico

O Admin inicial (`v0.4.0-alpha.3/.4`) fornecia CRUD, importação de fontes e reindexação. A v0.6-alpha.12 incorporou observação; a alpha.13 incorporou LLM. A evolução posterior na branch de pesquisa acrescentou `enforce`, TTS restaurado, pré-gate e bloqueio por entidade. Os números de versões anteriores são **marcos históricos**, não o estado do código atual.
