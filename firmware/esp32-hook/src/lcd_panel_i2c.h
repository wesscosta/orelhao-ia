#pragma once

// LCD 16x2 + backpack PCF8574. SDA=GPIO21, SCL=GPIO22.
// Never put 5V on ESP32 GPIOs: use a bidirectional I2C level shifter
// when the backpack is powered at 5V.
#include <Arduino.h>
#include <Wire.h>
#include <hd44780.h>
#include <hd44780ioClass/hd44780_I2Cexp.h>
#include <cstring>

namespace lcd_panel {
namespace {
constexpr int kColumns = 16;
constexpr int kRows = 2;
constexpr uint32_t kRetryMs = 10000;
hd44780_I2Cexp lcd;  // Auto-detecta endereco e mapeamento do backpack.
bool ready = false;
uint32_t lastAttempt = 0;
char input[96] = {};
size_t length = 0;
bool discarding = false;

void writeRow(uint8_t row, const char* text) {
  if (!ready) return;
  char buffer[kColumns + 1];
  size_t i = 0;
  while (i < kColumns && text[i] != '\0') {
    const unsigned char c = static_cast<unsigned char>(text[i]);
    buffer[i] = (c >= 32 && c <= 126) ? static_cast<char>(c) : ' ';
    ++i;
  }
  while (i < kColumns) buffer[i++] = ' ';
  buffer[kColumns] = '\0';
  lcd.setCursor(0, row);
  lcd.print(buffer);
}

void show(const char* first, const char* second) {
  writeRow(0, first);
  writeRow(1, second);
}

void state(const char* name) {
  if (strcmp(name, "READY") == 0) {
    show("LUMI - SENAC", "RETIRE O FONE");
  } else if (strcmp(name, "LISTENING") == 0) {
    show("LUMI - SENAC", "ESCUTANDO...");
  } else if (strcmp(name, "PROCESSING") == 0) {
    show("LUMI - SENAC", "PROCESSANDO...");
  } else if (strcmp(name, "SPEAKING") == 0) {
    show("LUMI - SENAC", "RESPONDENDO...");
  } else if (strcmp(name, "PAUSED") == 0) {
    show("LUMI - SENAC", "AGUARDANDO...");
  } else if (strcmp(name, "ERROR") == 0) {
    show("LUMI - SENAC", "INDISPONIVEL");
  }
}

void handle(char* message) {
  constexpr char kState[] = "LCD:STATE:";
  constexpr char kText[] = "LCD:TEXT:";
  if (strncmp(message, kState, sizeof(kState) - 1) == 0) {
    state(message + sizeof(kState) - 1);
  } else if (strncmp(message, kText, sizeof(kText) - 1) == 0) {
    char* first = message + sizeof(kText) - 1;
    char* separator = strchr(first, '|');
    if (separator == nullptr) return;
    *separator = '\0';
    show(first, separator + 1);
  }
}
}  // namespace

inline void begin() {
  Wire.begin(21, 22);
  Wire.setClock(100000);
  lastAttempt = millis();
  int status = lcd.begin(kColumns, kRows);
  ready = (status == 0);
  if (ready) {
    lcd.backlight();
    state("READY");
  }
  // Fail-open for hook: missing LCD must not block hook detection.
}

inline void poll() {
  if (!ready && millis() - lastAttempt >= kRetryMs) {
    lastAttempt = millis();
    int status = lcd.begin(kColumns, kRows);
    ready = (status == 0);
    if (ready) {
      lcd.backlight();
      state("READY");
    }
  }
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\n') {
      if (!discarding && length > 0) {
        input[length] = '\0';
        if (ready) handle(input);
      }
      length = 0;
      discarding = false;
    } else if (c != '\r' && !discarding) {
      if (length < sizeof(input) - 1) {
        input[length++] = c;
      } else {
        discarding = true;
      }
    }
  }
}
}  // namespace lcd_panel
