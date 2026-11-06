# Interface administrativa — decisões de UI/UX (06/11/2026)

Refatoração incremental da interface web do Orelhão IA (Lumi) na branch
`feat/admin-ui-ux-20261106`. O backend FastAPI, as rotas, as políticas de grounding,
a revisão humana do FAQ e a autorização da gravação diagnóstica não mudaram.
**Experimental, sem homologação no Dell.**

## Público e tarefas principais

| Público | Tarefa principal | Critério de sucesso |
|---|---|---|
| Gestor/supervisor | Saber se o Orelhão está atendendo e o que precisa de atenção | Visão geral responde em uma tela, com links para agir |
| Operador | Acompanhar uma ligação em tempo real | Ver em que etapa o turno está sem ler logs |
| Curador do conhecimento | Transformar perguntas sem resposta em FAQ revisado | Revisar, salvar e publicar sem perder texto em caso de erro |
| Técnico | Investigar falhas de microfone e da máquina | Comparar pico, ruído e limiar do VAD por amostra |

## Navegação

Menu lateral no desktop e menu recolhível no celular (botão "Menu", `Esc` fecha).
Todas as rotas anteriores foram preservadas; a única rota nova é `/overview`.

| Área | Página | Rota |
|---|---|---|
| Visão geral | Central de operações | `/overview` (nova) |
| Atendimento ao vivo | Monitor da ligação | `/monitor` |
| Conhecimento | Fontes e índice | `/` (inalterada, incluindo `/edit`, `/delete`, `/reindex`) |
| Conhecimento | FAQ supervisionado | `/audit/faq` |
| Conhecimento | Bancada de testes | `/workbench` |
| Diagnóstico | Áudio e microfone | `/audit/audio` |
| Diagnóstico | Máquina | `/system` |
| Administração | Auditoria e backups | `/audit` |

`/` continua sendo a página de fontes para não quebrar links e redirecionamentos
existentes. Tornar `/overview` a página inicial é uma decisão de homologação.

## Arquitetura do frontend

- **Renderização no servidor em Python**, sem Jinja2: o pacote não está instalado no
  ambiente e adicioná-lo seria uma dependência nova no Dell. Todo texto variável passa
  por `html.escape` (`ui.e`).
- `ui.py`: shell (`render_page`), navegação e componentes (`badge`, `alert`, `panel`,
  `stat`, `empty_state`, `icon`).
- Views por área: `overview_view.py`, `live_view.py`, `knowledge_view.py`,
  `workbench_view.py`, `learning_view.py` (FAQ e áudio), `system_view.py`, `audit_view.py`.
- `static/` servido em `/static`, sem CDN:
  - `css/tokens.css`, `css/layout.css`, `css/components.css`
  - `js/shell.js` (menu, foco no erro, estado de envio) e um script por tela
  - `icons.svg` (sprite local) e `fonts/` (Atkinson Hyperlegible, SIL OFL 1.1, `OFL.txt`)
- `ASSET_VERSION` é um hash do conteúdo de `static/`, então CSS/JS novos não ficam presos
  em cache após atualização.
- O JavaScript saiu das strings Python. Nenhum script usa `innerHTML` com dados de
  eventos; o monitor continua inserindo falas com `textContent`.
- SPA/React foram descartados: não há estado de cliente que justifique.

## Design system

- **Cor:** azul institucional como referência ao Senac Piauí (sem afirmar conformidade
  com manual de marca, que não foi consultado) e laranja do orelhão reservado ao estado
  "ligação ativa". Estados ok/aviso/erro/info com fundo suave e texto ≥ 4,5:1.
- **Modo escuro** automático por `prefers-color-scheme`; `data-theme="light"` força o claro.
- **Tipografia:** Atkinson Hyperlegible, criada para legibilidade; escala 1,2 a partir de 16 px.
- **Estados nunca dependem só da cor:** todo badge tem texto e marcador de forma distinta
  (círculo, losango, quadrado).
- **Movimento:** só no nó ativo do fluxo da ligação e no indicador de envio; tudo é
  desligado com `prefers-reduced-motion`.

## Telas

- **Central de operações:** monofone (SSE existente), LLM (`/workbench/llm-status`, uma
  consulta), índice (servidor), serviços e disco (`/system/state` a cada 30 s com a aba
  visível), alertas derivados desses dados e indicadores de 7 dias (`/audit/summary`,
  restrito ao administrador). Sem métricas simuladas; fonte indisponível aparece como
  "Indeterminado" ou mensagem explícita.
- **Monitor:** fluxo Escuta → STT → RAG → Grounding → LLM → TTS → Reprodução derivado
  somente dos eventos publicados pelo worker. RAG, Grounding e LLM chegam em um único
  evento (`voice.response` com `rag_ms`) e a tela diz isso. Rotas guiadas, avisos e relógio
  local aparecem como "Não executado". Abstenção aparece como aviso, não como falha.
  "Sinal da última captura" mostra pico RMS, piso de ruído e limiar do VAD do evento
  `voice.capture`; não é forma de onda.
