# LCD original do orelhao — bancada ESP32 (03/11/2026)

## Status e escolha

A partir desta etapa, o **LCD original do orelhao** e o candidato para a
montagem. LCD alternativo 1602 fica como contingencia. As fotografias
mostram 16 posicoes marcadas na sequencia **16, 15, 1, 2, ... 14**;
posicoes 15 e 16 em cabo separado vermelho/preto e posicoes 1 a 14
em conector de 14 vias. Isto **nao confirma** controlador, tensao,
numero de linhas ou presenca de limitador para backlight.
Nao foi encontrado datasheet conclusivo para a etiqueta fotografada.

### Validacoes eletricas antes de conectar ou gravar firmware

1. Desenergizar conjunto e verificar continuidade do chicote: mapear
   fisicamente 1..14 e o par 15/16, sem confiar apenas na cor.
2. Confirmar que o LED+, LED- estao de fato em 15/16 e se existe
   resistor limitador para backlight. Nao energizar esses dois
   contatos na primeira tentativa.
3. Confirmar VSS(1), VDD(2), VO(3), RS(4), RW(5), E(6),
   D0..D7(7..14), **somente se** a placa seguir HD44780 ou compativel.
4. Confirmar tensao da logica com documentacao ou medicao na placa
   original. **Nao presumir 5 V nem 3,3 V sem essa confirmacao**.
5. Se VDD = 5 V, usar **74HCT245 alimentado a 5 V** para elevar sinais
   do ESP32 3,3 V, com direcao A->B e /OE no GND.
   Ligar RW do LCD a GND para impedir dados de 5 V voltarem ao ESP32.
   As terras do ESP32, LCD, buffer e fonte devem ser comuns.
6. Contraste: potenciometro 10k, extremidades em VDD/GND,
   cursor em VO. Backlight desconectado na primeira inicializacao.
7. Testar fonte regulada com polaridade e corrente monitoradas e
   gabinete/placa isolados, sem conexao com linha telefonica.

### Plano de ligacao presumindo pinagem HD44780, modo 4 bits

| LCD original | Funcao | Ligacao apos verificacoes |
|---|---|---|
| 1 | VSS | GND |
| 2 | VDD | fonte nominal confirmada |
| 3 | VO | cursor potenciometro 10k |
| 4 | RS | GPIO16 (via buffer se necessario) |
| 5 | RW | GND |
| 6 | E | GPIO17 (via buffer se necessario) |
| 7..10 | D0..D3 | nao usar |
| 11 | D4 | GPIO18 (via buffer se necessario) |
| 12 | D5 | GPIO19 (via buffer se necessario) |
| 13 | D6 | GPIO21 (via buffer se necessario) |
| 14 | D7 | GPIO22 (via buffer se necessario) |
| 15 | A / LED+ provavel | nao ligar inicialmente |
| 16 | K / LED- provavel | nao ligar inicialmente |
| gancho | contato seco | GPIO27 - GND, INALTERADO |

### Firmware nao gravado

A variante `esp32dev-lcd-original` define temporariamente 16 colunas
por **1 linha**, porque ainda nao se confirmou a geometria interna;
`esp32dev-lcd` e para 16 colunas por 2 linhas. Se o display for de
16x1 dividido em duas metades (DDRAC 0x00/0x40), pode ser necessario
configurar tratamento especial de enderecamento.

```bash
cd /home/lumi/apps/orelhao-ia
/home/lumi/.local/share/orelhao-esp32-tools/bin/pio run -d firmware/esp32-hook -e esp32dev-lcd-original
```

**Nao gravar antes de montar e conferir tensao/pinagem e isolamento.**
Com o firmware novo, a serial USB permanece gerando
`orelhao.hook.v1` para o programa de voz e recebe opcionalmente
`LCD:STATE:READY\n`, `LCD:STATE:LISTENING\n`, etc. A conexao
serial e de propriedade do `orelhao-hook-voice.service`: a futura
integracao de estados deve partir dele, sem segundo monitor serial.
