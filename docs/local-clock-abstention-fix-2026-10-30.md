# Correção de data/hora e repetição do marcador de abstenção

**30/10/2026 — branch experimental `fix/local-clock-and-abstention-20261030`.** Implementação derivada do Workbench Cadu/Faber. Não altera a `main` nem constitui release/homologação do terminal físico.

## Defeito reproduzido

Na pergunta **“Que dia é hoje?”** em modo `observe`, o pipeline encaminhava a consulta ao RAG, recuperava chunks sobre cursos/vagas e enviava à LLM. O Tucano2 devolvia muitas repetições de `INSUFFICIENT CONTEXT`, com espaços, e às vezes uma última palavra `INSUFFICIENT` truncada. O normalizador anterior só reconhecia `INSUFFICIENT_CONTEXT` com underscore. O texto foi então exibido e enviado à síntese. O problema foi confirmado no arquivo JSONL da bancada e em captura da interface.

## Correções

1. **Serviço determinístico `local_clock.py`:** reconhece apenas perguntas estritamente sobre a data/hora do relógio, individualmente ou combinadas. Usa `datetime.now(ZoneInfo(...))` e fuso `ORELHAO_TIMEZONE` (padrão `America/Fortaleza`). A resposta inclui dia da semana e data por extenso, ou horas e minutos em pt-BR. Não chama retrieval, pré-gate, LLM ou NLI; economiza processamento e não depende de fontes RAG.
2. **Proveniência honesta:** `answer_origin=local_clock`; o JSONL contém `local_clock.kind`, fuso e timestamp ISO com offset. A decisão V3 permite o resultado com razão explícita `local_clock`. O NLI legado é marcado `not_applicable` e seus scores são serializados como `null`; não há score de entailment fabricado. A interface mostra **Resposta operacional** e **NLI não executado**.
3. **Proteção de escopo:** a intenção é reconhecida por padrões completos, não por encontrar a palavra `hoje` na pergunta. Perguntas como **“Há vagas disponíveis hoje?”**, **“Qual o horário de atendimento?”** e **“Que dia é hoje e há vagas?”** seguem no RAG e no Grounding V3. Não se usa o relógio para concluir disponibilidade institucional atual.
4. **Abstenção normalizada:** a rotina reconhece `INSUFFICIENT_CONTEXT`, `INSUFFICIENT CONTEXT`, repetições e a terminação truncada `INSUFFICIENT` quando a mensagem contém **somente** o marcador. Não substitui respostas mistas com informações factuais. O `LocalLLMAnswerGenerator` também aplica normalização defensiva ao receber o texto do backend.
5. **Áudio legado:** `ObservationLog.presented_answer_for` identifica marcadores repetidos já salvos e devolve uma abstenção em português para a síntese. O log original é mantido; não foi alterado retroativamente.

## Qualidade

- **327 testes Pytest aprovados**, 1 warning preexistente de Starlette; Ruff e Mypy aprovados nos módulos Knowledge/LLM.
- Testes determinísticos incluem 11 formas positivas, mais de 12 negativas e transição de dia pelo fuso, mais regressões de sentinel com e sem underscore.
- Testes de integração garantem que o relógio não aciona retriever, gerador ou verificador e que a resposta permanece acessível ao TTS em `observe` e `enforce`.
- **Smoke HTTP real**, porta experimental 8771 com Tucano2: `Que dia é hoje?`, `Que horas são agora?`, perguntas combinadas, todos HTTP 200, `grounding_v3.reason=local_clock`, `grounding.status=not_applicable`, `score=null`, sem fonte RAG; áudio Piper Faber HTTP 200, WAV PCM16 22.050 Hz, 3,59 segundos para a data.

## Execução

```bash
cd ~/Develop/orelhao-ia
ORELHAO_TIMEZONE=America/Fortaleza \
ORELHAO_CONFIG=config/benchmark-tucano2-15b-ptbr.yaml \
.venv/bin/orelhao admin --host 127.0.0.1 --port 8765
```

Após reiniciar a bancada, abra `http://127.0.0.1:8765/workbench`. Pergunte **“Que dia é hoje?”** ou **“Que horas são agora?”** e selecione Cadu/Faber para reproduzir o resultado.

**Limites:** a exatidão depende da data/hora correta do sistema operacional, de NTP e da configuração de fuso do terminal. O projeto não usa GPS para data/hora. A funcionalidade está integrada à **bancada textual/voz de testes**; o loop físico autônomo ainda carece de integração completa, homologação do Dell 8 GB e revisão humana do restante do Grounding.
