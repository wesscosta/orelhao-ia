# Auditoria de atendimentos, reconhecimento de voz e backups

**Status:** implementacao de codigo validada no notebook (04/11/2026).
Ainda nao implantada no Orelhao Server: a maquina estava offline.
Os historicos anteriores ao recurso nao podem ser reconstruidos a partir
do backup de codigo: o monitor antigo eliminava a sessao quando encerrada.

## Finalidade

- Saber quantos atendimentos aconteceram, os assuntos mais perguntados
  e os motivos recorrentes de ausencia de resposta.
- Diagnosticar entrada de audio (silencio, ruido, overflows),
  transcricoes vazias ou suspeitas do Whisper e latencias de STT.
- Separar falhas de captacao, STT, consulta RAG, resposta e TTS.
- Exportar CSV e baixar backups preexistentes por rota protegida.

## Arquitetura e dados

O `live_monitor.publish` gera eventos usados pelo monitor ao vivo; a
auditoria consome o mesmo fluxo, sem repetir gravacao, STT ou inferencia.
O `start_session` e `finish_session` contam sessoes e encerramentos.

Persistencia local SQLite com WAL:
`~/.local/state/orelhao-ia/audit.sqlite3`.
Pasta e arquivo sao privados (700 e 600). Nao vai ao Git.
Registros: data/hora UTC, id aleatorio de sessao, turno, etapa,
status, motivo, rota de resposta, assunto, pergunta canonica,
tempos, nivel de ruido, RMS, overflow e deteccao de fala.

**Por padrao, NAO grava texto bruto da transcricao, resposta, nem audio.**
Os assuntos e perguntas canonicas sao gerados por palavras-chave
predefinidas (heuristica, nao classificacao semantica confiavel).
Perguntas canonicas sem dados pessoais aparecem no ranking por padrao.

Frases reconhecidas podem ser habilitadas com
`ORELHAO_AUDIT_QUESTION_LABELS=1`, mas isso **nao equivale a
anonimizacao garantida**. O filtro apenas bloqueia padroes conhecidos
como CPF, e-mail, telefone e marcadores de dados pessoais. Manter
desabilitado para publico sem requisitos adequados de privacidade,
transparencia, base legal e processo de revisao.

Nao ha como medir WER/CER ou a taxa de reconhecimento *correto* apenas
com logs: precisaria transcricao humana de referencia. Silencio/ruido
nao deve ser interpretado automaticamente como defeito do Whisper.

## Habilitacao no servidor

1. Implantar o codigo e instalar dependencias do Admin.
2. Para o processo do gancho, configurar no systemd (usuario `lumi`):
   `ORELHAO_AUDIT_ENABLED=1`
   e `ORELHAO_AUDIT_RETENTION_DAYS=30`.
3. Configurar a senha **apenas no servico do Admin**:
   `ORELHAO_AUDIT_PASSWORD` com ao menos 16 caracteres, guardada
   em EnvironmentFile fora do Git (arquivo `chmod 600`).
   Nao reutilizar senha, nao inserir em query strings ou no Git.
4. O Admin deve continuar escutando em **127.0.0.1:8765**.
   Acessar de outro computador pelo tunel SSH autorizado:
   `ssh -L 8765:127.0.0.1:8765 lumi@ENDERECO_AUTORIZADO`
5. Abrir `http://127.0.0.1:8765/audit` e autenticar com usuario
   **admin** e a senha configurada. HTTPS/SSH e obrigatorio
   quando a conexao nao for apenas local.

Envio opcional de frases redigidas:
`ORELHAO_AUDIT_QUESTION_LABELS=1` apenas no processo de voz.
Sem `ORELHAO_AUDIT_ENABLED=1`, o modulo nao grava eventos.
Uma senha nao configurada resulta em HTTP 503, nunca acesso anonimo.
Qualquer tentativa fora de loopback retorna HTTP 403.

## Rotas

| Rota | Acao |
| --- | --- |
| `GET /audit` | Painel de auditoria (7/30/90 dias) e backups |
| `GET /audit/summary?days=30` | Indicadores JSON por periodo |
| `GET /audit/events.csv?days=30` | Exportacao de eventos sem textos brutos |
| `GET /audit/backups` | Lista arquivos existentes com nomes permitidos |
| `GET /audit/backups/{filename}` | Baixa arquivo preexistente selecionado |

Backups sao apenas **listados e baixados**, jamais criados na requisicao
HTTP. A origem padrao e `~/backups/orelhao-ia/`, ou a variavel
`ORELHAO_BACKUP_DIR`. Symlinks, nomes nao permitidos e caminhos
fora do diretorio sao rejeitados. Os arquivos podem conter configuracoes
sensíveis e devem permanecer restritos ao administrador.

## Retencao, desempenho e limitacoes

Os registros sao limitados a 30 dias (1-365 configuraveis) nas consultas
e descartados da base quando novos eventos chegam. Sem eventos novos,
o arquivo antigo pode persistir ate a proxima operacao de manutencao.
Nao fazer backup persistente de dados pessoais sem politica de retencao.
Cada evento realiza uma pequena escrita SQLite no fluxo da chamada:
time-out de 80 ms e, em falha, a auditoria e ignorada. A chamada de voz
nao deve falhar por indisponibilidade do banco. Revalidar latencia no Dell.

O codigo nao faz fine-tuning e nao altera os dados RAG automaticamente.
Um fluxo seguro de melhoria: inspecionar os assuntos frequentes,
conferir falhas por audio/STT/RAG, revisar as perguntas e fontes oficiais,
atualizar a base de conhecimento e executar novamente os testes.

## Testes

`tests/admin/test_audit_routes.py`: registros, categorias, consentimento
opt-in, sigilo dos textos brutos, CSV, autenticacao e download seguro.
Os testes usam banco temporario isolado e nao leem logs reais.
