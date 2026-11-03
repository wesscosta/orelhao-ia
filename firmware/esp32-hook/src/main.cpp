#include <Arduino.h>

#ifndef ORELHAO_LCD_ENABLED
#define ORELHAO_LCD_ENABLED 0
#endif

#if ORELHAO_LCD_ENABLED
#include "lcd_panel.h"
#endif

// GPIO27 <-> contato seco do gancho <-> GND.
// Nunca conectar tensao externa/linha telefonica ao GPIO.
namespace {
constexpr uint8_t kHookPin = 27;
constexpr uint32_t kDebounceMs = 70;
constexpr uint32_t kReportEveryMs = 5000;
constexpr uint32_t kLoopDelayMs = 10;
bool lastRawClosed = false;
bool stableClosed = false;
uint32_t lastRawChange = 0;
uint32_t lastReport = 0;
uint32_t sequence = 0;

void publish(const char* kind) {
  const uint32_t now = millis();
  Serial.printf(
      "{\"protocol\":\"orelhao.hook.v1\",\"kind\":\"%s\",\"gpio\":%u,"
      "\"contact\":\"%s\",\"seq\":%lu,\"uptime_ms\":%lu}\n",
      kind, static_cast<unsigned int>(kHookPin),
      stableClosed ? "closed" : "open",
      static_cast<unsigned long>(++sequence),
      static_cast<unsigned long>(now));
  lastReport = now;
}
}

void setup() {
  // INPUT_PULLUP: circuito fechado = LOW, aberto = HIGH.
  pinMode(kHookPin, INPUT_PULLUP);
  Serial.begin(115200);
  delay(250);
#if ORELHAO_LCD_ENABLED
  lcd_panel::begin();
#endif
  stableClosed = (digitalRead(kHookPin) == LOW);
  lastRawClosed = stableClosed;
  lastRawChange = millis();
  publish("state");
}

void loop() {
  const uint32_t now = millis();
  const bool rawClosed = (digitalRead(kHookPin) == LOW);
  if (rawClosed != lastRawClosed) {
    lastRawClosed = rawClosed;
    lastRawChange = now;
  }
  if (rawClosed != stableClosed && now - lastRawChange >= kDebounceMs) {
    stableClosed = rawClosed;
    publish("change");
  }
  if (now - lastReport >= kReportEveryMs) {
    publish("state");  // Recupera estado caso host abra porta depois do boot.
  }
#if ORELHAO_LCD_ENABLED
  lcd_panel::poll();
#endif
  delay(kLoopDelayMs);
}