- **FAQ supervisionado:** tabela de pendências (pergunta agrupada e assunto, frequência,
  estado da revisão, última ocorrência, ação) e painel de revisão com as três etapas.
  Erros de validação reapresentam o formulário com o texto digitado e levam o foco à
  mensagem. Falha de reindexação é capturada e informa que rascunho e índice anterior
  foram preservados. Publicação continua exigindo rascunho salvo e confirmação explícita.
- **Áudio e microfone:** estado da coleta (desligada por padrão), autorização da próxima
  sessão, indicadores agregados de 7 dias e amostras com barra pico/ruído/limiar e player
  restrito ao administrador. Nada foi adicionado à captura.
- **Alterações não salvas:** editor de fontes e formulário do FAQ avisam antes de sair da
  página; o aviso é desligado no envio.
- **Erros de navegação:** pedidos com `Accept: text/html` recebem página de erro legível;
  `fetch` e clientes de API continuam recebendo JSON `{"detail": ...}`.

## Acesso local (commits `a3288ef` e `df9566d`)

**Todo o Admin** (visão geral, monitor, máquina, fontes, edição, reindexação, bancada e
auditoria) responde 403 se o cliente **e** o cabeçalho `Host` não forem loopback
(`127.0.0.1`, `localhost`, `::1`). A regra é uma dependência global do FastAPI
(`orelhao/admin/access.py`), o que cobre rotas futuras e bloqueia:

- acesso remoto se o Admin for iniciado por engano com `--host 0.0.0.0`;
- *DNS rebinding* (um site externo resolvendo para 127.0.0.1 e lendo, pelo navegador do
  operador, transcrições ao vivo ou reescrevendo fontes).

`/audit*` mantém, além disso, Basic Auth. `/openapi.json` não é publicado. `/static` não
contém dados. Respostas de monitoramento e visão geral levam `no-store`, `nosniff`,
`X-Frame-Options: DENY` e `Referrer-Policy: no-referrer`. A visão geral envia
`X-Requested-With: fetch` ao consultar a auditoria para receber 401 sem o diálogo Basic do
navegador e mostrar "Indicadores restritos ao administrador".

A exceção do `TestClient` (cliente `testclient`, Host `testserver`) existe só em
`tests/admin/conftest.py`; `tests/admin/test_admin_access.py` usa a regra real
(marcador `real_access`).

Verificação no servidor de demonstração: `curl -H 'Host: evil.example'
http://127.0.0.1:8766/edit/x.md` → 403; o mesmo pedido a `/monitor/state` no commit
`2757f86` (antes) → 200 com o estado da ligação.

Consequência para operação: o túnel SSH deve ser acessado como `http://127.0.0.1:8765` ou
`http://localhost:8765`; outro nome de host (inclusive um proxy reverso) retorna 403.

## Verificação

Ambiente: Chrome no notebook Arch, servidor local com dados sintéticos isolados.

| Critério | Resultado | Evidência |
|---|---|---|
| Reflow 320/375/768 px, todas as páginas | Verificado | `scrollWidth ≤ innerWidth` em iframes de largura fixa; tabelas rolam no próprio contêiner |
| Defeito de reflow no FAQ em 320/375 px | Falhou, depois corrigido | `.visually-hidden` absoluto escapava da tabela; `.table-wrap { position: relative }` |
| Navegação por teclado e link "Pular para o conteúdo" | Verificado | Tab → link visível → Enter → foco no primeiro link do conteúdo |
| Foco visível | Verificado | `box-shadow` de foco medido no elemento ativo |
| Fluxo FAQ por teclado (erro → correção → rascunho → publicação) | Verificado | Texto preservado, `aria-invalid`, foco no alerta, mensagens de sucesso |
| Player de amostra autorizada | Verificado | `readyState 4`, duração correta |
| Modo claro e escuro | Verificado (visual) | Capturas em 375 px claro e 1440 px escuro |
| Erros de console | Verificado | Nenhum erro nas páginas visitadas |
| Zoom de 200% | Verificado (emulado) | Viewport de 720 px CSS com fator de escala 2 (equivalente a 1440 px em 200%); sem rolagem horizontal da página; a coluna de ação do FAQ rola dentro da tabela (região focável) |
| Leitor de tela | Não verificado | Semântica conferida no código e em testes; sem NVDA/Orca |
| Contraste medido com ferramenta | Não verificado | Valores escolhidos para ≥ 4,5:1, sem medição automatizada registrada |
| Ligação física real no monitor | Não verificado | Somente eventos sintéticos |

| Aviso de alterações não salvas | Verificado | `beforeunload` bloqueia com texto alterado e libera após envio |
| Erro de envio → "Voltar e corrigir" por teclado | Verificado | Foco no alerta → Tab → Enter; o formulário volta com o valor digitado e o botão reabilitado ("Salvar alterações") |
| Erros de JavaScript | Verificado | Nenhum `error`/`unhandledrejection` nas 8 páginas (HEAD) |

Uma checagem parcial não estabelece conformidade WCAG 2.2 AA.

### Auditoria Web Interface Guidelines (Vercel)

