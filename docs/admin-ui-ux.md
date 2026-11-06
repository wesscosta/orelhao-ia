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

## Acesso local (commit `a3288ef`)

`/overview`, `/monitor`, `/monitor/state`, `/monitor/events`, `/system` e `/system/state`
respondem 403 se o cliente **e** o cabeçalho `Host` não forem loopback (`127.0.0.1`,
`localhost`, `::1`), o que também bloqueia *DNS rebinding*. `/audit*` usa a mesma
verificação mais Basic Auth. Respostas privadas levam `no-store`, `nosniff`,
`X-Frame-Options: DENY` e `Referrer-Policy: no-referrer`. A visão geral envia
`X-Requested-With: fetch` ao consultar a auditoria para receber 401 sem o diálogo Basic do
navegador e mostrar "Indicadores restritos ao administrador".

Consequência para operação: o túnel SSH deve ser acessado como `http://127.0.0.1:8765` ou
`http://localhost:8765`; outro nome de host retorna 403. `/`, `/edit`, `/workbench` e
`/reindex` mantêm o comportamento anterior (sem essa verificação), como antes desta branch.

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
| Zoom de 200% | Não verificado | Coberto indiretamente pelo reflow em 768 px; não testado com zoom real |
| Leitor de tela | Não verificado | Semântica conferida no código e em testes; sem NVDA/Orca |
| Contraste medido com ferramenta | Não verificado | Valores escolhidos para ≥ 4,5:1, sem medição automatizada registrada |
| Ligação física real no monitor | Não verificado | Somente eventos sintéticos |

| Aviso de alterações não salvas | Verificado | `beforeunload` bloqueia com texto alterado e libera após envio |
| Página vem do bfcache após envio | Não verificado em navegador | Botões em envio são reabilitados em `pageshow` (código) |

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

## Testes e CI

- `tests/admin/test_admin_ui.py` e `tests/admin/test_admin_access.py`.
- Testes do perfil do servidor usam `tests/fixtures/orelhao-server.profile.yaml`, sem
  depender do arquivo privado `config/*.local.yaml` (agora no `.gitignore`).
- **GitHub Actions está desabilitado no repositório**: o push não executa CI. Os passos do
  workflow foram reproduzidos localmente (Ruff, Mypy no escopo do CI, Pytest).

Testes automatizados: `tests/admin/test_admin_ui.py` (shell, navegação nas cinco áreas,
rótulos de formulário, ausência de CDN, erros HTML/JSON, FAQ e áudio).

## Pendências para homologação no Dell

1. Confirmar que `static/` está presente na instalação (editável ou `package-data`).
2. Acessar pelo túnel usando `127.0.0.1` ou `localhost` (outros nomes de host retornam 403).
3. Abrir todas as páginas pelo túnel SSH e conferir autenticação da auditoria.
4. Validar o monitor durante uma ligação real, incluindo o sinal da captura.
5. Testar zoom de 200% e um leitor de tela.
6. Decidir se `/overview` passa a ser a página inicial.
