#pragma once

#include <Arduino.h>
#include <LiquidCrystal.h>

#include <cstring>

#ifndef ORELHAO_LCD_ROWS
#define ORELHAO_LCD_ROWS 2
#endif
#if ORELHAO_LCD_ROWS != 1 && ORELHAO_LCD_ROWS != 2
#error "LCD: only 1 or 2 character rows supported"
#endif

// LCD paralelo opcional, no modo 4 bits.
// HABILITAR somente apos confirmar pinagem, tensao e interface 3V3->5V.
// Pinos do ESP32: RS=16, E=17, D4=18, D5=19, D6=21, D7=22.
// GPIO27 permanece exclusivamente reservado ao gancho.
namespace lcd_panel {
namespace {
LiquidCrystal lcd(16, 17, 18, 19, 21, 22);
char input[96] = {};
size_t length = 0;
bool discarding = false;

void writeRow(uint8_t row, const char* text) {
  char buffer[17];
  size_t i = 0;
  while (text[i] != '\0' && i < 16) {
    const unsigned char c = static_cast<unsigned char>(text[i]);
    buffer[i] = (c >= 32 && c <= 126) ? static_cast<char>(c) : ' ';
    ++i;
  }
  while (i < 16) {
    buffer[i++] = ' ';
  }
  buffer[16] = '\0';
  lcd.setCursor(0, row);
  lcd.print(buffer);
}

void show(const char* first, const char* second) {
  writeRow(0, first);
#if ORELHAO_LCD_ROWS == 2
  writeRow(1, second);
#else
  (void)second;
#endif
}

void state(const char* name) {
#if ORELHAO_LCD_ROWS == 1
  if (strcmp(name, "READY") == 0) { show("LUMI - SENAC", ""); }
  else if (strcmp(name, "LISTENING") == 0) { show("ESCUTANDO...", ""); }
  else if (strcmp(name, "PROCESSING") == 0) { show("PROCESSANDO...", ""); }
  else if (strcmp(name, "SPEAKING") == 0) { show("RESPONDENDO...", ""); }
  else if (strcmp(name, "PAUSED") == 0) { show("AGUARDANDO...", ""); }
  else if (strcmp(name, "ERROR") == 0) { show("INDISPONIVEL", ""); }
#else
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
#endif
}

void handle(char* message) {
  constexpr char kState[] = "LCD:STATE:";
  constexpr char kText[] = "LCD:TEXT:";
  if (strncmp(message, kState, sizeof(kState) - 1) == 0) {
    state(message + sizeof(kState) - 1);
    return;
  }
  if (strncmp(message, kText, sizeof(kText) - 1) == 0) {
    char* first = message + sizeof(kText) - 1;
    char* separator = strchr(first, '|');
    if (separator == nullptr) return;
    *separator = '\0';
    show(first, separator + 1);
  }
}
}  // namespace

inline void begin() {
  lcd.begin(16, ORELHAO_LCD_ROWS);
  state("READY");
}

// Recebe comandos completos sem bloquear o loop do gancho.
inline void poll() {
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\n') {
      if (!discarding && length != 0) {
        input[length] = '\0';
        handle(input);
      }
      length = 0;
      discarding = false;
    } else if (c != '\r' && !discarding) {
      if (length < sizeof(input) - 1) {
        input[length++] = c;
      } else {
        discarding = true;  // Ignora a linha inteira se exceder 95 bytes.
      }
    }
  }
}
}  // namespace lcd_panel
