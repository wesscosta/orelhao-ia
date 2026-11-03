# Saúde do Servidor — Orelhão IA (03/11/2026)

## Rotas e acesso

- **Painel:** `GET /system`
- **Dados JSON:** `GET /system/state`
- **Navegação:** `Base | Bancada | Monitor | Máquina` no mesmo Knowledge Admin.

No Dell Ubuntu Server, o Admin permanece vinculado a **127.0.0.1:8765**. Acessar de outro computador usando o **túnel SSH já configurado** e abrir http://127.0.0.1:8765/system. Não publicar a porta 8765 na internet nem expor o JSON via proxy aberto: o Admin experimental ainda não tem autenticação de produção.

## Métricas disponibilizadas

| Indicador | Fonte | Observações |
|---|---|---|
| CPU (%) e carga média | `/proc/stat`, `os.getloadavg()` | Uso calculado a partir de duas leituras; na primeira aparece “—”. Carga média não é porcentagem. |
| Núcleos lógicos | `os.cpu_count()` | Não equivale necessariamente a núcleos físicos. |
| RAM disponível, usada, total, swap | `/proc/meminfo` | RAM usada = total menos MemAvailable; cache recuperável não é classificado como indisponível. |
| Disco do sistema | `os.statvfs('/')` | Apenas partição raiz, não discos removíveis ou volumes adicionais. |
| Temperaturas CPU e SSD | `/sys/class/hwmon` | Apenas sensores `coretemp`, `k10temp`, `zenpower` e `nvme`; rótulo e valor real do kernel. Ausentes mostram “—”. |
| Serviços do gancho e Admin | `systemctl --user is-active` | Apenas indica estado do serviço, não qualidade de áudio nem sucesso do RAG. |
| RSS LLM local e Orelhão Admin | `/proc/<pid>/comm` e `/proc/<pid>/status` | Memória residente agregada por processo permitido; não expõe PID, usuário, argumentos, arquivos de modelo ou caminhos. |
| Tempo de atividade | `/proc/uptime` | Segundos desde o boot. |

A rota não consulta o Whisper, Piper, Qwen nem o sistema de conhecimento. Não recolhe áudio, não grava histórico e não inicia uma segunda sessão de atendimento.

## Desempenho e privacidade

O navegador consulta a API **a cada 5 s** enquanto a aba está visível; o servidor compartilha um cache de **4 s**, evitando trabalho duplicado entre navegadores. Leituras rápidas de `/proc` e `/sys` não exigem processo residente nem dependências externas. Os comandos `systemctl` usam lista de argumentos fixa, sem shell, com limite de 1,5 s. As rotas são **GET somente leitura**, com `Cache-Control: no-store` e `X-Content-Type-Options: nosniff`. Textos no painel são inseridos com `textContent`.

**Medida no Dell (03/11/2026, ambiente ocioso):** coleta fria aproximadamente **20,37 ms**; coleta após expiração do cache **21,69 ms**; hit em cache aproximadamente **0,007 ms**. São medições pontuais, não benchmark sob carga, e não garantem zero impacto na latência. A telemetria não fornece histórico persistente, alertas remotos, temperatura de GPU ausente ou métricas detalhadas por thread do STT.

## Operação e verificação

```bash
# Executado no próprio Orelhão Server
curl -sS http://127.0.0.1:8765/system/state
curl -I http://127.0.0.1:8765/system
systemctl --user status orelhao-workbench-benchmark.service
```

Testes de unidade e integração: `tests/admin/test_system_metrics.py`. Não misturar com `/monitor`, que continua representando a sessão física do monofone e suas latências.
