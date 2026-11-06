# FAQ supervisionado e amostras de voz (MVP experimental)

Escopo: notebook/branch de desenvolvimento. **Não homologado nem implantado no Dell.**

## Objetivo e limites

O Orelhão aprende quais assuntos geram dúvidas, **não aprende respostas diretamente
do público**. A fila do FAQ deriva exclusivamente de eventos de auditoria: turno
com transcrição reconhecida e resposta final em abstenção por falta de evidência.
Falhas de captura/STT são contabilizadas separadamente; não viram respostas sugeridas.

A auditoria existente salva tema, rótulo canônico aproximado, métricas e motivo.
Não salva texto integral. Rótulos canônicos podem agregar perguntas diferentes
da mesma categoria. O supervisor deve escrever a pergunta exata e revisar
evidências, abrangência, unidade, prazo e URL oficial antes de publicar.

## Configuração (local, não expor à rede)

- `ORELHAO_AUDIT_ENABLED=1`: habilita métricas anônimas e candidatos ao FAQ.
- `ORELHAO_AUDIT_PASSWORD=<segredo-com-16+-caracteres>`: autenticação Basic
  do painel administrativo local. Use túnel SSH ao invés de abrir a porta.
- `ORELHAO_AUDIT_DB`: SQLite em `~/.local/state/orelhao-ia/audit.sqlite3`
  por padrão, com permissões 0600 e diretório privado.
- `ORELHAO_AUDIO_DIAGNOSTICS_ENABLED=1`: permite **apenas** que o gestor
  arme o diagnóstico, não ativa captura automática.
- `ORELHAO_AUDIO_DIAGNOSTICS_DIR`: diretório protegido opcional de WAV.
- `ORELHAO_AUDIO_RETENTION_DAYS`: 7 por padrão, máximo 14. A exclusão é
  executada ao listar amostras ou capturar novas; inclua limpeza diária
  agendada na operação para assegurar exclusão dentro do prazo.

Não copie credenciais, gravações nem banco SQLite para o GitHub.

## Fluxo de FAQ

1. Acesse `/audit/faq` após habilitar auditoria e ocorrerem abstenções reais.
2. O painel agrupa candidatos por rótulo canônico + tema.
3. O supervisor informa pergunta específica, resposta verificada e URL HTTPS
   de fonte institucional, salvando rascunho (sem indexar).
4. O supervisor confirma a revisão e clica **Publicar na base e reindexar**.
5. O aplicativo cria `knowledge/sources/faq/aprovados/faq-<id>.md`,
   constrói novo índice em staging e promove-o se a indexação terminar.
   Em falha durante a indexação, exclui a fonte candidata e preserva o índice anterior.
6. Uma FAQ publicada fica imutável nesta primeira versão. Ajustes posteriores
   seguem fluxo editorial e versionamento de fontes, não sobrescrita silenciosa.

A revisão humana deve verificar conteúdo e validade: a ferramenta valida somente
a presença e o formato HTTPS da URL, **não** verifica se o conteúdo é verdadeiro.
Uma sessão de voz já em andamento pode continuar usando o índice em memória.

## Fluxo de diagnóstico

**Informação e autorização aplicável ao visitante são pré-requisitos.**
O padrão é não coletar áudio. O gestor acessa `/audit/audio`, confirma que o
visitante foi informado e autorizou a gravação para diagnóstico, e arma a
próxima sessão por até 5 minutos. Quando o supervisor inicia essa sessão,
a autorização é consumida e não serve para sessões seguintes.

- São armazenadas até duas amostras WAV PCM16 mono (0,2 a 30 s) por sessão;
- não se registra transcrição integral, resposta do modelo ou identidade;
- o vínculo interno usa identificador de sessão aleatório;
- arquivos individuais 0600; pasta 0700; download autenticado e local;
- visualização via `/audit/audio`; remoção por retenção, sob demanda;
- ao desligar o monofone, encerra-se a autorização restante;
- nenhuma falha de armazenamento bloqueia o atendimento por voz.

O áudio pode conter dados pessoais pela própria natureza da voz. Para operar em
ambiente público, formalizar com o responsável institucional: finalidade, base
legal, avisos, autorização, retenção com limpeza diária, controle de acesso e
procedimento de exclusão. Não habilitar a flag até esses controles estarem
aprovados e testados no local. Dados agregados são suficientes fora do piloto.

## Critérios de homologação antes do Dell

- Testes automatizados em notebook sem alterar a operação atual.
- Abrir admin por túnel; verificar 401/403, acesso local e senhas adequadas.
- Reproduzir amostras autorizadas e comparar com a transcrição STT em monitor
  efêmero durante o teste, sem persistir a transcrição por padrão.
- Validar latência, RMS/pico, VAD e transcrição com monofone P3 físico.
- Verificar atualização/rollback do índice e queries em voz na versão do servidor.
- Agendar expurgo diário de gravações; conferir política institucional.
- Promover branch para o deployment só depois de testes no Dell e backup.

## Comandos de testes locais

```sh
PYTHONPATH=src python -m pytest -q tests/admin/test_learning_feedback.py tests/admin/test_audit_routes.py tests/unit/test_voice_worker.py
python -m ruff check src/orelhao/hardware src/orelhao/admin
```
