# Gancho ESP32: integração experimental

**Fase:** observação física. Não inicia conversas automaticamente.

## Ligação
- O ESP32 DevKit ESP32-D0WD-V3 comunica por USB CP2102 com o Ubuntu.
- Contato seco do gancho entre **GPIO 27** e **GND**.
- Sem fonte externa: **não ligar linha telefônica, 5 V ou tensão desconhecida** ao GPIO.
- Com `INPUT_PULLUP`, contato **aberto = HIGH**, **fechado = LOW**.
- A relação entre contato aberto/fechado e *monofone retirado* deve ser confirmada fisicamente.

## Protocolo
Firmware em `firmware/esp32-hook`, PlatformIO Arduino, serial 115200.
JSON Lines: `{"protocol":"orelhao.hook.v1","kind":"change","gpio":27,"contact":"closed","seq":2,"uptime_ms":900}`.
`kind=state` é enviado no boot e periodicamente (5 segundos); `kind=change` após 70 ms de estabilidade.

## Testes
Compilação: `pio run -d firmware/esp32-hook`.
Gravação: `pio run -d firmware/esp32-hook -t upload --upload-port /dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0`.
Monitor do Ubuntu (não inicia sessão de IA):
`python -m orelhao.hardware.serial_hook` (com o venv e pyserial instalados).
Mover o gancho e comparar `contact` em ambas as posições, antes de configurar
`--off-hook-contact open` ou `--off-hook-contact closed`.

Por segurança, o monitor não deve ser executado simultaneamente com a gravação.
A desconexão serial retorna o sensor para estado seguro e não inicia captura.
