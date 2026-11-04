# LCD I2C 16x2 com backpack PCF8574 no Orelhao IA

**Hardware fotografado:** modulo LCD alfanumerico com backpack preto "MH",
CI aparentemente PCF8574T, trimpot azul, LEDs POWER,
conector de quatro pinos e **dois pinos extras marcados LED**.

## Pinagem do conector de quatro vias

A serigrafia fotografada e `SCL | SDA | VCC | GND`
(na orientacao do verso usada nas fotos).

| Backpack | ESP32 DevKit V1 | Observacao |
|---|---|---|
| SCL | GPIO18 (D18) | via adaptador de nivel I2C, se alimentado 5 V |
| SDA | GPIO4 (D4) | via adaptador de nivel I2C, se alimentado 5 V |
| VCC | 5 V regulados/VIN medido | verificar especificacao e tensao real antes |
| GND | GND | terra comum |
| LED (2 pinos separados) | **nao ligar ao ESP32** | conector para jumper de habilitacao backlight |
| Gancho | GPIO27/GND | manter como esta |

**GPIO4:** verificar reinicializacao e modo de boot com o LCD conectado;
se surgir incompatibilidade, escolher GPIO comum alternativo, como GPIO19,
e ajustar o firmware. Nao confundir pino GPIO4 do ESP32 com o pino 4 do LCD paralelo.

**Seguranca eletrica:** os GPIOs do ESP32 nao toleram 5 V.
Backpacks comuns usam resistores pull-up I2C a VCC=5 V.
Se o LCD operar a 5 V, usar conversor de nivel bidirecional
I2C BSS138 com HV=5 V, LV=3V3 e GND comum.
A fotografia do LED POWER aceso nao confirma tensao segura,
enderecamento I2C nem funcionalidade do LCD. Nao energizar
com pinagem/polaridade desconhecida.

O par de pinos salientes ao lado de **LED** e tipicamente o
header de jumper da iluminacao: curto-circuitar os dois com
jumper apropriado habilita o backlight; nao e um conector
de dados ou entrada independente de alimentacao.

## Firmware e protocolo

Firmware: `firmware/esp32-hook/src/lcd_panel_i2c.h`
ativado pela variante `esp32dev-lcd-i2c`. O `esp32dev`
padrao preserva somente o gancho. A biblioteca hd44780_I2Cexp
faz a descoberta do endereco I2C e do mapeamento do backpack;
nao se deve assumir um endereco apenas por ser comum.

A biblioteca `hd44780_I2Cexp` detecta o endereco e tenta
identificar automaticamente o mapeamento do PCF8574. Ainda
pode haver backpacks incompativeis ou defeitos fisicos.

Comandos aceitos no USB serial (115200):
```text
LCD:STATE:READY
LCD:STATE:LISTENING
LCD:STATE:PROCESSING
LCD:STATE:SPEAKING
LCD:STATE:PAUSED
LCD:STATE:ERROR
LCD:TEXT:LUMI - SENAC|BEM-VINDO!
```

A rotina do gancho continua emitindo JSON Lines `orelhao.hook.v1`.
O supervisor serial transmite estados e paginas de resposta pela
mesma porta do gancho, sem abrir segunda conexao serial.
O bridge `src/orelhao/hardware/lcd_status.py` usa somente os
resultados apresentados ao usuario pelo fluxo validado (RAG/grounding).
A exibicao de respostas exige habilitacao explicita para evitar
exposicao involuntaria em uma tela publica. Perguntas transcritas
nao sao exibidas por padrao.

Variaveis de ambiente do servico:
- `ORELHAO_LCD_I2C_ENABLED=1`: ativa atualizacao de estados.
- `ORELHAO_LCD_SHOW_ANSWERS=1`: exibe o texto da resposta, com
  paginacao de 16x2 caracteres a cada 2,3 segundos.

Caracteres acentuados sao transliterados para ASCII; comandos de
controle sao neutralizados. Apenas os primeiros 480 caracteres
da resposta sao mostrados, com `...` quando truncada. O buffer
de paginas fica somente em memoria, e e apagado ao encerrar a
sessao. Nao ha persistencia adicional de transcricoes nesse recurso.
O firmware do ESP32 continua sendo o mesmo: a paginacao ocorre no host.

## Etapas de verificacao (ainda nao executadas fisicamente)

1. Confirmar VCC e polaridade com multimetro e validar conversor de nivel.
2. Com o hardware pronto, executar primeiro apenas a compilacao:
   `/home/lumi/.local/share/orelhao-esp32-tools/bin/pio run -d firmware/esp32-hook -e esp32dev-lcd-i2c`
3. Em janela controlada, interromper `orelhao-hook-voice.service`,
   gravar `esp32dev-lcd-i2c` e reativar o servico. Firmware
   do gancho permanece como fallback `esp32dev`.
4. Confirmar endereco `lcd=ready` no log de serial e a mensagem
   `LUMI - SENAC / RETIRE O FONE` no LCD. Se `lcd=not_found`:
   desligar e revisar SDA/SCL, tensao e adaptador de nivel.
5. Ajustar trimpot azul de contraste, conferir jumper de
   backlight, validar OFF_HOOK/ON_HOOK por 30+ ciclos.
6. Somente apos esse gate, habilitar a variavel de ambiente
   no servico de voz para refletir os estados em tempo real.
7. Nao deixar dois clientes simultaneos em /dev/ttyUSB0.

**Estado deste registro:** variante I2C gravada no ESP32 e
comunicacao basica confirmada visualmente; integracao das respostas
foi testada automaticamente no host. A validacao eletrica da
interface 3V3/5V continua necessaria, independentemente da tela
funcionar.