Regras obtidas de `vercel-labs/web-interface-guidelines` (`command.md`) em 06/11/2026.

| Achado | Severidade | Situação |
|---|---|---|
| Formulários longos sem aviso de alterações não salvas | Alta (perda de dados) | Corrigido |
| Barra superior fixa no celular podia cobrir o elemento focado | Média | Corrigido (`scroll-padding-top`) |
| Ausência de `meta theme-color` | Baixa | Corrigido |
| Marca sem `translate="no"` | Baixa | Corrigido |
| Controles sem `touch-action: manipulation` | Baixa | Corrigido |
| Campos do FAQ sem `autocomplete="off"` | Baixa | Corrigido |
| `innerHTML` (texto estático) em `audio.js` | Baixa | Corrigido |
| Barras de uso animam `width`, não `transform` | Baixa | Mantido: uma transição curta a cada 5 s, desligada com movimento reduzido |
| Datas do servidor formatadas com `strftime` em vez de `Intl` | Baixa | Mantido: renderização no servidor, formato pt-BR fixo com fuso UTC explícito |
| Placeholders sem "…" | Baixa | Não se aplica: placeholders são exemplos literais (`faq.md`, `https://`) |
| Title Case em títulos e botões | — | Não se aplica: português usa caixa de frase |
| Amostras de áudio sem transcrição | — | Não se aplica: transcrições não são retidas por política de privacidade |

### Reflow antes/depois (matriz automatizada)

Páginas `/overview`, `/`, `/monitor`, `/system`, `/workbench`, `/audit`, `/audit/faq`,
`/audit/audio` e `/edit/…` em 320, 375, 720, 768 e 1440 px (`scrollWidth ≤ innerWidth`).

| Commit | Resultado |
|---|---|
| `2757f86` (antes) | `/workbench` 320 px (363 > 320); `/audit/faq` 320 e 375 px (676 px) |
| HEAD (depois) | Nenhuma rolagem horizontal da página em nenhuma combinação |

### Capturas

Geradas com Chrome headless e dados sintéticos isolados, em `docs/admin-ui-ux/`:
`before-*.png` (commit `2757f86`) e `after-*.png` (HEAD) para FAQ 320/375 px,
bancada 320 px, monitor 375 px, visão geral 768/1440 px e FAQ em zoom de 200%.

### Code review (`/code-review`, base `6c92e07`)

| Achado | Severidade | Situação |
|---|---|---|
| Rotas de fontes/edição/reindexação/bancada sem restrição local | Alta | Corrigido (dependência global) |
| Botões em envio presos após voltar do bfcache | Alta | Corrigido (`pageshow`) |
| Monitor marcava RAG/LLM como executados em respostas de esclarecimento | Média | Corrigido |
| Aviso de índice desatualizado dizia "0 fonte(s)" após exclusão | Média | Corrigido |
| Consulta de status do STT parava após uma falha de rede | Média | Corrigido (recuo) |
| `stopRecording` podia rodar duas vezes durante o auto-stop | Média | Corrigido |
| Visão geral contava serviço iniciando/desconhecido como fora do ar | Baixa | Corrigido |
| Troca rápida de período na auditoria podia mostrar dados antigos | Baixa | Corrigido (`AbortController`) |
| Exceção do `TestClient` no código de produção | Baixa | Corrigido (só nos testes) |
| Lista de vozes fixa na bancada; código morto | Baixa | Corrigido |

`/verify` não está disponível neste ambiente.

## Testes e CI

- `tests/admin/test_admin_ui.py` e `tests/admin/test_admin_access.py`.
- Testes do perfil do servidor usam `tests/fixtures/orelhao-server.profile.yaml`, sem
  depender do arquivo privado `config/*.local.yaml` (agora no `.gitignore`).
- **GitHub Actions está desabilitado no repositório**: o push não executa CI. Os passos do
  workflow foram reproduzidos localmente em venv limpo com `.[dev,admin,vad,tts,semantic]`
  e sem o perfil privado: Ruff (escopo do CI) sem erros, Mypy (escopo do CI) sem erros,
  Pytest **556 aprovados**. Python local 3.14; o workflow fixa 3.12.
- Mypy em `src` inteiro: 62 → 52 erros, nenhum novo; os restantes são anteriores.

Testes automatizados: `tests/admin/test_admin_ui.py` (shell, navegação nas cinco áreas,
rótulos de formulário, ausência de CDN, erros HTML/JSON, FAQ e áudio).

## Pendências para homologação no Dell

1. Confirmar que `static/` está presente na instalação (editável ou `package-data`).
2. Acessar pelo túnel usando `127.0.0.1` ou `localhost` (outros nomes de host, inclusive
   proxy reverso, retornam 403 em todo o Admin).
3. Abrir todas as páginas pelo túnel SSH e conferir autenticação da auditoria.
4. Validar o monitor durante uma ligação real, incluindo o sinal da captura.
5. Testar zoom real de 200% no navegador do operador e um leitor de tela.
6. Decidir se `/overview` passa a ser a página inicial.
