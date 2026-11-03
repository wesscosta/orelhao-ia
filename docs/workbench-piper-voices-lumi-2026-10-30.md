# Workbench — seleção de Piper Cadu/Faber e identidade “o Lumi”

**Data:** 30/10/2026. **Estado:** implementação experimental na branch `feat/workbench-piper-voices-lumi-20261030`; não é release nem homologação do terminal físico.

## O problema

A comparação auditiva de 24 gravações (8 vozes/configurações × 3 textos) resultou em preferência individual por **Piper Faber (10/15)** sobre **Piper Cadu original (9/15)**. As vozes Kokoro receberam 3/15 cada, de modo que não há evidências para integrá-las como padrão agora. Foi apontada ainda a referência indevida **“a Lumi”** em vez da identidade masculina **“o Lumi”**.

## Mudanças implementadas

- Novo `WorkbenchPiperVoices`: catálogo fechado `cadu` e `faber`, criação preguiçosa das instâncias Piper e caminhos de modelos fixos. Nenhuma entrada HTTP pode determinar um caminho de arquivo. A troca de seleção é por requisição, sem estado global e sem reiniciar servidores.
- No formulário `/workbench`: seletor de voz + botão **Ouvir apresentação do Lumi**. `/workbench/voice-preview?voice=faber` sintetiza **apenas texto fixo**, não texto arbitrário enviado pelo navegador.
- No resultado da pergunta: seletor independente que permite ouvir **a mesma resposta apresentada** com Cadu ou Faber, sem executar retrieval/LLM/NLI novamente. `/workbench/speech/{observation_id}?voice=faber` continua validando a observação contra JSONL e jamais sintetiza texto livre fornecido pelo navegador.
- `/workbench/tts-status?voice=faber` consulta a disponibilidade do modelo escolhido. Se Faber não estiver provisionado, a operação informa indisponibilidade/falha; não há troca silenciosa de voz.
- A geração recebe instrução explícita de identidade masculina. `normalize_lumi_identity` corrige artigos como `a Lumi` → `o Lumi`, `da Lumi` → `do Lumi` e `à Lumi` → `ao Lumi` **antes** da checagem de Grounding. O campo `LLMCompletion.raw_text` mantém o retorno bruto na conclusão da LLM. **O JSONL da bancada não persiste esse campo**; a correção não modifica evidências ou corpus.
- Modelo Faber localmente provisionado em `models/tts/pt_BR-faber-medium.onnx` e `.onnx.json`, mantidos fora do Git conforme `.gitignore`.

## Como provisionar Faber em outra instalação

```bash
cd /caminho/orelhao-ia
source .venv/bin/activate
python scripts/provision_piper_faber.py
```

Requer `huggingface-hub` do conjunto de dependências de TTS. A rede é necessária apenas para baixar os pesos; o Piper opera localmente depois disso. Cadu permanece no caminho `models/tts/pt_BR-cadu-medium.onnx`.

## Como executar e testar

```bash
ORELHAO_CONFIG=config/benchmark-tucano2-15b-ptbr.yaml \
  .venv/bin/orelhao admin --host 127.0.0.1 --port 8765
```

1. Abra `http://127.0.0.1:8765/workbench`.
2. Selecione **Faber** e clique em **Ouvir apresentação do Lumi**.
3. Digite uma pergunta, escolha `enforce` e execute.
4. No resultado, selecione **Cadu** e ouça; mude para **Faber** e ouça novamente, sem repetir a consulta.
5. Confirme a identidade masculina na saudação de áudio e no texto apresentado quando a LLM se identificar.

O laboratório auditivo independente permanece em `http://127.0.0.1:8766` no computador Arch, quando o servidor local estiver ativo.

## Smoke test HTTP com os dois modelos locais

Validação real em 30/10/2026 no Arch com a instância experimental na porta 8770:

| Cenário | Resultado |
|---|---|
| Workbench e seletor | HTTP 200, ambos disponíveis pelo endpoint de status |
| Apresentação masculina, Cadu | HTTP 200, WAV PCM16 mono 22.050 Hz, 4,80 s |
| Apresentação masculina, Faber | HTTP 200, WAV PCM16 mono 22.050 Hz, 3,48 s |
| Voz não autorizada / caminho arbitrário | HTTP 422, sem leitura de arquivo solicitado |
| Pergunta real sobre faixa etária Senac Aprendiz | HTTP 200, Grounding V3 allow/supported, 14 a 24 anos |
| Mesma resposta por Cadu | HTTP 200, 5,62 s de áudio |
| Mesma resposta por Faber | HTTP 200, 4,45 s de áudio |
| Registros de observação para ambas as falas | Apenas **um**: a seleção de TTS não aciona nova geração |

Os áudios são distintos por hash SHA-256 e possuem amostras WAV válidas. O teste confirma integração, **não** superioridade de naturalidade nem funcionamento acústico no monofone. O conjunto continua restrito ao computador Arch.

## Limites e segurança

- O seletor atua **na bancada administrativa**, não no loop de voz físico/autônomo da appliance.
- O modo `enforce` preserva a decisão do Grounding V3: sintetiza somente `presented_answer`. O modo `observe` pode mostrar respostas sem evidência.
- O Admin não possui autenticação de produção; a porta deve permanecer em loopback.
- O benchmark perceptivo é de um avaliador, não homologação coletiva; os dois modelos continuam sujeitos a testes de pronúncia e conforto ao longo de diálogos.
- O modelo Faber e as WAVs do laboratório são arquivos locais, não versionados. Licença da Faber: CC0 conforme card obtido com o modelo.
- A identidade `o Lumi` é um contrato de apresentação, não nova fonte factual nem mudança de instruções do RAG.

## Verificações

A validação automatizada inclui testes de alternância para a mesma observação, isolamento entre seleções, bloqueio de caminhos arbitrários, prévia de frase fixa, identidade masculina e preservação do `raw_text`. As métricas automatizadas são **285 testes aprovados**, Ruff e Mypy sem erros nos módulos validados, além do smoke test acima. Para reproduzir: `pytest -q` e utilizar o Workbench com o código atualizado.

**Estado de produção:** NO-GO até revisão humana, benchmark independente e teste no Dell 8 GiB.
